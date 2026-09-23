"""Cross-binary enrollment regression in a NEW disposable Work, never a user store."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from verify_agent import capture, digest, private_directory, save


def schema_rejection(returncode, stderr):
    return returncode == 1 and stderr.strip() in (
        b"golem: corrupt journal", b"golem: unsupported version")


def verify(current, legacy, source, output):
    output = private_directory(output)
    samples = source / "samples/documents"
    work = output / "work"
    calls = []
    identities = {str(binary): digest(binary) for binary in (current, legacy)}

    def invoke(binary, *args, succeeds=True):
        index = len(calls)
        directory = private_directory(output / f"call-{index}")
        result = capture([binary, *args], directory, 30)
        calls.append({"binary_sha256": digest(binary), "process": result})
        if result["reason"] != "EXIT" or (result["returncode"] == 0) != succeeds:
            raise ValueError(f"unexpected cross-version result at call {index}")
        if not succeeds:
            with (directory / "stderr.log").open("rb") as stream:
                stderr = stream.read(4096)
            if not schema_rejection(result["returncode"], stderr):
                raise ValueError("legacy crash or unrelated failure is not schema rejection")

    def inventory():
        return {p.relative_to(work).as_posix(): digest(p) for p in work.rglob("*") if p.is_file()}

    invoke(legacy, "work", "start", work, samples / "work.json")
    invoke(legacy, "document", "submit", work, samples / "planning.json",
           samples / "planning.md", "legacy-document")
    invoke(current, "document", "inspect", work, "planning", "1")
    invoke(current, "profile", "register", work, source / "samples/runtime-profile.json", "enroll")
    before = inventory()
    save(output / "enrolled-inventory.json", json.dumps(before, indent=2).encode())
    # Even a retry of an old idempotency key must not bypass new record validation.
    invoke(legacy, "document", "submit", work, samples / "planning.json",
           samples / "planning.md", "legacy-document", succeeds=False)
    if before != inventory():
        raise ValueError("legacy writer changed enrolled Work")
    invoke(current, "document", "inspect", work, "planning", "1")
    if any(digest(Path(path)) != value for path, value in identities.items()):
        raise ValueError("binary changed during cross-version test")
    report = {"schema": "golem.runtime-legacy.v1", "status": "PASS", "calls": calls,
              "current_sha256": digest(current), "legacy_sha256": digest(legacy),
              "cases": ["legacy Work read", "profile enrollment", "old writer rejection",
                        "rejected write preserves bytes", "current reopen"],
              "actual_agent_verified": False, "release_ready": False}
    save(output / "report.json", json.dumps(report, indent=2).encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("current", "legacy", "source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        verify(args.current.resolve(), args.legacy.resolve(), args.source.resolve(), args.output)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
