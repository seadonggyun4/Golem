"""Installed CLI host; real Work claims, local QA, no provider process or SDK."""
import json
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time
import unittest

from execution_change_integration import Changes
from discovery_integration import CLI, SOURCE, ENV


class CandidateCLI(Changes):
    def setup_work(self, *args, **kwargs):
        super().setup_work(*args, **kwargs)
        self.cli("profile", "register", self.work, SOURCE / "samples/runtime-profile.json", "profile-1")

    def tearDown(self):
        host = getattr(self, "host", None)
        if host is not None:
            host.terminate()
            host.communicate(timeout=20)
            self.host = None
        control = getattr(self, "control", None)
        if control is not None:
            control.cleanup()
        super().tearDown()

    def begin_claim(self, ttl=3600000):
        r = self.session("claim", session_id="agent-a", expected_generation=self.generation,
                         source_snapshot=self.source, byte_budget=1048576, ttl_ms=ttl)
        self.active = r["state"]["active"]
        self.token = {k: self.active[k] for k in ("epoch", "attempt_id", "session_id")}
        self.input_digest = self.active["manifest_digest"]
        self.session("begin", token=self.token, input_digest=self.input_digest)

    def host_start(self, suffix="host.sock"):
        self.socket = Path(self.control.name).resolve() / suffix
        config = self.write("host-config.json", self.config)
        digest = self.raw("candidate", "host-validate", config).strip()
        self.host = subprocess.Popen([str(CLI), "candidate", "serve", str(config),
            str(self.socket), "--approve-config", digest], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=ENV)
        deadline = time.monotonic() + 15
        while not self.socket.exists() and self.host.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        if self.host.poll() is not None:
            _, err = self.host.communicate()
            self.fail(err.decode())
        self.assertTrue(self.socket.exists())

    def rpc(self, operation, approve=True, attest=False, ok=True, **fields):
        request = self.write("host-request.json", dict(operation=operation, **fields))
        args = ["candidate", "call", self.socket, request]
        digest = self.raw("candidate", "request-digest", request).strip()
        if approve:
            args += ["--approve-request", digest]
        if attest:
            args += ["--attest-termination", digest]
        output = self.raw(*args, ok=ok)
        return json.loads(output) if ok else None

    def group(self, op, candidate=None, **fields):
        return self.rpc(op, group_id="group", **({"candidate": candidate} if candidate else {}), **fields)

    def setup_host(self, version=4, large=False):
        self.configure(sessions=True, mode="real", version=version)
        if large:
            self.large_repository()
        self.begin_claim()
        base = subprocess.check_output(["/usr/bin/git", "-C", str(self.repo), "rev-parse", "HEAD"], env=ENV).decode().strip()
        self.parent = self.root / "parent"
        spec = json.loads((SOURCE / "samples/documents/work.json").read_text())
        spec["work_id"] = "parent"
        self.cli("work", "start", self.parent, self.write("parent-spec.json", spec))
        for name in ("admission", "trees", "build-a", "temp-a"):
            (self.root / name).mkdir(mode=0o700)
        self.control = tempfile.TemporaryDirectory(prefix="golem-host-", dir="/tmp")
        self.config = dict(schema_version=1, parent=str(self.parent), admission=str(self.root / "admission"),
            repository_id="fixture", repository_root=str(self.repo), worktree_root=str(self.root / "trees"),
            limits=dict(slots=1, cpu_millis=1000, memory_bytes=8192), target=None,
            bindings=[dict(candidate="a", session="agent-a", runtime_binding=self.active["runtime_binding"],
                work=str(self.work), tree=str(self.root / "trees/example-work/a"),
                build=str(self.root / "build-a"), temp=str(self.root / "temp-a"), environment="e" * 64)])
        # An unrelated candidate need not be openable while operating candidate a.
        self.config["bindings"].append(dict(candidate="unrelated", session="agent-b",
            runtime_binding="f" * 64, work=str(self.root / "not-created"),
            tree=str(self.root / "trees/other/b"), build=str(self.root / "build-b"),
            temp=str(self.root / "temp-b"), environment="e" * 64))
        self.host_start()
        self.rpc("workspace-create", candidate="a", base_commit=base)
        self.repo = Path(self.config["bindings"][0]["tree"])
        self.contract["snapshot_plan"]["repositories"][0]["root"] = str(self.repo)
        self.approval = self.raw("execution", "validate", self.write("contract.json", self.contract)).strip()
        self.cp = self.call("prepare", contract=self.contract)
        gates = self.raw("candidate", "gates", self.work, self.cp["receipt_digest"]).strip()
        self.manifest = dict(schema_version=1, group_id="group", parallel_opt_in=False,
            task_digest="b" * 64, base_commit=base, gates_digest=gates, protocol_digest="d" * 64,
            currency="USD", limits=dict(workers=1, cpu=1000, memory=8192, io=1, tokens=100, nano_cost=100),
            candidates=[dict(id="a", work_id="example-work", session_id="agent-a",
                runtime_binding=self.active["runtime_binding"], environment_digest="e" * 64,
                resources=dict(cpu=1000, memory=1024, io=1, tokens=10, nano_cost=10))], cohort=None)

    def launch(self):
        self.rpc("create", manifest=self.manifest)
        self.group("enroll", "a")
        self.group("reserve", "a")
        ticket = self.rpc("grant")
        self.admission_token = {k: ticket[k] for k in ("ticket", "epoch", "instance", "boot")}
        self.group("start", "a", token=self.admission_token)

    def settle(self, qa="", cancelled=False, known=True, attest=True, ok=True):
        return self.group("settle", "a", token=self.admission_token, qa=qa, cancelled=cancelled,
            tokens_known=known, cost_known=known, tokens=3 if known else 0,
            nano_cost=2 if known else 0, attest=attest, ok=ok)

    def clear_claim(self):
        r = self.session("resume", session_id="agent-a", ttl_ms=3600000)
        active = r["state"]["active"]
        self.token = {k: active[k] for k in ("epoch", "attempt_id", "session_id")}
        evidence = self.cli("evidence", "put", self.work,
            self.write("inspection.txt", "Fixture operator inspected nonexecution."))["digest"]
        self.session("reconcile", token=self.token, input_digest=self.input_digest,
            source_snapshot=self.source, output=None, evidence=[evidence], resolution="NO_EFFECTS")
        self.token = None

    def test_cli_claim_qa_comparison_selection(self):
        self.check_cli_selection()

    def test_cli_large_v5_qa_comparison_selection(self):
        self.check_cli_selection(version=5, large=True)

    def check_cli_selection(self, version=4, large=False):
        self.setup_host(version=version, large=large)
        self.launch()
        self.assertTrue(self.group("poll", "a", session="agent-a", approve=False)["may_continue"])
        self.group("start", "a", token=self.admission_token, ok=False)
        self.settle(ok=False)  # An operator flag cannot override a RUNNING claim.
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.finish()
        self.begin_claim()
        self.assertTrue(self.group("poll", "a", session="agent-a", approve=False)["may_continue"])
        qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="candidate-qa")
        self.assertEqual(qa["record"]["status"], "PASS")
        self.result("qa-result", qa)
        self.settle(qa["receipt_digest"], attest=False, ok=False)
        report = self.settle(qa["receipt_digest"])
        self.assertEqual(report["candidates"][0]["state"], "FINISHED")
        self.settle(qa["receipt_digest"])  # Same settlement is idempotent.
        self.assertEqual(self.group("compare")["decision"], "SOLE_PASS")
        self.group("select", "a", approve=False, ok=False)
        self.group("select", "a")
        self.rpc("shutdown")
        self.host.communicate(timeout=20)
        self.assertEqual(self.host.returncode, 0)
        self.host = None
        self.raw("candidate", "status", self.parent, "group")

    def test_cancel_mailbox_restart_fencing_and_unknown_usage(self):
        self.setup_host()
        self.launch()
        self.group("cancel", "a", token=self.admission_token)
        self.group("cancel", "a", token=self.admission_token)
        polled = self.group("poll", "a", session="agent-a", approve=False)
        self.assertTrue(polled["cancel_requested"])
        self.assertFalse(polled["may_continue"])
        self.assertTrue((self.work / "candidate-notifications/group").is_file())
        self.settle(cancelled=True, ok=False)
        self.host.kill()
        self.host.communicate(timeout=20)
        self.host = None
        self.host_start("recovered.sock")
        self.assertFalse(self.group("poll", "a", session="agent-a", approve=False)["may_continue"])
        self.group("start", "a", token=self.admission_token, ok=False)
        self.clear_claim()
        self.settle(cancelled=True, ok=False)  # The old epoch cannot settle.
        ticket = self.rpc("ticket", operation_id="cf-group-a", approve=False)
        self.admission_token = {k: ticket[k] for k in ("ticket", "epoch", "instance", "boot")}
        self.settle(cancelled=True, known=False)
        report = self.group("compare")
        self.assertFalse(report["cost_complete"])
        self.assertEqual(report["decision"], "INCOMPARABLE")
        self.assertEqual(report["dispatch_intent_denominator"], 1)

    def test_cancel_after_restart_keeps_reservation_and_delivers_notice(self):
        self.setup_host()
        self.launch()
        old_token = self.admission_token.copy()
        self.host.kill()
        self.host.communicate(timeout=20)
        self.host = None
        self.host_start("recovered.sock")
        self.group("cancel", "a", token=old_token, ok=False)
        ticket = self.rpc("ticket", operation_id="cf-group-a", approve=False)
        self.assertEqual(ticket["state"], 6)  # RECONCILE_REQUIRED retains resources.
        self.admission_token = {k: ticket[k] for k in ("ticket", "epoch", "instance", "boot")}
        self.group("cancel", "a", token=self.admission_token)
        self.group("cancel", "a", token=self.admission_token)
        self.assertTrue((self.work / "candidate-notifications/group").is_file())
        self.assertEqual(self.rpc("ticket", operation_id="cf-group-a", approve=False)["state"], 6)
        polled = self.group("poll", "a", session="agent-a", approve=False)
        self.assertTrue(polled["cancel_requested"])
        self.assertFalse(polled["may_continue"])
        self.settle(cancelled=True, ok=False)  # Cancellation is not termination.
        self.clear_claim()
        report = self.settle(cancelled=True, known=False)
        self.assertEqual(report["candidates"][0]["state"], "FINISHED")

    def test_approval_and_transport_fail_closed(self):
        self.setup_host()
        self.rpc("create", manifest=self.manifest, approve=False, ok=False)
        self.rpc("create", manifest=self.manifest)
        self.group("status", approve=False)
        request = self.write("denied.json", dict(operation="grant"))
        self.raw("candidate", "call", self.socket, request, "--approve-request", "0" * 64, ok=False)
        for frame in (struct.pack(">I", 2**31), struct.pack(">I", 2) + b"{", struct.pack(">I", 3) + b"bad"):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(self.socket))
                client.sendall(frame)
                client.shutdown(socket.SHUT_WR)
                client.settimeout(10)
                client.recv(4096)
        self.group("status", approve=False)
        self.socket.chmod(0o666)
        self.group("status", approve=False, ok=False)
        self.socket.chmod(0o600)
        self.group("status", approve=False)
        config = self.write("same-config.json", self.config)
        digest = self.raw("candidate", "host-validate", config).strip()
        self.raw("candidate", "serve", config, self.socket, "--approve-config", digest, ok=False)
        self.group("status", approve=False)  # Never unlink the existing listener.
        Path(self.control.name).chmod(0o755)
        self.group("status", approve=False, ok=False)
        Path(self.control.name).chmod(0o700)
        self.group("status", approve=False)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(CandidateCLI(name) for name in CandidateCLI.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
