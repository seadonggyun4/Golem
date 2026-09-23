"""Profile-enrolled end-to-end fixtures; never a model/agent attestation."""
import json
import sys
import unittest
from conformance_integration import Conformance
from execution_integration import SOURCE


class RuntimeCanary(Conformance):
    def setup_work(self):
        super().setup_work()
        profile = json.loads((SOURCE / "samples/runtime-profile.json").read_text())
        self.cli("profile", "register", self.work,
                 self.write("runtime-profile.json", profile), "canary-profile")

    def session(self, op, **fields):
        result = super().session(op, **fields)
        if op == "claim":
            binding = result["state"]["active"]["runtime_binding"]
            value = json.loads((self.work / "objects/sha256" / binding[:2] / binding[2:]).read_bytes())
            self.assertEqual(value["runtime_generation"], 1)
            self.assertEqual(value["claim_epoch"], result["state"]["active"]["epoch"])
        return result

    def test_profile_fail_revision_pass(self):
        self.test_e01_session_failure_revision_completion()

    def test_profile_restart_without_duplicate(self):
        self.test_e04_reopen_adopt_without_duplicate_output()

    def test_profile_stale_completion(self):
        self.ready(sessions=True)
        receipt = self.finalize()
        report = self.project()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a-b; }\n")
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")
        self.finalize(key="stale-snapshot", ok=False)
        self.assertEqual(self.finalize(), receipt)
        self.assertEqual(self.project(), report)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(RuntimeCanary(name) for name in (
        "test_profile_fail_revision_pass", "test_profile_restart_without_duplicate",
        "test_profile_stale_completion"))


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False).result
    sys.exit(0 if result.wasSuccessful() and result.testsRun == 3 and not result.skipped else 1)
