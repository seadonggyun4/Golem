"""Opt-in M0 reads of explicitly selected repository source files, POSIX only.

Not an authority registry, source extractor, secret detector or atomic snapshot.
No default root, recursive discovery, file writes, cleanup, retries or MCP hook.
Caller-supplied reviewed_new is a trusted review selection, not model consent.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import hashlib
import os
from pathlib import Path
import selectors
import stat
import subprocess
import time

from capability_ledger import BaseFieldError, validate_relative_path

FILE_COUNT_MAX = 4096
FILE_BYTES_MAX = 1024 * 1024
TOTAL_BYTES_MAX = 64 * 1024 * 1024
GIT = '/usr/bin/git'  # Trusted installed host dependency, never model/PATH selected.
GIT_ENVIRONMENT = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
    'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
    'GIT_TERMINAL_PROMPT': '0', 'GIT_OPTIONAL_LOCKS': '0'}
EXCLUDED_COMPONENTS = frozenset(('.git', '.golem', '.codex', '.cache', '__pycache__',
    '.pytest_cache', '.mypy_cache', '.ruff_cache', '.venv', 'venv', 'node_modules',
    'build', 'dist', '_build', '.tox', '.nox'))
STATE_ROOTS = frozenset(('approvals', 'registry', 'works', 'receipts', 'cas', 'journal'))


class SourceReadError(ValueError):
    def __init__(self, code, path=None):
        super().__init__(code)  # No source bytes or arbitrary child stderr in message.
        self.code, self.path = code, path


@dataclass(frozen=True)
class SourceFile:
    path: str
    sha256: str
    data: bytes


def _require(condition, code, path=None):
    if not condition:
        raise SourceReadError(code, path)


def _names(value):
    _require(type(value) in (tuple, list), 'SOURCE_PATH_LIST')
    _require(len(value) <= FILE_COUNT_MAX, 'SOURCE_FILE_COUNT_LIMIT')
    seen = set()
    for path in value:
        try:
            validate_relative_path(path)
        except BaseFieldError:
            raise SourceReadError('SOURCE_PATH', path) from None
        _require(path not in seen, 'SOURCE_DUPLICATE_PATH', path)
        seen.add(path)
    return tuple(value)


def _excluded(path, *, tracked_fixture):
    parts = path.split('/')
    _require(not any(p.casefold() in EXCLUDED_COMPONENTS or p.casefold().startswith('.env')
                     for p in parts), 'SOURCE_SCOPE_EXCLUDED', path)
    _require(parts[0].casefold() not in STATE_ROOTS, 'SOURCE_SCOPE_EXCLUDED', path)
    name = parts[-1].casefold()
    private_metadata = (name in ('policy.json', 'approval.json', 'registry.json', 'receipt.json') or
                        name.endswith(('-policy.json', '-approval.json')) or
                        name.startswith('golem-intent-authority.'))
    _require(not private_metadata or tracked_fixture, 'SOURCE_STATE_METADATA_EXCLUDED', path)


def _git_query(root, arguments, stdout_max):
    """Fixed, noninteractive queries; bound both pipes while reading, then reap."""
    # Metadata reads are deliberately not execution observations. Admit only
    # these fixed commands before Popen; never a caller-supplied Git operation.
    _require(type(arguments) is list and all(type(v) is str for v in arguments), 'SOURCE_GIT_QUERY')
    fixed = (['rev-parse', '--show-toplevel'], ['ls-files', '--cached', '--full-name', '-z'],
             ['ls-files', '--others', '--exclude-standard', '--full-name', '-z'])
    if arguments not in fixed:
        _require(arguments[:6] == ['ls-files', '--cached', '--error-unmatch', '--full-name', '-z', '--']
                 and 1 <= len(arguments[6:]) <= 16, 'SOURCE_GIT_QUERY')
        _names(arguments[6:])
    _require(type(stdout_max) is int and 0 <= stdout_max <= 4096 * 4097, 'SOURCE_GIT_QUERY')
    argv = [GIT, '--no-pager', '--literal-pathspecs', '-c', 'core.fsmonitor=false',
        '-c', 'core.untrackedCache=false', '-c', 'core.hooksPath=' + os.devnull,
        '-C', root, *arguments]
    process = None
    buffers = {'out': bytearray(), 'err': bytearray()}
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=dict(GIT_ENVIRONMENT), close_fds=True)
        deadline = time.monotonic() + 10  # Execution guard, not a data/quota policy.
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ, 'out')
            ready.register(process.stderr, selectors.EVENT_READ, 'err')
            while ready.get_map():
                remaining = deadline - time.monotonic()
                _require(remaining > 0, 'SOURCE_GIT_TIMEOUT')
                for key, _ in ready.select(remaining):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        ready.unregister(key.fileobj)
                        continue
                    target = buffers[key.data]
                    _require(len(target) + len(data) <= (stdout_max if key.data == 'out' else 4096),
                             'SOURCE_GIT_OUTPUT_LIMIT')
                    target.extend(data)
        process.wait(timeout=max(0.001, deadline - time.monotonic()))
        _require(process.returncode == 0 and not buffers['err'], 'SOURCE_GIT_REFUSED')
        return bytes(buffers['out'])
    except (OSError, subprocess.TimeoutExpired):
        raise SourceReadError('SOURCE_GIT_IO') from None
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()  # Only the child created by this query, never unrelated processes.
            process.wait()
            process.stdout.close()
            process.stderr.close()


def _repository(root):
    raw = _git_query(root, ['rev-parse', '--show-toplevel'], len(root.encode('utf-8')) + 1)
    _require(raw == root.encode('utf-8') + b'\n', 'SOURCE_REPOSITORY_ROOT')


def _tracked(root, paths):
    # Literal, bounded batches avoid arbitrary pathspecs and platform ARG_MAX.
    for start in range(0, len(paths), 16):
        batch = paths[start:start + 16]
        bound = 4 * sum(len(p.encode('utf-8')) + 1 for p in batch)
        raw = _git_query(root, ['ls-files', '--cached', '--error-unmatch', '--full-name', '-z', '--', *batch], bound)
        try:
            actual = raw.decode('utf-8', errors='strict').split('\0')
        except UnicodeDecodeError:
            raise SourceReadError('SOURCE_GIT_PATH_ENCODING') from None
        _require(actual[-1:] == [''], 'SOURCE_GIT_INDEX_FORMAT')
        actual = actual[:-1]
        _require(len(actual) == len(set(actual)) and set(actual) == set(batch), 'SOURCE_GIT_INDEX_BINDING')


def _directory_flags():
    _require(os.name == 'posix' and hasattr(os, 'O_NOFOLLOW') and hasattr(os, 'O_DIRECTORY'),
             'SOURCE_POSIX_REQUIRED')
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _open_root(root):
    _require(type(root) is str and root.startswith('/') and not root.startswith('//') and
             os.path.normpath(root) == root, 'SOURCE_ABSOLUTE_ROOT')
    _require(not any(p.casefold() in EXCLUDED_COMPONENTS for p in root.split('/')), 'SOURCE_ROOT_EXCLUDED')
    descriptor = os.open('/', _directory_flags())
    try:
        for part in Path(root).parts[1:]:
            child = os.open(part, _directory_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


@contextmanager
def _open_file(root_fd, path):
    directory, descriptor = os.dup(root_fd), None
    try:
        parts = path.split('/')
        for part in parts[:-1]:
            child = os.open(part, _directory_flags(), dir_fd=directory)
            os.close(directory)
            directory = child
            try:
                os.stat('.git', dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise SourceReadError('SOURCE_NESTED_REPOSITORY', path)
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        yield descriptor
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def _stamp(descriptor, path, limit=FILE_BYTES_MAX):
    value = os.fstat(descriptor)
    _require(stat.S_ISREG(value.st_mode), 'SOURCE_NOT_REGULAR', path)
    _require(value.st_nlink >= 1, 'SOURCE_CHANGED', path)
    _require(value.st_nlink == 1, 'SOURCE_HARDLINK', path)
    _require(value.st_size <= limit, 'SOURCE_FILE_BYTES_LIMIT', path)
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns,
            value.st_mode, value.st_uid, value.st_gid)


def _read_bytes(descriptor, path, limit=FILE_BYTES_MAX):
    chunks, size = [], 0
    while True:
        chunk = os.read(descriptor, min(65536, limit + 1 - size))
        if not chunk:
            return b''.join(chunks)
        size += len(chunk)
        _require(size <= limit, 'SOURCE_FILE_BYTES_LIMIT', path)
        chunks.append(chunk)


def _read_sources(root, paths, *, reviewed_new=(), reviewed_fixtures=(), protected_paths=(), inventory=False):
    """Return all selected bytes/hashes in input order or raise, never partial success.

    No default discovery of untracked/ignored files or traversal into nested Git
    repositories/submodules. Unknown source formats are
    raw bytes, not claimed parsed operations. Exclusions are explicit errors;
    caller must retain them as incomplete scope, never quietly skip and PASS.
    Reviewed new files/fixtures are trusted caller selections, not native grants.
    Merely living under tests/ does not classify private metadata as a fixture.
    Known protected paths always win; this is not automatic secret discovery.
    """
    selected, new = _names(paths), _names(reviewed_new)
    _require(set(new) <= set(selected), 'SOURCE_NEW_SELECTION')
    new = set(new)
    fixtures, protected = set(_names(reviewed_fixtures)), set(_names(protected_paths))
    _require(fixtures <= set(selected) - new and all(p.startswith('tests/') for p in fixtures),
             'SOURCE_FIXTURE_SELECTION')
    tracked = tuple(path for path in selected if path not in new)
    for path in selected:
        _require(path not in protected, 'SOURCE_SCOPE_EXCLUDED', path)
        _excluded(path, tracked_fixture=path in fixtures)
    root_fd = None
    current = None
    try:
        root_fd = _open_root(root)
        root_stat = os.fstat(root_fd)
        _repository(root)
        _tracked(root, tracked)
        results, stamps, total = [], {}, 0
        for current in selected:
            with _open_file(root_fd, current) as descriptor:
                limit = 16 * 1024 * 1024 if inventory and current == INVENTORY_PATH else FILE_BYTES_MAX
                before = _stamp(descriptor, current, limit)
                _require(total + before[2] <= TOTAL_BYTES_MAX, 'SOURCE_TOTAL_BYTES_LIMIT', current)
                data = _read_bytes(descriptor, current) if limit == FILE_BYTES_MAX else _read_bytes(descriptor, current, limit)
                after = _stamp(descriptor, current, limit)
                _require(before == after and len(data) == after[2], 'SOURCE_CHANGED', current)
                total += len(data)
                _require(total <= TOTAL_BYTES_MAX, 'SOURCE_TOTAL_BYTES_LIMIT', current)
                stamps[current] = after
                results.append(SourceFile(current, hashlib.sha256(data).hexdigest(), data))
        # A file read early may have changed while later files were being read.
        _tracked(root, tracked)
        _repository(root)
        for current in selected:
            with _open_file(root_fd, current) as descriptor:
                _require(_stamp(descriptor, current, 16 * 1024 * 1024 if inventory and current == INVENTORY_PATH else FILE_BYTES_MAX) == stamps[current], 'SOURCE_CHANGED', current)
        current = None
        final_fd = _open_root(root)
        try:
            final_stat = os.fstat(final_fd)
            _require((root_stat.st_dev, root_stat.st_ino) == (final_stat.st_dev, final_stat.st_ino),
                     'SOURCE_ROOT_CHANGED')
        finally:
            os.close(final_fd)
        return tuple(results)
    except OSError as error:
        code = 'SOURCE_UNSAFE_PATH' if error.errno in (errno.ELOOP, errno.ENOTDIR) else 'SOURCE_IO'
        raise SourceReadError(code, current) from None
    finally:
        if root_fd is not None:
            os.close(root_fd)


INVENTORY_PATH = 'docs/mcp-m0-observations.json'

def read_sources(root, paths, *, reviewed_new=(), reviewed_fixtures=(), protected_paths=()):
    return _read_sources(root,paths,reviewed_new=reviewed_new,reviewed_fixtures=reviewed_fixtures,protected_paths=protected_paths)

def read_inventory(root):
    """Read only the fixed M0 JSON using its adopted 16 MiB decoder domain.

    Reuses all source path/no-follow/change/Git checks. Source files retain the
    separate 1 MiB bound. This does not follow any names inside the inventory.
    """
    return _read_sources(root,[INVENTORY_PATH],reviewed_new=[INVENTORY_PATH],inventory=True)[0]
