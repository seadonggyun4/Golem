import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import verify_environment as verify


def inventory():
    return {"tests": [{"name": name, "command": [],
                       "properties": [{"name": "LABELS", "value": [verify.LABEL]}]}
                      for name in sorted(verify.REQUIRED_DIAGNOSTICS)] +
                     [{"name": "product", "command": [], "properties": []}]}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.source / ".gitignore").write_text("build/\n")
        (self.source / "CMakePresets.json").write_text("{}")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        self.build = self.source / "build/dev"
        self.build.mkdir(parents=True)
        (self.build / "golem").write_bytes(b"binary")
        (self.build / "CMakeCache.txt").write_text("fixture")
        self.compiler_info = self.build / "CMakeFiles/fixture/CMakeCCompiler.cmake"
        self.compiler_info.parent.mkdir(parents=True)
        self.compiler_info.write_text('set(CMAKE_C_COMPILER_VERSION "fixture")\n')
        self.output = self.root / "evidence"

    def git(self, *args):
        return verify.git(self.source, *args)

    def fake_execute(self, output, name, argv, timeout, source):
        directory = verify.private_directory(output / name)
        result = {"returncode": 0, "reason": "EXIT"}
        if name == "inventory":
            (directory / "stdout.log").write_text(json.dumps(inventory()))
        elif name == "doctor":
            profile = argv[argv.index("--profile") + 1]
            result["returncode"] = 1
            (directory / "stdout.log").write_text(json.dumps({
                "schema": "golem.environment.v1", "requested_profile": profile,
                "status": "UNSUPPORTED_ENVIRONMENT", "roots": [{"status": "FAIL"}],
                "binary_sha256": verify.digest(self.build / "golem"), "binary_unchanged": True}))
        elif name == "ctest":
            names = verify.select_tests(inventory(), "-L" in argv)
            (output / "results.xml").write_text('<testsuite>' + ''.join(
                f'<testcase name="{n}" status="run"/>' for n in names) + '</testsuite>')
        (directory / "result.json").write_text(json.dumps(result))
        return result

    def run_fixture(self, profile="restricted-sandbox", execute=None):
        with mock.patch.object(verify, "execute", side_effect=execute or self.fake_execute):
            return verify.run(self.source, "dev", profile, self.output, [self.root], 30)

    def test_restricted_pass_is_not_full_pass(self):
        report = self.run_fixture()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["environment"], "UNSUPPORTED_ENVIRONMENT")
        self.assertEqual(report["diagnostic_suite"], "PASS")
        self.assertEqual(report["full_suite"], "NOT_RUN")
        self.assertFalse(report["product_acceptance"])
        self.assertEqual(verify.check_bundle(self.output)["integrity"], "PASS")

    def test_full_runs_despite_unsupported_environment(self):
        report = self.run_fixture("full-ci")
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["full_suite"], "PASS")
        self.assertIn("ctest", report["processes"])

    def test_full_supported_pass_and_compiler_evidence(self):
        def execute(*args):
            result = self.fake_execute(*args)
            if args[1] == "doctor":
                path = self.output / "doctor/stdout.log"
                row = json.loads(path.read_text())
                row["status"] = "PASS"
                row["roots"] = [{"status": "PASS"}]
                result["returncode"] = 0
                path.write_text(json.dumps(row))
            return result
        report = self.run_fixture("full-ci", execute)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["full_suite"], "PASS")
        toolchain = json.loads((self.output / "toolchain.json").read_text())
        self.assertEqual(list(toolchain.values()), [self.compiler_info.read_text()])
        inputs = json.loads((self.output / "test-inputs.json").read_text())
        self.assertIn(str(self.compiler_info), inputs)

    def test_preset_filter_cannot_shrink_full_claim(self):
        def execute(*args):
            if args[1] == "inventory":
                self.assertNotIn("--preset", args[2])
                self.assertNotIn("-L", args[2])
            result = self.fake_execute(*args)
            if args[1] == "ctest":
                path = self.output / "results.xml"
                path.write_text(path.read_text().replace('<testcase name="product" status="run"/>', ''))
            return result
        report = self.run_fixture("full-ci", execute)
        self.assertEqual(report["full_suite"], "FAIL")
        self.assertIn("product", report["expected_tests"])

    def test_missing_compiler_identification_fails_with_evidence(self):
        self.compiler_info.unlink()
        report = self.run_fixture()
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("compiler identification", report["error"]["message"])
        verify.check_bundle(self.output)

    def test_full_failure_preserves_diagnostic_pass(self):
        def execute(*args):
            result = self.fake_execute(*args)
            if args[1] == "ctest":
                path = self.output / "results.xml"
                path.write_text(path.read_text().replace('name="product" status="run"/>',
                    'name="product" status="run"><failure/></testcase>'))
                result["returncode"] = 8
            return result
        report = self.run_fixture("full-ci", execute)
        self.assertEqual(report["full_suite"], "FAIL")
        self.assertEqual(report["diagnostic_suite"], "PASS")

    def test_source_identity_tracks_content_modes_deletion_and_untracked(self):
        original = verify.source_identity(self.source)
        path = self.source / "new.txt"
        path.write_text("first")
        first = verify.source_identity(self.source)
        path.write_text("second")
        second = verify.source_identity(self.source)
        path.chmod(0o700)
        third = verify.source_identity(self.source)
        (self.source / "CMakePresets.json").unlink()
        fourth = verify.source_identity(self.source)
        self.assertEqual(len({r["tree_sha256"] for r in (original, first, second, third, fourth)}), 5)
        self.assertFalse(original["dirty"])
        self.assertTrue(first["dirty"])
        self.assertEqual(fourth["files"]["CMakePresets.json"], {"kind": "deleted"})

    def test_source_or_binary_mutation_fails(self):
        for target in (self.source / "new.txt", self.build / "golem"):
            with self.subTest(target=target):
                self.output = self.root / ("evidence-" + target.name)
                def execute(*args):
                    result = self.fake_execute(*args)
                    if args[1] == "ctest":
                        target.write_bytes(b"changed")
                    return result
                report = self.run_fixture(execute=execute)
                self.assertEqual(report["status"], "FAIL")
                self.assertFalse(report["inputs_unchanged"])

    def test_build_failure_still_retains_report_and_manifest(self):
        def execute(*args):
            result = self.fake_execute(*args)
            if args[1] == "build":
                result["returncode"] = 1
            return result
        report = self.run_fixture(execute=execute)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["full_suite"], "NOT_RUN")
        self.assertIn("error", report)
        self.assertEqual(verify.check_bundle(self.output)["recorded_status"], "FAIL")

    def test_timeout_missing_or_malformed_junit_never_passes(self):
        for mode in ("timeout", "missing", "malformed", "skipped", "duplicate"):
            with self.subTest(mode=mode):
                self.output = self.root / mode
                def execute(*args):
                    result = self.fake_execute(*args)
                    if args[1] == "ctest":
                        path = self.output / "results.xml"
                        if mode == "timeout":
                            result["reason"] = "TIMEOUT"
                        elif mode == "missing":
                            path.unlink()
                        elif mode == "malformed":
                            path.write_text("<")
                        elif mode == "skipped":
                            path.write_text(path.read_text().replace('/>', '><skipped/></testcase>'))
                        else:
                            path.write_text(path.read_text().replace('</testsuite>',
                                '<testcase name="diagnostic_tools" status="run"/></testsuite>'))
                    return result
                self.assertEqual(self.run_fixture(execute=execute)["status"], "FAIL")
                verify.check_bundle(self.output)

    def test_tampering_missing_and_extra_files_fail_integrity(self):
        self.run_fixture()
        path = self.output / "source-before.json"
        original = path.read_bytes()
        path.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            verify.check_bundle(self.output)
        path.unlink()
        with self.assertRaises(ValueError):
            verify.check_bundle(self.output)
        path.write_bytes(original)
        (self.output / "extra").write_text("extra")
        with self.assertRaises(ValueError):
            verify.check_bundle(self.output)

    def test_output_never_reused(self):
        self.run_fixture()
        with self.assertRaises(FileExistsError):
            self.run_fixture()

    def test_unignored_output_refused(self):
        self.output = self.source / "evidence"
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_fixture()
        self.assertFalse(self.output.exists())

    def test_inventory_requires_unique_complete_diagnostic_set(self):
        for row in ({"tests": []}, {"tests": inventory()["tests"] * 2},
                    {"tests": inventory()["tests"][1:]}):
            with self.assertRaises(ValueError):
                verify.select_tests(row, True)

    def test_doctor_identity_mismatch_is_error_but_suite_still_runs(self):
        def execute(*args):
            result = self.fake_execute(*args)
            if args[1] == "doctor":
                path = self.output / "doctor/stdout.log"
                row = json.loads(path.read_text())
                row["binary_sha256"] = "wrong"
                path.write_text(json.dumps(row))
            return result
        report = self.run_fixture(execute=execute)
        self.assertEqual(report["environment"], "ERROR")
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["diagnostic_suite"], "PASS")


if __name__ == "__main__":
    unittest.main()
