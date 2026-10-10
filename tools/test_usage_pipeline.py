"""Durability, privacy, routing and delivery boundary regression tests."""
import io
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import hosted_usage as hosted
import usage_pipeline as pipeline
from execution_record import encoded
from test_usage_integrations import scope, turn, otlp


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.inbox = self.root / "inbox"
        self.inbox.mkdir(mode=0o700)
        self.mapping = {"schema": "golem.usage-route.v1", "run_id": "cost-run", "sequence": 1,
            "currency": "USD", "tool_calls": {"turn": 0}, "inbox": str(self.inbox), "require_billed": False}
        self.p = pipeline.Pipeline.create(self.root / "pipeline", scope(), self.mapping)

    def observed(self):
        self.p.accept(turn("turn/started"))
        self.p.accept(turn("thread/tokenUsage/updated", dict(zip(hosted.COUNTERS, [130, 25, 20, 5]))))
        self.p.accept(turn("turn/completed"))

    def test_restart_replay_and_exact_native_publication(self):
        self.observed()
        self.p = pipeline.Pipeline(self.p.directory)
        self.assertEqual(self.p.sync()["native_delivery"], "PENDING")
        result = self.p.close()
        self.assertEqual(result["native_delivery"], "PUBLISHED")
        self.assertEqual(result["native_application"], "OWNER_NOT_OBSERVED")
        path = self.inbox / "00000000000000000001.json"
        before = path.read_bytes()
        self.p.accept(turn("turn/started"))
        self.assertEqual(self.p.sync(), result)
        self.assertEqual(path.read_bytes(), before)
        report = json.loads(before)["reports"][0]
        self.assertEqual(report["usage"]["input_tokens"], "25")
        self.assertFalse(report["cost_known"])
        self.assertNotEqual(report["request_id"], "turn")

    def test_unknown_is_not_zero_or_sealed(self):
        result = self.p.close()
        self.assertEqual(result["native_delivery"], "PENDING")
        self.assertEqual(list(self.inbox.iterdir()), [])

    def test_failed_state_write_does_not_ack_or_change(self):
        before = (self.p.directory / "state.json").read_bytes()
        with patch.object(pipeline, "atomic", side_effect=OSError("full")):
            with self.assertRaises(OSError):
                self.p.accept(turn("turn/started"))
        self.assertEqual((self.p.directory / "state.json").read_bytes(), before)
        self.p.accept(turn("turn/started"))

    def test_failed_delivery_retains_closed_state_for_retry(self):
        self.observed()
        original = pipeline.atomic
        def fail(path, data):
            if path.parent == self.inbox:
                raise OSError("full")
            return original(path, data)
        with patch.object(pipeline, "atomic", side_effect=fail):
            with self.assertRaises(OSError):
                self.p.close()
        self.assertTrue(self.p.load()[1]["closed"])
        self.assertEqual(self.p.sync()["native_delivery"], "PUBLISHED")

    def test_required_billing_defers_without_inventing_cost(self):
        self.mapping["require_billed"] = True
        p = pipeline.Pipeline.create(self.root / "billed", scope(), self.mapping)
        self.p = p; self.observed()
        self.assertEqual(p.close()["reason"], "VERIFIED_BILLING_REQUIRED")
        self.assertEqual(list(self.inbox.iterdir()), [])

    def test_missing_tool_count_preserves_partial_tokens_not_known_zero(self):
        self.mapping["tool_calls"] = {}
        self.p = pipeline.Pipeline.create(self.root / "other", scope(), self.mapping)
        self.observed()
        result = self.p.close()
        self.assertEqual(result["native_delivery"], "PUBLISHED")
        self.assertFalse(result["tool_usage_complete"])
        report = json.loads(next(self.inbox.iterdir()).read_bytes())["reports"][0]
        self.assertFalse(report["usage_known"])
        self.assertEqual(report["usage"]["input_tokens"], "25")

    def test_native_conflict_not_overwritten(self):
        self.observed(); self.p.close()
        path = next(self.inbox.iterdir()); path.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "CONFLICT"):
            self.p.sync()
        self.assertEqual(path.read_bytes(), b"{}")

    def test_scope_fingerprint_rejects_changed_binding(self):
        path = self.p.directory / "config.json"
        value = json.loads(path.read_bytes()); value["binding"]["work_id"] = "different"
        path.write_bytes(encoded(value))
        with self.assertRaisesRegex(ValueError, "STATE"):
            self.p.load()

    def test_symlink_and_shared_permissions_rejected(self):
        link = self.root / "link"; link.symlink_to(self.p.directory, target_is_directory=True)
        with self.assertRaises(ValueError):
            pipeline.Pipeline(link)
        os.chmod(self.inbox, 0o755)
        with self.assertRaises(ValueError):
            self.p.sync()

    def test_claude_sanitizes_and_deduplicates(self):
        self.mapping["tool_calls"] = {"request": 0}
        self.p = pipeline.Pipeline.create(self.root / "claude", scope("claude.otel.v1"), self.mapping)
        self.p.accept(otlp()); self.p.accept(otlp())
        self.assertEqual(len(self.p.load()[1]["events"]), 1)
        self.assertNotIn(b"private prompt", (self.p.directory / "state.json").read_bytes())
        self.assertEqual(self.p.close()["native_delivery"], "PUBLISHED")

    def test_counter_conflict_is_transactional(self):
        self.observed()
        before = (self.p.directory / "state.json").read_bytes()
        with self.assertRaises(ValueError):
            self.p.accept(turn("thread/tokenUsage/updated", dict(zip(hosted.COUNTERS, [120, 25, 20, 5]))))
        self.assertEqual((self.p.directory / "state.json").read_bytes(), before)

    def test_child_environment_is_private_and_does_not_mutate_parent(self):
        parent = {"PATH": "p", "OTEL_LOG_USER_PROMPTS": "1", "BETA_TRACING_ENDPOINT": "secret",
                  "OTEL_EXPORTER_OTLP_LOGS_HEADERS": "secret"}
        env = pipeline.claude_environment("http://127.0.0.1:123/v1/logs", "t", parent)
        self.assertEqual(parent["OTEL_LOG_USER_PROMPTS"], "1")
        self.assertEqual(env["OTEL_LOG_RAW_API_BODIES"], "0")
        self.assertEqual(env["OTEL_LOG_USER_PROMPTS"], "0")
        self.assertNotIn("BETA_TRACING_ENDPOINT", env)
        self.assertNotIn("OTEL_EXPORTER_OTLP_LOGS_HEADERS", env)

    def test_cli_options_after_mode_and_incomplete_exit(self):
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(pipeline.main(["sync", "--directory", str(self.p.directory)]), 2)

    def test_initialization_success_is_not_pending_exit(self):
        for name, value in (("binding.json", scope()), ("route.json", self.mapping)):
            path = self.root / name
            path.write_bytes(encoded(value)); path.chmod(0o600)
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(pipeline.main(["init", "--directory", str(self.root / "new"),
                "--binding", str(self.root / "binding.json"), "--route", str(self.root / "route.json")]), 0)

    def test_live_notification_pump_closes_and_publishes(self):
        messages = [turn("turn/started"), turn("thread/tokenUsage/updated",
            dict(zip(hosted.COUNTERS, [130, 25, 20, 5]))), turn("turn/completed")]
        stream = io.TextIOWrapper(io.BytesIO(b"".join(encoded(m).replace(b"\n", b"") + b"\n" for m in messages)))
        with patch("sys.stdin", stream), patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(pipeline.main(["pump", "--directory", str(self.p.directory)]), 0)
        self.assertEqual(self.p.sync()["native_delivery"], "PUBLISHED")

    def test_child_requires_explicit_session(self):
        with self.assertRaisesRegex(ValueError, "CHILD_SCOPE"):
            pipeline.run_claude(self.p, ["claude"], 1)

    def test_signed_billing_automatically_routes_verified_cost(self):
        from test_usage_integrations import BillingTests
        fixture = BillingTests(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.payload["provider"] = "codex.app-server.v1"
        fixture.payload["entries"][0]["request_id"] = "turn"
        fixture.policy["provider"] = "codex.app-server.v1"
        (fixture.root / "export.json").write_bytes(encoded(fixture.payload))
        (fixture.root / "trust.json").write_bytes(encoded(fixture.policy))
        subprocess.run([fixture.openssl, "pkeyutl", "-sign", "-rawin", "-inkey",
            str(fixture.root / "private.pem"), "-in", str(fixture.root / "export.json"),
            "-out", str(fixture.root / "signature.bin")], check=True, capture_output=True)
        self.mapping["require_billed"] = True
        self.p = pipeline.Pipeline.create(self.root / "billed", scope(), self.mapping)
        self.observed(); self.p.close()
        evidence = [fixture.root / name for name in ("export.json", "signature.bin", "key.pem", "artifact.bin", "trust.json")]
        result = self.p.sync(evidence)
        self.assertEqual(result["native_delivery"], "PUBLISHED")
        report = json.loads(next(self.inbox.iterdir()).read_bytes())["reports"][0]
        self.assertTrue(report["cost_known"])
        self.assertEqual(report["nano_cost"], "13")
        self.assertEqual(result["totals"]["cost"], {"USD": 13})
        self.assertEqual(pipeline.Pipeline(self.p.directory).sync()["totals"]["cost"], {"USD": 13})
        (fixture.root / "artifact.bin").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            self.p.sync(evidence)

    def test_delivery_waiter_is_bounded_and_does_not_close_scope(self):
        with patch.object(pipeline.time, "sleep"), patch.object(pipeline.time, "monotonic", return_value=0):
            result = pipeline.deliver(self.p, 1)
        self.assertEqual(result["native_delivery"], "PENDING")
        self.assertFalse(self.p.load()[1]["closed"])

    def test_close_rejects_new_usage_and_serializes_concurrent_owner(self):
        self.observed(); self.p.close()
        with self.assertRaisesRegex(ValueError, "CLOSED"):
            self.p.accept(turn("thread/tokenUsage/updated", dict(zip(hosted.COUNTERS, [140, 25, 20, 5]))))
        with self.p.locked():
            with self.assertRaises(BlockingIOError):
                pipeline.Pipeline(self.p.directory).sync()


if __name__ == "__main__":
    unittest.main()
