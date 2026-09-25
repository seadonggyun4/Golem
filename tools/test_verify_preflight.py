"""Keep the preflight matrix complete when component qualification evolves."""
import unittest

from verify_preflight import audit_groups, RUNTIME, ISOLATION, ORCHESTRATION
from verify_runtime import required_tests


class Preflight(unittest.TestCase):
    def test_exact_union_without_duplicate_execution(self):
        expected = {"json_contract", "admission_contract"}
        for matrix in (RUNTIME, ISOLATION, ORCHESTRATION):
            expected.update(test for tests in matrix.values() for test in tests)
        self.assertEqual(required_tests(audit_groups()), expected)
        self.assertEqual(audit_groups(), audit_groups())


if __name__ == "__main__":
    unittest.main()
