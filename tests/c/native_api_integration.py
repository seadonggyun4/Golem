"""Direct C API recording, without caller-provided record_call wrappers."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from native_api_inventory import CORE_APIS as APIS, EXTENDED_APIS, LIFECYCLE_APIS

HELPER, SOURCE = map(Path, sys.argv[1:3])
LIFECYCLE = Path(sys.argv[3])
sys.path.insert(0, str(SOURCE / "tools"))
from native_record import check
sys.argv[1:] = []

class AutoAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / "records"
        self.root.mkdir(mode=0o700)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GOLEM_RECORD_")}
        self.env["GOLEM_RECORD_ROOT"] = str(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def run_helper(self, mode, target=None, env=None):
        subprocess.run([HELPER, mode, target or self.root], env=env or self.env,
                       check=True, capture_output=True, timeout=60)

    def records(self):
        return [(check(p), json.loads((p / "started.json").read_bytes())) for p in self.root.iterdir()]

    def test_all_command_boundaries_and_private_inputs(self):
        self.run_helper("reject")
        records = self.records()
        self.assertEqual({s["operation"] for _, s in records}, APIS)
        self.assertEqual(len(records), len(APIS))
        for r, s in records:
            self.assertEqual(r["kind"], "c_api_auto")
            self.assertEqual(r["result"]["operation_status"], 1)
            self.assertEqual(r["result"]["exit_code"], -1)
            self.assertEqual(s["argv"], [])
            self.assertNotIn("private-request-body", json.dumps(s))
            self.assertNotIn("private-key", json.dumps(s))

    def test_disabled(self):
        self.run_helper("reject", env={**self.env, "GOLEM_RECORD_ROOT": ""})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_extended_boundaries(self):
        self.run_helper("extended")
        records = self.records()
        self.assertEqual({s["operation"] for _, s in records}, EXTENDED_APIS)
        # Admission's convenience entry point calls its diagnostic entry point.
        self.assertEqual(len(records), len(EXTENDED_APIS) + 1)
        for r, s in records:
            self.assertEqual(r["result"]["recording_status"], 0)
            self.assertEqual(s["argv"], [])

    def test_lifecycle_boundaries(self):
        self.run_helper("lifecycle")
        records = self.records()
        self.assertEqual({s["operation"] for _, s in records}, LIFECYCLE_APIS)
        self.assertEqual(len(records), len(LIFECYCLE_APIS))
        self.assertTrue(all(r["result"]["recording_status"] == 0 for r, _ in records))

    def test_lifecycle_controls_and_durability_without_audit_storage(self):
        subprocess.run([LIFECYCLE, self.base], env=self.env, check=True,
                       capture_output=True, timeout=30)

    def test_required_controls_survive_recording_failure(self):
        self.run_helper("required", env={**self.env, "GOLEM_RECORD_ROOT": str(self.root / "missing")})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_real_commit_and_invalid_root_blocks_commit(self):
        work = self.base / "work"
        work.mkdir()
        self.run_helper("success", work)
        self.assertEqual(self.records()[0][0]["result"]["operation_status"], 0)
        blocked = self.base / "blocked"
        blocked.mkdir()
        self.run_helper("blocked", blocked, {**self.env, "GOLEM_RECORD_ROOT": str(self.root / "missing")})
        self.assertEqual(list(blocked.iterdir()), [])

    def test_inherited_explicit_scope(self):
        self.run_helper("nested", env={k: v for k, v in self.env.items() if not k.startswith("GOLEM_RECORD_")})
        records = self.records()
        parent = next(r for r, s in records if s["kind"] == "host")
        children = [r for r, s in records if s["kind"] == "c_api_auto"]
        self.assertEqual(len(children), len(APIS))
        self.assertTrue(all(r["parent"] == parent["id"] for r in children))

    def test_thread_handoff_outlives_parent_scope(self):
        self.run_helper("handoff", env={k: v for k, v in self.env.items() if not k.startswith("GOLEM_RECORD_")})
        records = self.records()
        parent = next(r for r, s in records if s["kind"] == "host")
        children = [r for r, s in records if s["kind"] == "c_api_auto"]
        self.assertEqual(len(children), len(APIS))
        self.assertTrue(all(r["parent"] == parent["id"] for r in children))

    def test_supervisor_rejections_are_observed(self):
        self.run_helper("supervisor-reject")
        records = self.records()
        self.assertEqual(len(records), 4)
        self.assertTrue(all(r["result"]["operation_status"] == 1 and not r["result"]["spawned"] for r, _ in records))

    def test_start_failure_prevents_effect(self):
        self.run_helper("begin-fail", env={**self.env, "GOLEM_RECORD_ROOT": str(self.root / "missing")})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_finish_failure_is_not_rollback(self):
        for mode in ("finish-fail", "operation-fail", "nested-fail"):
            with self.subTest(mode=mode):
                root = self.base / mode
                root.mkdir(mode=0o700)
                self.run_helper(mode, root, {**self.env, "GOLEM_RECORD_ROOT": str(root)})
                records = list(root.iterdir())
                incomplete = [p for p in records if not (p / "manifest.json").exists()]
                self.assertEqual(len(incomplete), 1)
                record = incomplete[0]
                self.assertTrue((record / "started.json").exists())
                with self.assertRaises(OSError):
                    check(record)
                if mode == "nested-fail":
                    self.assertEqual(len(records), 2)
                    parent = next(p for p in records if p != record)
                    result = check(parent)["result"]
                    self.assertEqual(result["operation_status"], 0)
                    self.assertNotEqual(result["recording_status"], 0)
                    self.assertEqual(result["state"], "RECORDING_FAILED")

    def test_thread_local_outcomes_and_parents(self):
        self.run_helper("threads")
        records = self.records()
        self.assertEqual(len(records), 2 * len(APIS))
        self.assertTrue(all(not r["parent"] for r, _ in records))

unittest.main()
