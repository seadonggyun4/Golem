import tempfile
import unittest
from pathlib import Path
from verify_runtime import adjudicate
from benchmark_runtime import summarize


class RuntimeReport(unittest.TestCase):
    def test_nearest_rank_percentiles(self):
        result = summarize(list(range(1, 31)))
        self.assertEqual(result["median"], 15.5)
        self.assertEqual(result["p95"], 29)
        self.assertEqual(result["p99"], 30)

    def test_missing_duplicate_skipped_and_failed_are_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.xml"
            self.assertFalse(adjudicate(path, ["a"]))
            for body in ("", '<testcase name="b" status="run"/>',
                         '<testcase name="a" status="run"/><testcase name="a" status="run"/>',
                         '<testcase name="a" status="run"><skipped/></testcase>',
                         '<testcase name="a" status="run"><failure/></testcase>',
                         '<testcase status="run"/>',
                         '<testcase name="a" status="notrun"/>'):
                path.write_text('<testsuite>' + body + '</testsuite>')
                self.assertFalse(adjudicate(path, ["a"]))
            path.write_text('<testsuite><testcase name="a" status="run"/></testsuite>')
            self.assertTrue(adjudicate(path, ["a"]))


if __name__ == "__main__":
    unittest.main()
