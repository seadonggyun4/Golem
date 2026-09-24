"""Host approval and script-byte boundaries; no shell safety inference."""
import copy
import hashlib
import sys
from pathlib import Path
import unittest
from execution_integration import Execution


class Boundary(Execution):
    def configure(self, body=None):
        self.setup_execution(mode="pass")
        script = self.repo / "qa.sh"
        script.write_text(body or "printf x >> invoked\n"
                          "printf '%s' '{\"schema_version\":1,\"cases\":["
                          "{\"id\":\"fix\",\"status\":\"PASS\"},"
                          "{\"id\":\"regression\",\"status\":\"PASS\"}]}'\n")
        self.contract["schema_version"] = 3
        self.contract["log_retention"] = {
            "mode": "DISCARD", "max_bytes": 0, "redactor": "none", "require_complete": False}
        self.contract["snapshot_plan"]["repositories"][0]["paths"].append("qa.sh")
        gate = self.contract["gates"][0]
        shell = Path("/bin/sh").resolve()
        gate["argv"] = [str(shell), str(script)]
        gate["protected_paths"].append("qa.sh")
        gate["execution"] = {"kind": "SHELL_SCRIPT",
            "executable_digest": hashlib.sha256(shell.read_bytes()).hexdigest(),
            "script": "qa.sh", "script_digest": hashlib.sha256(script.read_bytes()).hexdigest()}
        self.refresh()

    def refresh(self):
        self.approval = self.raw("execution", "validate", self.write("v3.json", self.contract)).strip()

    def shell_call(self, op, ok=True, shell=None, **fields):
        request = self.write("shell-request.json", {"schema_version": 1, "operation": op, **fields})
        return self.cli("execution", "call", self.work, request,
                        "--approve-contract", self.approval,
                        "--approve-shell-contract", shell or self.approval, ok=ok)

    def test_explicit_approval_idempotence_and_bundle(self):
        self.configure()
        self.call("prepare", contract=self.contract, ok=False)
        self.shell_call("prepare", contract=self.contract, shell="a" * 64, ok=False)
        self.cp = self.shell_call("prepare", contract=self.contract)
        self.finish()
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa", ok=False)
        self.assertFalse((self.repo / "invoked").exists())
        r = self.shell_call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa")
        self.assertEqual(r["record"]["status"], "PASS")
        self.assertEqual(r, self.shell_call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa"))
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        self.result("qa-result", r)
        self.cli("execution", "bundle", "inspect", self.work, r["receipt_digest"])
        (self.work / "execution-attempts/qa.done").unlink()
        self.shell_call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa", ok=False)
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_script_change_invalidates_approval(self):
        self.configure()
        self.cp = self.shell_call("prepare", contract=self.contract)
        self.finish()
        (self.repo / "qa.sh").write_text("touch unintended\n")
        self.shell_call("run", checkpoint=self.cp["receipt_digest"], attempt_id="changed", ok=False)
        self.assertFalse((self.repo / "unintended").exists())

    def test_whole_script_requires_approval_not_parser_classification(self):
        self.configure("printf x >> invoked\ntrue && true\nprintf ok | cat >/dev/null\n"
                       "value=$(printf safe)\nexit 17\n")
        self.call("prepare", contract=self.contract, ok=False)
        self.assertFalse((self.repo / "invoked").exists())
        self.cp = self.shell_call("prepare", contract=self.contract)
        self.finish()
        r = self.shell_call("run", checkpoint=self.cp["receipt_digest"], attempt_id="failure")
        self.assertEqual(r["record"]["gates"][0]["reason"], "NONZERO_EXIT")

    def test_invalid_contracts_and_json_cannot_approve(self):
        self.configure()
        for argv in (["sh", "qa.sh"], ["/bin/sh", "-c", "touch unintended"],
                     ["/bin/sh", "-s"], ["/bin/sh", "qa.sh"], ["/bin/sh", "a\nb"]):
            c = copy.deepcopy(self.contract)
            c["gates"][0]["argv"] = argv
            self.raw("execution", "validate", self.write("bad.json", c), ok=False)
        for field in ("approved_shell", "environment", "shell_contract"):
            self.call("prepare", contract=self.contract, **{field: True}, ok=False)
        c = copy.deepcopy(self.contract)
        c["gates"][0]["execution"] = {"kind": "DIRECT",
            "executable_digest": c["gates"][0]["execution"]["executable_digest"]}
        self.raw("execution", "validate", self.write("bad.json", c), ok=False)
        self.contract["gates"][0]["execution"]["script_digest"] = "a" * 64
        self.refresh()
        self.shell_call("prepare", contract=self.contract, ok=False)

    def test_legacy_shell_dispatch_is_not_implicitly_approved(self):
        self.configure()
        self.contract["schema_version"] = 2
        del self.contract["gates"][0]["execution"]
        self.refresh()
        self.shell_call("prepare", contract=self.contract, ok=False)

    def test_timeout_is_error(self):
        self.configure("printf x >> invoked\nsleep 5\n")
        self.contract["gates"][0]["timeout_ms"] = 100
        self.refresh()
        self.cp = self.shell_call("prepare", contract=self.contract)
        self.finish()
        r = self.shell_call("run", checkpoint=self.cp["receipt_digest"], attempt_id="timeout")
        self.assertEqual(r["record"]["status"], "ERROR")
        self.assertEqual(r["record"]["gates"][0]["reason"], "TIMEOUT")

    def test_direct_argv_has_no_shell_interpretation(self):
        self.configure()
        python = Path(sys.executable).resolve()
        gate = self.contract["gates"][0]
        gate["argv"] = [str(python), "runner.py", "$(touch unintended)", "; touch unintended", "&&", "|"]
        gate["execution"] = {"kind": "DIRECT", "executable_digest": hashlib.sha256(python.read_bytes()).hexdigest()}
        self.refresh()
        self.prepare()
        self.finish()
        r = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="direct")
        self.assertEqual(r["record"]["status"], "PASS")
        self.assertFalse((self.repo / "unintended").exists())

    def test_cwd_or_argv_change_needs_new_approval(self):
        self.configure()
        original = copy.deepcopy(self.contract)
        self.contract["gates"][0]["argv"].append("new argument")
        self.shell_call("prepare", contract=self.contract, ok=False)
        self.contract = original
        self.contract["snapshot_plan"]["repositories"][0]["root"] += "/subdir"
        self.contract["gates"][0]["argv"][1] = str(self.repo / "subdir/qa.sh")
        self.shell_call("prepare", contract=self.contract, ok=False)

    def test_prior_gate_mutation_blocks_next_dispatch(self):
        self.configure("printf x >> invoked\nprintf changed > logic.c\n")
        second = copy.deepcopy(self.contract["gates"][0])
        second["id"] = "second"
        self.contract["gates"].append(second)
        self.refresh()
        self.cp = self.shell_call("prepare", contract=self.contract)
        self.finish()
        self.shell_call("run", checkpoint=self.cp["receipt_digest"], attempt_id="mutated", ok=False)
        self.shell_call("run", checkpoint=self.cp["receipt_digest"], attempt_id="mutated", ok=False)
        self.assertEqual((self.repo / "invoked").read_text(), "x")


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Boundary(name) for name in Boundary.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
