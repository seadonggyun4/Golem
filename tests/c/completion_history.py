"""Pinned historical store: never regenerate in normal tests.

Capture is an explicit maintainer operation with a previously built binary.
The fixture contains synthetic data only; source projects are not restored or run.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def capture():
    import completion_integration
    case = completion_integration.Completion()
    case.setUp()
    try:
        case.ready(sessions=True)
        case.finalize()
        report = case.project()
        files = {}
        for path in sorted(case.work.rglob("*")):
            if path.is_file():
                data = path.read_bytes()
                if b"/Users/" in data or b"/Volumes/" in data:
                    raise ValueError("Private path in historical fixture")
                files[path.relative_to(case.work).as_posix()] = base64.b64encode(data).decode()
        value = {"producer_commit": "51849798f370b93fb2a9ed8c3c877a694163bf75",
                 "report_sha256": hashlib.sha256(report.encode()).hexdigest(), "files": files}
        destination = Path(__file__).parent / "fixtures/completion/v1-store.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(value, indent=2) + "\n")
    finally:
        case.tearDown()


def verify(cli, allocator_test):
    fixture = Path(__file__).parent / "fixtures/completion/v1-store.json"
    value = json.loads(fixture.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve() / "work"
        root.mkdir()
        for name, encoded in value["files"].items():
            relative = Path(name)
            assert not relative.is_absolute() and ".." not in relative.parts
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(encoded, validate=True))
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        # report opens/replays the entire old store. It must not run old QA or
        # require the original temporary source tree to still exist.
        result = subprocess.run([cli, "completion", "report", str(root), "1"],
                                env=env, capture_output=True, timeout=60)
        assert result.returncode == 0, result.stderr.decode()
        assert hashlib.sha256(result.stdout).hexdigest() == value["report_sha256"]
        assert (root / "completions/r0001/completion.md").read_bytes() == result.stdout
        subprocess.run([allocator_test, str(root)], check=True, timeout=60, env=env)


if __name__ == "__main__":
    if sys.argv[1] == "--capture":
        sys.argv.pop(1)
        capture()
    else:
        verify(str(Path(sys.argv[1]).resolve()), str(Path(sys.argv[2]).resolve()))
