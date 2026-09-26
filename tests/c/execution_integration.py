"""Real C build/test fixtures for document-driven development and QA receipts."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import workflow_integration as fixture
from discovery_integration import CLI, SOURCE, ENV

CC = str(Path(sys.argv.pop(1)).resolve())


class Execution(unittest.TestCase):
    setUp = fixture.Workflow.setUp
    tearDown = fixture.Workflow.tearDown
    write = fixture.Workflow.write
    cli = fixture.Workflow.cli
    validate = fixture.Workflow.validate
    answered = fixture.Workflow.answered
    confirmed = fixture.Workflow.confirmed
    body = fixture.Workflow.body
    metadata = fixture.Workflow.metadata
    publish = fixture.Workflow.publish
    setup_work = fixture.Workflow.setup_work
    register_selection = fixture.Workflow.register_selection
    next = fixture.Workflow.next

    def raw(self, *args, ok=True):
        p = subprocess.run([str(CLI), *map(str, args)], capture_output=True, env=ENV, timeout=90)
        self.assertEqual(p.returncode == 0, ok, p.stderr.decode())
        return p.stdout.decode()

    def inputs(self, kind, ok=True, budget=None):
        budget = budget or (1048576 if getattr(self, "sessions", False) else 16777216)
        return fixture.Workflow.inputs(self, kind, ok=ok, budget=budget)

    def git(self, *args):
        subprocess.run(["/usr/bin/git", "-C", str(self.repo), *args], env=ENV,
                       capture_output=True, check=True)

    def session(self, op, **fields):
        request = {"schema_version": 1, "operation": op, "work_id": "example-work",
                   "key": f"session-{self.seq + 1}", "expected_sequence": self.seq, **fields}
        r = self.cli("session", "call", self.work, self.write("session-request.json", request))
        self.seq = r["sequence"]
        return r

    def begin_claim(self, ttl=60000):
        r = self.session("claim", session_id="current-agent", expected_generation=self.generation,
                         source_snapshot=self.source, byte_budget=1048576, ttl_ms=ttl)
        active = r["state"]["active"]
        self.token = {k: active[k] for k in ("epoch", "attempt_id", "session_id")}
        self.input_digest = active["manifest_digest"]
        self.session("begin", token=self.token, input_digest=self.input_digest)

    def session_submit(self, kind):
        result = self.docs[kind]
        self.session("submit", token=self.token, input_digest=self.input_digest, source_snapshot=self.source,
                     output={"document_id": kind, "revision": result["revision"], "digest": result["manifest_digest"]},
                     evidence=[result["body_digest"]])
        self.token = None

    def managed(self, kind, doc_id=None):
        if not getattr(self, "sessions", False):
            return fixture.Workflow.managed(self, kind, doc_id)
        self.begin_claim()
        manifest = self.inputs(kind)
        m = self.metadata(kind, doc_id, manifest["direct"], 4)
        m.update(input_manifest=manifest, producer_attempt=self.token["attempt_id"])
        result = self.publish(m)
        self.session_submit(kind)
        return result

    def setup_execution(self, mode="real", plan=True, sessions=False):
        self.setup_work()
        self.register_selection()
        self.sessions = sessions
        self.token = None
        if sessions:
            self.seq = 0
            self.session("start", selection_id="selection")
        self.managed("planning")
        if plan:
            self.managed("development-plan")
        self.repo = self.root / "project"
        self.repo.mkdir()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a-b; }\n")
        (self.repo / "test.c").write_text(r'''#include <stdio.h>
int add(int,int);
int main(void) {
    int ok=add(3,2)==5, regression=add(0,0)==0 && add(7,0)==7;
    printf("{\"schema_version\":1,\"cases\":[{\"id\":\"fix\",\"status\":\"%s\"},{\"id\":\"regression\",\"status\":\"%s\"}]}",ok?"PASS":"FAIL",regression?"PASS":"FAIL");
    return ok && regression?0:1;
}
''')
        script = "from pathlib import Path\nimport os,sys,json,subprocess,time,signal\n"
        script += "p=Path('invoked'); p.write_text(p.read_text()+'x' if p.exists() else 'x')\n"
        normal = "print(json.dumps({'schema_version':1,'cases':[{'id':'fix','status':'PASS'},{'id':'regression','status':'PASS'}]}))\n"
        if mode == "real":
            script += f"subprocess.run([{CC!r},'-Wall','-Wextra','-Werror','logic.c','test.c','-o','test-bin'],check=True)\n"
            script += "sys.exit(subprocess.run(['./test-bin']).returncode)\n"
        elif mode == "timeout":
            script += "time.sleep(3)\n"
        elif mode == "signal":
            script += "os.kill(os.getpid(),signal.SIGTERM)\n"
        elif mode == "overflow":
            script += "print('x'*30000)\n"
        elif mode == "empty":
            script += "print('{\"schema_version\":1,\"cases\":[]}')\n"
        elif mode == "changed":
            script += "Path('logic.c').write_text('changed during QA')\n" + normal
        elif mode == "env":
            script += "assert 'GOLEM_TEST_SECRET' not in os.environ\n" + normal
        elif mode == "lease":
            script += "time.sleep(9)\n" + normal
        else:
            script += normal
        (self.repo / "runner.py").write_text(script)
        (self.repo / "user.txt").write_text("committed user work\n")
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        (self.repo / "user.txt").write_text("preexisting uncommitted user work\n")
        self.contract = {"schema_version": 1, "selection_id": "selection",
            "development_plan": {"document_id": "development-plan", "revision": 1,
                "digest": self.docs.get("development-plan", {}).get("manifest_digest", "a" * 64)},
            "snapshot_plan": {"schema_version": 1, "timeout_seconds": 15, "repositories": [{
                "id": "project", "root": str(self.repo), "paths": ["logic.c", "test.c", "runner.py", "user.txt"],
                "toolchain": "host C compiler fixture", "test_configuration": "two declared C test cases"}]},
            "gates": [{"id": "regression", "version": 1, "repository": "project",
                "argv": [str(Path(sys.executable).resolve()), "runner.py"], "timeout_ms": 150 if mode == "timeout" else 15000,
                "cases": [{"id": "fix", "requirement_id": "REQ-1"}, {"id": "regression", "requirement_id": "REQ-1"}],
                "protected_paths": ["test.c", "runner.py"]}]}
        self.approval = self.raw("execution", "validate", self.write("contract.json", self.contract)).strip()

    def call(self, op, ok=True, approval=True, **fields):
        if getattr(self, "token", None) and op != "verify":
            fields["token"] = self.token
        p = self.write("execution.json", {"schema_version": 1, "operation": op, **fields})
        args = ["execution", "call", self.work, p]
        if approval:
            args += ["--approve-contract", self.approval]
        return self.cli(*args, ok=ok)

    def prepare(self):
        if self.sessions:
            self.begin_claim()
        self.cp = self.call("prepare", contract=self.contract)
        return self.cp

    def result(self, kind, receipt, tamper=False):
        manifest = receipt["record"]["manifest"]
        m = self.metadata(kind, parents=manifest["direct"], version=5)
        m.update(input_manifest=manifest, execution_receipt=receipt["receipt_digest"])
        if self.sessions:
            m["producer_attempt"] = self.token["attempt_id"]
        path = self.write("result-meta.json", m)
        body = self.raw("execution", "render", self.work, path)
        content = body.replace("**FAIL**", "**PASS**") if tamper else body
        output = self.cli("document", "submit", self.work, path, self.write("result.md", content),
                          f"{kind}-{m['revision']}", ok=not tamper)
        if not tamper:
            self.generation += 1
            self.docs[kind] = output
            if self.sessions:
                self.session_submit(kind)
        return body

    def finish(self):
        r = self.call("finish", checkpoint=self.cp["receipt_digest"])
        self.result("development-result", r)
        self.managed("qa-plan")
        return r

    def test_real_failure_repair_and_reverification(self):
        self.setup_execution()
        self.prepare()
        dev = self.finish()
        first = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa-1")
        self.assertEqual(first["record"]["status"], "FAIL")
        self.result("qa-result", first, tamper=True)
        text = self.result("qa-result", first)
        self.assertIn("**FAIL**", text)
        self.assertEqual(self.next()["target_kind"], "qa-result")
        self.inputs("completion", ok=False)
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.call("verify", receipt=dev["receipt_digest"], ok=False)
        repaired = self.finish()
        self.assertEqual((self.repo / "logic.c").read_text(), "int add(int a,int b) { return a+b; }\n")
        self.assertNotEqual(repaired["receipt_digest"], dev["receipt_digest"])
        passed = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qa-2")
        self.assertEqual(passed["record"]["status"], "PASS", json.dumps(passed, indent=2))
        self.assertNotEqual(passed["receipt_digest"], first["receipt_digest"])
        self.assertFalse(passed["acceptance_verified"])
        self.call("verify", receipt=passed["receipt_digest"])
        text = self.result("qa-result", passed)
        self.assertIn("**PASS**", text)
        self.assertIn("REQ-1 | fix | PASS | PASS", text)
        self.assertIn("user.txt | yes", text)
        self.assertEqual((self.repo / "user.txt").read_text(), "preexisting uncommitted user work\n")
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a-b; }\n")
        self.call("verify", receipt=passed["receipt_digest"], ok=False)

    def test_permission_and_missing_plan(self):
        self.setup_execution(plan=False)
        self.call("prepare", contract=self.contract, ok=False)
        self.managed("development-plan")
        self.contract["development_plan"]["digest"] = self.docs["development-plan"]["manifest_digest"]
        self.approval = self.raw("execution", "validate", self.write("contract.json", self.contract)).strip()
        self.call("prepare", contract=self.contract, approval=False, ok=False)
        self.prepare()
        self.finish()
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="denied", approval=False, ok=False)
        self.assertFalse((self.repo / "invoked").exists())

    def test_protected_test_change_denied(self):
        self.setup_execution()
        self.prepare()
        (self.repo / "test.c").write_text("int main(void) { return 0; }\n")
        self.call("prepare", contract=self.contract, ok=False)
        self.finish()
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="weakened", ok=False)
        self.assertFalse((self.repo / "invoked").exists())

    def test_idempotent_and_uncertain_attempt(self):
        self.setup_execution(mode="pass")
        self.prepare()
        self.finish()
        r = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="same")
        duplicate = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="same")
        self.assertEqual(r, duplicate)
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        (self.work / "execution-attempts/same.done").unlink()
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="same", ok=False)
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_raw_environment_not_inherited(self):
        self.setup_execution(mode="env")
        self.prepare()
        self.finish()
        ENV["GOLEM_TEST_SECRET"] = "must-not-reach-child"
        try:
            r = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="env")
        finally:
            ENV.pop("GOLEM_TEST_SECRET")
        self.assertEqual(r["record"]["status"], "PASS")

    def test_stale_upstream_document(self):
        self.setup_execution()
        self.prepare()
        self.managed("planning")
        self.call("finish", checkpoint=self.cp["receipt_digest"], ok=False)

    def test_current_agent_session_integration(self):
        self.setup_execution(mode="pass", sessions=True)
        self.prepare()
        self.finish()
        self.begin_claim()
        good = self.token
        self.token = {**good, "epoch": good["epoch"] + 1}
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="stale-owner", ok=False)
        self.assertFalse((self.repo / "invoked").exists())
        self.token = good
        receipt = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="owned")
        self.result("qa-result", receipt)
        state = self.cli("session", "call", self.work, self.write("status.json", {
            "schema_version": 1, "operation": "status", "work_id": "example-work"}))
        self.assertIsNone(state["state"]["active"])

    def test_enrollment_cannot_downgrade_result_or_change_contract(self):
        self.setup_execution()
        self.prepare()
        manifest = self.inputs("development-result")
        m = self.metadata("development-result", parents=manifest["direct"], version=4)
        m["input_manifest"] = manifest
        self.publish(m, ok=False)
        changed = copy.deepcopy(self.contract)
        changed["gates"][0]["cases"].pop()
        self.approval = self.raw("execution", "validate", self.write("changed.json", changed)).strip()
        self.call("prepare", contract=changed, ok=False)

    def test_duplicate_keys_unknown_fields_and_empty_cases(self):
        self.setup_execution()
        for field in ("gates", "snapshot_plan", "development_plan"):
            c = copy.deepcopy(self.contract)
            del c[field]
            self.raw("execution", "validate", self.write("invalid.json", c), ok=False)
        c = copy.deepcopy(self.contract)
        c["gates"][0]["cases"] = []
        self.raw("execution", "validate", self.write("invalid.json", c), ok=False)
        self.raw("execution", "validate", self.write("duplicate.json", '{"schema_version":1,"schema_version":1}'), ok=False)
        c = copy.deepcopy(self.contract)
        c["gates"][0]["unexpected"] = True
        self.raw("execution", "validate", self.write("unknown.json", c), ok=False)

    def test_observation_loss_and_started_marker_loss(self):
        self.setup_execution(mode="pass")
        self.prepare()
        self.finish()
        receipt = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="retained")
        digest = receipt["record"]["gates"][0]["observation_digest"]
        (self.work / "objects/sha256" / digest[:2] / digest[2:]).unlink()
        self.call("verify", receipt=receipt["receipt_digest"], ok=False)
        (self.work / "execution-attempts/retained.started").unlink()
        self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="retained", ok=False)
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_lease_expiry_during_command(self):
        self.setup_execution(mode="lease", sessions=True)
        self.prepare()
        self.finish()
        self.begin_claim(ttl=6000)
        receipt = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="expires")
        self.assertEqual(receipt["record"]["status"], "ERROR")
        self.assertEqual(receipt["record"]["gates"][0]["reason"], "LEASE_EXPIRED")

    def test_failure_modes(self):
        for mode, reason in [("timeout", "TIMEOUT"), ("signal", "SIGNAL"), ("overflow", "LOG_LIMIT"),
                             ("empty", "INVALID_OR_MISSING_CASES"), ("changed", "SNAPSHOT_CHANGED")]:
            with self.subTest(mode=mode):
                self.tearDown()
                self.setUp()
                self.setup_execution(mode=mode)
                self.prepare()
                self.finish()
                r = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="failure")
                self.assertNotEqual(r["record"]["status"], "PASS")
                observed = r["record"]["reason"] if mode == "changed" else r["record"]["gates"][0]["reason"]
                self.assertEqual(observed, reason)


if __name__ == "__main__":
    unittest.main()
