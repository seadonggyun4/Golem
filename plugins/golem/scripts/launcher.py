"""POSIX owner-local adapter for an explicitly reviewed Golem launcher."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

LIMIT = 256 * 1024
SCHEMA = 'golem.codex-launcher.v1'


class SetupError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise SetupError(code)


def pairs(items):
    value = {}
    for key, item in items:
        require(key not in value, 'DUPLICATE_FIELD')
        value[key] = item
    return value


def canonical(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'ABSOLUTE_PATH_REQUIRED')
    require(all(not p.is_symlink() for p in (path, *path.parents)), 'SYMLINK')
    return path


def read_private(path):
    path = canonical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_uid == os.getuid() and before.st_mode & 0o077 == 0
                and before.st_size <= LIMIT, 'UNSAFE_PRIVATE_FILE')
        data = os.read(fd, LIMIT + 1)
        after = os.fstat(fd)
        require(len(data) == before.st_size and len(data) <= LIMIT
                and (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'FILE_CHANGED')
        return data
    finally:
        os.close(fd)


def decode(data):
    return json.loads(data.decode('utf-8'), object_pairs_hook=pairs)


def validate_launcher(value):
    require(isinstance(value, dict) and set(value) == {'command', 'args'}, 'LAUNCHER_FIELDS')
    require(isinstance(value['command'], str) and Path(value['command']).is_absolute()
            and isinstance(value['args'], list)
            and all(isinstance(v, str) for v in value['args']), 'LAUNCHER_VALUES')
    require(all('\x00' not in v and '${' not in v
                for v in [value['command'], *value['args']]), 'LAUNCHER_EXPANSION')
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def directory(path, create=False, private=False):
    path = canonical(path)
    if create:
        try:
            path.mkdir(mode=0o700)
        except FileExistsError:
            pass
    info = path.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and info.st_mode & (0o077 if private else 0o022) == 0, 'UNSAFE_DIRECTORY')
    return path


@contextmanager
def locked(state, write=False):
    state = directory(state, create=write)
    private = directory(state / 'golem-launcher', create=write, private=True)
    flags = (os.O_RDWR if write else os.O_RDONLY) | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    fd = os.open(private / 'owner.lock', flags | (os.O_CREAT if write else 0), 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and info.st_uid == os.getuid() and info.st_mode & 0o077 == 0, 'UNSAFE_LOCK')
        fcntl.flock(fd, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        pending = private / 'approval.pending'
        require(not pending.exists() and not pending.is_symlink(), 'PARTIAL_PUBLICATION')
        yield private
    finally:
        os.close(fd)


def load(private):
    value = decode(read_private(private / 'approval.json'))
    require(isinstance(value, dict) and set(value) == {'schema', 'launcher', 'launcher_sha256'}
            and value['schema'] == SCHEMA, 'APPROVAL_FIELDS')
    raw = value['launcher']
    require(isinstance(raw, str) and digest(raw.encode()) == value['launcher_sha256'], 'APPROVAL_DIGEST')
    return validate_launcher(decode(raw.encode())), value['launcher_sha256']


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def configure(state, source, reviewed, approved):
    require(approved, 'OWNER_LAUNCHER_APPROVAL_REQUIRED')
    raw = read_private(source)
    require(digest(raw) == reviewed, 'REVIEWED_LAUNCHER_CHANGED')
    launcher = validate_launcher(decode(raw))
    value = {'schema': SCHEMA, 'launcher': raw.decode(), 'launcher_sha256': reviewed}
    data = (json.dumps(value, separators=(',', ':')) + '\n').encode()
    require(len(data) <= LIMIT, 'APPROVAL_TOO_LARGE')
    with locked(state, write=True) as private:
        if (private / 'approval.json').exists():
            require(load(private) == (launcher, reviewed), 'EXISTING_APPROVAL_DIFFERS')
            return {'state': 'CONFIGURED', 'changed': False, 'launcher_sha256': reviewed}
        fd = os.open(private / 'approval.pending', os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(private / 'approval.pending', private / 'approval.json', follow_symlinks=False)
        sync_directory(private)
        (private / 'approval.pending').unlink()
        sync_directory(private)
    return {'state': 'CONFIGURED', 'changed': True, 'launcher_sha256': reviewed}


def status(state):
    with locked(state) as private:
        _, pin = load(private)
    return {'state': 'CONFIGURED', 'launcher_sha256': pin, 'project_access_verified': False}


def serve(state):
    with locked(state) as private:
        launcher, _ = load(private)
    os.execv(launcher['command'], [launcher['command'], *launcher['args']])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('configure', 'status', 'serve'))
    parser.add_argument('--state', type=Path)
    parser.add_argument('--launcher', type=Path)
    parser.add_argument('--reviewed-launcher-sha256')
    parser.add_argument('--approve-launcher', action='store_true')
    args = parser.parse_args()
    try:
        state = args.state or Path.home() / '.local/share/golem/codex-plugin'
        require(state.is_absolute(), 'STATE_PATH_REQUIRED')
        if args.operation == 'configure':
            require(args.launcher is not None and args.reviewed_launcher_sha256 is not None,
                    'REVIEWED_LAUNCHER_REQUIRED')
            result = configure(state, args.launcher, args.reviewed_launcher_sha256, args.approve_launcher)
        elif args.operation == 'status':
            result = status(state)
        else:
            serve(state)
            return
        print(json.dumps(result, separators=(',', ':')))
    except (OSError, ValueError, TypeError, RecursionError) as error:
        code = str(error) if isinstance(error, SetupError) else 'SETUP_VALIDATION_FAILED'
        print(json.dumps({'state': 'SETUP_REQUIRED', 'code': code,
              'next_action': 'RUN_GOLEM_SETUP', 'execution_authorized': False}), file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
