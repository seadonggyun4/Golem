"""Private synthetic case-study exports. No actual user data is exported."""
import hashlib
import json
import os
import unittest
from research_integration import Research


class Bundle(Research):
    def export(self, name="bundle", profile="MINIMAL", case=None, ok=True, policy=None):
        policy = policy or dict(schema_version=1, profile=profile, acknowledge_linkability=profile == "LINKABLE")
        return self.run_cli("research", "export", self.work, "--case", case or self.case["case_id"],
                            "--output", self.root / name, "--redact", self.file(policy, "policy.json"), ok=ok)

    def setup_private_case(self):
        self.case["context"]["product"] = "secret@example.invalid /private/customer/password.txt"
        self.case["research_questions"][0]["question"] = "secret-token-EXAMPLE"
        self.case["unit_of_analysis"] = "<script>secret-context</script>"
        self.receipt = self.create()
        plan = self.attempt(self.receipt)
        plan["hypothesis"] = "private-hypothesis-EXAMPLE"
        plan["intervention"] = "private-intervention-EXAMPLE"
        planned = self.call("attempt-plan", plan, "plan")
        decision = self.result(plan, planned["record_digest"])
        decision["observations"][0]["summary"] = "secret-summary-EXAMPLE"
        self.call("attempt-record", decision, "decision")

    def files(self, name="bundle"):
        return {p.name: p.read_bytes() for p in (self.root / name).iterdir()}

    def test_minimal_redaction_roundtrip_and_readonly(self):
        self.setup_private_case()
        fingerprint = lambda: {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).digest())
                               for p in self.work.rglob("*") if p.is_file()}
        before = fingerprint()
        result = self.export()
        self.assertEqual(result["status"], "EXPORTED")
        self.assertFalse(result["redaction_verified"])
        verified = self.run_cli("research", "bundle-verify", self.root / "bundle")
        self.assertEqual(verified["manifest_sha256"], result["manifest_sha256"])
        self.assertFalse(verified["authenticity_verified"])
        self.run_cli("research", "bundle-verify", self.root / "bundle", "--expect-manifest", result["manifest_sha256"])
        self.run_cli("research", "bundle-verify", self.root / "bundle", "--expect-manifest", "0" * 64, ok=False)
        self.assertEqual(before, fingerprint())
        files = self.files(); self.assertEqual(len(files), 10)
        all_bytes = b"\n".join(files.values())
        for secret in (self.case["case_id"], self.spec["work_id"], "secret@", "secret-token", "private-hypothesis",
                       "private-intervention", "secret-summary", "<script>", "/private/", self.receipt["record_digest"]):
            self.assertNotIn(secret.encode(), all_bytes)
        inv = json.loads(files["evidence-inventory.json"])
        self.assertEqual(inv["count"], 3)
        self.assertTrue(all(x["disposition"] == "RAW_OMITTED" for x in inv["items"]))
        self.assertTrue(all("source_sha256" not in x for x in inv["items"]))
        attempts = [json.loads(row) for row in files["attempt-decisions.jsonl"].splitlines()]
        self.assertEqual(attempts[0]["attempt"], attempts[1]["attempt"])
        for line in files["checksums.sha256"].decode().splitlines():
            digest, name = line.split("  ")
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(), digest)
        self.assertEqual(os.stat(self.root / "bundle").st_mode & 0o777, 0o700)

    def test_determinism_and_no_overwrite(self):
        self.setup_private_case(); self.export()
        self.export("second")
        self.assertEqual(self.files(), self.files("second"))
        before = self.files()
        self.export(ok=False)
        self.assertEqual(before, self.files())

    def test_linkable_retains_only_explicit_digest_metadata(self):
        self.setup_private_case(); self.export(profile="LINKABLE")
        files = self.files(); inv = json.loads(files["evidence-inventory.json"])
        self.assertIn(self.receipt["record_digest"], [x["source_sha256"] for x in inv["items"]])
        self.assertIn("source_work_head", json.loads(files["manifest.json"]))
        self.assertNotIn(b"secret@", b"\n".join(files.values()))
        self.assertNotIn(self.case["case_id"].encode(), b"\n".join(files.values()))

    def test_policy_rejection_and_unknown_case_leave_no_destination(self):
        self.create()
        for policy in ({"schema_version": 1, "profile": "NONE", "acknowledge_linkability": False},
                       {"schema_version": 1, "profile": "LINKABLE", "acknowledge_linkability": False},
                       {"schema_version": 1, "profile": "MINIMAL", "acknowledge_linkability": 0},
                       {"schema_version": 2, "profile": "MINIMAL", "acknowledge_linkability": False},
                       {"schema_version": 1, "profile": "MINIMAL", "acknowledge_linkability": False, "copy_raw": True}):
            self.export(ok=False, policy=policy)
        self.export(case="missing", ok=False)
        self.assertFalse((self.root / "bundle").exists())

    def test_other_cases_and_orphans_not_exported(self):
        self.setup_private_case()
        self.call("case-create", dict(self.case, case_id="secret-other-case"), "other")
        orphan = self.work / "objects/sha256/ff"
        orphan.mkdir(exist_ok=True); (orphan / ("f" * 62)).write_bytes(b"secret-orphan")
        self.export()
        data = b"\n".join(self.files().values())
        self.assertNotIn(b"secret-other", data); self.assertNotIn(b"secret-orphan", data)
        self.assertEqual(json.loads(self.files()["manifest.json"])["selected_record_count"], 3)

    def test_corruption_missing_extra_and_partial_rejected(self):
        self.setup_private_case(); self.export()
        root = self.root / "bundle"; path = root / "narrative.md"; original = path.read_bytes()
        path.write_bytes(original + b"tampered")
        self.run_cli("research", "bundle-verify", root, ok=False)
        path.write_bytes(original)
        extra = root / "secret.txt"; extra.write_bytes(b"secret")
        self.run_cli("research", "bundle-verify", root, ok=False); extra.unlink()
        marker = root / "manifest.json"; content = marker.read_bytes(); marker.unlink()
        self.run_cli("research", "bundle-verify", root, ok=False)
        marker.write_bytes(content)
        self.run_cli("research", "bundle-verify", root)

    def test_no_symlink_traversal_or_work_mutation(self):
        self.create()
        self.export(name="work/export", ok=False)
        self.assertFalse((self.work / "export").exists())
        target = self.root / "target"; target.mkdir()
        (self.root / "link").symlink_to(target, target_is_directory=True)
        self.export(name="link/export", ok=False)
        self.assertFalse((target / "export").exists())
        self.export()
        path = self.root / "bundle/narrative.md"; content = path.read_bytes(); path.unlink()
        external = self.root / "external.md"; external.write_bytes(content); path.symlink_to(external)
        self.run_cli("research", "bundle-verify", self.root / "bundle", ok=False)

    def test_case_only_empty_streams_and_missing_source(self):
        receipt = self.create(); self.export()
        self.assertEqual(self.files()["attempt-decisions.jsonl"], b"")
        self.assertEqual(self.files()["outcome-adjudications.jsonl"], b"")
        path = self.cas_path(receipt["record_digest"])
        path.chmod(0o600); path.write_bytes(b"corrupt")
        self.export(name="bad", ok=False)
        self.assertFalse((self.root / "bad").exists())

    def test_cohort_member_export_does_not_disclose_other_members(self):
        from cohort_integration import Cohort
        Cohort.setup_cohort(self)
        Cohort.register(self)
        self.call("cohort-observe", Cohort.observation(self, 0, status="NOT_DONE"), "observation")
        self.export(case="case-0")
        files = self.files()
        rows = [json.loads(x) for x in files["cohort-observations.jsonl"].splitlines()]
        self.assertEqual(rows[0]["status"], "NOT_DONE")
        for secret in ("case-0", "case-2", "block-0", self.cohort["record_digest"]):
            self.assertNotIn(secret.encode(), b"\n".join(files.values()))
        self.assertEqual(json.loads(files["manifest.json"])["selected_record_count"], 2)

    def test_inventory_bound_fails_without_partial_export(self):
        receipt = self.create(); previous = ""
        for i in range(63):
            result = self.result(self.attempt(receipt, f"a-{i}", previous))
            observations = []
            for j in range(32):
                data = f"synthetic-{i}-{j}".encode(); digest = hashlib.sha256(data).hexdigest()
                path = self.work / "objects/sha256" / digest[:2] / digest[2:]
                path.parent.mkdir(exist_ok=True); path.write_bytes(data)
                observations.append(dict(digest=digest, summary="Synthetic", counts=[]))
            result["observations"] = observations
            previous = self.call("attempt-record", result, f"record-{i}")["record_digest"]
        self.export(ok=False)
        self.assertFalse((self.root / "bundle").exists())

    def test_recomputed_checksums_need_independent_manifest_pin(self):
        self.create(); receipt = self.export()
        root = self.root / "bundle"
        (root / "narrative.md").write_text("Altered prose. Integrity is not identity.\n")
        manifest = json.loads((root / "manifest.json").read_text())
        for entry in manifest["files"]:
            content = (root / entry["name"]).read_bytes()
            entry["sha256"] = hashlib.sha256(content).hexdigest(); entry["size"] = len(content)
        (root / "manifest.json").write_text(json.dumps(manifest))
        names = [line.split("  ")[1] for line in (root / "checksums.sha256").read_text().splitlines()]
        (root / "checksums.sha256").write_text("".join(
            hashlib.sha256((root / name).read_bytes()).hexdigest() + "  " + name + "\n" for name in names))
        result = self.run_cli("research", "bundle-verify", root)
        self.assertFalse(result["authenticity_verified"])
        self.run_cli("research", "bundle-verify", root, "--expect-manifest", receipt["manifest_sha256"], ok=False)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Bundle(name) for name in Bundle.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
