"""29A real CLI and Work replay; synthetic private temporary data only."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = str(Path(sys.argv.pop(1)).resolve())
SOURCE = Path(sys.argv.pop(1)).resolve()
TMP = Path(sys.argv.pop(1)).resolve()


class Research(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TMP, prefix="research-")
        self.root = Path(self.temp.name).resolve()
        self.work = self.root / "work"
        self.spec = json.loads((SOURCE / "samples/documents/work.json").read_text())
        self.case = json.loads((SOURCE / "samples/research/case.json").read_text())
        self.start()

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, ok=True, raw=False):
        p = subprocess.run([CLI, *map(str, args)], capture_output=True, timeout=30)
        if not ok:
            self.assertNotEqual(p.returncode, 0, p.stdout)
            return p
        self.assertEqual(p.returncode, 0, p.stderr.decode())
        return p.stdout if raw else json.loads(p.stdout)

    def file(self, value, name="input.json"):
        p = self.root / name
        p.write_text(json.dumps(value))
        return p

    def start(self):
        self.run_cli("work", "start", self.work, self.file(self.spec))

    def call(self, op, record, key, ok=True):
        return self.run_cli("research", "call", self.work,
                            self.file(dict(schema_version=1, operation=op, key=key, record=record)), ok=ok)

    def create(self):
        return self.run_cli("research", "case", "create", self.work, self.file(self.case), "case-key")

    def attempt(self, case, name="a1", previous=""):
        return dict(schema_version=1, work_id=self.spec["work_id"], case_id=self.case["case_id"],
                    attempt_id=name, case_digest=case["record_digest"], previous_attempt_digest=previous,
                    started_at=1000, actor_kind="CURRENT_AGENT", hypothesis="Parser handling explains the failure.",
                    intervention="Run the bounded parser regression.",
                    input_refs=[dict(role="CONTEXT", digest=case["record_digest"])])

    def result(self, plan, plan_digest=""):
        return dict(plan, ended_at=1100, observations=[dict(digest=plan["case_digest"],
                    summary="Synthetic context observation only.", counts=[dict(name="observed", value=1)])],
                    classification="INSUFFICIENT_EVIDENCE", next_action="BLOCKED",
                    decision_rule="rule-v1", confidence="LOW", plan_digest=plan_digest)

    def count(self):
        return len(list((self.work / "events").glob("*.evt")))

    def cas_path(self, digest):
        matches = [p for p in self.work.rglob("*") if p.is_file() and p.name in (digest, digest[2:])]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_plan_record_replay_and_same_receipt(self):
        case = self.create()
        plan = self.attempt(case)
        p = self.run_cli("research", "attempt", "plan", self.work, self.file(plan), "plan-key")
        result = self.result(plan, p["record_digest"])
        r = self.run_cli("research", "attempt", "record", self.work, self.file(result), "result-key")
        self.assertEqual(r["status"], "RECORDED")
        self.assertFalse(r["adjudicated"])
        self.assertFalse(r["execution_authorized"])
        self.assertEqual(self.count(), 4)
        for seq, receipt in enumerate((case, p, r), 1):
            self.assertEqual(receipt, self.run_cli("research", "inspect", self.work, seq))
        self.assertEqual(case, self.create())
        self.assertEqual(r, self.call("attempt-record", dict(reversed(list(result.items()))), "result-key"))
        md = self.run_cli("research", "report", self.work, 3, raw=True)
        self.assertIn(b"earlier recorded plan", md)
        self.assertIn(b"hypothesis", md)
        self.assertEqual(md, self.run_cli("research", "report", self.work, 3, raw=True))
        self.assertEqual(self.count(), 4)
        self.assertEqual(self.run_cli("research", "status", self.work)["count"], 3)

    def test_retrospective_and_chain(self):
        case = self.create()
        a = self.result(self.attempt(case))
        r = self.call("attempt-record", a, "a1")
        self.assertIn(b"retrospective", self.run_cli("research", "report", self.work, 2, raw=True))
        second = self.result(self.attempt(case, "a2"))
        self.call("attempt-record", second, "a2", ok=False)
        second["previous_attempt_digest"] = r["record_digest"]
        self.call("attempt-record", second, "a2")
        self.assertEqual(r, self.call("attempt-record", a, "a1"))
        self.assertEqual(self.count(), 4)

    def test_identity_and_plan_mismatch(self):
        case = self.create()
        changed = dict(self.case, project_id="other")
        self.call("case-create", changed, "case-key", ok=False)
        self.call("case-create", self.case, "new-key", ok=False)
        plan = self.attempt(case)
        p = self.call("attempt-plan", plan, "plan")
        self.call("attempt-plan", plan, "duplicate-plan", ok=False)
        result = self.result(plan, p["record_digest"])
        for changes in ({"hypothesis": "A rewritten hypothesis"}, {"plan_digest": ""},
                        {"case_digest": "0" * 64}, {"work_id": "other"}, {"case_id": "missing"}):
            self.call("attempt-record", dict(result, **changes), "bad", ok=False)
        self.call("attempt-record", result, "good")
        self.call("attempt-record", result, "duplicate-id", ok=False)
        self.assertEqual(self.count(), 4)

    def test_policy_and_references(self):
        case = self.create()
        result = self.result(self.attempt(case))
        result["observations"][0]["digest"] = "0" * 64
        self.call("attempt-record", result, "missing", ok=False)
        result = self.result(self.attempt(case))
        result["input_refs"][0]["digest"] = "0" * 64
        self.call("attempt-record", result, "missing", ok=False)
        for permission in ("DENY", "ASK_ALWAYS", "ASK_ON_EXTERNAL_EFFECT"):
            self.work = self.root / permission
            self.spec["permission"] = permission
            self.start()
            self.call("case-create", self.case, "case", ok=permission == "ASK_ON_EXTERNAL_EFFECT")

    def test_bad_models_and_encoding(self):
        case = self.create()
        result = self.result(self.attempt(case))
        changes = [{"ended_at": 999}, {"started_at": True}, {"ended_at": -1}, {"confidence": "CERTAIN"},
                   {"hypothesis": " "}, {"intervention": "x" * 4097}, {"attempt_id": "../escape"},
                   {"next_action": "EXECUTE"}, {"classification": "DONE"}, {"schema_version": 2},
                   {"extra": "bad"}, {"decision_rule": ""}, {"input_refs": []},
                   {"actor_kind": "ROOT"}, {"observations": [{"digest": "0" * 64}]},
                   {"classification": "UNCERTAIN_EXTERNAL_EFFECT", "next_action": "RERUN_ALLOWED"},
                   {"next_action": "FINALIZE_CANDIDATE"}]
        for update in changes:
            with self.subTest(update=update):
                self.call("attempt-record", dict(result, **update), "bad", ok=False)
        result["observations"] = []
        self.call("attempt-record", dict(result, classification="PRODUCT_PASS_OBSERVED"), "bad", ok=False)
        self.call("attempt-record", result, "empty-observation")
        request = dict(schema_version=1, operation="case-create", key="case", record=self.case)
        good = json.dumps(request).encode()
        for bad in (good.replace(b'"schema_version": 1', b'"schema_version": 1,"schema_version": 1', 1),
                    good + b"\xff", good + b"\x00", b"x" * 65537,
                    good.replace(b"parser-case", b"parser\\u0000case")):
            path = self.root / "bad.json"
            path.write_bytes(bad)
            self.run_cli("research", "validate", path, ok=False)
        self.assertEqual(self.count(), 3)

    def test_case_shape_matrix(self):
        for change in ({"context": "unstructured"}, {"privacy_level": "AUTO_PUBLIC"},
                       {"research_questions": []}, {"project_id": "../../bad"},
                       {"pre_registered_plan_digest": None}, {"case_type": "GENERAL_PROOF"},
                       {"research_questions": [self.case["research_questions"][0]] * 2}):
            self.call("case-create", dict(self.case, **change), "bad", ok=False)
        self.assertEqual(self.count(), 1)

    def test_missing_and_corrupt_evidence_fail_replay(self):
        case = self.create()
        path = self.cas_path(case["record_digest"])
        content = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(content + b" ")
        self.run_cli("research", "status", self.work, ok=False)
        path.write_bytes(content)
        self.assertEqual(self.run_cli("research", "status", self.work)["count"], 1)
        path.unlink()
        self.run_cli("research", "status", self.work, ok=False)

    def test_missing_event_and_pending_orphans(self):
        self.create()
        pending = self.work / "events/.pending-interrupted"
        pending.write_bytes(b"partial uncommitted frame")
        before = self.run_cli("research", "status", self.work)
        self.assertEqual(before["count"], 1)
        self.assertEqual(before, self.run_cli("research", "status", self.work))
        self.assertEqual(pending.read_bytes(), b"partial uncommitted frame")
        (self.work / "events/00000001.evt").unlink()
        self.run_cli("research", "status", self.work, ok=False)

    def test_documents_interleave_and_markdown_escape(self):
        self.case["unit_of_analysis"] = "# Forged\n<script>alert(1)</script> [run](https://invalid.test)"
        self.create()
        samples = SOURCE / "samples/documents"
        d = self.run_cli("document", "submit", self.work, samples / "planning.json", samples / "planning.md", "plan")
        self.assertEqual(int(d["generation"]), 2)
        self.assertFalse(d["acceptance_verified"])
        self.assertEqual(self.run_cli("research", "status", self.work)["count"], 1)
        md = self.run_cli("research", "report", self.work, 1, raw=True)
        self.assertNotIn(b"<script>", md)
        self.assertNotIn(b"\n# Forged", md)
        self.assertNotIn(b"](https://", md)

    def test_local_lock_and_readonly_inspection(self):
        import fcntl
        import os
        fd = os.open(self.work, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.run_cli("research", "status", self.work, ok=False)
        finally:
            os.close(fd)
        self.create()
        before = {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).digest())
                  for p in self.work.rglob("*") if p.is_file()}
        self.run_cli("research", "inspect", self.work, 1)
        self.run_cli("research", "report", self.work, 1, raw=True)
        self.assertEqual(before, {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).digest())
                                 for p in self.work.rglob("*") if p.is_file()})

    def test_rehashed_invalid_event_is_rejected(self):
        case = self.create()
        event = copy.deepcopy(case["event"])
        event["sequence"] = 17
        data = json.dumps(event).encode()
        digest = hashlib.sha256(data).hexdigest()
        path = self.work / "objects/sha256" / digest[:2] / digest[2:]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        frame_path = self.work / "events/00000002.evt"
        frame = frame_path.read_bytes()
        frame_path.chmod(0o600)
        frame_path.write_bytes(frame[:48] + bytes.fromhex(digest))
        self.run_cli("research", "status", self.work, ok=False)

    def test_referenced_evidence_reverified_on_replay(self):
        case = self.create()
        evidence = b"A bounded synthetic observation."
        digest = hashlib.sha256(evidence).hexdigest()
        path = self.work / "objects/sha256" / digest[:2] / digest[2:]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(evidence)
        result = self.result(self.attempt(case))
        result["observations"][0]["digest"] = digest
        self.call("attempt-record", result, "observed")
        path.write_bytes(b"tampered")
        self.run_cli("research", "status", self.work, ok=False)

    def test_capacity_and_idempotency_at_capacity(self):
        first = self.create()
        for i in range(1, 256):
            self.call("case-create", dict(self.case, case_id=f"case-{i}"), f"key-{i}")
        self.assertEqual(self.run_cli("research", "status", self.work)["count"], 256)
        self.call("case-create", dict(self.case, case_id="overflow"), "overflow", ok=False)
        self.assertEqual(first, self.create())
        self.assertEqual(self.count(), 257)

    def test_derived_index_collisions_survive_reopen(self):
        buckets = {}
        for i in range(1025):
            key = f"collision-{i}"
            digest = 2166136261
            for byte in key.encode():
                digest = ((digest ^ byte) * 16777619) & 0xffffffff
            bucket = digest % 512
            if bucket in buckets:
                pair = (buckets[bucket], key)
                break
            buckets[bucket] = key
        else:
            self.fail("collision fixture did not collide")
        replies = []
        for key in pair:
            replies.append(self.call("case-create", dict(self.case, case_id=key), key))
        for key, original in zip(pair, replies):
            self.assertEqual(original,
                             self.call("case-create", dict(self.case, case_id=key), key))
        self.call("case-create", dict(self.case, case_id="different"), pair[0], ok=False)
        self.call("case-create", dict(self.case, case_id=pair[0]), "different", ok=False)
        self.assertEqual(self.run_cli("research", "status", self.work)["count"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
