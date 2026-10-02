"""Real subprocess observations, conservative delta and evidence integrity contracts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import agent_io as io


class AgentIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self.git("init", "-q")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "--allow-empty", "-qm", "initial")
        self.count = 0

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.source), *args], check=True, capture_output=True)

    def plan(self, script="print('observation')", task="code"):
        return {"schema": io.PLAN_SCHEMA, "task": task, "commands": [
            {"id": "check", "argv": [str(Path(sys.executable).resolve()), "-c", script], "timeout": 5}]}

    def run_plan(self, plan=None, scope=None):
        self.count += 1
        output = io.private_directory(self.root / f"run-{self.count}")
        io.run(plan or self.plan(), self.source, output, scope)
        return output

    def test_success_is_observation_not_acceptance(self):
        output = self.run_plan()
        result = io.view(output)
        self.assertEqual(result["status"], "RECORDED")
        self.assertEqual(result["steps"][0]["status"], "EXIT_OK")
        self.assertFalse(result["product_acceptance"])
        self.assertFalse(result["execution_authorized"])
        self.assertIsNone(result["token_usage"])
        self.assertEqual(io.read_raw(output, "check", "stdout.log", 0, 100)["text"], "observation\n")
        self.assertFalse((output / "report.md").exists())

    def test_failure_stops_later_commands_and_keeps_diagnostics(self):
        plan = self.plan("import sys; print('before'); print('FAIL errno=1', file=sys.stderr); sys.exit(7)")
        plan["commands"].append({"id": "later", "argv": [sys.executable, "-c", "raise Exception('must not run')"], "timeout": 5})
        output = self.run_plan(plan)
        result = io.view(output)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["steps"][0]["returncode"], 7)
        self.assertIn("errno=1", result["steps"][0]["stderr_preview"])
        self.assertEqual(result["steps"][1]["status"], "NOT_RUN")
        self.assertFalse((output / "later").exists())

    def test_timeout_keeps_partial_logs(self):
        plan = self.plan("import time; print('started', flush=True); time.sleep(30)")
        plan["commands"][0]["timeout"] = 1
        output = self.run_plan(plan)
        result = io.view(output)
        self.assertEqual(result["steps"][0]["reason"], "TIMEOUT")
        self.assertIn("started", io.read_raw(output, "check", "stdout.log", 0, 100)["text"])

    def test_missing_executable_is_recorded(self):
        plan = self.plan()
        plan["commands"][0]["argv"][0] = str(self.root / "missing")
        output = self.run_plan(plan)
        self.assertEqual(io.view(output)["steps"][0]["reason"], "LAUNCH_OR_CAPTURE_ERROR")

    def test_identical_delta_omits_only_unchanged_steps(self):
        first, second = self.run_plan(), self.run_plan()
        key = io.digest(first / "record.json")
        result = io.view(second, first, key)
        self.assertEqual(result["mode"], "DELTA")
        self.assertEqual(result["steps"], [])
        self.assertEqual(result["unchanged_steps"], 1)
        self.assertTrue(result["raw_required_before_effects"])

    def test_changed_output_in_delta(self):
        # Same argv, different external data: output hashes must still invalidate.
        external = self.root / "external.txt"
        external.write_text("old")
        plan = self.plan(f"from pathlib import Path; print(Path({str(external)!r}).read_text())")
        first = self.run_plan(plan)
        external.write_text("new")
        second = self.run_plan(plan)
        result = io.view(second, first, io.digest(first / "record.json"))
        self.assertEqual(result["mode"], "DELTA")
        self.assertEqual(len(result["steps"]), 1)

    def test_unknown_wrong_missing_and_corrupt_baselines_fall_back(self):
        first, second = self.run_plan(), self.run_plan()
        for path, revision in ((first, None), (None, "0" * 64), (first, "0" * 64),
                               (self.root / "missing", "0" * 64)):
            with self.subTest(path=path, revision=revision):
                result = io.view(second, path, revision)
                self.assertEqual(result["mode"], "FULL")
                self.assertIsNotNone(result["fallback"])
        key = io.digest(first / "record.json")
        (first / "check/stdout.log").write_text("tampered")
        self.assertEqual(io.view(second, first, key)["mode"], "FULL")

    def test_plan_source_or_scope_changes_force_full(self):
        first = self.run_plan()
        changed_plan = self.run_plan(self.plan("print('different')"))
        self.assertEqual(io.view(changed_plan, first, io.digest(first / "record.json"))["mode"], "FULL")
        (self.source / "new.txt").write_text("changed")
        second = self.run_plan()
        self.assertEqual(io.view(second, first, io.digest(first / "record.json"))["mode"], "FULL")
        third = self.run_plan(scope={"work": "another"})
        self.assertEqual(io.view(third, second, io.digest(second / "record.json"))["mode"], "FULL")

    def test_failed_baseline_never_suppresses_repeated_failure(self):
        plan = self.plan("raise SystemExit(3)")
        first, second = self.run_plan(plan), self.run_plan(plan)
        result = io.view(second, first, io.digest(first / "record.json"))
        self.assertEqual(result["mode"], "FULL")
        self.assertEqual(result["steps"][0]["status"], "FAILED")

    def test_current_tamper_extra_missing_and_symlink_rejected(self):
        for change in ("tamper", "extra", "missing", "symlink"):
            output = self.run_plan()
            path = output / "check/stdout.log"
            if change == "tamper":
                path.write_text("tampered")
            elif change == "extra":
                (output / "extra").write_text("extra")
            elif change == "missing":
                path.unlink()
            else:
                path.unlink()
                path.symlink_to(self.source)
            with self.subTest(change=change), self.assertRaises(ValueError):
                io.view(output)

    def test_byte_windows_and_diagnostic_omissions(self):
        output = self.run_plan(self.plan("import sys; print('x'*10000); print('a'*2000, file=sys.stderr)"))
        window = io.read_raw(output, "check", "stdout.log", 500, 20)
        self.assertEqual((window["bytes"], window["next_offset"], window["eof"]), (20, 520, False))
        result = io.view(output)
        self.assertEqual(result["steps"][0]["stderr_omitted_bytes"], 2001 - 512)
        self.assertLess(len(io.encoded(result)), result["raw_bytes"])
        for offset, count in ((-1, 20), (0, 0), (0, 65537)):
            with self.assertRaises(ValueError):
                io.read_raw(output, "check", "stdout.log", offset, count)
        with self.assertRaises(ValueError):
            io.read_raw(output, "../source", "stdout.log", 0, 10)

    def test_blocked_json_at_exit_zero_is_not_qa_pass(self):
        data = {"schema_version": 1, "action": "BLOCKED", "reason": "POLICY_REQUIRES_PERMISSION",
                "acceptance_verified": False, "execution_authorized": False, "requirements": ["must read"]}
        output = self.run_plan(self.plan(f"print({json.dumps(data)!r})"), scope={"work": "fixture"})
        observed = io.view(output)["steps"][0]["observed"]
        self.assertEqual(observed["fields"]["action"], "BLOCKED")
        self.assertIn("requirements", observed["omitted_fields"])
        self.assertFalse(io.view(output)["product_acceptance"])

    def test_unknown_json_schema_requires_raw(self):
        for data in ('{"schema_version":2}', '{"schema_version":1,"schema_version":1}', 'not JSON'):
            output = self.run_plan(self.plan(f"print({data!r})"), scope={"work": "fixture"})
            self.assertEqual(io.view(output)["steps"][0]["observed"]["projection"], "UNSUPPORTED_READ_RAW")

    def test_source_mutation_recorded_not_declared_verified(self):
        output = self.run_plan(self.plan("from pathlib import Path; Path('new.txt').write_text('change')"))
        self.assertTrue(io.view(output)["source_changed"])
        self.assertFalse(io.view(output)["product_acceptance"])

    def test_incomplete_source_capture_retains_started_evidence(self):
        with patch.object(io, "source_identity", side_effect=ValueError("unsupported")):
            output = self.run_plan()
        self.assertEqual(io.view(output)["status"], "INCOMPLETE")
        self.assertTrue((output / "started.json").is_file())

    def test_readonly_observer_plan_has_no_mutating_operations(self):
        output = io.private_directory(self.root / "observer")
        plan = io.observe_plan(Path(sys.executable), self.source, "work", "selection", output, "docs")
        self.assertEqual([c["id"] for c in plan["commands"]], ["work-record", "next", "completion"])
        self.assertEqual(plan["commands"][0]["argv"][3:5], ["work", "record"])
        self.assertEqual([io.read_json(Path(c["argv"][-1]))["operation"] for c in plan["commands"][1:]],
                         ["next", "resume"])
        self.assertEqual(plan["commands"][-1]["argv"][1:4], ["--output-mode", "full", "completion"])

    def test_plan_validation_unknown_fields_duplicates_relative_timeout(self):
        bad = []
        p = self.plan(); p["extra"] = True; bad.append(p)
        p = self.plan(); p["commands"].append(copy.deepcopy(p["commands"][0])); bad.append(p)
        p = self.plan(); p["commands"][0]["argv"][0] = "python"; bad.append(p)
        p = self.plan(); p["commands"][0]["timeout"] = True; bad.append(p)
        p = self.plan(); p["commands"][0]["id"] = "../bad"; bad.append(p)
        p = self.plan(); p["commands"] = []; bad.append(p)
        for value in bad:
            with self.subTest(plan=value), self.assertRaises(ValueError):
                io.validate_plan(value)

    def test_live_history_plan_requires_pinned_compatible_baseline(self):
        scope = {"work": "fixture", "query": "history-v2"}
        previous = {"scope": scope, "status": "RECORDED", "steps": [{"id": "history", "status": "EXIT_OK"}]}
        page = {"schema_version": 2, "work_id": "work", "cursor": {"opaque": "native validates"}}
        for i, (revision, old, raw, expected) in enumerate((
            ("a" * 64, previous, page, page["cursor"]),
            (None, previous, page, {"invalid_baseline": True}),
            ("b" * 64, previous, page, {"invalid_baseline": True}),
            ("a" * 64, {**previous, "status": "FAILED"}, page, {"invalid_baseline": True}),
            ("a" * 64, {**previous, "scope": {}}, page, {"invalid_baseline": True}),
            ("a" * 64, previous, [], {"invalid_baseline": True}),
        )):
            output = io.private_directory(self.root / f"history-{i}")
            with patch.object(io, "load_bundle", return_value=(old, "a" * 64)), patch.object(io, "read_json", return_value=raw):
                plan = io.history_plan(Path(sys.executable), self.source, "work", output, "code", scope,
                                       self.root / "baseline", revision)
            self.assertEqual(io.read_json(output / "history-request.json")["cursor"], expected)
            self.assertEqual(plan["commands"][0]["argv"][3:5], ["work", "history"])

    def test_live_history_missing_and_corrupt_baselines_fall_back(self):
        for i, error in enumerate((OSError("missing"), io.ObservationError("INTEGRITY"))):
            output = io.private_directory(self.root / f"missing-history-{i}")
            with patch.object(io, "load_bundle", side_effect=error):
                io.history_plan(Path(sys.executable), self.source, "work", output, "code", {},
                                self.root / "missing", "a" * 64)
            self.assertEqual(io.read_json(output / "baseline.json")["status"],
                             "BASELINE_UNAVAILABLE_OR_INCOMPATIBLE")
            self.assertEqual(io.read_json(output / "history-request.json")["cursor"], {"invalid_baseline": True})

    def test_report_is_deterministic_readonly_and_not_created_during_run(self):
        output = self.run_plan()
        before = io.file_inventory(output)
        text = io.report(output)
        self.assertEqual(text, io.report(output))
        self.assertIn(io.digest(output / "record.json"), text)
        self.assertEqual(before, io.file_inventory(output))

    def test_legacy_record_has_explicit_no_consolidation_fallback(self):
        plan = self.plan()
        plan["commands"][0]["id"] = "work-record"
        output = self.run_plan(plan)
        with self.assertRaises(io.ObservationError) as raised:
            io.work_record(output)
        self.assertEqual(raised.exception.code, "WORK_RECORD")
        self.assertNotIn("## Work Record", io.report(output))

    def test_consolidated_views_reuse_record_and_reject_tamper(self):
        value = {"schema": "golem.work-record.v1", "schema_version": 1,
                 "derived_only": True, "execution_authorized": False, "acceptance_verified": False,
                 "document_head": "a" * 64, "agent_head": "b" * 64,
                 "work_specification": {"requirements": ["preserve"]},
                 "assessments": {"c" * 64: {"note": "# untrusted\\nFAIL"}},
                 "documents": [{"metadata": {}, "assessment_ref": "c" * 64}],
                 "status": {"sequence": 0, "lease_live": False}, "journal": []}
        plan = self.plan(f"print({json.dumps(value)!r})")
        plan["commands"][0]["id"] = "work-record"
        output = self.run_plan(plan, scope={"work": "fixture"})
        before = io.file_inventory(output)
        full = io.work_record(output)
        for section in ("assessments", "documents", "status", "journal"):
            self.assertEqual(io.work_record(output, section)["value"], value[section])
            self.assertEqual(io.work_record(output, section)["sha256"], full["sha256"])
        self.assertEqual(before, io.file_inventory(output))
        self.assertEqual(io.report(output), io.report(output))
        self.assertIn("    {", io.report(output))
        (output / "work-record/stdout.log").write_text("{}")
        with self.assertRaises(io.ObservationError):
            io.work_record(output)

    def test_consolidation_rejects_dangling_and_unreferenced_assessments(self):
        value = {"schema": "golem.work-record.v1", "schema_version": 1,
                 "derived_only": True, "execution_authorized": False, "acceptance_verified": False,
                 "document_head": "a" * 64, "agent_head": "b" * 64,
                 "work_specification": {}, "assessments": {}, "documents": [],
                 "status": {"sequence": 0, "lease_live": False}, "journal": []}
        io.validate_work_record(value)
        for change in ({"documents": [{"metadata": {}, "assessment_ref": "f" * 64}]},
                       {"assessments": {"f" * 64: {}}}, {"schema": "future"},
                       {"execution_authorized": True}, {"status": {}},
                       {"documents": [{"metadata": {"assessment": {}}}]}):
            with self.subTest(change=change), self.assertRaises(io.ObservationError):
                io.validate_work_record({**value, **change})

    def test_private_directory_never_overwrites(self):
        output = self.run_plan()
        with self.assertRaises(FileExistsError):
            io.private_directory(output)
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)

    def test_measurement_is_exact_not_a_token_estimate(self):
        output = self.run_plan()
        metrics = io.measure(output)
        self.assertEqual(metrics["view_bytes"], len(io.encoded(io.view(output))))
        self.assertEqual(metrics["byte_difference"], metrics["raw_bytes"] - metrics["view_bytes"])
        self.assertLess(metrics["byte_difference"], 0)  # Short output can expand.
        self.assertIsNone(metrics["token_usage"])
        self.assertIsNone(metrics["agent_success"])

    def test_recorder_changes_invalidate_recording(self):
        before = io.producer()
        after = {**before, "python": "changed"}
        with patch.object(io, "producer", side_effect=[before, after]):
            output = self.run_plan()
        self.assertEqual(io.view(output)["status"], "INCOMPLETE")
        self.assertEqual(io.view(output)["diagnostic"], "RECORDER_CHANGED")

    def test_repository_subdirectory_is_incomplete(self):
        subdir = self.source / "subdir"
        subdir.mkdir()
        output = io.private_directory(self.root / "subdir-output")
        io.run(self.plan(), subdir, output)
        result = io.view(output)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["diagnostic"], "REPOSITORY_ROOT")

    def test_cli_rejects_in_source_output_and_explains_recovery(self):
        plan = self.root / "plan.json"
        plan.write_bytes(io.encoded(self.plan()))
        output = self.source / "evidence"
        result = subprocess.run([sys.executable, str(Path(io.__file__).resolve()), "run",
                                 "--cwd", str(self.source), "--plan", str(plan), "--output", str(output)],
                                capture_output=True)
        self.assertEqual(result.returncode, 2)
        error = json.loads(result.stderr)
        self.assertEqual(error["code"], "OUTPUT_LOCATION")
        self.assertIn("outside", error["next_action"])
        self.assertFalse(output.exists())

    def test_cli_roundtrip_and_guides_exist(self):
        script = Path(io.__file__).resolve()
        plan = self.root / "plan.json"
        plan.write_bytes(io.encoded(self.plan()))
        output = self.root / "cli-output"
        result = subprocess.run([sys.executable, str(script), "run", "--cwd", str(self.source),
                                 "--plan", str(plan), "--output", str(output)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "RECORDED")
        for task, docs in io.ROUTES.items():
            for name in docs + io.COMMON:
                # Source export deliberately omits docs; validate where present.
                root = script.parents[1] / "docs"
                if root.is_dir():
                    self.assertTrue((root / name).is_file(), (task, name))


if __name__ == "__main__":
    unittest.main()
