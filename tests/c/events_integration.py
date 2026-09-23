"""Private admission snapshots, no writer enrollment and no diagnostic authority."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(sys.argv[1]).resolve()
HELPER = Path(sys.argv[2]).resolve()


class Events(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="golem-events-cli-")
        self.root = Path(self.temp.name).resolve()
        self.invoke([HELPER, "fixture", self.root])

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, args, ok=True):
        p = subprocess.run([str(v) for v in args], capture_output=True, timeout=30)
        self.assertEqual(p.returncode == 0, ok, p.stderr.decode())
        return p

    def hashes(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}

    def test_read_only_cursor_and_exports(self):
        before = self.hashes()
        p = self.invoke([CLI, "events", self.root, "--jsonl"])
        rows = [json.loads(line) for line in p.stdout.splitlines()]
        self.assertEqual(rows[0]["count"], len(rows) - 1)
        self.assertEqual(rows[0]["authority"], "DERIVED_ONLY")
        self.assertNotIn(b"secret-", p.stdout)
        self.assertTrue(all(not row["elapsed_known"] for row in rows[1:]))
        cursor = rows[0]["next"]
        empty = self.invoke([CLI, "events", self.root, "--jsonl", "--after", cursor])
        self.assertEqual(json.loads(empty.stdout)["count"], 0)
        otlp = json.loads(self.invoke([CLI, "events", self.root, "--otlp"]).stdout)
        logs = otlp["resourceLogs"][0]["scopeLogs"][0]["logRecords"]
        self.assertEqual(len(logs), len(rows))
        self.assertTrue(all("timeUnixNano" not in log and "traceId" not in log for log in logs))
        prov = json.loads(self.invoke([CLI, "events", self.root, "--prov"]).stdout)
        self.assertEqual(len(prov["wasDerivedFrom"]), len(rows) - 1)
        self.assertEqual(before, self.hashes())
        self.invoke([CLI, "events", self.root, "--jsonl", "--after", "invalid"], ok=False)
        fields = cursor.split(":")
        fields[1] = "f" * 64
        self.invoke([CLI, "events", self.root, "--jsonl", "--after", ":".join(fields)], ok=False)

    def test_corrupt_journal_emits_no_records(self):
        path = sorted(p for p in self.root.iterdir() if p.name.isdigit())[-1]
        path.chmod(0o600)
        path.write_bytes(b"corrupt")
        p = self.invoke([CLI, "events", self.root, "--jsonl"], ok=False)
        self.assertEqual(p.stdout, b"")

    def test_prov_identity_across_pages_and_streams(self):
        def export(root, after=None):
            args = [CLI, "events", root, "--prov"]
            if after:
                args += ["--after", after]
            return json.loads(self.invoke(args).stdout)

        full = export(self.root)
        self.assertEqual(full, export(self.root))
        rows = [json.loads(line) for line in self.invoke(
            [CLI, "events", self.root, "--jsonl"]).stdout.splitlines()]
        partial = export(self.root, rows[1]["cursor"])
        for section in ("entity", "wasDerivedFrom"):
            shared = full[section].keys() & partial[section].keys()
            self.assertTrue(shared)
            for key in shared:
                self.assertEqual(full[section][key], partial[section][key])
        for key, entity in full["entity"].items():
            if "golem:diagnostic" in entity:
                digest = hashlib.sha256(entity["golem:diagnostic"].encode()).hexdigest()
                self.assertEqual(key, "golem:projection_v1_" + digest)
        with tempfile.TemporaryDirectory(prefix="golem-events-other-") as directory:
            other = Path(directory).resolve()
            self.invoke([HELPER, "fixture", other])
            independent = export(other)
            self.assertFalse(full["entity"].keys() & independent["entity"].keys())
        for relation in partial["wasDerivedFrom"].values():
            self.assertIn(relation["prov:generatedEntity"], partial["entity"])
            self.assertIn(relation["prov:usedEntity"], partial["entity"])

    def test_expired_cursor_requires_explicit_resync(self):
        p = self.invoke([CLI, "events", self.root, "--jsonl"])
        cursor = json.loads(p.stdout.splitlines()[0])["next"]
        self.invoke([HELPER, "fill", self.root])
        before = self.hashes()
        stale = self.invoke([CLI, "events", self.root, "--jsonl", "--after", cursor], ok=False)
        self.assertEqual(stale.stdout, b"")
        self.assertIn(b"missed=", stale.stderr)
        p = self.invoke([CLI, "events", self.root, "--jsonl"])
        meta = json.loads(p.stdout.splitlines()[0])
        self.assertGreater(meta["dropped"], 0)
        self.assertEqual(meta["count"], 64)
        self.assertEqual(before, self.hashes())


if __name__ == "__main__":
    unittest.main(argv=[__file__])
