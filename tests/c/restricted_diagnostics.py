"""Check real doctor behavior on supported and permission-restricted processes.

This is diagnostic acceptance only. Unexpected errors are failures, not skips.
"""
import errno
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BINARY = Path(sys.argv.pop(1)).resolve()


class RestrictedDiagnostics(unittest.TestCase):
    def call(self, *args):
        result = subprocess.run([str(BINARY), "doctor", *map(str, args)],
                                capture_output=True, text=True, timeout=20)
        row = json.loads(result.stdout)
        self.assertEqual(row["schema"], "golem.doctor.v1")
        self.assertIn(row["status"], ("PASS", "FAIL"))
        self.assertEqual(result.returncode, 0 if row["status"] == "PASS" else 1)
        self.assertEqual(row["code"] == 0, row["status"] == "PASS")
        return row

    def test_clock_denial_does_not_publish_or_change_ledger(self):
        clock = self.call("clock")
        with tempfile.TemporaryDirectory(prefix="golem-diag-") as temporary:
            root = Path(temporary).resolve()
            first = self.call("admission", root)
            if clock["status"] == "PASS":
                self.assertEqual(first["status"], "PASS", first)
                return
            allowed = (errno.EPERM, errno.EACCES)
            self.assertIn(clock["diagnostic"],
                          [f"session.boot_identity_clock errno={n}" for n in allowed])
            self.assertEqual(first["status"], "FAIL")
            self.assertEqual(first["diagnostic"], clock["diagnostic"].replace("session.", "admission."))
            self.assertEqual({p.name for p in root.iterdir()}, {".owner"})
            def snapshot():
                return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir()}
            before = snapshot()
            second = self.call("admission", root)
            self.assertEqual(second, first)
            self.assertEqual(snapshot(), before)


if __name__ == "__main__":
    unittest.main()
