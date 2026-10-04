"""Portable cgroup control-file I/O tests, not kernel enforcement validation."""
from pathlib import Path
import subprocess
import sys
import tempfile

cases = ("success", "populated", "missing", "write-close", "short-write",
         "write-eintr", "read-close", "read-eintr", "close", "empty", "malformed")
for case in cases:
    with tempfile.TemporaryDirectory() as root:
        subprocess.run([sys.argv[1], str(Path(root).resolve()), case], check=True)
print(f"{len(cases)} resource I/O diagnostic scenarios passed")
