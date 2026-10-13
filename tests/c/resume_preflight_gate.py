"""Observed execution adapter for the full native session regression suite."""
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
build = Path(sys.argv[1]).resolve()
run = subprocess.run(
    [sys.executable, str(root / 'tests/c/session_integration.py'), str(build / 'golem'),
     str(root), str(build / 'tests/c/golem_agent_client')],
    capture_output=True, timeout=50,
)
sys.stderr.buffer.write(run.stdout)
sys.stderr.buffer.write(run.stderr)
summary = re.search(rb'Ran (\d+) tests? in ', run.stderr)
passed = run.returncode == 0 and summary is not None and int(summary[1]) == 24
print(json.dumps({'schema_version': 1, 'cases': [
    {'id': 'native-session-regression', 'status': 'PASS' if passed else 'FAIL'}]}))
sys.exit(0 if passed else 1)
