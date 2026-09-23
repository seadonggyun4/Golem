import unittest
from verify_runtime_legacy import schema_rejection


class LegacyRejection(unittest.TestCase):
    def test_only_explicit_schema_errors_qualify(self):
        for text in (b"golem: corrupt journal\n", b"golem: unsupported version\n"):
            self.assertTrue(schema_rejection(1, text))
            for status in (0, -11, -9, 2, 127):
                self.assertFalse(schema_rejection(status, text))
        for text in (b"", b"golem: I/O error", b"unrecognized command"):
            self.assertFalse(schema_rejection(1, text))


if __name__ == "__main__":
    unittest.main()
