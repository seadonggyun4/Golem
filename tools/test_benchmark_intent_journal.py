import tempfile
import unittest
from pathlib import Path

from benchmark_intent_journal import measure, payload, publish, replay


class JournalExperimentTests(unittest.TestCase):
    def test_exact_payload_sizes(self):
        for size in (1024, 16384, 262144):
            self.assertEqual(len(payload(65536, size)), size)

    def test_round_trip_and_accounting(self):
        with tempfile.TemporaryDirectory() as root:
            result = measure(root, 4, 1024, False, 2)
            self.assertEqual(result["files"], 8)
            self.assertEqual(result["logical_bytes"], 4 * (1024 + 80))
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_reject_truncated_frame(self):
        with tempfile.TemporaryDirectory() as root:
            publish(Path(root) / "00000001.evt", b"short", False)
            with self.assertRaisesRegex(ValueError, "frame shape"):
                replay(Path(root), 1)

    def test_publication_never_overwrites(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "record"
            publish(path, b"first", False)
            with self.assertRaises(FileExistsError):
                publish(path, b"second", False)
            self.assertEqual(path.read_bytes(), b"first")


if __name__ == "__main__":
    unittest.main()
