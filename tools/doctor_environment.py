"""Measure runtime prerequisites without changing existing Work or admission data.

Creates only disposable, private probe directories under explicitly selected roots.
Failure is never converted to a passing or skipped product test.
"""
import argparse
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import tempfile


def attempt(name, operation):
    try:
        details = operation()
        return {"probe": name, "status": "PASS", "details": details}
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return {"probe": name, "status": "FAIL", "error": type(exc).__name__,
                "operation": getattr(exc, "golem_operation", name),
                "errno": getattr(exc, "errno", None)}


def engine(binary, *args):
    result = subprocess.run([str(binary), "doctor", *args], capture_output=True,
                            text=True, timeout=15)
    row = json.loads(result.stdout)
    if (row.get("schema") != "golem.doctor.v1" or
            row.get("status") not in ("PASS", "FAIL") or
            (result.returncode == 0) != (row["status"] == "PASS")):
        raise ValueError("invalid doctor response")
    return row


def filesystem(root):
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    phase = "openat"
    try:
        fd = os.open("data", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW,
                     0o600, dir_fd=directory)
        try:
            phase = "write"
            os.write(fd, b"golem-probe")
            phase = "file_fsync"
            os.fsync(fd)
        finally:
            os.close(fd)
        phase = "linkat"
        os.link("data", "published", src_dir_fd=directory, dst_dir_fd=directory)
        phase = "directory_fsync"
        os.fsync(directory)
        phase = "symlinkat"
        os.symlink("data", "symlink", dir_fd=directory)
        phase = "nofollow_openat"
        try:
            fd = os.open("symlink", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        except OSError as exc:
            if exc.errno != errno.ELOOP:
                raise
        else:
            os.close(fd)
            raise ValueError("O_NOFOLLOW did not reject symlink")
    except OSError as exc:
        exc.golem_operation = phase
        raise
    finally:
        os.close(directory)


def lock(root):
    with (root / "lock").open("xb") as first, (root / "lock").open("rb") as second:
        fcntl.flock(first, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        raise ValueError("exclusive lock did not exclude second owner")


def unix_socket(root):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.bind(str(root / "s"))
        sock.listen(1)


def root_probe(binary, path):
    rows = []
    try:
        # Keep the spelling in the report; engine requires symlink-free canonical paths.
        with tempfile.TemporaryDirectory(prefix="golem-probe-", dir=path) as temporary:
            root = Path(temporary).resolve()
            for name, operation in (("filesystem", filesystem), ("flock", lock),
                                    ("unix_socket", unix_socket)):
                rows.append(attempt(name, lambda operation=operation: operation(root)))
            admission = root / "admission"
            admission.mkdir(mode=0o700)
            row = attempt("admission", lambda: engine(binary, "admission", str(admission)))
            if row["status"] == "PASS":
                row["status"] = row["details"]["status"]
            rows.append(row)
    except OSError as exc:
        rows.append({"probe": "scratch_directory", "status": "FAIL", "errno": exc.errno})
    return {"root": str(path), "probes": rows,
            "status": "PASS" if rows and all(r["status"] == "PASS" for r in rows) else "FAIL"}


def collect(binary, roots, profile):
    before = hashlib.sha256(binary.read_bytes()).hexdigest()
    clock = attempt("boot_identity_clock", lambda: engine(binary, "clock"))
    if clock["status"] == "PASS":
        clock["status"] = clock["details"]["status"]
    observations = [root_probe(binary, root) for root in roots]
    unchanged = before == hashlib.sha256(binary.read_bytes()).hexdigest()
    supported = unchanged and clock["status"] == "PASS" and all(
        r["status"] == "PASS" for r in observations)
    return {"schema": "golem.environment.v1", "requested_profile": profile,
            "status": "PASS" if supported else "UNSUPPORTED_ENVIRONMENT",
            "system": platform.system(), "release": platform.release(),
            "architecture": platform.machine(), "binary_sha256": before,
            "binary_unchanged": unchanged, "clock": clock, "roots": observations,
            "product_tests_passed": False,
            "limitations": ["No Work replay or product acceptance performed.",
                            "Process spawn observed through doctor; no sandbox isolation proof.",
                            "Profile is declared, not an authority grant or automatic detection."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, help="Optional new JSON file; never overwrite evidence")
    parser.add_argument("--profile", choices=("full-ci", "local-dev", "restricted-sandbox",
                                               "read-only-observation"), required=True)
    args = parser.parse_args()
    try:
        report = collect(args.binary.resolve(), args.root, args.profile)
        if args.output:
            with args.output.open("x", encoding="utf-8") as output:
                json.dump(report, output, indent=2)
                output.write("\n")
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "error": type(exc).__name__}))
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
