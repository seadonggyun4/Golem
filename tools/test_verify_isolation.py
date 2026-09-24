import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import verify_isolation as gate
from verify_agent import save
from verify_runtime import adjudicate


class Qualification(unittest.TestCase):
    def test_required_groups_are_unique_and_nonempty(self):
        names = [n for group in gate.GROUPS.values() for n in group]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(gate.GROUPS.values()))
        self.assertIn("candidate_cli_host", names)
        self.assertIn("execution_change_large_cli", names)
        self.assertEqual(set(gate.BINDINGS["language_contracts"]),
                         {"binding_abi", "binding_python", "binding_typescript"})

    def test_failure_or_missing_evidence_never_becomes_release_claim(self):
        for status in ("PASS", "FAIL"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                def observed(build, output, *args, **kwargs):
                    output.mkdir()
                    result = {"status": status}
                    save(output / "report.json", json.dumps(result).encode())
                    return result
                with patch.object(gate, "run", side_effect=observed):
                    report = gate.qualify(root, root, root / "out")
                self.assertEqual(report["status"], status)
                for flag in ("actual_agent_verified", "release_ready", "installation_verified", "provider_invoked",
                             "production_candidate_host_verified", "physical_resource_limits_verified",
                             "selected_patch_application_verified"):
                    self.assertIs(report[flag], False)
                self.assertEqual(len(report["reports"]), 2)
                with self.assertRaises(FileExistsError):
                    gate.qualify(root, root, root / "out")

    def test_skip_and_empty_junit_are_not_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.xml"
            for body in ("", '<testcase name="x" status="run"><skipped/></testcase>',
                         '<testcase name="wrong" status="run"/>'):
                path.write_text("<testsuite>" + body + "</testsuite>")
                self.assertFalse(adjudicate(path, ("x",)))


if __name__ == "__main__":
    unittest.main()
