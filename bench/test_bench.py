"""Functional tests, never speed gates on shared CI runners."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import benchmark as bench

BINARY = Path(sys.argv.pop(1)).resolve()


def fixture():
    env = {key: "test" for key in bench.ENV_KEYS}
    env.update(configuration="Release", sanitized=False, system="test", release="test",
               architecture="test", cpu="test", storage_device="test", environment_id="synthetic")
    metrics = {name: {"bytes_per_op": 64, "events_per_op": 1, "durable": name == "journal_append_fsync",
                      "samples": [{"iterations": 10, "elapsed_ns": 1000} for _ in range(7)]}
               for name in bench.METRICS}
    return {"schema": 1, "workload_version": 1, "mode": "baseline", "environment": env,
            "settings": {"sample_count": 7, "target_ms": 50}, "metrics": metrics}


class BenchmarkTests(unittest.TestCase):
    def test_comparison(self):
        baseline = fixture()
        self.assertEqual(bench.compare(baseline, copy.deepcopy(baseline))["status"], "pass")
        current = copy.deepcopy(baseline)
        for sample in current["metrics"]["json_decode"]["samples"]:
            sample["elapsed_ns"] = 1200
        self.assertEqual(bench.compare(baseline, current)["status"], "pass")
        for sample in current["metrics"]["json_decode"]["samples"]:
            sample["elapsed_ns"] = 1201
        self.assertEqual(bench.compare(baseline, current)["status"], "regression")

    def test_noise(self):
        baseline, current = fixture(), fixture()
        for sample, duration in zip(current["metrics"]["digest_4k"]["samples"], (500, 600, 700, 1000, 1400, 1500, 1700)):
            sample["elapsed_ns"] = duration
        self.assertEqual(bench.compare(baseline, current)["status"], "inconclusive")

    def test_mismatches(self):
        for key, value in (("compiler", "other"), ("sanitized", True), ("configuration", "Debug"), ("environment_id", "different")):
            current = fixture(); current["environment"][key] = value
            with self.assertRaises(ValueError): bench.compare(fixture(), current)
        current = fixture(); current["mode"] = "smoke"
        with self.assertRaises(ValueError): bench.compare(fixture(), current)
        current = fixture(); current["metrics"]["json_encode"]["bytes_per_op"] += 1
        with self.assertRaises(ValueError): bench.compare(fixture(), current)
        current = fixture(); del current["metrics"]["digest_4k"]
        with self.assertRaises(ValueError): bench.compare(fixture(), current)
        current = fixture(); current["settings"]["target_ms"] = 25
        with self.assertRaises(ValueError): bench.compare(fixture(), current)

    def test_bad_samples(self):
        for value in (0, -1, True, float("nan"), float("inf"), "100"):
            current = fixture(); current["metrics"]["digest_4k"]["samples"][0]["elapsed_ns"] = value
            with self.assertRaises(ValueError): bench.validate(current)
        current = fixture(); current["metrics"]["digest_4k"]["samples"].pop()
        with self.assertRaises(ValueError): bench.validate(current)
        for text in ('{"schema":1,"schema":2}', '{"x":NaN}'):
            with self.assertRaises(ValueError): bench.load(text)
        self.assertFalse(bench.positive(10**1000))
        current = fixture(); current["schema"] = True
        with self.assertRaises(ValueError): bench.validate(current)

    def test_projection(self):
        text = bench.projection(fixture())
        self.assertIn("MiB/s", text)
        self.assertIn("10000000.0", text)
        self.assertEqual(len(text.splitlines()), len(bench.METRICS) + 2)

    def test_thresholds(self):
        thresholds = bench.load(Path(__file__).with_name("thresholds.json").read_text())
        self.assertEqual(thresholds, bench.DEFAULT_THRESHOLDS)
        for bad in ({}, {**thresholds, "digest_4k": -1}, {**thresholds, "digest_4k": True}):
            with self.assertRaises(ValueError): bench.compare(fixture(), fixture(), bad)
        for bad in (0, float("nan"), 2):
            with self.assertRaises(ValueError): bench.compare(fixture(), fixture(), max_noise=bad)

    def test_runner_and_collection(self):
        with tempfile.TemporaryDirectory(prefix="golem-bench-test-") as directory:
            root = Path(directory)
            report = bench.collect(BINARY, root, "test-only", 3, 1, smoke=True)
            self.assertEqual(set(report["metrics"]), set(bench.METRICS))
            self.assertEqual(list(root.iterdir()), [])
            target = root / "report.json"
            bench.write_new(target, report)
            self.assertEqual(bench.read(target), report)
            with self.assertRaises(FileExistsError): bench.write_new(target, report)
            for metric, count in (("unknown", "1"), ("digest_4k", "0"), ("digest_4k", "-1"),
                                  ("digest_4k", "1000001"), ("digest_4k", "1junk"),
                                  ("journal_append_fsync", "4097")):
                result = subprocess.run([str(BINARY), metric, count, directory], capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 2)

    def test_cli_exit_codes(self):
        script = Path(__file__).with_name("benchmark.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); a = root / "a.json"; b = root / "b.json"
            a.write_text(json.dumps(fixture())); b.write_text(json.dumps(fixture()))
            result = subprocess.run([sys.executable, str(script), "compare", str(a), str(b)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0)
            current = fixture()
            for sample in current["metrics"]["digest_4k"]["samples"]: sample["elapsed_ns"] = 1500
            b.write_text(json.dumps(current))
            result = subprocess.run([sys.executable, str(script), "compare", str(a), str(b)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 1)
            b.write_text('{}')
            result = subprocess.run([sys.executable, str(script), "compare", str(a), str(b)], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
