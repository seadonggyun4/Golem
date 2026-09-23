"""Bounded metadata probe and read-only descriptor CLI, no real agents invoked."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

CLI, HELPER = map(lambda p: Path(p).resolve(), sys.argv[1:3])
sys.argv[1:] = []


class DescriptorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="golem-descriptor-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def cli(self, *args, ok=True):
        result = subprocess.run([str(CLI), "adapter", *map(str, args)], capture_output=True,
                                env={**os.environ, "GOLEM_TEST_SECRET": "do-not-inherit"}, timeout=15)
        self.assertEqual(result.returncode == 0, ok, result.stderr.decode())
        return result

    def describe(self, value, ok=True):
        file = self.root / "descriptor.json"
        file.write_text(json.dumps(value))
        return self.cli("describe", file, ok=ok)

    def test_readonly_current(self):
        for agent in ("codex", "claude"):
            output = json.loads(self.cli("describe", "--current", agent).stdout)
            self.assertEqual(output["session_id"], "")
            self.assertEqual(output["adapter_version"], "")
            for key in ("inputs_known", "features_known", "hidden_prompt_known", "sandbox", "effect"):
                self.assertEqual(output[key], 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_golden_and_legacy(self):
        value = json.loads(self.cli("describe", "noop").stdout)
        self.assertEqual(value["simulation"], 2)
        self.assertEqual(value["features_known"], 0)
        canonical = self.describe(value).stdout.strip()
        self.assertEqual(canonical, json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
        legacy = self.cli("noop", "probe").stdout
        self.assertEqual(legacy.strip(), b'{"type":"1","version":"1","adapter_id":"local.noop","stages":"63","effect":"1","simulation":"1"}')
        packed = subprocess.run([CLI, "adapter", "convert", "json", "msgpack"], input=legacy,
                                capture_output=True, check=True).stdout
        back = subprocess.run([CLI, "adapter", "convert", "msgpack", "json"], input=packed,
                              capture_output=True, check=True).stdout
        self.assertEqual(back, legacy)

    def test_strict_schema(self):
        good = json.loads(self.cli("describe", "noop").stdout)
        for key, value in (("credential", "secret"), ("stages", 0), ("features_known", 8),
                           ("features_supported", 1), ("inputs_known", 16), ("inputs_supported", 1),
                           ("schema_version", 2), ("protocol_version", 2), ("stages", 2**64),
                           ("sandbox", -1), ("current_agent", True), ("adapter_id", "bad\x00id"),
                           ("session_id", "unbound-session")):
            with self.subTest(key=key, value=value):
                self.describe({**good, key: value}, ok=False)
        file = self.root / "duplicate.json"
        file.write_text(json.dumps(good)[:-1] + ',"schema_version":1}')
        self.cli("describe", file, ok=False)
        for field in good:
            value = dict(good)
            del value[field]
            self.describe(value, ok=False)

    def test_tool_bounds_and_order(self):
        good = json.loads(self.cli("describe", "noop").stdout)
        tools = [{"id": f"tool-{i:02d}", "digest": "0" * 64} for i in range(64)]
        good["tools"] = list(reversed(tools))
        self.assertEqual(json.loads(self.describe(good).stdout)["tools"], tools)
        good["tools"].append({"id": "tool-overflow", "digest": "0" * 64})
        self.describe(good, ok=False)
        good["tools"] = tools[:1] * 2
        self.describe(good, ok=False)

    def probe(self, mode, ok, timeout=5000):
        exe = self.root / f"probe-{mode}"
        shutil.copy2(HELPER, exe)
        digest = hashlib.sha256(exe.read_bytes()).hexdigest()
        result = self.cli("probe", exe, digest, self.root, timeout, "--allow-process", ok=ok)
        return json.loads(result.stdout)

    def test_probe_success_is_not_host_authority(self):
        receipt = self.probe("ok", True)
        self.assertFalse(receipt["execution_authorized"])
        self.assertFalse(receipt["host_capabilities_verified"])
        self.assertEqual(receipt["exit_code"], 0)
        self.assertEqual(receipt["stderr_digest"], hashlib.sha256(b"").hexdigest())
        self.assertNotEqual(receipt["descriptor_digest"], "0" * 64)

    def test_probe_failure_bounds(self):
        for mode in ("hang", "overflow", "exit", "signal", "bad"):
            with self.subTest(mode=mode):
                receipt = self.probe(mode, False, 250 if mode == "hang" else 5000)
                self.assertFalse(receipt["execution_authorized"])
                if mode == "hang":
                    self.assertTrue(receipt["timed_out"])
                if mode == "exit":
                    self.assertEqual(receipt["exit_code"], 17)
                    self.assertNotIn("private diagnostic", json.dumps(receipt))
                self.assertEqual(receipt["descriptor_digest"], "0" * 64)

    def test_probe_denied_before_spawn(self):
        digest = hashlib.sha256(HELPER.read_bytes()).hexdigest()
        for args in ((HELPER, digest, self.root, 1000),
                     (HELPER, "0" * 64, self.root, 1000, "--allow-process"),
                     (HELPER, digest, self.root, 30001, "--allow-process")):
            self.assertEqual(self.cli("probe", *args, ok=False).stdout, b"")


unittest.main()
