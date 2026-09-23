"""Ring measurement correctness, never a timing threshold on shared CI."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

BINARY = Path(sys.argv.pop(1)).resolve()


class RuntimeBench(unittest.TestCase):
    def test_modes_and_checksum(self):
        for observers in (0, 1, 32):
            result = subprocess.run([str(BINARY), str(observers)], check=True,
                                    capture_output=True, timeout=30)
            data = json.loads(result.stdout)
            self.assertEqual(data["iterations"], 100000)
            self.assertEqual(data["observers"], observers)
            self.assertEqual(data["checksum"], observers * 16 * 6250 * 6251 // 2)
            self.assertGreater(data["elapsed_ns"], 0)
            self.assertGreater(data["rss_bytes"], 0)

    def test_bad_mode(self):
        self.assertEqual(subprocess.run([str(BINARY), "33"], capture_output=True,
                                        timeout=30).returncode, 2)


if __name__ == "__main__":
    unittest.main()
