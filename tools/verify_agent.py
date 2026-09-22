"""Installed-CLI fixture conformance and private current-Work observation.

Neither mode launches a provider, grants authority, or certifies agent identity.
Reports deliberately distinguish fixture success from actual-agent validation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time

LIMIT = 32 * 1024 * 1024
SCHEMA = "golem.conformance.v1"
CASES = tuple(f"E28-{i:02d}" for i in range(1, 9))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def suite_digest(source):
    h = hashlib.sha256()
    for directory in (source / "tests/c", source / "samples"):
        for path in sorted(directory.rglob("*")):
            if path.suffix not in (".py", ".json", ".md") or not path.is_file():
                continue
            h.update(path.relative_to(source).as_posix().encode() + b"\0")
            h.update(digest(path).encode() + b"\0")
    return h.hexdigest()


def strict_json(data):
    def reject_constant(value):
        raise ValueError("non-finite JSON")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result
    if len(data) > LIMIT:
        raise ValueError("JSON size limit")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=reject_constant)


def private_directory(path):
    path = path.absolute()
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise ValueError("symlink output path")
    path.mkdir(mode=0o700)  # Never reuse, erase, or overwrite an earlier run.
    return path


def save(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def capture(argv, destination, timeout, cwd=None):
    """Bound output and wall time; stop the whole test process group on failure."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in ("PYTHONPATH", "PYTHONHOME")}
    paths = [destination / "stdout.log", destination / "stderr.log"]
    started = time.monotonic()
    reason = "EXIT"
    with paths[0].open("xb") as out, paths[1].open("xb") as err:
        os.chmod(paths[0], 0o600)
        os.chmod(paths[1], 0o600)
        process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env,
                                   stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                if time.monotonic() - started > timeout:
                    reason = "TIMEOUT"
                    break
                if any(p.stat().st_size > LIMIT for p in paths):
                    reason = "OUTPUT_LIMIT"
                    break
                time.sleep(0.05)
        finally:
            # A completed launcher must not leave a detached-in-group gate running.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    if any(p.stat().st_size > LIMIT for p in paths):
        reason = "OUTPUT_LIMIT"
    return {"returncode": process.returncode, "reason": reason,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "logs": {p.name: digest(p) for p in paths}}


def base(cli, mode):
    if platform.system() not in ("Darwin", "Linux"):
        raise ValueError("only macOS and Linux are supported")
    if not cli.is_file() or not os.access(cli, os.X_OK):
        raise ValueError("CLI must be an executable file")
    return {"schema": SCHEMA, "mode": mode, "host": platform.system(),
            "architecture": platform.machine(), "cli_sha256": digest(cli),
            "python_version": platform.python_version(),
            "actual_agent_verified": False, "release_ready": False,
            "provider_invoked": False, "usage": None, "cost": None}


def fixture(cli, source, cc, output, timeout):
    report = base(cli, "FIXTURE_CONFORMANCE")
    script = source / "tests/c/conformance_integration.py"
    if not script.is_file() or not cc.is_file():
        raise ValueError("missing conformance script or compiler")
    report["suite_sha256"] = digest(script)
    report["suite_source_sha256"] = suite_digest(source)
    report["compiler_sha256"] = digest(cc)
    result = capture([sys.executable, script, cli, source, cc], output, timeout, output)
    with (output / "stderr.log").open("rb") as stream:
        text = stream.read(LIMIT).decode("utf-8", errors="replace")
    # Fail closed on skipped/empty/truncated suites, not just an exit status of 0.
    seen = re.findall(r"^test_e(0[1-8])_[^\n]+ \.\.\. ok$", text, re.M)
    complete = sorted(seen) == [f"{i:02d}" for i in range(1, 9)]
    complete = complete and bool(re.search(r"\nRan 8 tests in [^\n]+\n\nOK\s*$", text))
    unchanged = suite_digest(source) == report["suite_source_sha256"]
    passed = result["returncode"] == 0 and result["reason"] == "EXIT" and complete and unchanged
    report.update(status="PASS" if passed else "FAIL", process=result,
                  cases=[{"id": case, "status": "PASS" if f"{i:02d}" in seen else "NOT_PASSED"}
                         for i, case in enumerate(CASES, 1)],
                  limitations=["Synthetic tasks and scripted decisions, not model evaluation.",
                               "No actual-agent identity or independent review attestation.",
                               "Reference inertness is not universal prompt-injection resistance."])
    return report


