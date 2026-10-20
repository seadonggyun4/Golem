"""Synthetic historical registration; never open or recover a product Work."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

CAPTURE = len(sys.argv) > 1 and sys.argv[1] == "--capture"
if CAPTURE:
    sys.argv.pop(1)
import session_integration as sessions
CC = None if CAPTURE else sys.argv.pop(1)

FIXTURE = Path(__file__).parent / "fixtures/session/wrong-kind-v1.json"


def capture():
    if FIXTURE.exists():
        raise ValueError("Historical fixture already exists; preserve it and review a separately versioned capture.")
    expected = "20d3221870af8ba3db4264a1caed36264edff02da75f374a496f3e597fbfd742"
    if hashlib.sha256(sessions.fixture.CLI.read_bytes()).hexdigest() != expected:
        raise ValueError("Capture requires the recorded pre-rejection 265a83a binary; not an installed product Work.")
    case = sessions.Session()
    case.setUp()
    try:
        case.setup_work(mode="documents")
        case.register_selection()
        case.now, case.boot, case.seq, case.key, case.actual = 1000, 1, 0, 0, False
        case.request("start", selection_id="selection")
        for kind in ("planning", "development-plan", "qa-plan"):
            case.claim(); case.begin(); case.output(); case.submit()
        case.claim(); case.begin()
        assert case.active["kind"] == "qa-result"
        inputs = case.cli("workflow", "inputs", case.work, "selection", "planning", case.source, 1048576)
        metadata = case.metadata("planning", parents=inputs["direct"], version=4)
        metadata.update(producer_attempt=case.active["attempt_id"], input_manifest=inputs)
        receipt = case.publish(metadata)
        case.ref = dict(document_id="planning", revision=receipt["revision"], digest=receipt["manifest_digest"])
        case.submit(ok=False)
        resumed = case.request("resume", session_id="agent-a", ttl_ms=10000)
        case.active = resumed["state"]["active"]
        case.token = {k: case.active[k] for k in ("epoch", "attempt_id", "session_id")}
        files = {}
        for path in sorted(case.work.rglob("*")):
            if path.is_file():
                raw = path.read_bytes()
                assert b"/Users/" not in raw and b"/Volumes/" not in raw
                files[path.relative_to(case.work).as_posix()] = base64.b64encode(raw).decode()
        attributes = {key: getattr(case, key) for key in (
            "docs", "generation", "source", "now", "boot", "seq", "key", "active", "token", "ref", "evidence")}
        value = dict(schema_version=1, synthetic=True, producer_commit="265a83aad5d36b30e010e0d669605d930642fd6b",
                     binary_sha256=hashlib.sha256(sessions.fixture.CLI.read_bytes()).hexdigest(),
                     attributes=attributes, files=files)
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(value, indent=2) + "\n")
    finally:
        case.tearDown()


class Rejection(unittest.TestCase):
    tearDown = sessions.Session.tearDown
    write = sessions.Session.write
    cli = sessions.Session.cli
    raw = sessions.Session.raw
    request = sessions.Session.request
    claim = sessions.Session.claim
    begin = sessions.Session.begin
    output = sessions.Session.output
    submit = sessions.Session.submit
    metadata = sessions.Session.metadata
    publish = sessions.Session.publish
    body = sessions.Session.body
    work_bytes = sessions.Session.work_bytes

    def setUp(self):
        sessions.Session.setUp(self)
        value = json.loads(FIXTURE.read_text())
        self.work = self.root / "work"
        self.work.mkdir(mode=0o700)
        for name, encoded in value["files"].items():
            relative = Path(name)
            assert not relative.is_absolute() and ".." not in relative.parts
            path = self.work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(encoded, validate=True))
        for key, value in value["attributes"].items():
            setattr(self, key, value)
        self.actual = False

    def approval(self, **changes):
        manifest = self.request("context", token=self.token, max_bytes=33554432)["manifest"]
        value = dict(schema_version=1, domain="golem.registered-output-rejection.v1", work_id="example-work",
                     work_spec_digest=self.active["policy_digest"],
                     expected_sequence=self.seq, token=self.token, input_digest=self.active["manifest_digest"],
                     input_generation=self.active["input_generation"], registered_generation=self.generation,
                     source_snapshot=self.source, selection=manifest["selection"], output=self.ref,
                     evidence=[self.evidence], decision="REJECT_REGISTERED_OUTPUT",
                     external_effects="NONE_IDENTIFIED_AFTER_INSPECTION", reason="WRONG_KIND")
        value.update(changes)
        return self.cli("evidence", "put", self.work, self.write("approval.json", value))["digest"]

    def reject(self, ok=True, **changes):
        approval = changes.pop("approval_digest", None)
        if approval is None:
            approval = self.approval()
        fields = dict(token=self.token, input_digest=self.active["manifest_digest"], source_snapshot=self.source,
                      expected_generation=self.generation, output=self.ref, evidence=[self.evidence],
                      approval_digest=approval)
        fields.update(changes)
        return self.request("reject_output", ok=ok, **fields)

    def test_exact_rejection_preserves_prefix_and_is_idempotent(self):
        prefix = self.work_bytes()
        receipt = self.reject()
        self.assertFalse(receipt["acceptance_verified"])
        self.assertIsNone(receipt["state"]["active"])
        rejected = receipt["state"]["rejected_outputs"]
        self.assertNotIn("approval", receipt["record"]["data"])
        self.assertNotIn("evidence", rejected[-1])
        approval = self.cli("--output-store", self.work, "output", "read", rejected[-1]["approval_digest"])
        self.assertEqual(approval["work_spec_digest"], self.active["policy_digest"])
        self.assertEqual(rejected[-1]["output"], self.ref)
        self.assertEqual(rejected[-1]["outcome"], "REJECTED_UNSUCCESSFUL")
        self.assertNotIn(self.ref, receipt["state"]["completed"])
        context = dict(schema_version=1, renderer_version=2, recipe="current-v1", selection_id="selection",
                       target_kind="planning", source_snapshot=self.source, byte_budget=2097152,
                       excerpt_bytes=0, token_budget=0, tokenizer_id="none", agent_note="")
        selected = self.cli("context", "render", self.work, self.write("current-context.json", context))
        self.assertEqual(selected["mandatory_facts"]["history_selection"]["reason"], "REJECTED_OUTPUT_HISTORY")
        for path, raw in prefix.items():
            self.assertEqual((self.work / path).read_bytes(), raw)
        after = self.work_bytes()
        self.assertEqual(self.raw(self.last_request), receipt)
        self.assertEqual(after, self.work_bytes())
        changed = copy.deepcopy(self.last_request)
        changed["output"]["digest"] = "a" * 64
        self.raw(changed, ok=False)
        self.assertEqual(after, self.work_bytes())
        self.assertEqual(self.request("next")["reason"], "CLAIM_REQUIRED")
        self.claim(); self.begin(); self.output(); self.submit()
        self.assertEqual(self.active["kind"], "planning")
        self.assertNotEqual(self.ref, rejected[-1]["output"])
        for expected in ("development-plan", "qa-plan", "qa-result", "completion"):
            self.claim(); self.begin(); self.output(); self.submit()
            self.assertEqual(self.active["kind"], expected)
        contract = self.cli("role", "template", "doc-only")
        digest = self.cli("role", "validate", self.write("role-contract.json", contract))["contract_digest"]
        self.cli("role", "call", self.work, self.write("enroll.json", dict(
            schema_version=1, operation="enroll", selection_id="selection", key="enroll",
            expected_generation=self.generation, contract=contract)), "--approve-contract", digest)
        self.cli("role", "call", self.work, self.write("assess.json", dict(
            schema_version=1, operation="assess", selection_id="selection", key="assess",
            expected_generation=self.generation, review=None)))
        self.cli("completion", "call", self.work, self.write("complete.json", dict(
            schema_version=2, operation="finalize", selection_id="selection", key="done",
            expected_generation=self.generation, issues=[])))
        report = subprocess.run([str(sessions.fixture.CLI), "--output-mode", "full", "completion", "report",
                                 str(self.work), "1"], env=sessions.fixture.ENV, capture_output=True, timeout=90)
        self.assertEqual(report.returncode, 0, report.stderr.decode())
        self.assertEqual(self.request("next")["action"], "DONE")
        for path, raw in prefix.items():
            self.assertEqual((self.work / path).read_bytes(), raw)

    def test_rejection_requires_exact_approval_and_current_fences(self):
        for field, value in (("expected_sequence", self.seq - 1), ("expected_generation", self.generation - 1),
                             ("input_digest", "a" * 64), ("source_snapshot", "a" * 64),
                             ("approval_digest", "a" * 64),
                             ("token", dict(self.token, session_id="other-owner"))):
            approval = self.approval()
            before = self.work_bytes()
            changes = {field: value}
            changes.setdefault("approval_digest", approval)
            self.reject(ok=False, **changes)
            self.assertEqual(before, self.work_bytes())
        approval = self.approval(external_effects="UNKNOWN")
        before = self.work_bytes()
        self.reject(ok=False, approval_digest=approval)
        self.assertEqual(before, self.work_bytes())

    def test_invalid_approval_identities_and_missing_fields_never_commit(self):
        wrong_output = dict(self.ref, digest="b" * 64)
        for changes in (dict(work_id="other-work"), dict(work_spec_digest="a" * 64), dict(token=dict(self.token, epoch=1)),
                        dict(output=wrong_output), dict(input_generation=1),
                        dict(selection=dict(document_id="selection", revision=1, digest="c" * 64)),
                        dict(decision="ADOPT_OUTPUT"), dict(reason="PINNED_INPUT_MISMATCH"),
                        dict(unexpected=True)):
            approval = self.approval(**changes)
            before = self.work_bytes()
            self.reject(ok=False, approval_digest=approval)
            self.assertEqual(before, self.work_bytes())
        approval = self.approval()
        before = self.work_bytes()
        self.reject(ok=False, approval_digest=approval, output=wrong_output)
        self.assertEqual(before, self.work_bytes())

    def test_expired_lease_requires_new_resume_and_new_approval(self):
        approval = self.approval()
        self.now = self.active["expires_ms"]
        before = self.work_bytes()
        self.reject(ok=False, approval_digest=approval)
        self.assertEqual(before, self.work_bytes())
        result = self.request("resume", session_id="new-owner", ttl_ms=10000)
        self.active = result["state"]["active"]
        self.token = {k: self.active[k] for k in ("epoch", "attempt_id", "session_id")}
        before = self.work_bytes()
        self.reject(ok=False, approval_digest=approval)
        self.assertEqual(before, self.work_bytes())
        self.reject()

    def test_known_native_execution_state_blocks_document_only_disposition(self):
        (self.work / "execution-attempts").mkdir()
        approval = self.approval()
        before = self.work_bytes()
        self.reject(ok=False, approval_digest=approval)
        self.assertEqual(before, self.work_bytes())

    def test_real_cli_uses_lawful_resume_before_rejection(self):
        self.actual = True
        resumed = self.request("resume", session_id="real-cli-owner", ttl_ms=60000)
        self.active = resumed["state"]["active"]
        self.token = {k: self.active[k] for k in ("epoch", "attempt_id", "session_id")}
        receipt = self.reject()
        self.assertEqual(receipt["record"]["schema_version"], 4)
        self.assertEqual(receipt["record"]["operation"], "reject_output")
        self.assertFalse(receipt["acceptance_verified"])

    def test_rejected_attempt_cannot_register_legacy_outputs(self):
        old_attempt = self.active["attempt_id"]
        self.reject()
        metadata = self.metadata("planning", parents=[])
        metadata["producer_attempt"] = old_attempt
        before = self.work_bytes()
        self.publish(metadata, ok=False)
        self.assertEqual(before, self.work_bytes())

    def test_recovery_then_real_approved_qa_and_native_completion(self):
        saved = list(sys.argv)
        try:
            sys.argv.insert(1, CC)
            import completion_integration as real
        finally:
            sys.argv[:] = saved
        prefix = self.work_bytes()
        self.reject()
        case = real.Completion()
        case.__dict__.update(self.__dict__)
        case.sessions, case.token = True, None
        case.session("resume", session_id="current-agent", ttl_ms=60000)
        selected = case.cli("workflow", "select", case.work, "scope", 1, "development")
        case.register_selection(p=selected)
        case.managed("planning")
        case.managed("development-plan")
        case.setup_execution_source()
        case.prepare()
        (case.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        case.finish()
        case.begin_claim()
        qa = case.call("run", checkpoint=case.cp["receipt_digest"], attempt_id="recovered-qa")
        self.assertEqual(qa["record"]["status"], "PASS")
        self.assertEqual(qa["record"]["checkpoint"], case.cp["receipt_digest"])
        self.assertEqual(qa["record"]["manifest"]["source_snapshot"], case.source)
        self.assertEqual(qa["record"]["manifest"]["selection"]["revision"], case.docs["selection"]["revision"])
        case.call("verify", receipt=qa["receipt_digest"])
        case.result("qa-result", qa)
        case.managed("completion")
        finalized = case.finalize()
        self.assertEqual(finalized["record"]["record"]["assessment"]["policy"]["predicate"],
                         "golem.completion.development.v1")
        self.assertEqual(case.completion()["action"], "RECOVER_REPORT")
        case.project()
        self.assertEqual(case.completion()["action"], "DONE")
        self.assertTrue(case.next()["acceptance_verified"])
        self.assertEqual((case.repo / "invoked").read_text(), "x")
        self.assertEqual((case.repo / "user.txt").read_text(), "preexisting uncommitted user work\n")
        for name, data in prefix.items():
            self.assertEqual((case.work / name).read_bytes(), data)
        if os.environ.get("GOLEM_REJECTION_EVIDENCE_OUTPUT"):
            sys.path.insert(0, str(sessions.fixture.SOURCE / "tools"))
            import execution_record as records
            output = records.private_directory(os.environ["GOLEM_REJECTION_EVIDENCE_OUTPUT"])
            records.save(output / "checkpoint.json", records.encoded(case.cp))
            records.save(output / "qa-receipt.json", records.encoded(qa))
            records.save(output / "completion-receipt.json", records.encoded(finalized))
            records.save(output / "original-prefix.json", records.encoded({
                name: hashlib.sha256(data).hexdigest() for name, data in prefix.items()}))
            shutil.copytree(case.work, output / "work")
            shutil.copytree(case.repo, output / "project")
            records.save(output / "e2e.json", records.encoded(dict(
                schema="golem.rejection-e2e.v1", origin="SYNTHETIC_OWNED_FIXTURE",
                work_restoration_supported=False, original_contract_roots_are_temporary=True,
                original_prefix_preserved=True, original_prefix_files=len(prefix),
                qa_receipt_digest=qa["receipt_digest"], checkpoint_digest=case.cp["receipt_digest"],
                source_scope_snapshot=case.source, native_completion="DONE", actual_c_qa=True,
                binary_sha256=hashlib.sha256(sessions.fixture.CLI.read_bytes()).hexdigest(),
                test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())))

    def test_rejected_revision_and_its_explicit_descendant_are_stale(self):
        metadata = self.metadata("development-plan", "dependent-plan", parents=[self.ref])
        published = self.publish(metadata)
        before = self.work_bytes()
        self.reject()
        for name, raw in before.items():
            self.assertEqual((self.work / name).read_bytes(), raw)
        for document, revision in ((self.ref["document_id"], self.ref["revision"]),
                                   ("dependent-plan", published["revision"])):
            trace = self.cli("workflow", "trace", self.work, document, revision)
            self.assertEqual(trace["state"], "STALE")

    def test_compatible_output_still_requires_normal_adoption(self):
        case = sessions.Session()
        case.setUp()
        try:
            case.setup_session(); case.claim(); case.begin(); case.output()
            resumed = case.request("resume", session_id="agent-a", ttl_ms=10000)
            case.active = resumed["state"]["active"]
            case.token = {k: case.active[k] for k in ("epoch", "attempt_id", "session_id")}
            approval = Rejection.approval(case, reason="PINNED_INPUT_MISMATCH")
            before = case.work_bytes()
            Rejection.reject(case, ok=False, approval_digest=approval)
            self.assertEqual(before, case.work_bytes())
            adopted = case.request("reconcile", token=case.token, input_digest=case.active["manifest_digest"],
                                   source_snapshot=case.source, output=case.ref, evidence=[case.evidence],
                                   resolution="ADOPT_OUTPUT")
            self.assertIn(case.ref, adopted["state"]["completed"])
        finally:
            case.tearDown()

    def test_new_registration_checks_active_kind_and_pinned_manifest(self):
        case = sessions.Session()
        case.setUp()
        try:
            case.setup_session()
            case.claim(); case.begin(); case.output(); case.submit()
            case.claim(); case.begin()
            self.assertEqual(case.active["kind"], "development-plan")
            for kind, budget, version in (("planning", 1048576, 4), ("planning", 1048576, 1),
                                           ("development-plan", 2097152, 4)):
                inputs = case.cli("workflow", "inputs", case.work, "selection", kind, case.source, budget)
                metadata = case.metadata(kind, parents=inputs["direct"], version=version)
                metadata["producer_attempt"] = case.active["attempt_id"]
                if version == 4:
                    metadata["input_manifest"] = inputs
                before = case.work_bytes()
                case.publish(metadata, ok=False)
                self.assertEqual(before, case.work_bytes())
            case.output(); case.submit()
        finally:
            case.tearDown()

    def crash_rejection(self, mode):
        request = dict(schema_version=1, operation="reject_output", work_id="example-work", key="crash-rejection",
                       expected_sequence=self.seq, token=self.token, input_digest=self.active["manifest_digest"],
                       source_snapshot=self.source, expected_generation=self.generation, output=self.ref,
                       evidence=[self.evidence], approval_digest=self.approval())
        path = self.write("crash-rejection.json", request)
        before = self.work_bytes()
        result = subprocess.run([str(sessions.CLIENT), str(self.work), str(path), str(self.now), str(self.boot), mode],
                                env=sessions.fixture.ENV, capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 86 if mode == "crash_before_commit" else 87, result.stderr.decode())
        for name, data in before.items():
            self.assertEqual((self.work / name).read_bytes(), data)
        status = self.request("status")
        if mode == "crash_before_commit":
            self.assertEqual(status["sequence"], self.seq)
            self.assertEqual(status["state"]["active"]["state"], "RECOVERY_REQUIRED")
        else:
            self.assertEqual(status["sequence"], self.seq + 1)
            self.assertIsNone(status["state"]["active"])
        receipt = self.raw(request)
        self.assertEqual(receipt["sequence"], self.seq + 1)
        after = self.work_bytes()
        self.assertEqual(self.raw(request), receipt)
        self.assertEqual(after, self.work_bytes())

    def test_process_exit_before_commit_preserves_retry(self):
        self.crash_rejection("crash_before_commit")

    def test_process_exit_after_commit_replays_exact_receipt(self):
        self.crash_rejection("crash_after_commit")

    def temporal_publication(self, mode, reason):
        request = dict(schema_version=1, operation="reject_output", work_id="example-work", key="late-publication",
                       expected_sequence=self.seq, token=self.token, input_digest=self.active["manifest_digest"],
                       source_snapshot=self.source, expected_generation=self.generation, output=self.ref,
                       evidence=[self.evidence], approval_digest=self.approval())
        before = self.work_bytes()
        events = sorted((self.work / "agent-events").glob("*.evt"))
        result = subprocess.run([str(sessions.CLIENT), str(self.work), str(self.write("late.json", request)),
                                 str(self.now), str(self.boot), mode],
                                env=sessions.fixture.ENV, capture_output=True, timeout=90)
        self.assertNotEqual(result.returncode, 0, result.stdout.decode())
        self.assertEqual(events, sorted((self.work / "agent-events").glob("*.evt")))
        for name, data in before.items():
            self.assertEqual((self.work / name).read_bytes(), data)
        if mode == "expire_before_publication":
            self.now += 10000
        elif mode == "rollback_before_publication":
            self.now -= 1
        else:
            self.boot += 1
        status = self.request("status")
        self.assertEqual(status["sequence"], self.seq)
        self.assertEqual(status["state"]["active"]["state"], "RECOVERY_REQUIRED")
        self.assertEqual(status["resume_preflight"]["reason"], reason)

    def test_expiry_after_commit_clock_blocks_frame_publication(self):
        self.temporal_publication("expire_before_publication", "LEASE_EXPIRED")

    def test_rollback_after_commit_clock_blocks_frame_publication(self):
        self.temporal_publication("rollback_before_publication", "CLOCK_REGRESSED")

    def test_boot_change_after_commit_clock_blocks_frame_publication(self):
        self.temporal_publication("boot_before_publication", "BOOT_CHANGED")


if __name__ == "__main__":
    if CAPTURE:
        capture()
    else:
        unittest.main()
