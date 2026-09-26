"""Real doctor probes. These require a supported host and never skip restrictions."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BINARY = Path(sys.argv.pop(1)).resolve()


class DoctorTests(unittest.TestCase):
    def call(self, *args, ok=True):
        result = subprocess.run([str(BINARY), "doctor", *map(str, args)],
                                capture_output=True, text=True, timeout=20)
        row = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0 if ok else 1, row)
        self.assertEqual(row["status"], "PASS" if ok else "FAIL")
        return row

    def test_clock(self):
        self.call("clock")

    def test_open_reopen_symlink_and_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            ledger = root / "ledger"
            ledger.mkdir(mode=0o700)
            self.call("admission", ledger)
            self.call("admission", ledger)
            link = root / "link"
            link.symlink_to(ledger)
            denied = self.call("admission", link, ok=False)
            self.assertIn("admission.root_open", denied["diagnostic"])
            with (ledger / ".owner").open("rb") as owner:
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                denied = self.call("admission", ledger, ok=False)
                self.assertIn("admission.owner_lock", denied["diagnostic"])
            self.call("admission", ledger)

    def test_relative_argument_rejected(self):
        row = self.call("admission", "relative-do-not-create", ok=False)
        self.assertIn("admission.arguments", row["diagnostic"])

    def test_work_probe_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary).resolve() / "work"
            spec = Path(__file__).resolve().parents[2] / "samples/documents/work.json"
            subprocess.run([str(BINARY), "work", "start", str(work), str(spec)],
                           check=True, capture_output=True, timeout=20)
            def inventory():
                return {str(p.relative_to(work)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in work.rglob("*") if p.is_file()}
            before = inventory()
            self.call("work", work)
            self.assertEqual(before, inventory())

    def test_session_and_host_bootstrap_errors_are_structured(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing = str(Path(temporary) / "missing.json")
            commands = ((["session", "call", temporary, missing], "golem.session-error.v1"),
                        (["candidate", "serve", missing, str(Path(temporary) / "s"),
                          "--approve-config", "0" * 64], "golem.host-error.v1"))
            for args, schema in commands:
                result = subprocess.run([str(BINARY), *args], capture_output=True,
                                        text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                records = [json.loads(line) for line in result.stderr.splitlines()
                           if line.startswith("{")]
                self.assertTrue(any(row.get("schema") == schema for row in records), result.stderr)


if __name__ == "__main__":
    unittest.main()