def observe(cli, work, selection, output, timeout):
    report = base(cli, "WORK_OBSERVATION")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", selection):
        raise ValueError("invalid selection id")
    if not work.is_dir():
        raise ValueError("missing Work directory")
    if output == work or work in output.parents:
        raise ValueError("observation output must be outside the Work store")
    request = output / "request.json"
    save(request, json.dumps({"schema_version": 1, "operation": "resume",
                             "selection_id": selection}).encode())
    result = capture([cli, "completion", "call", work, request], output, timeout, output)
    report.update(status="FAIL", process=result)
    if result["returncode"] != 0 or result["reason"] != "EXIT":
        return report
    with (output / "stdout.log").open("rb") as stream:
        state = strict_json(stream.read(LIMIT + 1))
    if (not isinstance(state, dict) or type(state.get("schema_version")) is not int
            or state["schema_version"] != 1):
        raise ValueError("unsupported completion response")
    # Do not copy arbitrary authored text, snapshots, paths, or transcripts to summary.
    done = state.get("action") == "DONE" and state.get("acceptance_verified") is True
    done = done and state.get("execution_authorized") is False
    event = state.get("completion", {})
    if not isinstance(event, dict) or not isinstance(event.get("record", {}), dict):
        raise ValueError("invalid completion record")
    record = event.get("record", {})
    receipt = state.get("receipt_digest", "")
    root = record.get("evidence_root", "")
    if done and (not re.fullmatch(r"[a-f0-9]{64}", receipt) or not re.fullmatch(r"[a-f0-9]{64}", root)):
        raise ValueError("missing durable completion identity")
    report.update(status="PASS" if done else "BLOCKED",
                  completion_current=done, receipt_digest=receipt if done else None,
                  evidence_root=root if done else None,
                  limitations=["Live declared-gate observation, not proof of who authored the work.",
                               "No provider was started and no execution authority was issued.",
                               "Raw logs contain private Work data; never publish this directory."])
    return report


def write_report(output, report):
    save(output / "report.json", (json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
    lines = ["# Golem Conformance Observation", "", f"- Mode: {report['mode']}",
             f"- Status: {report['status']}", "- Actual agent verified: false",
             "- Release ready: false", "- Usage/cost: unknown", "",
             "This result is scoped evidence, not a deployment authorization.", ""]
    for item in report.get("cases", []):
        lines.append(f"- {item['id']}: {item['status']}")
    lines += ["", "## Limits", ""] + ["- " + value for value in report.get("limitations", [])]
    save(output / "report.md", ("\n".join(lines) + "\n").encode())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("fixture", "observe"))
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new private directory, never upload")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cc", type=Path)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--selection", default="selection")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 3600:
        parser.error("timeout must be 1..3600 seconds")
    if (args.mode == "fixture" and not args.cc) or (args.mode == "observe" and not args.work):
        parser.error("fixture requires --cc; observe requires --work")
    output = None
    try:
        cli = args.cli.resolve(strict=True)
        output = private_directory(args.output)
        report = (fixture(cli, args.source.resolve(strict=True), args.cc.resolve(strict=True), output, args.timeout)
                  if args.mode == "fixture" else
                  observe(cli, args.work.resolve(strict=True), args.selection, output, args.timeout))
        if digest(cli) != report["cli_sha256"]:
            report["status"] = "FAIL"
            report["binary_changed"] = True
        write_report(output, report)
        print(f"{report['mode']}: {report['status']}; actual-agent verification and release readiness not asserted")
        return 0 if report["status"] == "PASS" else 1
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        # Do not echo paths, authored text, or credentials into public CI logs.
        print("Conformance failed; inspect the explicitly selected private output directory.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
