"""Private syscall injection: no production failure switches or host permissions."""
import subprocess
import sys
import tempfile
from pathlib import Path

cases = ("success", "openat", "write", "write_no_progress", "fchmod", "fsync_file",
         "close", "linkat", "unlinkat", "fsync_directory")
for case in cases:
    with tempfile.TemporaryDirectory(prefix="golem-system-error-") as root:
        subprocess.run([sys.argv[1], str(Path(root).resolve()), case], check=True, timeout=20)
print(f"{len(cases)} syscall diagnostic scenarios passed")
