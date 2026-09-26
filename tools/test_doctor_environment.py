import errno
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import doctor_environment as doctor


class DoctorTests(unittest.TestCase):
    def test_errno_preserved_without_sensitive_message(self):
        def denied():
            raise PermissionError(errno.EPERM, "secret path")
        result = doctor.attempt("fsync", denied)
        self.assertEqual(result["errno"], errno.EPERM)
        self.assertNotIn("secret", str(result))

    def test_engine_failure_not_wrapped_as_pass(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(doctor, "engine", return_value={"status": "FAIL"}):
                row = doctor.root_probe(Path("unused"), Path(root))
        self.assertEqual(row["status"], "FAIL")
        self.assertEqual(row["probes"][-1]["status"], "FAIL")

    def test_missing_root_not_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            row = doctor.root_probe(Path("unused"), Path(root) / "absent")
        self.assertEqual(row["status"], "FAIL")
        self.assertEqual(row["probes"][0]["probe"], "scratch_directory")

    def test_socket_creation_and_bind_denial(self):
        for operation in ("create", "bind"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as root:
                with mock.patch.object(doctor.socket, "socket") as constructor:
                    denied = PermissionError(errno.EPERM, "private path")
                    if operation == "create":
                        constructor.side_effect = denied
                    else:
                        constructor.return_value.__enter__.return_value.bind.side_effect = denied
                    row = doctor.attempt("unix_socket", lambda: doctor.unix_socket(Path(root)))
                self.assertEqual(row["status"], "FAIL")
                self.assertEqual(row["errno"], errno.EPERM)
                self.assertNotIn("private path", str(row))

    def test_fsync_and_link_denial_identified(self):
        for target, expected in (("fsync", "file_fsync"), ("link", "linkat")):
            with tempfile.TemporaryDirectory() as root:
                with mock.patch.object(doctor.os, target, side_effect=PermissionError(errno.EPERM, "denied")):
                    row = doctor.attempt("filesystem", lambda: doctor.filesystem(Path(root)))
            self.assertEqual(row["status"], "FAIL")
            self.assertEqual(row["operation"], expected)

    def test_failed_clock_blocks_every_profile(self):
        with tempfile.TemporaryDirectory() as root:
            binary = Path(root) / "binary"
            binary.write_bytes(b"fixture")
            with mock.patch.object(doctor, "engine", return_value={"status": "FAIL"}):
                for profile in ("full-ci", "local-dev", "restricted-sandbox", "read-only-observation"):
                    row = doctor.collect(binary, [], profile)
                    self.assertEqual(row["status"], "UNSUPPORTED_ENVIRONMENT")
                    self.assertFalse(row["product_tests_passed"])


if __name__ == "__main__":
    unittest.main()
