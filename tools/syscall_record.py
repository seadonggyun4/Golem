"""Explicit Linux syscall diagnostics for a new command, never attach or replay.

The trusted strace backend owns ptrace, fork following and architecture decoding.
Evidence is private and unsigned, not a sandbox or proof of complete coverage.
"""
import argparse
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sys

import execution_record as record


def command(tracer, target, output):
    return [str(tracer), "--kill-on-exit", "-f", "-qq", "-ttt", "-e", "raw=all",
            "-e", "signal=none", "-o", str(output), "--", *map(str, target)]


def capture(target, destination, *, timeout=30, limit=record.LIMIT, cwd=None,
            source=None, tracer=None):
    if not target or any(not isinstance(s, str) or "\0" in s for s in target):
        raise ValueError("a nonempty command argv is required")
    if not math.isfinite(timeout) or timeout <= 0 or limit < 1:
        raise ValueError("invalid capture limits")
    destination = record.private_directory(Path(destination).absolute())
    cwd = Path(cwd or Path.cwd()).resolve()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in ("PYTHONPATH", "PYTHONHOME")}
    env["LC_ALL"] = "C"
    result = {"schema": "golem.syscall-observation.v1", "state": "UNSUPPORTED",
              "target_attempted": False, "platform": platform.system(),
              "backend": "strace", "coverage": "NOT_OBSERVED",
              "product_acceptance": False, "authenticity_verified": False,
              "target": record.executable_identity(target, cwd, env)}

    def finish(state, diagnostic):
        result.update(state=state, diagnostic=diagnostic)
        record.save(destination / "trace.json", record.encoded(result))
        return result

    if result["platform"] != "Linux":
        return finish("UNSUPPORTED", "trace.platform_unsupported")
    executable = tracer or shutil.which("strace", path=env.get("PATH", os.defpath))
    if not executable:
        return finish("UNSUPPORTED", "trace.backend_missing")
    identity = record.executable_identity([str(executable)], cwd, env)
    result["tracer"] = identity
    if identity["status"] != "OBSERVED":
        return finish("UNSUPPORTED", "trace.backend_unavailable")
    if result["target"]["status"] != "OBSERVED":
        return finish("BLOCKED", "trace.target_unavailable")
    executable = identity["path"]
    # Probe only a fixed no-effect command. Never retry the user's command to
    # detect capabilities. Kernel/container policy may still change afterwards.
    probe = record.private_directory(destination / "probe")
    result["probe"] = record.capture(command(executable, ["/bin/true"], probe / "syscalls.log"),
        probe, min(timeout, 5), cwd, source=source, env=env, limit=limit,
        extra_logs=("syscalls.log",))
    if (result["probe"]["reason"] != "EXIT" or result["probe"]["returncode"] != 0 or
            result["probe"]["recording"] != "RECORDED" or
            (probe / "syscalls.log").stat().st_size == 0):
        return finish("BLOCKED", "trace.probe_failed")
    record.check(probe)
    if record.executable_identity([executable], cwd, env) != identity:
        return finish("BLOCKED", "trace.backend_changed")
    run = record.private_directory(destination / "run")
    result["target_attempted"] = True
    result["process"] = record.capture(
        command(executable, target, run / "syscalls.log"), run, timeout, cwd,
        source=source, env=env, limit=limit, extra_logs=("syscalls.log",))
    result["target_after"] = record.executable_identity(target, cwd, env)
    result["target_unchanged"] = result["target"] == result["target_after"]
    record.check(run)
    result["coverage"] = "OBSERVED" if (run / "syscalls.log").stat().st_size else "NOT_OBSERVED"
    # EXIT is an observation of the tracer, not proof every syscall was captured
    # or that an external effect succeeded. Keep the command's failure separate.
    complete = result["process"]["reason"] == "EXIT" and result["coverage"] == "OBSERVED"
    return finish("OBSERVED" if complete else "INCOMPLETE",
                  "trace.observed" if complete else "trace.capture_incomplete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--limit", type=int, default=record.LIMIT)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--strace", type=Path)
    parser.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
    try:
        result = capture(argv, args.destination, timeout=args.timeout, limit=args.limit,
                         cwd=args.cwd, source=args.source, tracer=args.strace)
    except (OSError, ValueError) as error:
        print(json.dumps({"state": "INCOMPLETE", "diagnostic": "trace.recording_error",
                          "error_type": type(error).__name__, "errno": getattr(error, "errno", None)}))
        return 2
    print(json.dumps({"state": result["state"], "diagnostic": result["diagnostic"],
                      "target_attempted": result["target_attempted"],
                      "evidence": str(args.destination.absolute() / "trace.json")}))
    return 0 if result["state"] == "OBSERVED" and result["process"]["returncode"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
