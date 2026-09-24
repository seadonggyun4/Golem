"""Inventory enforcement through real execution and live receipt validation."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from execution_integration import Execution
from completion_integration import Completion


class Changes(Execution):
    completion = Completion.completion
    finalize = Completion.finalize
    project = Completion.project
    def configure(self, exclude=True, maximum=5, version=4, mode="pass", sessions=False):
        self.setup_execution(mode=mode, sessions=sessions)
        self.contract["schema_version"] = version
        self.contract["log_retention"] = {
            "mode": "DISCARD", "max_bytes": 0, "redactor": "none", "require_complete": False}
        self.contract["snapshot_plan"]["schema_version"] = 3 if version == 5 else 2
        repo = self.contract["snapshot_plan"]["repositories"][0]
        repo["change_policy"] = {"schema_version": 1,
            "protected": [{"kind": "DIR_PREFIX", "pattern": "private"}],
            "excluded": [{"kind": "EXACT", "pattern": "invoked"}] if exclude else [],
            "limit": {"mode": "BOUNDED", "max_changed_paths": maximum}}
        if mode == "real":
            repo["change_policy"]["excluded"].append({"kind": "EXACT", "pattern": "test-bin"})
        python = Path(sys.executable).resolve()
        self.contract["gates"][0]["execution"] = {
            "kind": "DIRECT", "executable_digest": hashlib.sha256(python.read_bytes()).hexdigest()}
        self.approval = self.raw("execution", "validate", self.write("v4.json", self.contract)).strip()

    def test_pass_then_unlisted_change_is_stale(self):
        self.configure()
        self.prepare()
        development = self.finish()
        r = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa")
        self.assertEqual(r["record"]["status"], "PASS")
        self.result("qa-result", r)
        findings = sorted(p.name for p in (self.work / "change-findings").iterdir())
        (self.repo / "new-source.c").write_text("new source")
        self.call("verify", receipt=r["receipt_digest"], ok=False)
        self.call("verify", receipt=development["receipt_digest"], ok=False)
        self.assertEqual(findings, sorted(p.name for p in (self.work / "change-findings").iterdir()))

    def test_self_mutating_qa_not_pass(self):
        self.configure(exclude=False)
        self.prepare()
        self.finish()
        r = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa")
        self.assertEqual(r["record"]["status"], "ERROR")
        self.assertEqual(r["record"]["reason"], "SNAPSHOT_CHANGED")

    def test_new_protected_path_blocks_finish(self):
        self.configure()
        self.prepare()
        (self.repo / "private").mkdir()
        (self.repo / "private/key").write_text("do not change")
        self.call("finish", checkpoint=self.cp["receipt_digest"], ok=False)
        markers = list((self.work / "change-findings").iterdir())
        self.assertEqual(len(markers), 1)
        marker = markers[0]
        self.assertEqual(marker.read_bytes().hex(), marker.name)
        data = (self.work / "objects/sha256" / marker.name[:2] / marker.name[2:]).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), marker.name)
        receipt = json.loads(data)
        self.assertFalse(receipt["allowed"])
        self.assertEqual(receipt["checkpoint"], self.cp["receipt_digest"])
        self.assertEqual(receipt["findings"][0]["protected_paths"], 1)

    def test_completion_rechecks_unlisted_paths(self):
        self.configure()
        self.prepare()
        self.finish()
        qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa")
        self.result("qa-result", qa)
        self.managed("completion")
        self.finalize()
        self.project()
        self.assertEqual(self.completion()["action"], "DONE")
        (self.repo / "late-source.c").write_text("late edit")
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")
        self.finalize(key="late", ok=False)

    def test_zero_limit_preserves_preexisting_changes(self):
        self.configure(maximum=0)
        self.prepare()
        self.finish()
        (self.repo / "untracked").write_text("new")
        self.call("finish", checkpoint=self.cp["receipt_digest"], ok=False)
        self.assertEqual((self.repo / "user.txt").read_text(), "preexisting uncommitted user work\n")

    def test_declared_inputs_cannot_be_excluded(self):
        self.configure()
        policy = self.contract["snapshot_plan"]["repositories"][0]["change_policy"]
        policy["excluded"].append({"kind": "EXACT", "pattern": "test.c"})
        self.raw("execution", "validate", self.write("excluded.json", self.contract), ok=False)

    def large_repository(self):
        # Four original tracked files plus 1,020 additional entries reach the
        # exact inventory limit, while declared test inputs remain bounded.
        for i in range(1020):
            (self.repo / f"source-{i:04d}.c").write_text(f"/* source {i} */\n")
        self.git("add", "source-*.c")
        self.git("commit", "-qm", "large source fixture")

    def object_path(self, digest):
        return self.work / "objects/sha256" / digest[:2] / digest[2:]

    def test_large_v5_qa_markdown_completion_and_staleness(self):
        self.configure(version=5, mode="real")
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.large_repository()
        self.prepare()
        snapshot = self.cp["record"]["baseline"]
        ref = snapshot["repositories"][0]["inventory_ref"]
        inventory = self.object_path(ref["digest"]).read_bytes()
        self.assertEqual(len(json.loads(inventory)["entries"]), 1024)
        self.assertGreater(len(inventory), 262144 // 3)
        self.assertEqual(len(inventory), ref["size"])
        self.assertEqual(hashlib.sha256(inventory).hexdigest(), ref["digest"])
        self.assertLess(len(json.dumps(snapshot)), 262144 // 3)
        self.finish()
        qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="large-qa")
        self.assertEqual(qa["record"]["status"], "PASS")
        self.assertIn("**PASS**", self.result("qa-result", qa))
        self.managed("completion")
        self.finalize()
        self.project()
        self.assertEqual(self.completion()["action"], "DONE")
        objects = sorted(str(p) for p in (self.work / "objects").rglob("*"))
        self.call("verify", receipt=qa["receipt_digest"])
        (self.repo / "source-1019.c").write_text("/* late change */\n")
        self.call("verify", receipt=qa["receipt_digest"], ok=False)
        self.assertEqual(objects, sorted(str(p) for p in (self.work / "objects").rglob("*")))
        self.assertEqual(self.completion()["action"], "REVALIDATE_COMPLETION")

    def test_v4_large_snapshot_still_rejects_without_silent_upgrade(self):
        self.configure()
        self.large_repository()
        self.call("prepare", contract=self.contract, ok=False)

    def test_v5_missing_and_corrupt_inventory_block_receipt(self):
        self.configure(version=5)
        self.prepare()
        dev = self.finish()
        ref = self.cp["record"]["baseline"]["repositories"][0]["inventory_ref"]
        path = self.object_path(ref["digest"])
        original = path.read_bytes()
        backup = path.with_name(path.name + ".fixture-backup")
        path.rename(backup)
        self.call("verify", receipt=dev["receipt_digest"], ok=False)
        backup.rename(path)
        path.chmod(0o600)
        path.write_bytes(b"x" * len(original))
        self.call("verify", receipt=dev["receipt_digest"], ok=False)
        path.write_bytes(original)
        path.chmod(0o400)
        self.call("verify", receipt=dev["receipt_digest"])

    def test_v5_protected_change_and_external_findings(self):
        self.configure(version=5)
        self.prepare()
        (self.repo / "private").mkdir()
        (self.repo / "private/secret").write_text("protected fixture")
        self.call("finish", checkpoint=self.cp["receipt_digest"], ok=False)
        marker = next((self.work / "change-findings").iterdir())
        receipt = json.loads(self.object_path(marker.name).read_bytes())
        self.assertEqual(receipt["schema_version"], 2)
        self.assertFalse(receipt["allowed"])
        findings = json.loads(self.object_path(receipt["findings_ref"]["digest"]).read_bytes())
        self.assertEqual(findings[0]["protected_paths"], 1)

    def test_v5_requires_explicit_plan_version(self):
        self.configure(version=5)
        self.contract["snapshot_plan"]["schema_version"] = 2
        self.raw("execution", "validate", self.write("wrong-plan.json", self.contract), ok=False)


def load_tests(loader, tests, pattern):
    # The full 1024-path QA/completion scenario has a separate CTest entry and
    # timeout. Keep the compatibility/error suite independently diagnosable.
    return unittest.TestSuite(Changes(name) for name in Changes.__dict__
                             if name.startswith("test_") and
                             name != "test_large_v5_qa_markdown_completion_and_staleness")


if __name__ == "__main__":
    unittest.main()
