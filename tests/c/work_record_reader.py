"""Common read mechanism: legacy identities, corruption and read-only failures."""
from pathlib import Path
import subprocess
import sys
import tempfile

modes = ("document", "agent", "magic", "sequence", "previous", "truncated",
         "missing-cas", "corrupt-cas", "gap", "name", "limit", "symlink", "directory")
for mode in modes:
    with tempfile.TemporaryDirectory() as root:
        subprocess.run([sys.argv[1], str(Path(root).resolve()), mode], check=True)
print(f"{len(modes)} common-reader scenarios passed")
