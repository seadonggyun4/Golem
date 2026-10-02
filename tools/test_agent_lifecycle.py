"""Lifecycle boundaries, typed result gates and no replay of uncertain effects."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import agent_lifecycle as life


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        life.records.git(self.repo, "init", "-q")
        life.records.git(self.repo, "-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                         "-c", "commit.gpgsign=false", "commit", "--allow-empty", "-qm", "fixture")
        self.binary = str(Path(sys.executable).resolve())
        self.binary_hash = life.records.digest(Path(self.binary))
        self.store = self.root / "store"

    def plan(self):
        phases = {}
        for phase in life.PHASES:
            marker = self.root / phase
            script = f"from pathlib import Path; Path({str(marker)!r}).open('x').close(); print('{{\"state\":\"OK\"}}')"
            phases[phase] = [{"id": phase, "argv": [self.binary, "-c", script], "timeout": 10,
                              "executable_sha256": self.binary_hash,
                              "expect": [{"path": ["state"], "equals": "OK"}]}]
        return {"schema": life.SCHEMA, "run_id": "attempt-1", "cwd": str(self.repo),
                "inputs": {}, "phases": phases}

    def execute(self, plan=None):
        plan = plan or self.plan()
        return life.run(plan, self.store, life.io.identity(plan))

    def test_success_and_duplicate_are_one_execution(self):
        plan = self.plan()
        first = self.execute(plan)
        self.assertEqual(first["status"], "FINISHED")
        self.assertTrue(all(r["status"] == "CHECKS_PASSED" for r in first["steps"]))
        self.assertFalse(first["product_acceptance"])
        self.assertEqual(self.execute(plan), first)
        self.assertEqual(life.inspect(self.store / plan["run_id"]), first)
        for phase in life.PHASES:
            self.assertTrue((self.root / phase).exists())
            self.assertEqual(life.records.check(self.store / plan["run_id"] / phase)["integrity"], "PASS")

    def test_exit_zero_blocked_prevents_later_phases(self):
        plan = self.plan()
        plan["phases"]["prepare"][0]["argv"][-1] = 'print(\'{"state":"PENDING_APPROVAL"}\')'
        result = self.execute(plan)
        self.assertEqual(result["status"], "STOPPED")
        self.assertEqual([r["status"] for r in result["steps"]], ["BLOCKED", "NOT_RUN", "NOT_RUN"])
        self.assertFalse((self.root / "execute").exists())

    def test_execute_failure_does_not_finalize_or_replay(self):
        plan = self.plan()
        plan["phases"]["execute"][0]["argv"][-1] = "raise SystemExit(7)"
        result = self.execute(plan)
        self.assertEqual(result["steps"][1]["returncode"], 7)
        self.assertFalse((self.root / "finalize").exists())
        self.assertEqual(self.execute(plan), result)

    def test_typed_checks_and_missing_paths(self):
        checks = [{"path": ["receipt", "verified"], "equals": True}]
        self.assertTrue(life.check_result({"receipt": {"verified": True}}, checks))
        for value in ({}, {"receipt": []}, {"receipt": {"verified": 1}}):
            self.assertFalse(life.check_result(value, checks))

    def test_review_and_schema_fail_before_dispatch(self):
        plan = self.plan()
        with self.assertRaises(ValueError):
            life.run(plan, self.store, "0" * 64)
        for change in ({"schema": "v2"}, {"run_id": "../bad"}, {"phases": {}}, {"extra": True}):
            with self.assertRaises(ValueError):
                life.validate({**plan, **change})
        invalid = copy.deepcopy(plan)
        invalid["phases"]["execute"][0]["expect"] = []
        with self.assertRaises(ValueError):
            life.validate(invalid)
        self.assertFalse(self.store.exists())

    def test_all_executable_pins_preflight_before_prepare(self):
        plan = self.plan()
        plan["phases"]["finalize"][0]["executable_sha256"] = "0" * 64
        result = self.execute(plan)
        self.assertEqual(result["status"], "STOPPED")
        self.assertFalse((self.root / "prepare").exists())

    def test_input_drift_stops_next_dispatch(self):
        pinned = self.root / "request.json"
        pinned.write_text("original")
        plan = self.plan()
        plan["inputs"] = {str(pinned): life.records.digest(pinned)}
        plan["phases"]["prepare"][0]["argv"][-1] = (
            f"from pathlib import Path; Path({str(pinned)!r}).write_text('changed'); print('{{\"state\":\"OK\"}}')")
        result = self.execute(plan)
        self.assertEqual(result["status"], "STOPPED")
        self.assertFalse((self.root / "execute").exists())

    def test_interrupted_dispatch_requires_reconciliation(self):
        plan = self.plan()
        with patch.object(life.records, "capture", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.execute(plan)
        with patch.object(life.records, "capture") as launch:
            result = self.execute(plan)
            self.assertEqual(result["status"], "RECONCILE_REQUIRED")
            launch.assert_not_called()

    def test_durable_dispatch_failure_prevents_launch(self):
        original = life.records.save
        def save(path, data):
            if path.name.endswith("-dispatch.json"):
                raise OSError("disk full")
            return original(path, data)
        with patch.object(life.records, "save", side_effect=save), patch.object(life.records, "capture") as launch:
            result = self.execute()
            self.assertEqual(result["status"], "STOPPED")
            launch.assert_not_called()

    def test_terminal_write_failure_never_reruns_effects(self):
        original = life.records.save
        def save(path, data):
            if path.name == "result.json" and path.parent.name == "attempt-1":
                raise OSError("disk full")
            return original(path, data)
        plan = self.plan()
        with patch.object(life.records, "save", side_effect=save):
            with self.assertRaises(OSError):
                self.execute(plan)
        self.assertTrue((self.root / "finalize").exists())
        self.assertEqual(self.execute(plan)["status"], "RECONCILE_REQUIRED")

    def test_run_identity_conflict_and_corruption(self):
        plan = self.plan()
        self.execute(plan)
        changed = copy.deepcopy(plan)
        changed["phases"]["execute"][0]["timeout"] += 1
        with self.assertRaises(ValueError):
            self.execute(changed)
        (self.store / "attempt-1" / "execute" / "stdout.log").write_text("corrupt")
        with self.assertRaises(ValueError):
            self.execute(plan)

    def test_concurrent_same_id_has_one_dispatch_owner(self):
        plan = self.plan()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.execute(plan), range(2)))
        self.assertTrue(any(r["status"] == "FINISHED" for r in results))
        self.assertTrue(all(r["status"] in ("FINISHED", "RECONCILE_REQUIRED") for r in results))
        self.assertEqual(life.inspect(self.store / "attempt-1")["status"], "FINISHED")

    def test_real_controller_kill_never_replays(self):
        plan = self.plan()
        plan["phases"]["prepare"][0]["argv"][-1] = (
            "import os,signal; os.kill(os.getppid(),signal.SIGKILL); os._exit(0)")
        request = self.root / "kill-plan.json"
        request.write_text(json.dumps(plan))
        result = subprocess.run([sys.executable, life.__file__, "run", str(request),
                                 "--store", str(self.store), "--reviewed-plan", life.io.identity(plan)],
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, -signal.SIGKILL, result.stderr)
        self.assertTrue((self.store / "attempt-1" / "00-dispatch.json").exists())
        self.assertEqual(self.execute(plan)["status"], "RECONCILE_REQUIRED")
        self.assertFalse((self.root / "execute").exists())

    def test_timeout_and_invalid_json_stop_before_execute(self):
        for index, script in enumerate(("import time; time.sleep(10)", "print('not-json')")):
            plan = self.plan()
            plan["run_id"] = f"attempt-{index}"
            plan["phases"]["prepare"][0]["argv"][-1] = script
            plan["phases"]["prepare"][0]["timeout"] = 1
            result = self.execute(plan)
            self.assertEqual(result["status"], "STOPPED")
            self.assertFalse((self.root / "execute").exists())

    def test_unsafe_store_and_symlink_are_rejected(self):
        plan = self.plan()
        with self.assertRaises(ValueError):
            life.run(plan, self.repo / "evidence", life.io.identity(plan))
        self.store.symlink_to(self.repo, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.execute(plan)

    def test_cli_validation_and_inspection(self):
        plan = self.plan()
        request = self.root / "plan.json"
        request.write_text(json.dumps(plan))
        cli = Path(life.__file__)
        result = subprocess.run([sys.executable, str(cli), "validate", str(request)],
                                capture_output=True, check=True, timeout=30)
        self.assertEqual(json.loads(result.stdout)["plan_sha256"], life.io.identity(plan))


if __name__ == "__main__":
    unittest.main()
