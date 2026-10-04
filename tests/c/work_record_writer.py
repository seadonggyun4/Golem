"""Common record writer fault boundaries and unchanged on-disk representations."""
from pathlib import Path
import subprocess
import sys
import tempfile

for mode in ("document", "agent", "raw", "hex", "readonly", "budget", "missing",
             "fault-before", "fault-after", "conflict", "guard", "invalid-name", "corrupt",
             "serialize-once"):
    with tempfile.TemporaryDirectory() as root:
        subprocess.run([sys.argv[1], str(Path(root).resolve()), mode], check=True)
print("14 common-writer scenarios passed")
