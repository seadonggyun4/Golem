"""31E: deterministic derived packs, source verification and immutable publication."""
import copy
import hashlib
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from execution_bundle_integration import Bundle


class Proof(Bundle):
    def request(self, receipts, link=False):
        return {"schema_version": 1, "renderer_version": 1,
                "qa_receipts": receipts, "redaction": {
                    "schema_version": 1, "profile": "LINKABLE" if link else "MINIMAL",
                    "acknowledge_linkability": link}}

    def render_pack(self, request):
        return self.cli("proof", "render", self.work, self.write("proof-request.json", request))

    def setup_proof(self, **options):
        self.setup_bundle(**options)
        receipt = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="proof-qa")
        self.request_data = self.request([receipt["receipt_digest"]])
        self.pack = self.render_pack(self.request_data)
        self.pack_path = self.write("proof-pack.json", self.pack)
        self.export = self.root / "exports"
        self.export.mkdir()
        return receipt

    def test_roundtrip_redaction_and_readonly(self):
        secret = "secret-should-never-appear-in-proof"
        receipt = self.setup_proof(script="import sys\nsys.stderr.write(" + repr(secret) + ")\n"
            "print('invalid QA output')\n")
        # Deliberately invalid QA output must stay ERROR, not a successful export verdict.
        inventory = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in self.work.rglob("*") if p.is_file()}
        before = inventory()
        for _ in range(2):
            self.assertEqual(self.pack, self.render_pack(self.request_data))
        self.cli("proof", "verify", self.work, self.write("request.json", self.request_data), self.pack_path)
        self.assertEqual(before, inventory())
        encoded = json.dumps(self.pack)
        self.assertNotIn(secret, encoded)
        self.assertNotIn(str(self.repo), encoded)
        self.assertNotIn(receipt["receipt_digest"], encoded)
        self.assertIn("ERROR", self.pack["files"]["summary.md"])
        link = self.render_pack(self.request([receipt["receipt_digest"]], True))
        self.assertIn(receipt["receipt_digest"], json.dumps(link))
        self.assertNotIn(secret, json.dumps(link))
        manifest = json.loads(link["files"]["manifest.json"])
        for key in ("acceptance_verified", "raw_evidence_included", "public_export_approved"):
            self.assertFalse(manifest[key])
        for value in self.pack["files"].values():
            self.assertTrue(value.endswith("\n"))
            self.assertNotIn("\r", value)

    def test_order_duplicate_and_policy(self):
        first = self.setup_proof()
        second = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="proof-qa-2")
        keys = [first["receipt_digest"], second["receipt_digest"]]
        self.assertEqual(self.render_pack(self.request(keys)), self.render_pack(self.request(keys[::-1])))
        bad_requests = [self.request([]), self.request([keys[0]] * 2), self.request(["0" * 64])]
        bad = self.request(keys)
        bad["redaction"]["acknowledge_linkability"] = True
        bad_requests.append(bad)
        bad_requests.append({**self.request(keys), "renderer_version": 2})
        bad_requests.append({**self.request(keys), "extra": True})
        for bad in bad_requests:
            self.cli("proof", "render", self.work, self.write("bad-request.json", bad), ok=False)

    def test_publish_idempotency_missing_and_tamper(self):
        self.setup_proof()
        result = self.cli("proof", "publish", self.pack_path, self.export)
        digest = result["manifest_sha256"]
        folder = self.export / digest
        self.assertEqual(set(self.pack["files"]), {p.name for p in folder.iterdir()})
        self.assertEqual(result, self.cli("proof", "publish", self.pack_path, self.export))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.cli("proof", "publish", self.pack_path, self.export), range(2)))
        self.assertEqual(results, [result, result])
        self.cli("proof", "verify-dir", self.export, digest)
        self.cli("proof", "integrity", self.pack_path, digest)
        self.cli("proof", "integrity", self.pack_path, "0" * 64, ok=False)
        marker = folder / "COMMIT.json"
        marker.unlink()
        self.cli("proof", "verify-dir", self.export, digest, ok=False)
        self.cli("proof", "publish", self.pack_path, self.export)
        for name in ("summary.md", "manifest.json"):
            target = folder / name
            target.unlink()
            self.cli("proof", "verify-dir", self.export, digest, ok=False)
            self.cli("proof", "publish", self.pack_path, self.export)
        target = folder / "summary.md"
        target.chmod(0o600)
        target.write_text("tampered")
        self.cli("proof", "publish", self.pack_path, self.export, ok=False)
        self.cli("proof", "verify-dir", self.export, digest, ok=False)
        self.assertEqual(target.read_text(), "tampered")

    def test_manifest_and_source_checks_are_distinct(self):
        self.setup_proof()
        tampered = copy.deepcopy(self.pack)
        tampered["files"]["summary.md"] = "# Forged success\n"
        path = self.write("bad-pack.json", tampered)
        self.cli("proof", "integrity", path, ok=False)
        # An attacker can rehash a self-contained package. Source verification
        # must still reject it, and an external manifest pin must differ.
        manifest = json.loads(tampered["files"]["manifest.json"])
        value = tampered["files"]["summary.md"].encode()
        manifest["files"][0].update(size=len(value), sha256=hashlib.sha256(value).hexdigest())
        wire = json.dumps(manifest, separators=(",", ":")) + "\n"
        tampered["files"]["manifest.json"] = wire
        commit = json.loads(tampered["files"]["COMMIT.json"])
        commit["manifest_sha256"] = hashlib.sha256(wire.encode()).hexdigest()
        tampered["files"]["COMMIT.json"] = json.dumps(commit, separators=(",", ":")) + "\n"
        path = self.write("rehash-pack.json", tampered)
        self.cli("proof", "integrity", path)
        self.cli("proof", "verify", self.work, self.write("request.json", self.request_data), path, ok=False)
        for field, value in [("renderer_version", 2), ("acceptance_verified", True), ("extra", True)]:
            changed = copy.deepcopy(self.pack)
            m = json.loads(changed["files"]["manifest.json"])
            m[field] = value
            changed["files"]["manifest.json"] = json.dumps(m) + "\n"
            self.cli("proof", "integrity", self.write("invalid.json", changed), ok=False)

    def test_paths_symlinks_orphans_and_extra_files(self):
        self.setup_proof()
        result = self.cli("proof", "publish", self.pack_path, self.export)
        digest = result["manifest_sha256"]
        folder = self.export / digest
        pending = folder / (".pending-" + "a" * 24)
        pending.write_text("not an authority")
        self.cli("proof", "verify-dir", self.export, digest)
        extra = folder / "unlisted.txt"
        extra.write_text("extra")
        self.cli("proof", "verify-dir", self.export, digest, ok=False)
        self.cli("proof", "publish", self.pack_path, self.export, ok=False)
        extra.unlink()
        target = folder / "proof.md"
        target.unlink()
        target.symlink_to(self.pack_path)
        self.cli("proof", "verify-dir", self.export, digest, ok=False)
        self.cli("proof", "publish", self.pack_path, self.export, ok=False)
        alias = self.root / "export-alias"
        alias.symlink_to(self.export, target_is_directory=True)
        self.cli("proof", "publish", self.pack_path, alias, ok=False)
        bad = copy.deepcopy(self.pack)
        bad["files"]["../escape"] = "bad"
        self.cli("proof", "publish", self.write("escape.json", bad), self.export, ok=False)
        self.assertFalse((self.root / "escape").exists())

    def test_truncated_discarded_and_missing_source(self):
        receipt = self.setup_proof(cap=1)
        self.assertIn("TRUNCATED", self.pack["files"]["evidence-inventory.json"])
        bundle = self.cli("execution", "bundle", "inspect", self.work, receipt["receipt_digest"])
        self.object_path(bundle["gates"][0]["logs"][0]["retained_receipt"]).unlink()
        self.cli("proof", "render", self.work, self.write("request.json", self.request_data), ok=False)
        self.cli("proof", "integrity", self.pack_path)
        self.tearDown()
        self.setUp()
        self.setup_proof(mode="DISCARD")
        self.assertIn("DISCARDED", self.pack["files"]["evidence-inventory.json"])

    def test_historical_unknown(self):
        self.setup_execution(mode="pass")
        self.prepare()
        self.finish()
        r = self.call("run", checkpoint=self.cp["receipt_digest"], attempt_id="historical-proof")
        pack = self.render_pack(self.request([r["receipt_digest"]]))
        self.assertIn("HISTORICAL_DISCARDED_COMPLETENESS_UNKNOWN", pack["files"]["evidence-inventory.json"])
        self.assertIn('"total_bytes_known":false', pack["files"]["evidence-inventory.json"])

    def test_renderer_v1_golden(self):
        receipt = self.setup_proof()
        inventory = ('{"schema_version":1,"kind":"DERIVED_REFERENCE_INVENTORY",'
            '"raw_evidence_included":false,"runs":[{"run":1,"status":"PASS",'
            '"reason":"DECLARED_GATES_PASSED","scope":"DECLARED_FILES_NONATOMIC",'
            '"gates":[{"gate":1,"status":"PASS","reason":"DECLARED_CASES_PASSED",'
            '"exit_code":0,"signal":0,"timed_out":false,"logs":['
            '{"stream":"stdout","state":"COMPLETE","total_bytes_known":true,"included":"NONE_REFERENCE_ONLY"},'
            '{"stream":"stderr","state":"COMPLETE","total_bytes_known":true,"included":"NONE_REFERENCE_ONLY"}]}]}]}')
        expected = {
            "summary.md": "# Verification summary\n\nDerived projection; not Work completion or public-release approval.\n\n"
                          "- Run 1: PASS. Log availability is listed in evidence-inventory.json.\n",
            "proof.md": "# Verification proof\n\nSource receipt verification is separate from file integrity.\n"
                        "Raw stream digests, retained receipt digests and projection digests name different domains;\n"
                        "equal hashes do not imply equal roles. No original logs are included.\n\n```json\n" + inventory + "\n```\n",
            "comparison.md": "# Descriptive comparison\n\nNo ranking, causal claim or candidate eligibility is established.\n\n"
                             "| Run | QA outcome | Gates |\n| --- | --- | --- |\n| 1 | PASS | 1 |\n",
            "evidence-inventory.json": inventory + "\n"}
        manifest = {"schema_version": 1, "renderer_version": 1, "format": "golem.proof-pack.v1",
                    "privacy": "PRIVATE_REVIEW_REQUIRED", "time_basis": "RECEIPT_MONOTONIC_NO_WALL_CLOCK",
                    "redaction": self.request_data["redaction"], "raw_evidence_included": False,
                    "acceptance_verified": False, "public_export_approved": False,
                    "files": [{"name": name, "size": len(value.encode()), "sha256": hashlib.sha256(value.encode()).hexdigest()}
                              for name, value in expected.items()]}
        expected["manifest.json"] = json.dumps(manifest, separators=(",", ":")) + "\n"
        expected["COMMIT.json"] = json.dumps({"schema_version": 1, "format": "golem.proof-commit.v1",
            "manifest_sha256": hashlib.sha256(expected["manifest.json"].encode()).hexdigest()}, separators=(",", ":")) + "\n"
        self.assertEqual(self.pack, {"schema_version": 1, "files": expected})
        reordered = self.request_data.copy()
        reordered["redaction"] = dict(reversed(list(reordered["redaction"].items())))
        self.assertEqual(self.pack, self.render_pack(reordered))
        linked = self.render_pack(self.request([receipt["receipt_digest"]], True))
        stream = json.loads(linked["files"]["evidence-inventory.json"])["runs"][0]["gates"][0]["logs"][1]
        self.assertEqual(stream["observed_bytes"], 0)
        self.assertEqual(stream["observed_digest"], stream["retained_artifact_digest"])


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Proof(name) for name in Proof.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
