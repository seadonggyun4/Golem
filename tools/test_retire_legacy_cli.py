import hashlib
from pathlib import Path
import tempfile
import unittest
from retire_legacy_cli import TEMPLATES, recognized, retire


class RetireLegacyCLI(unittest.TestCase):
    def test_recognition(self):
        for template in TEMPLATES:
            self.assertTrue(recognized(b"#!/usr/bin/python3\n" + template.encode()))
        self.assertFalse(recognized(b"\x7fELF"))
        self.assertFalse(recognized(b"#!/bin/sh\nexec /native/golem\n"))
        self.assertFalse(recognized(b"#!/usr/bin/python3\nfrom golem.cli import main\nmain()\n"))

    def test_audit_and_quarantine(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "golem"
            data = b"#!/usr/bin/python3\n" + TEMPLATES[0].encode()
            path.write_bytes(data)
            report = retire(path)
            self.assertFalse(report["changed"])
            self.assertTrue(path.exists())
            with self.assertRaises(ValueError):
                retire(path, "0" * 64)
            backup = Path(report["backup"])
            backup.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                retire(path, report["sha256"])
            self.assertEqual(path.read_bytes(), data)
            backup.unlink()
            self.assertTrue(retire(path, hashlib.sha256(data).hexdigest())["changed"])
            self.assertFalse(path.exists())
            self.assertEqual(backup.read_bytes(), data)
            path.symlink_to(backup)
            with self.assertRaises(OSError):
                retire(path)
            self.assertTrue(backup.exists())


if __name__ == "__main__":
    unittest.main()
