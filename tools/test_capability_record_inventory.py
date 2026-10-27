import unittest
from unittest.mock import patch
from capability_record_inventory import compare_file_inventory


class Inventories(unittest.TestCase):
    def test_required_manifest_overlap_and_no_execution(self):
        files = {'started.json': b'{}', 'logs/stdout.log': b'not executed'}
        with patch('builtins.open', side_effect=AssertionError('no IO')):
            result = compare_file_inventory(files, ['started.json'], ['started.json', 'logs/stdout.log'])
        self.assertTrue(result.file_set_matches)
        self.assertFalse(result.blocked)
        self.assertEqual(files['logs/stdout.log'], b'not executed')

    def test_missing_and_extra_preserved(self):
        result = compare_file_inventory({'extra': b''}, ['required'], ['log'])
        self.assertEqual(result.missing, ('log', 'required'))
        self.assertEqual(result.extra, ('extra',))
        self.assertTrue(result.blocked)

    def test_native_present_bytes_not_child_verification(self):
        result = compare_file_inventory({'native/x/result.json': b'{}'}, [],
            ['native/x/result.json'], unresolved_native=['native/x/result.json'])
        self.assertTrue(result.file_set_matches)
        self.assertTrue(result.blocked)
        self.assertEqual(result.unresolved_native, ('native/x/result.json',))

    def test_duplicate_names_rejected(self):
        for args in [(['a', 'a'], [], ()), ([], ['a', 'a'], ()), ([], [], ('a', 'a'))]:
            with self.assertRaises(ValueError):
                compare_file_inventory({}, args[0], args[1], unresolved_native=args[2])

    def test_unsafe_and_file_directory_collisions(self):
        for required in (['../outside'], ['/outside'], ['a', 'a/b']):
            with self.assertRaises(ValueError):
                compare_file_inventory({}, required, [])
        with self.assertRaises(ValueError):
            compare_file_inventory({'a': b''}, [], ['a/b'])

    def test_empty_does_not_invent_manifest(self):
        result = compare_file_inventory({}, [], [])
        self.assertEqual(result.missing, ())
        self.assertFalse(hasattr(result, 'integrity'))
        self.assertFalse(hasattr(result, 'execution_verified'))


if __name__ == '__main__':
    unittest.main()
