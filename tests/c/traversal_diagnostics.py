"""Deterministic private syscall injection against real traversal implementations."""
from pathlib import Path
import subprocess
import sys
import tempfile

inventory, workspace, queue = sys.argv[1:]
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "file").write_bytes(b"content")
    (root / "link").symlink_to("file")
    (root / "child").mkdir()
    (root / "child" / "file").write_bytes(b"child")
    common = ("success", "open", "fdopendir-close", "closedir", "readdir", "fstatat", "fstat", "identity")
    for helper, cases in ((inventory, common + ("read", "readlink", "eintr", "clock", "clock-value")), (workspace, common)):
        for case in cases:
            result = subprocess.run([helper, case, directory], capture_output=True, timeout=20)
            if result.returncode:
                raise AssertionError(f"{helper} {case}: {result.stderr.decode(errors='replace')}")
    print("21 traversal diagnostic cases passed")
with tempfile.TemporaryDirectory() as directory:
    result = subprocess.run([queue, str(Path(directory).resolve())], capture_output=True, timeout=20)
    if result.returncode:
        raise AssertionError(f"queue format denial: {result.stderr.decode(errors='replace')}")
    print("Queue format denial preserves unpublished state")
