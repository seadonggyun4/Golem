import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import capability_files as source


@unittest.skipUnless(os.name == 'posix' and os.path.isfile(source.GIT), 'POSIX and trusted /usr/bin/git required')
class SelectedSources(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='golem-m0-source-')
        self.addCleanup(self.temporary.cleanup)
        self.root = (Path(self.temporary.name).resolve() / 'repo')
        self.root.mkdir()
        self.git('init', '--quiet')
        self.write('a.c', b'A')
        self.write('nested/b.py', b'B\n')
        self.git('add', '--', 'a.c', 'nested/b.py')

    def git(self, *args):
        return subprocess.run([source.GIT, '--no-pager', '--literal-pathspecs', '-C', str(self.root),
            *args], env=dict(source.GIT_ENVIRONMENT), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    def write(self, path, data):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    def read(self, paths, **kwargs):
        return source.read_sources(str(self.root), paths, **kwargs)

    def test_selected_order_bytes_hashes_modes_and_index_preserved(self):
        paths = ['nested/b.py', 'a.c']
        before = {name: ((self.root / name).read_bytes(), (self.root / name).stat().st_mode) for name in paths}
        index = (self.root / '.git/index').read_bytes()
        result = self.read(paths)
        self.assertEqual([row.path for row in result], paths)
        for row in result:
            self.assertEqual(row.data, before[row.path][0])
            self.assertEqual(row.sha256, hashlib.sha256(row.data).hexdigest())
            self.assertEqual((self.root / row.path).stat().st_mode, before[row.path][1])
        self.assertEqual((self.root / '.git/index').read_bytes(), index)

    def test_untracked_or_ignored_require_explicit_reviewed_selection(self):
        self.write('.gitignore', b'new.py\n')
        self.write('new.py', b'never execute this')
        with self.assertRaises(source.SourceReadError):
            self.read(['new.py'])
        result = self.read(['new.py'], reviewed_new=['new.py'])
        self.assertEqual(result[0].data, b'never execute this')
        with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_NEW_SELECTION$'):
            self.read(['a.c'], reviewed_new=['new.py'])

    def test_no_glob_expansion_or_option_injection(self):
        paths = [':(glob)*', '-source.py']
        for name in paths:
            self.write(name, b'literal name')
        self.git('add', '--', *paths)
        self.assertEqual([row.path for row in self.read(paths)], paths)

    def test_private_and_generated_paths_rejected_before_git(self):
        for name in ('.git/config', '.golem/work/state.json', '.codex/config.toml',
                     '.env', '.env.local', 'build/x.c', 'dist/x.py', 'node_modules/x',
                     'registry/active.json', 'tools/policy.json', 'tools/claude-policy.json'):
            with self.subTest(path=name), patch.object(source, '_git_query', side_effect=AssertionError('must not query')):
                with self.assertRaises(source.SourceReadError):
                    self.read([name], reviewed_new=[name])

    def test_tracked_public_fixture_is_not_active_approval(self):
        self.write('tests/fixtures/policy.json', b'{"synthetic":true}')
        self.git('add', '--', 'tests/fixtures/policy.json')
        with self.assertRaises(source.SourceReadError):
            self.read(['tests/fixtures/policy.json'])
        self.assertEqual(self.read(['tests/fixtures/policy.json'],
            reviewed_fixtures=['tests/fixtures/policy.json'])[0].data, b'{"synthetic":true}')
        with self.assertRaises(source.SourceReadError):
            self.read(['tests/fixtures/policy.json'], reviewed_fixtures=['tests/fixtures/policy.json'],
                      protected_paths=['tests/fixtures/policy.json'])
        self.write('tests/new-policy.json', b'not a tracked fixture')
        with self.assertRaises(source.SourceReadError):
            self.read(['tests/new-policy.json'], reviewed_new=['tests/new-policy.json'])
        with self.assertRaises(source.SourceReadError):
            self.read(['tests/new-policy.json'], reviewed_new=['tests/new-policy.json'],
                      reviewed_fixtures=['tests/new-policy.json'])

    def test_unsafe_relative_paths_duplicates_and_wrong_types_rejected(self):
        for paths in (['../outside'], ['/etc/passwd'], ['a.c', 'a.c'], ['nested//b.py'],
                      ['nested/./b.py'], ['C:/outside'], ['a\0.c'], ['a\\b'], [None], 'a.c'):
            with self.subTest(paths=paths), self.assertRaises(source.SourceReadError):
                self.read(paths)

    def test_root_and_intermediate_and_file_symlinks_are_rejected(self):
        alias = self.root.parent / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(source.SourceReadError):
            source.read_sources(str(alias), ['a.c'])
        (self.root / 'alias-dir').symlink_to(self.root / 'nested', target_is_directory=True)
        (self.root / 'alias-file').symlink_to(self.root / 'a.c')
        for name in ('alias-dir/b.py', 'alias-file'):
            with self.subTest(name=name), self.assertRaises(source.SourceReadError):
                self.read([name], reviewed_new=[name])

    def test_hardlinks_directory_and_fifo_rejected_without_blocking(self):
        os.link(self.root / 'a.c', self.root / 'second-name')
        with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_HARDLINK$'):
            self.read(['a.c'])
        os.mkfifo(self.root / 'pipe')
        for name in ('nested', 'pipe'):
            with self.subTest(name=name), self.assertRaisesRegex(source.SourceReadError, '^SOURCE_NOT_REGULAR$'):
                self.read([name], reviewed_new=[name])

    def test_single_file_exact_and_over_limit(self):
        self.write('large.c', b'x' * source.FILE_BYTES_MAX)
        self.assertEqual(len(self.read(['large.c'], reviewed_new=['large.c'])[0].data), source.FILE_BYTES_MAX)
        with (self.root / 'large.c').open('ab') as stream:
            stream.write(b'x')
        with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_FILE_BYTES_LIMIT$'):
            self.read(['large.c'], reviewed_new=['large.c'])

    def test_total_bytes_exact_and_over_limit(self):
        names = [f'large-{i}.c' for i in range(64)]
        block = b'x' * source.FILE_BYTES_MAX
        for name in names:
            self.write(name, block)
        rows = self.read(names, reviewed_new=names)
        self.assertEqual(sum(len(row.data) for row in rows), source.TOTAL_BYTES_MAX)
        del rows
        self.write('extra.c', b'x')
        with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_TOTAL_BYTES_LIMIT$'):
            self.read([*names, 'extra.c'], reviewed_new=[*names, 'extra.c'])

    def test_file_count_exact_and_over_limit(self):
        names = [f'empty-{i}.c' for i in range(4096)]
        for name in names:
            self.write(name, b'')
        self.assertEqual(len(self.read(names, reviewed_new=names)), 4096)
        with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_FILE_COUNT_LIMIT$'):
            self.read([*names, 'one-extra.c'])

    def test_modification_during_read_never_returns_partial_result(self):
        real_read = source._read_bytes
        def changed(descriptor, path):
            data = real_read(descriptor, path)
            self.write(path, b'changed length')
            return data
        with patch.object(source, '_read_bytes', side_effect=changed):
            with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_CHANGED$'):
                self.read(['a.c'])

    def test_change_to_earlier_file_is_rechecked_after_later_read(self):
        real_read = source._read_bytes
        def changed(descriptor, path):
            data = real_read(descriptor, path)
            if path == 'nested/b.py':
                self.write('a.c', b'changed after first read')
            return data
        with patch.object(source, '_read_bytes', side_effect=changed):
            with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_CHANGED$'):
                self.read(['a.c', 'nested/b.py'])

    def test_same_bytes_path_replacement_is_not_adopted(self):
        real_read = source._read_bytes
        def replaced(descriptor, path):
            data = real_read(descriptor, path)
            (self.root / path).unlink()
            self.write(path, data)
            return data
        with patch.object(source, '_read_bytes', side_effect=replaced):
            with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_CHANGED$'):
                self.read(['a.c'])

    def test_inherited_git_variables_are_not_forwarded(self):
        actual_popen = source.subprocess.Popen
        calls = []
        def observed(argv, **kwargs):
            calls.append((argv, kwargs['env']))
            self.assertEqual(argv[0], '/usr/bin/git')
            self.assertIn('--no-pager', argv)
            self.assertIn('--literal-pathspecs', argv)
            self.assertIn('core.fsmonitor=false', argv)
            self.assertEqual(kwargs['env'], source.GIT_ENVIRONMENT)
            return actual_popen(argv, **kwargs)
        poison = {'GIT_DIR': '/not-the-repo', 'GIT_WORK_TREE': '/not-the-repo',
                  'GIT_PAGER': 'must-not-run', 'GIT_CONFIG_COUNT': '99'}
        with patch.dict(os.environ, poison), patch.object(source.subprocess, 'Popen', side_effect=observed):
            self.assertEqual(self.read(['a.c'])[0].data, b'A')
        self.assertEqual(len(calls), 4)

    def test_git_output_limit_timeout_and_redacted_failures(self):
        with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_GIT_OUTPUT_LIMIT$'):
            source._git_query(str(self.root), ['rev-parse', '--show-toplevel'], 0)
        with patch.object(source.time, 'monotonic', side_effect=[0, 11]):
            with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_GIT_TIMEOUT$'):
                source._git_query(str(self.root), ['rev-parse', '--show-toplevel'], 4096)
        with self.assertRaises(source.SourceReadError) as caught:
            self.read(['not-tracked-secret-file'])
        self.assertNotIn('not-tracked-secret-file', str(caught.exception))

    def test_subdirectory_root_and_missing_files_and_empty_selection(self):
        with self.assertRaises(source.SourceReadError):
            source.read_sources(str(self.root / 'nested'), ['b.py'], reviewed_new=['b.py'])
        with self.assertRaises(source.SourceReadError):
            self.read(['absent.c'], reviewed_new=['absent.c'])
        self.assertEqual(self.read([]), ())  # Empty selection is not coverage completion.

    def test_binary_bytes_are_not_implicitly_decoded_or_executed(self):
        raw = b'\x00\xff\xfe'
        self.write('selected.bin', raw)
        self.assertEqual(self.read(['selected.bin'], reviewed_new=['selected.bin'])[0].data, raw)

    def test_nested_git_repository_is_not_another_source_scope(self):
        nested = self.root / 'nested-repo'
        nested.mkdir()
        self.git('init', '--quiet', str(nested))
        self.write('nested-repo/other.py', b'other project')
        with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_NESTED_REPOSITORY$'):
            self.read(['nested-repo/other.py'], reviewed_new=['nested-repo/other.py'])

    def test_directory_rename_and_replacement_is_rechecked(self):
        actual_read = source._read_bytes
        def replaced(descriptor, path):
            data = actual_read(descriptor, path)
            if path == 'nested/b.py':
                (self.root / 'nested').rename(self.root / 'retained-old-directory')
                self.write('nested/b.py', data)
            return data
        with patch.object(source, '_read_bytes', side_effect=replaced):
            with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_CHANGED$'):
                self.read(['nested/b.py'])

    def test_metadata_git_exception_cannot_dispatch_other_commands(self):
        rejected = (['status'], ['commit', '-m', 'forbidden'], ['reset', '--hard'],
                    ['config', '--global', 'x', 'y'], ['rev-parse', '--git-dir'],
                    ['ls-files', '--stage'], ['ls-files', '--cached', '--error-unmatch', '--full-name', '-z', '--'],
                    ['ls-files', '--cached', '--error-unmatch', '--full-name', '-z', '--', *(['a.c'] * 17)],
                    ['ls-files', '--cached', '--error-unmatch', '--full-name', '-z', '--', '../outside'],
                    'rev-parse', ['rev-parse', None])
        for arguments in rejected:
            with self.subTest(arguments=arguments), patch.object(source.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
                with self.assertRaises(source.SourceReadError):
                    source._git_query(str(self.root), arguments, 4096)
        for bound in (-1, 4096 * 4097 + 1, True, None):
            with self.subTest(bound=bound), patch.object(source.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
                with self.assertRaises(source.SourceReadError):
                    source._git_query(str(self.root), ['rev-parse', '--show-toplevel'], bound)

    def test_git_warning_is_not_silently_accepted(self):
        class Child:
            returncode = 0
            def __init__(self, *args, **kwargs):
                self.stdout = self.pipe(b'expected\n')
                self.stderr = self.pipe(b'warning: unsupported environment\n')
            @staticmethod
            def pipe(data):
                read_fd, write_fd = os.pipe()
                os.write(write_fd, data)
                os.close(write_fd)
                return os.fdopen(read_fd, 'rb', buffering=0)
            def wait(self, **kwargs):
                return 0
            def poll(self):
                return 0
        with patch.object(source.subprocess, 'Popen', Child):
            with self.assertRaisesRegex(source.SourceReadError, '^SOURCE_GIT_REFUSED$'):
                source._git_query(str(self.root), ['rev-parse', '--show-toplevel'], 4096)


if __name__ == '__main__':
    unittest.main()

class InventoryDomain(unittest.TestCase):
    setUp=SelectedSources.setUp
    git=SelectedSources.git
    write=SelectedSources.write
    read=SelectedSources.read
    """The adopted JSON domain cannot widen generic source-file reads."""
    def test_fixed_inventory_uses_decoder_domain_only(self):
        raw=b' '*(source.FILE_BYTES_MAX+1)
        self.write(source.INVENTORY_PATH,raw)
        observed=source.read_inventory(str(self.root))
        self.assertEqual(observed.data,raw)
        with self.assertRaises(source.SourceReadError) as failure:
            self.read([source.INVENTORY_PATH],reviewed_new=[source.INVENTORY_PATH])
        self.assertEqual(failure.exception.code,'SOURCE_FILE_BYTES_LIMIT')
    def test_inventory_reuses_no_follow_and_large_file_rejection(self):
        path=self.write(source.INVENTORY_PATH,b'{}');path.unlink();path.symlink_to(self.root/'a.c')
        with self.assertRaises(source.SourceReadError):source.read_inventory(str(self.root))
        path.unlink()
        with path.open('wb') as stream:stream.truncate(16*1024*1024+1)
        with self.assertRaises(source.SourceReadError) as failure:source.read_inventory(str(self.root))
        self.assertEqual(failure.exception.code,'SOURCE_FILE_BYTES_LIMIT')
