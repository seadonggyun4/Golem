"""Build and retain environment-scoped CTest evidence; no failure-to-skip conversion."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

from verify_agent import capture, digest, private_directory, save
from verify_runtime import adjudicate, test_inputs

SCHEMA = "golem.environment-verification.v1"
LABEL = "restricted-diagnostic"
REQUIRED_DIAGNOSTICS = {"admission_open_diagnostics", "restricted_diagnostics", "diagnostic_tools"}
PROFILES = ("full-ci", "local-dev", "restricted-sandbox")


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2).encode() + b"\n"


def git(source, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-C", str(source), *args], check=True,
                          capture_output=True, timeout=30, env=env).stdout


def source_identity(source):
    """Hash tracked and nonignored untracked content, modes and deletions.

    No source bytes or arbitrary environment variables are exported. Submodules
    require a future explicit recursive policy rather than incomplete provenance.
    """
    entries = git(source, "ls-files", "--stage", "-z").split(b"\0")
    if any(row.startswith(b"160000 ") for row in entries):
        raise ValueError("submodules are not supported by source identity v1")
    names = git(source, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    files = {}
    for raw in sorted(set(names.split(b"\0")) - {b""}):
        name = os.fsdecode(raw)
        path = source / name
        if path.is_symlink():
            files[name] = {"kind": "symlink", "sha256": hashlib.sha256(
                os.fsencode(os.readlink(path))).hexdigest()}
        elif path.is_file():
            files[name] = {"kind": "file", "sha256": digest(path),
                           "executable": bool(path.stat().st_mode & 0o111)}
        elif not path.exists():
            files[name] = {"kind": "deleted"}
        else:
            raise ValueError("unsupported source file kind: " + name)
    status = git(source, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    return {"commit": git(source, "rev-parse", "HEAD").decode().strip(),
            "dirty": bool(status), "status_sha256": hashlib.sha256(status).hexdigest(),
            "diff_sha256": hashlib.sha256(git(source, "diff", "HEAD", "--binary", "--no-ext-diff",
                                               "--no-textconv")).hexdigest(),
            "tree_sha256": hashlib.sha256(encoded(files)).hexdigest(), "files": files}


def select_tests(inventory, restricted):
    tests = inventory["tests"]
    names = [t["name"] for t in tests]
    if not names or len(names) != len(set(names)):
        raise ValueError("empty or duplicate CTest inventory")
    diagnostic = []
    for test in tests:
        props = {p["name"]: p["value"] for p in test.get("properties", [])}
        if LABEL in props.get("LABELS", []):
            diagnostic.append(test["name"])
    if not REQUIRED_DIAGNOSTICS.issubset(diagnostic):
        raise ValueError("required diagnostic tests missing from label")
    return diagnostic if restricted else names


def verdict(report):
    """Environment and suite verdicts remain independent, even on failed runs."""
    if report.get("error") or not report.get("inputs_unchanged", False):
        return "FAIL"
    if report["profile"] == "restricted-sandbox":
        return "PASS" if (report["diagnostic_suite"] == "PASS" and
                          report["environment"] in ("PASS", "UNSUPPORTED_ENVIRONMENT")) else "FAIL"
    return "PASS" if report["environment"] == "PASS" and report["full_suite"] == "PASS" else "FAIL"


def execute(output, name, argv, timeout, source):
    directory = private_directory(output / name)
    command = list(map(str, argv))
    save(directory / "command.json", encoded({"argv": command, "cwd": str(source),
        "environment": {k: os.environ[k] for k in ("ASAN_OPTIONS", "UBSAN_OPTIONS", "TMPDIR")
                        if k in os.environ}}))
    try:
        result = capture(command, directory, timeout, source)
    except OSError as exc:
        result = {"returncode": None, "reason": "LAUNCH_ERROR", "error": type(exc).__name__}
    save(directory / "result.json", encoded(result))
    return result


def successful(result):
    return result["returncode"] == 0 and result["reason"] == "EXIT"


def read_doctor(output, result, binary_hash, profile):
    if result["reason"] != "EXIT" or result["returncode"] not in (0, 1):
        raise ValueError("doctor process did not complete normally")
    row = json.loads((output / "doctor" / "stdout.log").read_bytes())
    if (row.get("schema") != "golem.environment.v1" or
            row.get("requested_profile") != profile or
            row.get("status") not in ("PASS", "UNSUPPORTED_ENVIRONMENT") or
            (row["status"] == "PASS") != (result["returncode"] == 0) or
            row.get("binary_sha256") != binary_hash or row.get("binary_unchanged") is not True or
            not row.get("roots")):
        raise ValueError("doctor evidence identity or status mismatch")
    return row["status"]


def check_bundle(output):
    """Integrity only, including faithfully retained FAIL reports; not authenticity."""
    manifest = json.loads((output / "manifest.json").read_bytes())
    if manifest.get("schema") != "golem.verification-manifest.v1":
        raise ValueError("unsupported manifest schema")
    paths = list(output.rglob("*"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("symlink in evidence bundle")
    files = {p.relative_to(output).as_posix(): digest(p) for p in paths
             if p.is_file() and p != output / "manifest.json"}
    if files != manifest.get("files") or "report.json" not in files:
        raise ValueError("evidence digest or file inventory mismatch")
    report = json.loads((output / "report.json").read_bytes())
    if report.get("schema") != SCHEMA:
        raise ValueError("unsupported report schema")
    return {"integrity": "PASS", "recorded_status": report["status"], "authenticity_verified": False}


def run(source, preset, profile, output, roots, timeout, definitions=()):
    source = source.resolve()
    output = output.absolute()
    # An output inside the source must be ignored, or it changes its own identity.
    if output == source or source in output.parents:
        relative = output.relative_to(source).as_posix() + "/"
        git(source, "check-ignore", "--", relative)
    output = private_directory(output)
    report = {"schema": SCHEMA, "profile": profile, "preset": preset,
              "status": "FAIL", "environment": "NOT_RUN", "full_suite": "NOT_RUN",
              "diagnostic_suite": "NOT_RUN", "inputs_unchanged": False,
              "started_at": datetime.now(timezone.utc).isoformat(),
              "system": {"os": platform.system(), "release": platform.release(),
                         "architecture": platform.machine(), "python": platform.python_version()},
              "ci": {k: os.environ[k] for k in ("GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID",
                     "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "RUNNER_OS", "RUNNER_ARCH") if k in os.environ},
              "processes": {}, "product_acceptance": False,
              "limitations": ["Unsigned local evidence; no SLSA level or independent reproduction claim.",
                              "Source snapshots are not atomic and do not trace ignored dependencies.",
                              "Hashes detect changes, not authenticity or universal correctness."]}
    save(output / "started.json", encoded(report))
    before = None
    hashes = {}
    try:
        before = source_identity(source)
        save(output / "source-before.json", encoded(before))
        report["source_commit"] = before["commit"]
        report["source_tree_sha256"] = before["tree_sha256"]
        report["source_dirty"] = before["dirty"]
        for tool in ("cmake", "ctest"):
            result = execute(output, tool + "-version", [tool, "--version"], 30, source)
            report["processes"][tool + "-version"] = result
            if not successful(result):
                raise ValueError(tool + " unavailable")
        # Pin one build directory across configuration, binary identity and tests.
        build = source / "build" / preset
        for name, command in (("configure", ["cmake", "--preset", preset, "-B", build, *definitions]),
                              ("build", ["cmake", "--build", build])):
            result = execute(output, name, command, timeout, source)
            report["processes"][name] = result
            if not successful(result):
                raise ValueError(name + " failed")
        binary = build / "golem"
        report["binary_sha256"] = digest(binary)
        save(output / "CMakeCache.txt", (build / "CMakeCache.txt").read_bytes())
        save(output / "CMakePresets.json", (source / "CMakePresets.json").read_bytes())
        toolchain = sorted(build.glob("CMakeFiles/*/CMake*Compiler.cmake"))
        if not toolchain:
            raise ValueError("missing generated compiler identification")
        save(output / "toolchain.json", encoded({p.relative_to(build).as_posix(): p.read_text()
                                                for p in toolchain}))
        restricted = profile == "restricted-sandbox"
        ctest = ["ctest", "--preset", preset, "--test-dir", build]
        if restricted:
            ctest += ["-L", "^" + LABEL + "$"]
        # Inventory is unfiltered: a future preset exclusion must not silently
        # shrink a full-suite claim. JUnit must match this independently selected set.
        result = execute(output, "inventory", ["ctest", "--test-dir", build,
                                               "--show-only=json-v1"], 30, source)
        report["processes"]["inventory"] = result
        if not successful(result):
            raise ValueError("CTest inventory failed")
        inventory = json.loads((output / "inventory" / "stdout.log").read_bytes())
        names = select_tests(inventory, restricted)
        report["expected_tests"] = names
        inputs = test_inputs(inventory["tests"], set(names), build)
        inputs.update(str(p) for p in (binary, build / "CMakeCache.txt"))
        inputs.update(str(p) for p in toolchain)
        inputs.update(str(p) for p in build.rglob("CTestTestfile.cmake"))
        hashes = {path: digest(Path(path)) for path in sorted(inputs)}
        save(output / "test-inputs.json", encoded(hashes))
        doctor = [sys.executable, source / "tools/doctor_environment.py", "--binary", binary,
                  "--profile", profile]
        for root in roots:
            doctor += ["--root", root]
        result = execute(output, "doctor", doctor, timeout, source)
        report["processes"]["doctor"] = result
        try:
            report["environment"] = read_doctor(output, result, report["binary_sha256"], profile)
        except (OSError, ValueError, TypeError) as exc:
            report["environment"] = "ERROR"
            report["doctor_error"] = str(exc)
        # A failing preflight never suppresses a requested full suite.
        junit = output / "results.xml"
        result = execute(output, "ctest", [*ctest, "--output-on-failure", "--no-tests=error",
                                         "--output-junit", junit], timeout, source)
        report["processes"]["ctest"] = result
        passed = successful(result) and adjudicate(junit, names)
        report["diagnostic_suite" if restricted else "full_suite"] = "PASS" if passed else "FAIL"
        if not restricted:
            diagnostic = select_tests(inventory, True)
            # Subset status is available from the same execution, without rerunning.
            report["diagnostic_suite"] = "FAIL"
            if junit.is_file() and junit.stat().st_size <= 16 * 1024 * 1024:
                cases = list(ET.parse(junit).getroot().iter("testcase"))
                selected = [c for c in cases if c.get("name") in diagnostic]
                report["diagnostic_suite"] = "PASS" if (
                    result["reason"] == "EXIT" and sorted(c.get("name") for c in selected) == sorted(diagnostic)
                    and all(c.get("status") == "run" and not any(c.find(t) is not None
                            for t in ("failure", "error", "skipped")) for c in selected)) else "FAIL"
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, subprocess.SubprocessError) as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        try:
            after = source_identity(source)
            save(output / "source-after.json", encoded(after))
            report["inputs_unchanged"] = before == after and all(
                Path(p).is_file() and digest(Path(p)) == value for p, value in hashes.items())
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        report["status"] = verdict(report)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save(output / "report.json", encoded(report))
        files = {p.relative_to(output).as_posix(): digest(p)
                 for p in sorted(output.rglob("*")) if p.is_file()}
        save(output / "manifest.json", encoded({"schema": "golem.verification-manifest.v1", "files": files}))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-bundle", type=Path, help="Verify retained file hashes, not authenticity or acceptance")
    parser.add_argument("--preset", choices=("dev", "release", "asan"))
    parser.add_argument("--profile", choices=PROFILES)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--root", type=Path, action="append")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--define", action="append", default=[], help="CMake NAME=VALUE cache definition")
    args = parser.parse_args()
    if args.check_bundle:
        try:
            print(json.dumps(check_bundle(args.check_bundle)))
            return 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if not all((args.preset, args.profile, args.output, args.root)):
        parser.error("--preset, --profile, --output and --root are required for a run")
    if not 1 <= args.timeout <= 7200:
        parser.error("timeout must be 1..7200 seconds per phase")
    if any("=" not in value or value.startswith("-") for value in args.define):
        parser.error("--define requires NAME=VALUE")
    try:
        report = run(args.source, args.preset, args.profile, args.output, args.root,
                     args.timeout, ["-D" + value for value in args.define])
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({k: report[k] for k in ("status", "environment", "diagnostic_suite", "full_suite")}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
