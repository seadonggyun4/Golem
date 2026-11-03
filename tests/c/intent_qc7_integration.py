"""QC7 disposable native integration. Authored under HOLD; NOT_RUN.

Explicit CTest opt-in only. Uses actual native parser, reviews, enrollment,
execution, QA acceptance and completion. Synthetic attestations are NOT human
identity proof. Never accepts a live Work/registry path as an argument.
"""
import copy
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import tempfile
import selectors
from execution_integration import Execution
from discovery_integration import SOURCE, ENV

DRIVER = Path(sys.argv.pop(1)).resolve()
ZERO = "0" * 64
STAGES = ("REQUIREMENTS", "DESIGN", "TASK_DECOMPOSITION", "IMPLEMENTATION",
          "TEST_DESIGN", "INTEGRATION", "FINAL_VALIDATION")


def wire(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


class IntentFlow(Execution):
    """Only the explicitly named test methods below are registered."""
    def setUp(self):
        parent = os.environ.get("GOLEM_QC7_OUTPUT")
        if parent:
            self.root = Path(tempfile.mkdtemp(prefix="qc7-", dir=parent)).resolve()
        else:
            self.root = Path(tempfile.mkdtemp(prefix="golem-qc7-")).resolve()
        print(f"QC7 fixture root (retained on failure): {self.root}", file=sys.stderr)
        self.a = json.loads((SOURCE / "samples/discovery/assessment.json").read_text())
        self.logs = Path(os.environ.get("GOLEM_QC7_LOGS", str(self.root))).resolve()
        self.work_id = "work"
        self.authority = self.root / "authority"
        self.authority.mkdir(mode=0o700)
        self.owner_lock = self.root / "d01.lock"
        self.owner_lock.touch(mode=0o600)
        self.epoch = 0
        self.evidence = []
        self.serial = 0
        self.base_op, self.base_req = sha("baseline-op"), sha("baseline-request")
        seed = json.loads((SOURCE / "tests/fixtures/intent/qa-resolved-local.json").read_text())
        self.seed = seed
        self.base = {k: seed[k] for k in ("source", "text", "definition", "baseline", "policy", "policy_pin", "registration")}
        self.baseline_id = json.loads(seed["bundle"])["baseline_digest"]
        self.base.update(authority=str(self.authority), baseline_operation=self.base_op,
                         baseline_request=self.base_req)
        self.definitions = self.native(dict(op="baseline"))["definitions"]
        # Synthetic source/owner evidence remains in a private disposable root.
        self.review_stage(0, sha("initial-requirements"))
        initial = self.last_stage
        self.statement("SOURCE_ADOPTION", dict(disposition="ADOPT_EXACT_BASELINE",
                                               all_source_decisions_reviewed=True), owner=True)
        self.activation = self.statement("ACTIVATION", dict(review_digest=initial,
                                          policy_digest=self.base["policy_pin"]), owner=True)
        self.review("activate", dict(decision_digest=self.activation, review_digest=initial,
                                     policy_digest=self.base["policy_pin"]))

    def tearDown(self):
        # Fault/unknown artifacts must survive even an assertion failure.
        print(f"QC7 retained fixture: {self.root}", file=sys.stderr)

    def cli(self, *args, **kw):
        if args[:2] == ("work", "start"):
            path = Path(args[3])
            spec = json.loads(path.read_text())
            spec.update(schema_version=3, runtime_profile=json.loads((SOURCE / "samples/runtime-profile.json").read_text()), support_profile="LOCAL_NO_MERGE", intent_binding={
                "registration_ref": self.base["registration"], "baseline_ref": self.baseline_id,
                "policy_ref": self.base["policy_pin"]})
            path.write_text(wire(spec))  # before native create; never migrate/rewrite a Work
        return super().cli(*args, **kw)

    def native(self, packet, fault="", ok=True):
        self.serial += 1
        payload = dict(self.base, **packet)
        if hasattr(self, "work"):
            payload["work"] = str(self.work)
        # Same order as D01 host: fixture common-dir lock -> native Work -> authority.
        with self.owner_lock.open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            result = subprocess.run([str(DRIVER), fault], input=wire(payload).encode(),
                                    capture_output=True, env=ENV, timeout=40)
        log = self.logs / f"native-{self.serial:04d}"
        log.with_suffix(".request.json").write_text(wire(payload))
        log.with_suffix(".stdout").write_bytes(result.stdout)
        log.with_suffix(".stderr").write_bytes(result.stderr)
        log.with_suffix(".meta.json").write_text(wire(dict(returncode=result.returncode, fault=fault)))
        self.last_native_log = log
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        return result

    def context_checkpoint(self, name):
        # Capture only completed calls, never repeat them for evidence collection.
        golden = json.loads((SOURCE / "tests/fixtures/intent/context-golden.json").read_text())
        if name not in golden["checkpoints"]:
            raise ValueError("unknown context checkpoint")
        log = self.last_native_log
        pins = {suffix: hashlib.sha256(log.with_suffix("." + suffix).read_bytes()).hexdigest()
                for suffix in ("request.json", "stdout", "stderr", "meta.json")}
        sources = {path: hashlib.sha256((SOURCE / path).read_bytes()).hexdigest()
                   for path in golden["sources"]}
        with (self.logs / ("context-" + name + ".json")).open("x") as stream:
            json.dump(dict(checkpoint=name, stem=log.name, sha256=pins,
                           source_sha256=sources), stream, indent=2)

    def scenario_record(self, case, before, after, codes):
        # Existing read-only snapshots and actual exit codes, not a retry.
        files = {}
        for path in sorted(self.logs.glob("native-*.*")):
            files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with (self.logs / ("scenario-" + case + ".json")).open("x") as stream:
            json.dump(dict(case=case, before=before, after=after,
                           returncodes=codes, files=files, retries=0), stream, indent=2)

    def digest(self, obj, kind="domain"):
        return self.native(dict(op="digest", kind=kind, bytes=wire(obj)))["digest"]

    def snapshot(self):
        return self.native(dict(op="snapshot"))

    def statement(self, purpose, body, owner=False, domain=False):
        who = "owner" if owner else "reviewer"
        e = dict(schema="golem.intent.review-host-evidence.v1", purpose=purpose,
                 project_id="demo", work_id="work", baseline_digest=self.baseline_id,
                 policy_digest=self.base["policy_pin"], policy_epoch=1,
                 issuer=who, issuer_session=who + "-session",
                 producer="" if owner else "producer",
                 producer_session="" if owner else "producer-session", body=body)
        raw = wire(e)
        row = dict(sha256=sha(raw), bytes=raw)
        if row not in self.evidence:
            self.evidence.append(row)
        return self.digest(e) if domain else sha(raw)

    def host(self, control, operation, state=None):
        if state is None:
            raise AssertionError("native CAS snapshot is required")
        raw = wire(control)
        bundle = dict(schema="golem.intent.review-host-bundle.v1", project_id="demo", work_id="work",
                      baseline_digest=self.baseline_id, policy_digest=self.base["policy_pin"],
                      registration_digest=self.base["registration"], control_digest=sha(raw),
                      owner="owner", owner_session="owner-session", not_before=100, expires_at=200,
                      evidence=self.evidence, publication_operation=operation,
                      expected_sequence=state["authority_sequence"], expected_head=state["authority_head"])
        return dict(control=raw, bundle=wire(bundle), bundle_pin=sha(wire(bundle)))

    def review(self, operation, body):
        # The adapter reads actual authority CAS; derive its initial head from
        # native snapshot rather than guessing hashes. review-state is read-only.
        state = self.native(dict(op="review-state"))
        control = dict(schema="golem.intent.review-control.v1", project_id="demo", work_id="work",
                       baseline_digest=self.baseline_id, operation=operation,
                       expected_epoch=self.epoch, body=body)
        op = sha(f"review-{self.epoch}-{operation}")
        self.native(dict(op="review", operation=op, **self.host(control, op, state)))
        self.epoch += 1

    def review_stage(self, index, input_digest):
        body = dict(stage=STAGES[index], input_manifest=input_digest,
                    definitions_digest=self.definitions, verdict="PASS", original_source_reviewed=True)
        evidence = self.statement("STAGE", body)
        self.last_stage = evidence
        self.review("review", dict(stage=STAGES[index], producer="producer", reviewer="reviewer",
                                   input_manifest=input_digest, definitions_digest=self.definitions,
                                   verdict="PASS", evidence_digest=evidence))

    def resolve_question(self):
        q = sha("qc7-question")
        self.review("question", dict(question_digest=q, evidence_digest=sha("question-evidence")))
        answer = self.statement("ANSWER", dict(question_digest=q, disposition="SAME_BASELINE"), owner=True)
        self.review("answer", dict(question_digest=q, evidence_digest=answer))
        resolution = self.statement("RESOLUTION", dict(close=[q], carry=[], disposition="SAME_BASELINE"))
        self.review("resolve", dict(close=[q], carry=[], evidence_digest=resolution))
        self.review_stage(0, sha("resolved-requirements"))

    def enroll(self):
        state = self.snapshot()
        e = dict(schema="golem.intent.work-enrollment.v1", project_id="demo", work_id="work",
                 created_by_assertion="qc7-fixture", baseline_digest=self.baseline_id,
                 body=dict(baseline_ref=self.baseline_id, work_spec_digest=state["work_spec"],
                           requirement_mapping=[dict(requirement_ref=json.loads(self.base["baseline"])["body"]["requirement_refs"][0], acceptance_id="REQ-1")],
                           support_profile="LOCAL_NO_MERGE", policy_ref=self.base["policy_pin"],
                           activation_decision_ref=self.activation, predecessor_ref=None))
        op = sha("enroll")
        control = dict(project_id="demo", work_id="work", baseline_digest=self.baseline_id)
        packet = dict(enrollment=wire(e), operation=op, authority_sequence=state["authority_sequence"],
                      authority_head=state["authority_head"], **self.host(control, op, state))
        approval = self.native(dict(packet, op="enrollment-digest"))["digest"]
        self.native(dict(packet, op="enroll", approval=approval))

    def paths(self):
        # Retain concrete local targets and legitimate four-route N/A decisions.
        self.evidence += json.loads(self.seed["bundle"])["evidence"]
        obligations = json.loads(self.seed["obligations"])
        one = obligations["body"]["obligations"][0]
        two = copy.deepcopy(one)
        two["id"] = "ob2"
        obligations["body"]["obligations"].append(two)
        mapping = json.loads(self.seed["mapping"])
        mapping["body"].update(obligations_ref=self.digest(obligations),
                              execution_contract_digest=self.digest(self.contract, "contract"),
                              mappings=[dict(obligation_id="ob1", gate_id="regression", gate_version=1, case_id="fix"),
                                        dict(obligation_id="ob2", gate_id="regression", gate_version=1, case_id="regression")])
        self.path_material = dict(baseline=self.base["baseline"],
                                 sources=[dict(control=self.base["source"], text=self.base["text"])],
                                 definitions=[self.base["definition"]], applicability=self.seed["applicability"],
                                 obligations=wire(obligations), mapping=wire(mapping), execution_contract=wire(self.contract),
                                 objects=self.seed["objects"])

    def scope(self, request, channel, boundary, fresh_reviews=True):
        state = self.snapshot()
        dummy = dict(project_id="demo", work_id="work", baseline_digest=self.baseline_id)
        kind = "development-result" if boundary == "DEVELOPMENT" else "qa-result"
        native = self.native(dict(op="native-inputs", contract=wire(self.contract), input_kind=kind,
                                  **self.host(dummy, sha("inspect-inputs"), state)))
        material = dict(schema="golem.intent.product-material.v1", project_id="demo", work_id="work",
                        baseline_digest=self.baseline_id, body=dict(self.path_material, native_inputs=native))
        material_sha = sha(wire(material))
        if fresh_reviews:
            for index in range(3 if boundary == "DEVELOPMENT" else 5):
                self.review_stage(index, material_sha)
            if channel in ("QA", "COMPLETION"):
                final = self.digest(dict(domain="golem.intent.qa-review-input.v1", material_sha256=material_sha,
                                         execution_receipt_ref=self.qa["receipt_digest"]), "json")
                self.review_stage(5, final)
                self.review_stage(6, final)
        state = self.snapshot()
        control = dict(schema="golem.intent.product-access.v1", project_id="demo", work_id="work",
                       baseline_digest=self.baseline_id, body=dict(material_sha256=material_sha,
                       work_spec=state["work_spec"], work_sequence=state["work_sequence"], work_head=state["work_head"],
                       review_epoch=self.epoch, baseline_operation=self.base_op, baseline_request=self.base_req,
                       boundary=boundary, channel=channel, request_digest=sha(wire(request)), input_kind=kind))
        return dict(material=wire(material), request=wire(request), **self.host(control, sha("product"), state))

    def call(self, op, ok=True, approval=True, **fields):
        request = dict(schema_version=1, operation=op, **fields)
        packet = self.scope(request, "EXECUTION", "QA_DISPATCH" if op == "run" else "DEVELOPMENT")
        return self.native(dict(packet, op="execution", approval=self.approval), ok=ok)

    def ready(self):
        self.resolve_question()
        self.setup_execution()
        self.enroll()
        self.paths()
        self.prepare()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a+b; }\n")
        self.finish()
        self.qa = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="qc7-only-qa")
        self.assertEqual(self.qa["record"]["status"], "PASS")
        self.result("qa-result", self.qa)
        self.managed("completion")

    def acceptance(self):
        # Review changes authority head, so finalize exact request AFTER reviews.
        provisional = dict(schema="golem.intent.qa-request.v1", operation="accept",
                           execution_receipt_ref=self.qa["receipt_digest"], semantic_reviews=[],
                           authority_sequence=0, authority_head=ZERO,
                           prepare_operation=sha("qa-prepare"), accept_operation=sha("qa-accept"))
        self.scope(provisional, "QA", "QA_ACCEPTANCE")
        state = self.snapshot()
        provisional.update(authority_sequence=state["authority_sequence"], authority_head=state["authority_head"])
        self.accept_request = provisional
        return dict(self.scope(provisional, "QA", "QA_ACCEPTANCE", False), op="accept")

    def inventory(self):
        return {str(p.relative_to(self.root)): (p.stat().st_mode, hashlib.sha256(p.read_bytes()).hexdigest())
                for root in (self.work, self.authority) for p in root.rglob("*") if p.is_file()}

    def current(self):
        packet = self.scope(self.accept_request, "QA", "QA_ACCEPTANCE", False)
        before = self.inventory()
        result = self.native(dict(packet, op="current"))
        self.assertEqual(before, self.inventory())
        return result

    def test_full_progression(self):
        self.ready()
        result = self.native(self.acceptance())
        self.assertEqual(result["body"]["intent_qa_status"], "ACCEPTED")
        self.context_checkpoint("accept")
        self.assertEqual(self.current()["body"]["intent_qa_status"], "ACCEPTED")
        self.context_checkpoint("current")
        state = self.snapshot()
        request = dict(schema_version=3, operation="finalize", selection_id="selection", key="qc7-finish",
                       expected_generation=self.generation, issues=[],
                       predicate="golem.completion.intent.local-no-merge.v1", intent_qa_observation=state["observation"])
        # Same material/review epoch: finalization must not invalidate accepted QA.
        finalize = dict(self.scope(request, "COMPLETION", "COMPLETION", False), op="completion")
        if os.environ.get("GOLEM_QC7_CASE") == "completion-response-lost":
            lost = self.native(finalize, fault="response-lost", ok=False)
            self.assertEqual(lost.returncode, 77)
        else:
            self.native(finalize)
        self.raw("completion", "report", self.work, 1)
        resume = dict(schema_version=3, operation="resume", selection_id="selection")
        packet = dict(self.scope(resume, "COMPLETION", "COMPLETION", False), op="completion")
        before = self.inventory()
        result = self.native(packet)  # separate process reopens both journals
        self.assertEqual(result["action"], "DONE")
        self.assertTrue(result["acceptance_verified"])
        self.context_checkpoint("done")
        self.assertEqual(before, self.inventory())
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        self.assertEqual((self.repo / "user.txt").read_text(), "preexisting uncommitted user work\n")

        # A real source change must invalidate current acceptance without QA rerun.
        before = self.inventory()
        (self.repo / "logic.c").write_text("int add(int a,int b) { return a-b; }\n")
        changed = self.current()
        self.assertNotEqual(changed["body"]["intent_qa_status"], "ACCEPTED")
        self.assertEqual(changed["body"]["execution_status"], "PASS")
        self.context_checkpoint("stale")
        self.assertEqual(before, self.inventory())
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_crash_boundaries(self):
        self.ready()
        packet = self.acceptance()
        before = self.snapshot()
        old = self.inventory()
        fault = os.environ["GOLEM_QC7_CASE"]
        result = self.native(packet, fault=fault, ok=False)
        expected_exit = 1 if fault.endswith("-io") else 77
        self.assertEqual(result.returncode, expected_exit)
        after = self.snapshot()
        # Existing immutable bytes are never removed or rewritten.
        now = self.inventory()
        for name, value in old.items():
            self.assertEqual(now.get(name), value, name)
        prepared = fault not in ("before-prepared", "prepared-io", "prepared-pending-crash")
        observation = fault in ("after-observation", "before-accepted", "accepted-io", "accepted-pending-crash", "after-accepted", "response-lost")
        accepted = fault in ("after-accepted", "response-lost")
        self.assertEqual(after["authority_sequence"] - before["authority_sequence"], int(prepared) + int(accepted))
        self.assertEqual(after["pending"], fault.endswith("pending-crash"))
        self.assertEqual(after["observations"] - before["observations"], int(observation))
        self.assertEqual(after["work_sequence"] - before["work_sequence"], int(observation))
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        if observation and after["pending"]:
            probe = self.scope(self.accept_request, "QA", "QA_ACCEPTANCE", False)
            denied = self.native(dict(probe, op="current"), ok=False)
            self.assertIn(b"invalid state transition", denied.stderr)
        elif observation:
            status = self.current()["body"]["intent_qa_status"]
            self.assertEqual(status == "ACCEPTED", accepted)
        self.scenario_record(fault, before, after, [result.returncode])
        # Never invoke accept again, including after lost response. No repair.

    def test_real_enospc(self):
        # Only the bounded-image supervisor may choose this fixture. Never fill
        # the workspace/temp host volume, even when environment is incomplete.
        device = int(os.environ["GOLEM_QC7_VOLUME_DEVICE"])
        self.assertEqual(self.root.stat().st_dev, device)
        self.assertNotEqual(self.logs.stat().st_dev, device)
        self.ready()
        packet = self.acceptance()
        completion = os.environ["GOLEM_QC7_CASE"] == "completion"
        if completion:
            self.native(packet)
            state = self.snapshot()
            request = dict(schema_version=3, operation="finalize", selection_id="selection", key="enospc-finish",
                           expected_generation=self.generation, issues=[],
                           predicate="golem.completion.intent.local-no-merge.v1", intent_qa_observation=state["observation"])
            packet = dict(self.scope(request, "COMPLETION", "COMPLETION", False), op="completion")
        before = self.snapshot()
        old = self.inventory()
        filler = self.root / "bounded-volume-filler"
        observed = []
        written = 0
        fd = os.open(filler, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            for block in (65536, 4096, 512):
                while written < 64 * 1024 * 1024:
                    try:
                        amount = os.write(fd, b"x" * block)
                        self.assertGreater(amount, 0)
                        written += amount
                    except OSError as exc:
                        self.assertEqual(exc.errno, errno.ENOSPC)
                        observed.append(dict(operation="write", errno=exc.errno, bytes_written=written, block=block))
                        break
            try:
                os.fsync(fd)
            except OSError as exc:
                self.assertEqual(exc.errno, errno.ENOSPC)
                observed.append(dict(operation="fsync", errno=exc.errno))
        finally:
            os.close(fd)
        self.assertTrue(observed, "bounded filesystem did not produce ENOSPC")
        (self.logs / "kernel-enospc.json").write_text(wire(dict(device=device, observations=observed)))
        result = self.native(packet, ok=False)  # no fault argument/syscall substitution
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"qc7 native status=", result.stderr)
        after = self.snapshot()  # read only; no accept/finalize/QA retry or repair
        self.assertEqual(after["observations"], before["observations"])
        self.assertEqual(after["completions"], before["completions"])
        self.assertEqual(after["work_sequence"], before["work_sequence"])
        now = self.inventory()
        for name, value in old.items():
            self.assertEqual(now.get(name), value, name)
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        self.scenario_record("enospc-completion" if completion else "enospc-qa", before, after, [result.returncode])
        # Keep filler, partial publication, image and stderr for later inspection.

    def test_completion_crash(self):
        self.ready()
        self.native(self.acceptance())
        state = self.snapshot()
        request = dict(schema_version=3, operation="finalize", selection_id="selection", key="qc7-finish",
                       expected_generation=self.generation, issues=[],
                       predicate="golem.completion.intent.local-no-merge.v1", intent_qa_observation=state["observation"])
        packet = dict(self.scope(request, "COMPLETION", "COMPLETION", False), op="completion")
        old = self.inventory()
        fault = os.environ["GOLEM_QC7_CASE"]
        result = self.native(packet, fault=fault, ok=False)
        self.assertEqual(result.returncode, 1 if fault.endswith("-io") else 77)
        after = self.snapshot()
        committed = fault == "after-completion-event"
        self.assertEqual(after["work_sequence"] - state["work_sequence"], int(committed))
        self.assertEqual(after["completions"] - state["completions"], int(committed))
        self.assertEqual(after["authority_head"], state["authority_head"])
        now = self.inventory()
        for name, value in old.items():
            self.assertEqual(now.get(name), value, name)
        self.assertEqual(self.current()["body"]["intent_qa_status"], "ACCEPTED")
        resume = dict(schema_version=3, operation="resume", selection_id="selection")
        read = dict(self.scope(resume, "COMPLETION", "COMPLETION", False), op="completion")
        before_read = self.inventory()
        outcome = self.native(read)
        self.assertFalse(outcome["acceptance_verified"])
        self.assertEqual(outcome["action"], "RECOVER_REPORT" if committed else "VERIFY_COMPLETION")
        self.assertEqual(before_read, self.inventory())
        self.assertEqual((self.repo / "invoked").read_text(), "x")
        self.scenario_record(fault, state, after, [result.returncode])
        # No finalize retry or report repair: uncertain artifacts stay retained.

    def test_lock_exit_and_isolation(self):
        self.ready()
        before_state = self.snapshot()
        before = self.inventory()
        read_fd, write_fd = os.pipe()
        authority_lock = os.environ.get("GOLEM_QC7_CASE") == "authority-exit"
        packet = dict(self.base, op="hold-authority" if authority_lock else "hold", work=str(self.work), release_fd=read_fd)
        with self.owner_lock.open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            holder = subprocess.Popen([str(DRIVER), ""], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      env=ENV, pass_fds=(read_fd,))
            os.close(read_fd)
            try:
                holder.stdin.write(wire(packet).encode())
                holder.stdin.close()
                holder.stdin = None
                with selectors.DefaultSelector() as selector:
                    selector.register(holder.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(10), "native Work lock acquisition timed out")
                self.assertEqual(holder.stdout.readline(), b"READY\n")
                # The competing reader requests the native exclusive Work lock;
                # it must fail boundedly, not execute or wait indefinitely.
                blocked = self.native(dict(op="snapshot"), ok=False)
                self.assertIn(b"qc7 native status=", blocked.stderr)
                with self.owner_lock.open("rb") as writer:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
                other = self.root / "unrelated-work"
                self.cli("work", "start", other, self.root / "work-spec.json")
                original = self.work
                try:
                    self.work = other
                    if authority_lock:
                        self.native(dict(op="snapshot"), ok=False)
                    else:
                        self.assertEqual(self.snapshot()["observations"], 0)
                finally:
                    self.work = original
                holder.terminate()  # read-only holder; never an acceptance request
                holder.wait(timeout=10)
            finally:
                os.close(write_fd)
                if holder.poll() is None:
                    holder.kill()
                    holder.wait()
                holder.communicate(timeout=5)
        self.assertEqual(before, self.inventory())
        after_state = self.snapshot()  # native locks released on holder process exit
        self.scenario_record("authority-exit" if authority_lock else "lock-exit", before_state, after_state, [blocked.returncode])
        with self.owner_lock.open("rb") as writer:
            fcntl.flock(writer, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertEqual((self.repo / "invoked").read_text(), "x")

    def test_competing_acceptance(self):
        self.ready()
        packet = self.acceptance()
        payload = wire(dict(self.base, **packet, work=str(self.work))).encode()
        before = self.snapshot()
        # Parent holds D01 shared lock for both children; native Work lock and
        # exact old CAS decide the winner. No sleep-based ordering assumptions.
        with self.owner_lock.open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_SH)
            children = [subprocess.Popen([str(DRIVER), ""], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV) for _ in range(2)]
            for child in children:
                child.stdin.write(payload)
                child.stdin.close()
                child.stdin = None
            try:
                outputs = [child.communicate(timeout=40) for child in children]
            finally:
                for child in children:
                    if child.poll() is None:
                        child.kill()
                        child.wait()
        self.assertEqual(sorted(child.returncode for child in children), [0, 1], outputs)
        for index, (stdout, stderr) in enumerate(outputs):
            (self.root / f"contender-{index}.stdout").write_bytes(stdout)
            (self.root / f"contender-{index}.stderr").write_bytes(stderr)
        after = self.snapshot()
        self.assertEqual(after["authority_sequence"] - before["authority_sequence"], 2)
        self.assertEqual(after["observations"] - before["observations"], 1)
        self.scenario_record("concurrent", before, after, [child.returncode for child in children])
        self.assertEqual(self.current()["body"]["intent_qa_status"], "ACCEPTED")
        self.assertEqual((self.repo / "invoked").read_text(), "x")


if __name__ == "__main__":
    # Explicit list prevents inherited legacy tests from masquerading as v3 coverage.
    name = os.environ.get("GOLEM_QC7_TEST", "test_full_progression")
    if name not in ("test_full_progression", "test_crash_boundaries", "test_competing_acceptance", "test_lock_exit_and_isolation", "test_completion_crash", "test_real_enospc"):
        raise SystemExit("unknown QC7 scenario")
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([IntentFlow(name)]))
    raise SystemExit(not result.wasSuccessful())
