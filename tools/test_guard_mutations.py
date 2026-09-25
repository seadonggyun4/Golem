import tempfile
from pathlib import Path
import unittest

from check_guard_mutations import detected, replacement


class GuardMutations(unittest.TestCase):
    def test_exact_site_required(self):
        self.assertEqual(replacement("a guard b", "guard", "broken"), "a broken b")
        for text in ("absent", "guard guard"):
            with self.assertRaises(ValueError):
                replacement(text, "guard", "broken")

    def test_only_actual_selected_test_failure_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.xml"
            for message, expected in (("Failed", True), ("Timeout", False),
                                      ("SEGFAULT", False), ("Not Run", False)):
                path.write_text('<testsuite><testcase name="guard" status="fail">'
                                f'<failure message="{message}"/></testcase></testsuite>')
                self.assertEqual(detected(path, "guard", 8), expected)
                self.assertFalse(detected(path, "guard", 0))
                self.assertFalse(detected(path, "missing", 8))


if __name__ == "__main__":
    unittest.main()
