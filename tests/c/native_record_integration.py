"""Native recording contract, host execution required for supervisor paths."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI, HELPER, SUPERVISOR, SOURCE = map(Path, sys.argv[1:5])
STREAM = Path(sys.argv[5])
sys.path.insert(0, str(SOURCE / "tools"))
from native_record import check
from execution_record import capture, check as check_execution
sys.argv[1:] = []


class NativeRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = {**os.environ, "GOLEM_RECORD_ROOT": str(self.root)}

    def tearDown(self):
        self.tmp.cleanup()

    def records(self):
        return [check(p) for p in self.root.iterdir() if p.is_dir()]

    def test_cli_success_failure_and_no_output_change(self):
        for args in (["--version"], ["invalid-command"]):
            plain = subprocess.run([CLI, *args], capture_output=True,
                                   env={k: v for k, v in os.environ.items() if not k.startswith("GOLEM_RECORD_")})
            recorded = subprocess.run([CLI, *args], capture_output=True, env=self.env)
            self.assertEqual((plain.returncode, plain.stdout, plain.stderr),
                             (recorded.returncode, recorded.stdout, recorded.stderr))
        self.assertEqual(len(self.records()), 2)

    def test_c_api_nested_and_streams(self):
        subprocess.run([HELPER, "call", self.root], check=True, capture_output=True,
                       env={k: v for k, v in os.environ.items() if not k.startswith("GOLEM_RECORD_")})
        records = self.records()
        self.assertEqual(len(records), 2)
        parent = next(r for r in records if r["kind"] == "c_api")
        child = next(r for r in records if r["kind"] == "process")
        self.assertEqual(child["parent"], parent["id"])
        self.assertTrue(child["result"]["reaped"])
        self.assertEqual((self.root / child["id"] / "stdout.log").read_bytes(), b"raw out\n")
        self.assertEqual((self.root / child["id"] / "stderr.log").read_bytes(), b"raw error\n")

    def test_supervisor_error_paths(self):
        for mode in ("echo", "exit", "signal", "hang", "overflow", "stderr", "cancel"):
            subprocess.run([SUPERVISOR, mode], env=self.env, check=True, capture_output=True)
        records = self.records()
        self.assertTrue(any(r["result"]["timed_out"] for r in records))
        self.assertTrue(any(r["result"]["exit_code"] == 17 for r in records))
        self.assertTrue(any(r["result"]["signal_number"] for r in records))

    def test_bulk_and_streamed_preserve_callbacks(self):
        subprocess.run([STREAM], env=self.env, check=True, capture_output=True)
        records = self.records()
        self.assertTrue(any(r["result"].get("stdout_bytes") == 524288 for r in records))
        processes = [r for r in records if r["kind"] == "process"]
        rejected = [r for r in records if r["kind"] == "c_api_auto"]
        self.assertEqual(len(records), len(processes) + len(rejected))
        self.assertTrue(processes)
        self.assertTrue(all(r["result"]["reaped"] for r in processes))
        self.assertTrue(rejected)
        for record in rejected:
            self.assertEqual(record["result"]["operation_status"], 1)
            self.assertFalse(record["result"]["spawned"])
            self.assertFalse(record["result"]["reaped"])

    def test_bad_root_prevents_dispatch(self):
        target = self.root / "must-not-exist"
        result = subprocess.run([CLI, "init", target], capture_output=True,
                                env={**self.env, "GOLEM_RECORD_ROOT": str(self.root / "missing")})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target.exists())

    def test_private_and_symlink_root(self):
        public = self.root / "public"
        public.mkdir(mode=0o755)
        link = self.root / "link"
        link.symlink_to(self.root)
        for root in (public, link):
            result = subprocess.run([CLI, "--version"], capture_output=True,
                                    env={**self.env, "GOLEM_RECORD_ROOT": str(root)})
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"")

    def test_crash_has_no_completion(self):
        result = subprocess.run([HELPER, "crash", self.root], capture_output=True)
        self.assertLess(result.returncode, 0)
        record = next(self.root.iterdir())
        self.assertTrue((record / "started.json").exists())
        with self.assertRaises(OSError):
            check(record)

    def test_concurrency_and_scope_order(self):
        def run(_):
            subprocess.run([HELPER, "order", self.root], check=True, capture_output=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(run, range(8)))
        self.assertEqual(len(self.records()), 16)

    def test_finish_failure_does_not_erase_successful_operation(self):
        result = subprocess.run([HELPER, "finish-fail", self.root], capture_output=True, check=True)
        recording, operation = map(int, result.stdout.split())
        self.assertNotEqual(recording, 0)
        self.assertEqual(operation, 0)
        record = next(self.root.iterdir())
        self.assertTrue((record / "started.json").exists())
        with self.assertRaises(OSError):
            check(record)

    def test_tamper_rejected(self):
        subprocess.run([HELPER, "reject", self.root], check=True, capture_output=True)
        self.assertNotEqual(self.records()[0]["result"]["operation_status"], 0)
        record = next(self.root.iterdir())
        (record / "result.json").write_text("{}")
        with self.assertRaises(ValueError):
            check(record)

    def test_thread_isolation_and_record_failure(self):
        subprocess.run([HELPER, "threads", self.root], check=True, capture_output=True)
        self.assertEqual(len(self.records()), 4)
        self.assertTrue(all(r["parent"] == "" for r in self.records()))
        subprocess.run([HELPER, "record-fail", self.root], check=True, capture_output=True)
        failed = next(r for r in self.records() if r["result"]["state"] == "RECORDING_FAILED")
        self.assertNotEqual(failed["result"]["recording_status"], 0)
        self.assertNotEqual(failed["result"]["operation_status"], 0)

    def test_invalid_outcome_rejected_even_with_matching_hashes(self):
        subprocess.run([HELPER, "reject", self.root], check=True, capture_output=True)
        record = next(self.root.iterdir())
        result = json.loads((record / "result.json").read_bytes())
        result["operation_status"] = True
        data = json.dumps(result).encode()
        (record / "result.json").write_bytes(data)
        manifest = json.loads((record / "manifest.json").read_bytes())
        manifest["result.json"] = hashlib.sha256(data).hexdigest()
        (record / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            check(record)

    def test_python_bridge_and_source_identity(self):
        result = capture([CLI, "--version"], self.root, 30, cwd=SOURCE)
        self.assertEqual(result["native_recording"], "RECORDED")
        self.assertEqual(check_execution(self.root)["integrity"], "PASS")
        record = next((self.root / "native").iterdir())
        start = json.loads((record / "started.json").read_bytes())
        self.assertEqual(start["source_manifest_before"]["status_code"], 0)
        self.assertIn("sha256", start["source_manifest_before"])
        (record / "started.json").write_text("{}")
        with self.assertRaises(ValueError):
            check_execution(self.root)


unittest.main()
