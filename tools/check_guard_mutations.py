"""Curated guard-removal experiments in a disposable source copy, never the checkout.

Build errors, missing tests and timeouts are inconclusive, not detected mutants.
This is a small sensitivity experiment, not an exhaustive mutation score.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from verify_agent import digest, private_directory, save
from verify_runtime import adjudicate

MUTATIONS = (
    ("30-epoch-fence", "src/daemon/admission_model.c",
     "e->epoch != m->epoch ||", "false ||", "admission_contract"),
    ("31-patch-content", "src/candidate/patch.c",
     '!json_object_equal(dw_get(a, "entries"), dw_get(b, "entries"))',
     "false", "candidate_model"),
    ("32-schema-version", "src/policy/approval_model.c",
     'dw_uint(r, "schema_version") != 1',
     '(dw_uint(r, "schema_version") != 1 && dw_uint(r, "schema_version") != 2)',
     "approval_api"),
)
TARGETS = ("golem_test_admission_contract", "golem_test_candidate", "golem_test_approval")


def replacement(text, before, after):
    if text.count(before) != 1:
        raise ValueError("mutation site changed or ambiguous")
    return text.replace(before, after, 1)


def detected(junit, name, returncode):
    if returncode != 8 or not junit.is_file():
        return False
    cases = list(ET.parse(junit).getroot().iter("testcase"))
    return (len(cases) == 1 and cases[0].get("name") == name and
            cases[0].get("status") == "fail" and
            cases[0].find("failure") is not None and
            cases[0].find("failure").get("message") == "Failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), private_directory(args.output)
    report = {"schema": "golem.guard-mutations.v1", "status": "INCOMPLETE",
              "exhaustive": False, "mutations": []}

    def command(argv, name, timeout=180):
        result = subprocess.run([str(a) for a in argv], capture_output=True, timeout=timeout)
        save(output / (name + ".stdout"), result.stdout)
        save(output / (name + ".stderr"), result.stderr)
        return result.returncode

    try:
        with tempfile.TemporaryDirectory(prefix="golem-guard-mutations-") as root:
            root = Path(root)
            checkout, build = root / "source", root / "build"
            # Includes uncommitted tests/changes, excludes credentials, state and builds.
            checkout.mkdir()
            for name in ("CMakeLists.txt", "include", "src", "cmake", "tests", "samples", "fuzz", "bench", "bindings"):
                path = source / name
                if path.is_dir():
                    shutil.copytree(path, checkout / name,
                                    ignore=shutil.ignore_patterns("__pycache__", "node_modules", "*.egg-info"))
                else:
                    shutil.copy2(path, checkout / name)
            if command(["cmake", "-S", checkout, "-B", build, "-G", "Ninja",
                        "-DCMAKE_BUILD_TYPE=Debug", "-DBUILD_TESTING=ON"], "configure"):
                raise ValueError("configuration failed")
            def compile_targets(label):
                if command(["cmake", "--build", build, "--parallel", "4", "--target", *TARGETS], label):
                    raise ValueError("build failed; not a detected mutant")
            compile_targets("baseline-build")
            for name, relative, before, after, test in MUTATIONS:
                path = checkout / relative
                original = path.read_text()
                baseline = output / (name + "-baseline.xml")
                rc = command(["ctest", "--test-dir", build, "-R", "^" + test + "$",
                              "--output-junit", baseline], name + "-baseline")
                if rc or not adjudicate(baseline, (test,)):
                    raise ValueError("baseline not passing")
                row = {"id": name, "test": test, "source_sha256": digest(path),
                       "status": "INCONCLUSIVE"}
                report["mutations"].append(row)
                try:
                    path.write_text(replacement(original, before, after))
                    row["mutant_sha256"] = digest(path)
                    compile_targets(name + "-build")
                    junit = output / (name + ".xml")
                    rc = command(["ctest", "--test-dir", build, "-R", "^" + test + "$",
                                  "--output-junit", junit], name)
                    row["status"] = "DETECTED" if detected(junit, test, rc) else "NOT_DETECTED"
                finally:
                    path.write_text(original)
                compile_targets(name + "-restore")
            report["status"] = "PASS" if all(
                row["status"] == "DETECTED" for row in report["mutations"]) else "FAIL"
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as exc:
        report["error"] = str(exc)
    save(output / "report.json", json.dumps(report, indent=2).encode())
    print(json.dumps(report))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
