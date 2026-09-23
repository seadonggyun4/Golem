import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from benchmark_runtime import sample


class BenchmarkInput(unittest.TestCase):
    def test_only_complete_numeric_contract_is_accepted(self):
        good = {"schema": 1, "observers": 0, "iterations": 100000,
                "elapsed_ns": 100, "rss_bytes": 1024, "checksum": 0}
        def run(value):
            with patch("benchmark_runtime.subprocess.run", return_value=SimpleNamespace(
                    stdout=json.dumps(value).encode())):
                return sample(Path("unused"), 0)
        self.assertEqual(run(good), good)
        for value in ([], {}, {**good, "extra": 1}, {**good, "observers": False},
                      {**good, "schema": 2}, {**good, "elapsed_ns": 0},
                      {**good, "rss_bytes": -1}, {**good, "checksum": 1}):
            with self.assertRaises(ValueError):
                run(value)


if __name__ == "__main__":
    unittest.main()
