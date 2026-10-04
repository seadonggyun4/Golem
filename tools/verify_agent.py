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
import subprocess
import sys
import execution_record
from execution_record import digest, private_directory

LIMIT = 32 * 1024 * 1024
SCHEMA = "golem.conformance.v1"
CASES = tuple(f"E28-{i:02d}" for i in range(1, 9))


def save(path, data):
    # Preserve existing report-write semantics; new execution records use fsync.
    execution_record.save(path, data, durable=False)


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


def capture(argv, destination, timeout, cwd=None, *, source=None):
    """Compatibility entrypoint; all callers now retain mechanical records."""
    return execution_record.capture(argv, destination, timeout, cwd, source=source, limit=LIMIT)


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
    result = capture([sys.executable, script, cli, source, cc], output, timeout, output, source=source)
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
    result = capture([cli, "--output-mode", "full", "completion", "call", work, request], output, timeout, output)
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


def render_report(data):
    """Pure, explicit projection of one saved observation; never execute its commands."""
    report = strict_json(data)
    if (not isinstance(report, dict) or report.get("schema") != SCHEMA
            or report.get("mode") not in ("FIXTURE_CONFORMANCE", "WORK_OBSERVATION")
            or report.get("status") not in ("PASS", "FAIL", "BLOCKED")
            or any(report.get(k) is not False for k in
                   ("actual_agent_verified", "release_ready", "provider_invoked"))):
        raise ValueError("unsupported observation")
    lines = ["# Golem Conformance Observation", "", f"- Mode: {report['mode']}",
             f"- Status: {report['status']}", "- Actual agent verified: false",
             "- Release ready: false", "- Usage/cost: unknown", "",
             f"- Observation SHA256: `{hashlib.sha256(data).hexdigest()}`",
             "- Renderer: `golem.conformance-markdown.v1`", "",
             "This result is scoped evidence, not a deployment authorization.", ""]
    for item in report.get("cases", []):
        if not isinstance(item, dict) or item.get("id") not in CASES or item.get("status") not in ("PASS", "NOT_PASSED"):
            raise ValueError("unsupported case")
        lines.append(f"- {item['id']}: {item['status']}")
    limits = report.get("limitations", [])
    if not isinstance(limits, list) or not all(isinstance(v, str) for v in limits):
        raise ValueError("unsupported limitations")
    lines += ["", "## Limits", ""] + ["    " + json.dumps(value, ensure_ascii=True) for value in limits]
    return "\n".join(lines) + "\n"


def write_report(output, report, *, report_at=None):
    if report_at not in (None, "requested", "handoff", "completion"):
        raise ValueError("unsupported report boundary")
    # This JSON is gate evidence, not optional narrative. Preserve it before any
    # presentation operation so a rendering failure cannot erase the result.
    data = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    execution_record.save(output / "report.json", data)
    if report_at is not None:
        execution_record.save(output / "report.md", render_report(data).encode())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("fixture", "observe", "report"))
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="new private directory; existing observation for report mode")
    parser.add_argument("--report-at", choices=("requested", "handoff", "completion"),
                        help="opt in to one Markdown projection after capture; never changes acceptance")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--cc", type=Path)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--selection", default="selection")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args(argv)
    if args.mode != "report" and args.cli is None:
        parser.error("fixture/observe requires --cli")
    if not 1 <= args.timeout <= 3600:
        parser.error("timeout must be 1..3600 seconds")
    if (args.mode == "fixture" and not args.cc) or (args.mode == "observe" and not args.work):
        parser.error("fixture requires --cc; observe requires --work")
    output = None
    try:
        if args.mode == "report":
            with (args.output / "report.json").open("rb") as stream:
                data = stream.read(LIMIT + 1)
            print(render_report(data), end="")
            return 0
        cli = args.cli.resolve(strict=True)
        output = private_directory(args.output)
        report = (fixture(cli, args.source.resolve(strict=True), args.cc.resolve(strict=True), output, args.timeout)
                  if args.mode == "fixture" else
                  observe(cli, args.work.resolve(strict=True), args.selection, output, args.timeout))
        if digest(cli) != report["cli_sha256"]:
            report["status"] = "FAIL"
            report["binary_changed"] = True
        write_report(output, report, report_at=args.report_at)
        print(f"{report['mode']}: {report['status']}; actual-agent verification and release readiness not asserted")
        return 0 if report["status"] == "PASS" else 1
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        # Do not echo paths, authored text, or credentials into public CI logs.
        print("Conformance failed; inspect the explicitly selected private output directory.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
