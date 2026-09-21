"""Black-box CLI contract tests. Artifacts are isolated outside the source tree."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

CLI = str(Path(sys.argv[1]).resolve())
ROOT = str(Path(sys.argv[2]).resolve())
sys.argv = [sys.argv[0]]


class CLIIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cli-mvp-", dir=ROOT)
        self.root = Path(self.tmp.name)
        self.call("init", self.root / "project")
        self.capsule = self.root / "project/capsule.json"

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, *args, code=0):
        p = subprocess.run([CLI, *map(str, args)], capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, code, (args, p.stdout, p.stderr))
        if code:
            self.assertEqual(p.stdout, "")
            self.assertTrue(p.stderr)
            return None
        return json.loads(p.stdout) if p.stdout.startswith("{") else p.stdout

    def run_bundle(self, name="run"):
        path = self.root / name
        result = self.call("run", "--noop", self.capsule, "--output", path)
        self.assertEqual(result["state"], "SUCCEEDED")
        self.assertFalse(result["acceptance_verified"])
        self.assertEqual(result["simulation"], "verified_noop")
        return path

    def edit(self, callback):
        obj = json.loads(self.capsule.read_text())
        callback(obj)
        self.capsule.write_text(json.dumps(obj))

    def test_lifecycle(self):
        self.call("--help")
        self.call("--version")
        self.call("capsule", "validate", self.capsule)
        run = self.run_bundle()
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in run.rglob("*") if p.is_file()}
        replay = self.call("replay", run)
        self.assertTrue(replay["bundle_verified"])
        bill = self.call("cost", "report", run)
        self.assertEqual(len(bill["entries"]), 6)
        self.assertEqual(bill["actual"]["nano_cost"], "0")
        self.assertTrue(bill["actual"]["cost_known"])
        self.assertEqual(bill["unsettled"], "0")
        raw = self.call("replay", run / "journal.bin", "--require-terminal")
        self.assertFalse(raw["bundle_verified"])
        self.assertEqual(raw["journal_records"], "13")
        envelope = json.loads((run / "stage-1.json").read_text())
        digests = [v for v in envelope.values() if isinstance(v, str) and len(v) == 64]
        self.assertTrue(digests)
        for digest in digests:
            if digest != "0" * 64:
                self.call("evidence", "verify", run / "evidence", digest)
        after = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in run.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        second = self.run_bundle("second")
        self.assertNotEqual(json.loads((run / "complete.json").read_text())["run_id"], json.loads((second / "complete.json").read_text())["run_id"])

    def test_overwrite_and_usage(self):
        self.call("init", self.root / "project", code=1)
        run = self.run_bundle()
        original = (run / "journal.bin").read_bytes()
        self.call("run", "--noop", self.capsule, "--output", run, code=1)
        self.assertEqual(original, (run / "journal.bin").read_bytes())
        for args in [("run",), ("run", str(self.capsule)), ("capsule", "validate"), ("cost", "report"), ("replay", str(run), "--bad")]:
            self.call(*args, code=2)

    def test_schema(self):
        original = self.capsule.read_text()
        mutations = [lambda o: o.update(schema_version=None), lambda o: o.update(schema_version=2),
                     lambda o: o.update(extra=True), lambda o: o.update(stages=["planning", "planning"]),
                     lambda o: o.update(stages=[]), lambda o: o.update(goal=" "),
                     lambda o: o.update(permissions={}), lambda o: o.update(id="../escape")]
        for mutation in mutations:
            self.capsule.write_text(original)
            self.edit(mutation)
            self.call("capsule", "validate", self.capsule, code=1)
        for text in [original[:-1] + ',"id":"duplicate"}', original + '{}', original.replace('"AUTO_LOCAL"', '"AUTO_LOCAL","planning":"DENY"', 1), '{', 'x' * 131073]:
            self.capsule.write_text(text)
            self.call("capsule", "validate", self.capsule, code=1)

    def test_custom_graph_and_policy(self):
        self.edit(lambda o: o.update(stages=["development", "qa"]))
        run = self.run_bundle()
        self.assertEqual(len(self.call("cost", "report", run)["entries"]), 2)
        for mode in ["ASK_ALWAYS", "DENY"]:
            self.edit(lambda o: o["permissions"].update(development=mode))
            target = self.root / mode
            self.call("run", "--noop", self.capsule, "--output", target, code=1)
            self.assertFalse((target / "complete.json").exists())
            self.assertFalse((target / "stage-1.json").exists())
            self.call("cost", "report", target, code=1)
            self.call("replay", target)

    def test_corruption(self):
        base = self.run_bundle()
        for i, filename in enumerate(["capsule.json", "journal.bin", "stage-1.json", "cost.json", "complete.json"]):
            target = self.root / f"corrupt-{i}"
            shutil.copytree(base, target)
            file = target / filename
            file.write_bytes(file.read_bytes()[:-1])
            self.call("replay", target, code=1)
            self.call("cost", "report", target, code=1)
        target = self.root / "missing"
        shutil.copytree(base, target)
        (target / "stage-2.json").unlink()
        self.call("cost", "report", target, code=1)
        objects = [p for p in (base / "evidence").rglob("*") if p.is_file() and p.stat().st_size > 0]
        self.assertTrue(objects)
        objects[0].chmod(0o600)
        objects[0].write_bytes(b"corrupted")
        self.call("cost", "report", base, code=1)

    def test_cost_reconstruction(self):
        run = self.run_bundle()
        bill = json.loads((run / "cost.json").read_text())
        bill["actual"]["nano_cost"] = "123"
        changed = json.dumps(bill, separators=(",", ":")).encode()
        (run / "cost.json").write_bytes(changed)
        manifest = json.loads((run / "complete.json").read_text())
        manifest["files"]["cost.json"] = hashlib.sha256(changed).hexdigest()
        (run / "complete.json").write_text(json.dumps(manifest, separators=(",", ":")))
        self.call("cost", "report", run, code=1)

    def test_incomplete_and_paths(self):
        run = self.run_bundle()
        (run / "complete.json").unlink()
        self.assertFalse(self.call("replay", run)["bundle_verified"])
        self.call("cost", "report", run, code=1)
        data = (run / "journal.bin").read_bytes()
        (run / "journal.bin").write_bytes(data[:-64])
        self.call("replay", run)
        self.call("replay", run, "--require-terminal", code=1)
        (self.root / "link").symlink_to(self.capsule)
        self.call("capsule", "validate", self.root / "link", code=1)
        self.call("capsule", "validate", self.root / "project/../project/capsule.json", code=1)
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        self.call("capsule", "validate", fifo, code=1)


if __name__ == "__main__":
    unittest.main()
