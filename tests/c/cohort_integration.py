"""Fixed three-arm rosters, declared observations and deterministic replay."""
import copy
import hashlib
import json
import unittest
from research_integration import Research


class Cohort(Research):
    def setup_cohort(self, size=3):
        self.receipts = []
        members = []
        for i in range(size):
            case = dict(self.case, case_id=f"case-{i}")
            receipt = self.call("case-create", case, f"case-{i}")
            self.receipts.append(receipt)
            members.append(dict(case_id=f"case-{i}", case_digest=receipt["record_digest"],
                                arm=("NON_USE", "PARTIAL_USE", "FULL_USE")[i % 3], block_id=f"block-{i // 3}"))
        digest = self.receipts[0]["record_digest"]
        self.definition = dict(schema_version=1, work_id=self.spec["work_id"], cohort_id="study",
                               design="MATCHED_BLOCKS", members=members,
                               **{k: digest for k in ("protocol_digest", "task_digest", "acceptance_digest",
                                                    "environment_digest", "evaluation_digest")})
        return self.definition

    def register(self):
        self.cohort = self.run_cli("research", "cohort", "create", self.work,
                                   self.file(self.definition), "cohort")
        return self.cohort

    def observation(self, case=0, **kwargs):
        return dict(schema_version=1, work_id=self.spec["work_id"], cohort_id="study",
                    cohort_digest=self.cohort["record_digest"], case_id=f"case-{case}", supersedes="",
                    status="PASS", observed_arm=self.definition["members"][case]["arm"],
                    environment_digest=self.definition["environment_digest"],
                    evidence_digest=self.receipts[case]["record_digest"], leakage=False) | kwargs

    def compare(self):
        return self.run_cli("research", "compare", self.work, "study")

    def test_fixed_roster_missing_and_replay(self):
        self.setup_cohort()
        original = self.register()
        self.assertEqual(original, self.register())
        self.assertEqual(original["event"]["schema_version"], 2)
        first = self.compare()
        self.assertEqual([g["declared_status_counts"]["NOT_RECORDED"] for g in first["arms"]], [1, 1, 1])
        self.assertFalse(first["acceptance_verified"])
        self.assertFalse(first["causal_effect_verified"])
        obs = self.observation()
        receipt = self.run_cli("research", "cohort", "observe", self.work, self.file(obs), "obs")
        self.assertEqual(receipt, self.call("cohort-observe", obs, "obs"))
        output = self.compare()
        self.assertEqual(output, self.compare())
        self.assertEqual(output["arms"][0]["declared_status_counts"]["PASS"], 1)
        self.assertEqual(len(output["members"]), 3)
        self.assertEqual(len(output["source_records"]), 2)
        digest = output.pop("projection_digest")
        self.assertEqual(digest, hashlib.sha256(json.dumps(output, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest())
        self.assertIn(b"Fixed assignment", self.run_cli("research", "report", self.work, 4, raw=True))

    def test_revision_chain_deviations_never_disappear(self):
        self.setup_cohort(); self.register()
        old = self.call("cohort-observe", self.observation(status="FAIL", observed_arm="FULL_USE", leakage=True,
                        environment_digest=self.receipts[1]["record_digest"]), "first")
        self.call("cohort-observe", self.observation(), "stale", ok=False)
        self.call("cohort-observe", self.observation(supersedes=old["record_digest"]), "second")
        view = self.compare()
        self.assertEqual(view["arms"][0]["declared_status_counts"]["PASS"], 1)
        self.assertEqual(view["arms"][0]["observation_revision_count"], 2)
        self.assertEqual(view["arms"][0]["ever_declared_deviation_count"], 1)
        self.assertEqual(view["members"][0]["assigned_arm"], "NON_USE")

    def test_preexecution_only_and_global_membership(self):
        self.setup_cohort(); self.register()
        self.call("cohort-create", dict(self.definition, cohort_id="other"), "other", ok=False)
        self.call("cohort-create", self.definition, "other-key", ok=False)
        self.work = self.root / "late"
        self.start(); self.setup_cohort()
        plan = dict(self.attempt(self.receipts[0]), case_id="case-0")
        self.call("attempt-plan", plan, "plan")
        self.call("cohort-create", self.definition, "late", ok=False)

    def test_invalid_models_and_references(self):
        self.setup_cohort()
        for change in ({"members": []}, {"design": "RANDOMIZED_PROOF"}, {"extra": 1},
                       {"protocol_digest": "0" * 64}, {"work_id": "wrong"}):
            self.call("cohort-create", dict(self.definition, **change), "bad", ok=False)
        for field, value in (("case_id", "missing"), ("case_digest", "0" * 64),
                             ("arm", "INVALID"), ("block_id", "separate")):
            bad = copy.deepcopy(self.definition)
            bad["members"][0][field] = value
            self.call("cohort-create", bad, "bad", ok=False)
        self.register()
        for change in ({"leakage": 1}, {"status": "DONE"}, {"supersedes": None},
                       {"case_id": "missing"}, {"cohort_digest": "0" * 64},
                       {"evidence_digest": "0" * 64}, {"environment_digest": "0" * 64},
                       {"observed_arm": "NONE"}, {"extra": 1}):
            self.call("cohort-observe", self.observation(**change), "bad", ok=False)
        self.assertEqual(self.count(), 5)
        self.run_cli("research", "compare", self.work, "missing", ok=False)
        self.run_cli("research", "compare", self.work, "study", "extra", ok=False)

    def test_all_statuses_observational_and_missing_not_zero(self):
        self.setup_cohort(6)
        self.definition["design"] = "OBSERVATIONAL"
        self.definition["members"][0]["block_id"] = "unmatched"
        self.register()
        for i, status in enumerate(("PASS", "FAIL", "SKIPPED", "NOT_DONE", "UNKNOWN")):
            self.call("cohort-observe", self.observation(i, status=status), f"obs-{i}")
        view = self.compare()
        self.assertEqual(sum(g["assigned"] for g in view["arms"]), 6)
        self.assertEqual(sum(g["observations"] for g in view["arms"]), 5)
        self.assertEqual(view["arms"][2]["declared_status_counts"]["NOT_RECORDED"], 1)

    def test_readonly_metrics_compatibility(self):
        self.setup_cohort()
        before = self.run_cli("research", "metrics", self.work)
        self.register(); self.call("cohort-observe", self.observation(), "obs")
        after = self.run_cli("research", "metrics", self.work)
        self.assertEqual(before["counts"], after["counts"])
        fingerprint = lambda: {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).digest())
                               for p in self.work.rglob("*") if p.is_file()}
        original = fingerprint()
        self.compare(); self.run_cli("research", "report", self.work, 4, raw=True)
        self.assertEqual(original, fingerprint())

    def test_corrupt_contract_rejected_on_replay(self):
        self.setup_cohort(); self.register()
        path = self.cas_path(self.receipts[0]["record_digest"])
        path.chmod(0o600); path.write_bytes(b"changed")
        self.run_cli("research", "compare", self.work, "study", ok=False)

    def test_maximum_roster(self):
        self.setup_cohort(48); self.register()
        self.assertEqual([g["assigned"] for g in self.compare()["arms"]], [16, 16, 16])
        bad = copy.deepcopy(self.definition)
        bad["members"].append(bad["members"][0])
        self.call("cohort-create", bad, "too-big", ok=False)

    def test_duplicate_member_and_unbalanced_matched_block(self):
        self.setup_cohort()
        bad = copy.deepcopy(self.definition)
        bad["members"][1] = copy.deepcopy(bad["members"][0])
        self.call("cohort-create", bad, "duplicate", ok=False)
        bad = copy.deepcopy(self.definition)
        bad["members"][1]["arm"] = "NON_USE"
        self.call("cohort-create", bad, "unbalanced", ok=False)
        self.assertEqual(self.count(), 4)

    def test_rehashed_invalid_roster_rejected(self):
        self.setup_cohort(); self.register()
        event = copy.deepcopy(self.cohort["event"])
        event["request"]["record"]["members"][0]["case_digest"] = "0" * 64
        data = json.dumps(event).encode()
        digest = hashlib.sha256(data).hexdigest()
        path = self.work / "objects/sha256" / digest[:2] / digest[2:]
        path.parent.mkdir(exist_ok=True); path.write_bytes(data)
        frame_path = self.work / "events/00000005.evt"
        frame = frame_path.read_bytes()
        frame_path.chmod(0o600); frame_path.write_bytes(frame[:48] + bytes.fromhex(digest))
        self.run_cli("research", "compare", self.work, "study", ok=False)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Cohort(name) for name in Cohort.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
