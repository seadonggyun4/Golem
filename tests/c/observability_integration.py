"""Derived snapshot contract, privacy and source-authority regression tests."""
import hashlib
import json
import unittest
from bundle_integration import Bundle


class Observability(Bundle):
    def mapping(self, fmt="otlp", profile="MINIMAL", case=None, policy=None, ok=True):
        policy = policy or dict(schema_version=1, profile=profile, acknowledge_linkability=profile == "LINKABLE")
        return self.run_cli("research", "observability", self.work, "--case", case or self.case["case_id"],
                            "--format", fmt, "--redact", self.file(policy, "redact.json"), ok=ok)

    @staticmethod
    def attributes(values):
        assert len({x["key"] for x in values}) == len(values)
        assert all(set(x) == {"key", "value"} and set(x["value"]) == {"stringValue"} for x in values)
        return {x["key"]: x["value"]["stringValue"] for x in values}

    def test_otlp_wire_shape_and_exact_redacted_payloads(self):
        self.setup_private_case(); self.export()
        doc = self.mapping()
        self.assertEqual(set(doc), {"resourceLogs"})
        self.assertEqual(len(doc["resourceLogs"]), 1)
        resource = doc["resourceLogs"][0]
        attrs = self.attributes(resource["resource"]["attributes"])
        self.assertEqual(attrs["golem.authority"], "DERIVED_ONLY")
        self.assertEqual(attrs["golem.source.manifest.sha256"], hashlib.sha256(self.files()["manifest.json"]).hexdigest())
        self.assertEqual(len(resource["scopeLogs"]), 1)
        scope = resource["scopeLogs"][0]
        self.assertEqual(scope["scope"], dict(name="golem.research.derived", version="1"))
        logs = scope["logRecords"]; self.assertEqual(len(logs), 9)
        names = set()
        for record in logs:
            self.assertEqual(set(record), {"body", "attributes"})
            self.assertEqual(set(record["body"]), {"stringValue"})
            name = self.attributes(record["attributes"])["golem.payload.name"]
            names.add(name)
            self.assertEqual(record["body"]["stringValue"].encode(), self.files()[name])
        self.assertEqual(names, set(self.files()) - {"checksums.sha256"})

    def test_prov_relations_refer_to_entities_and_correct_direction(self):
        self.setup_private_case(); self.export()
        doc = self.mapping("prov")
        self.assertEqual(set(doc), {"prefix", "entity", "activity", "used", "wasGeneratedBy", "wasDerivedFrom"})
        self.assertEqual(doc["prefix"]["prov"], "http://www.w3.org/ns/prov#")
        inventory = json.loads(self.files()["evidence-inventory.json"])["items"]
        self.assertEqual(len(doc["entity"]), len(inventory) + 2)
        self.assertEqual(set(doc["activity"]), {"g:redact", "g:map"})
        for group in ("used", "wasGeneratedBy"):
            for relation in doc[group].values():
                self.assertIn(relation["prov:entity"], doc["entity"])
                self.assertIn(relation["prov:activity"], doc["activity"])
        for relation in doc["wasDerivedFrom"].values():
            self.assertIn(relation["prov:generatedEntity"], ("g:bundle", "g:projection"))
            self.assertIn(relation["prov:usedEntity"], doc["entity"])
            self.assertNotEqual(relation["prov:generatedEntity"], relation["prov:usedEntity"])
        self.assertEqual(doc["wasDerivedFrom"]["g:db"],
                         {"prov:generatedEntity": "g:projection", "prov:usedEntity": "g:bundle"})
        for item in inventory:
            self.assertEqual(doc["entity"]["g:" + item["evidence_id"]]["g:disposition"], "RAW_OMITTED")

    def test_deterministic_private_readonly_exports(self):
        self.setup_private_case()
        fingerprint = lambda: {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).digest())
                               for p in self.work.rglob("*") if p.is_file()}
        before = fingerprint()
        for fmt in ("otlp", "prov"):
            value = self.mapping(fmt)
            self.assertEqual(value, self.mapping(fmt))
            text = json.dumps(value)
            for forbidden in (self.case["case_id"], self.spec["work_id"], "secret@", "secret-token",
                              "private-hypothesis", "private-intervention", "secret-summary", "/private/",
                              self.receipt["record_digest"], "timeUnixNano", "spanId", "traceId", "prov:agent"):
                self.assertNotIn(forbidden, text)
        self.assertEqual(before, fingerprint())

    def test_linkability_requires_explicit_policy(self):
        self.setup_private_case()
        for fmt in ("otlp", "prov"):
            text = json.dumps(self.mapping(fmt, "LINKABLE"))
            self.assertIn(self.receipt["record_digest"], text)
            self.assertNotIn("secret@", text)
            self.mapping(fmt, policy=dict(schema_version=1, profile="LINKABLE", acknowledge_linkability=False), ok=False)

    def test_unknown_format_case_and_malformed_policy(self):
        self.create()
        self.mapping("unknown", ok=False)
        for fmt in ("otlp", "prov"):
            self.mapping(fmt, case="missing", ok=False)
            self.mapping(fmt, policy=dict(schema_version=99), ok=False)
            self.mapping(fmt, policy=dict(schema_version=1, profile="MINIMAL", acknowledge_linkability=False, raw=True), ok=False)

    def test_corrupt_original_evidence_rejected(self):
        self.setup_private_case()
        path = self.cas_path(self.receipt["record_digest"])
        path.chmod(0o600); path.write_bytes(b"corrupted")
        for fmt in ("otlp", "prov"):
            self.mapping(fmt, ok=False)

    def test_case_only_and_other_case_isolation(self):
        self.create()
        self.call("case-create", dict(self.case, case_id="private-other-case"), "other")
        for fmt in ("otlp", "prov"):
            self.assertNotIn("private-other-case", json.dumps(self.mapping(fmt)))
        self.assertEqual(len(self.mapping("prov")["entity"]), 3)

    def test_export_permission_is_not_bypassed(self):
        for permission in ("DENY", "ASK_ALWAYS"):
            self.work = self.root / permission
            self.spec["permission"] = permission
            self.start()
            for fmt in ("otlp", "prov"):
                result = self.mapping(fmt, ok=False)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"policy denied" if permission == "DENY" else b"approval required", result.stderr)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Observability(name) for name in Observability.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
