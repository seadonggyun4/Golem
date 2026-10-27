import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from capability_scope import compare_scope, tracked_scope,untracked_scope
from capability_scope_registry import TRACKED_PATHS


class Scope(unittest.TestCase):
    def test_entire_index_baseline_and_new_code(self):
        self.assertTrue(compare_scope(TRACKED_PATHS, TRACKED_PATHS).matches)
        diff=compare_scope(TRACKED_PATHS, (*TRACKED_PATHS, 'src/new_dispatch.c'))
        self.assertEqual(diff.added, ('src/new_dispatch.c',))

    def test_build_and_docs_changes_also_require_review(self):
        for path in ('CMakeLists.txt','README.md'):
            diff=compare_scope(TRACKED_PATHS, tuple(p for p in TRACKED_PATHS if p != path))
            self.assertEqual(diff.removed, (path,))

    def test_invalid_duplicate(self):
        for names in (['x','x'], ['../secret'], ['a']*4097):
            with self.assertRaises(ValueError): compare_scope([],names)

    def test_fixed_query_no_source_reads(self):
        with tempfile.TemporaryDirectory() as directory, patch('capability_scope._repository'), patch('capability_scope._git_query',return_value=b'src/a.c\0') as git:
            self.assertEqual(tracked_scope(str(Path(directory).resolve())), ('src/a.c',))
        self.assertEqual(git.call_args.args[1], ['ls-files','--cached','--full-name','-z'])

    def test_untracked_query_is_fixed_metadata_only(self):
        with tempfile.TemporaryDirectory() as directory,patch('capability_scope._repository'),patch('capability_scope._git_query',return_value=b'tools/new.py\0') as git:
            self.assertEqual(untracked_scope(str(Path(directory).resolve())),('tools/new.py',))
        self.assertEqual(git.call_args.args[1],['ls-files','--others','--exclude-standard','--full-name','-z'])


if __name__=='__main__': unittest.main()
