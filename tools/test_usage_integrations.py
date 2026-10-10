"""Hosted identity/window isolation, authenticated export and native boundaries."""
import copy
import hashlib
import json
import io
from email.message import Message
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import billing_evidence as billing
import hosted_usage as hosted
import provider_usage as usage
import test_provider_usage


def scope(provider="codex.app-server.v1"):
    result = {"schema": "golem.hosted-usage-binding.v1", "provider": provider,
        "account_id": "account", "project_id": "project", "work_id": "work",
        "attempt_id": "attempt", "session_id": "session"}
    if provider == "codex.app-server.v1":
        result.update(turn_ids=["turn"], baseline=dict(zip(hosted.COUNTERS, [100, 20, 10, 2])))
    else:
        result["prompt_ids"] = ["prompt"]
        result["session_owned"] = False
    return result


def turn(method, total=None, identifier="turn"):
    params = {"threadId": "session", "turn": {"id": identifier, "status": "completed"}}
    if total is not None:
        params = {"threadId": "session", "turnId": identifier, "tokenUsage": {"total": total}}
    return {"method": method, "params": params}


def otlp(request="request", incoming=10):
    values = {"event.name": "api_request", "session.id": "session", "prompt.id": "prompt",
              "request_id": request, "model": "claude", "input_tokens": incoming,
              "output_tokens": 5, "cache_read_tokens": 20, "cache_creation_tokens": 30}
    attrs = [{"key": k, "value": {"intValue": str(v)} if type(v) is int else {"stringValue": v}}
             for k, v in values.items()]
    return {"resourceLogs": [{"scopeLogs": [{"logRecords": [{"attributes": attrs,
                       "body": {"stringValue": "private prompt never retained"}}]}]}]}


class HostedTests(unittest.TestCase):
    def test_chunked_bounds_and_ambiguous_framing(self):
        headers = Message(); headers["Transfer-Encoding"] = "chunked"
        self.assertEqual(hosted.http_body(headers, io.BytesIO(b"2\r\n{}\r\n0\r\n\r\n")), b"{}")
        for invalid in (b"2;extension\r\n{}\r\n0\r\n\r\n", b"2\r\n{", b"0\r\nsecret: x\r\n\r\n",
                        b"100001\r\n"):
            with self.assertRaises(ValueError):
                hosted.http_body(headers, io.BytesIO(invalid))
        headers["Content-Length"] = "2"
        with self.assertRaisesRegex(ValueError, "FRAMING"):
            hosted.http_body(headers, io.BytesIO(b"{}"))

    def test_codex_cumulative_baseline_is_not_previous_usage(self):
        c = hosted.Collector(scope())
        c.accept(turn("turn/started"))
        total = dict(zip(hosted.COUNTERS, [130, 25, 20, 5]))
        c.accept(turn("thread/tokenUsage/updated", total))
        c.accept(turn("thread/tokenUsage/updated", total))
        self.assertFalse(usage.totals([c.record()])["usage_complete"])
        c.accept(turn("turn/completed"))
        result = usage.totals([c.record(), c.record()])
        self.assertEqual(result["token_usage"], dict(zip(usage.BUCKETS, [25, 5, 7, 3])))
        self.assertEqual(result["requests"], 1)
        self.assertTrue(result["reasoning_breakdown_known"])

    def test_unknown_reset_overlap_and_unbound_turn_are_rejected(self):
        c = hosted.Collector(scope())
        with self.assertRaisesRegex(ValueError, "BASELINE"):
            c.accept(turn("thread/tokenUsage/updated", scope()["baseline"]))
        c.accept(turn("turn/started"))
        before = c.record()
        with self.assertRaisesRegex(ValueError, "RESET"):
            c.accept(turn("thread/tokenUsage/updated", dict(zip(hosted.COUNTERS, [99, 20, 10, 2]))))
        self.assertEqual(c.record(), before)
        with self.assertRaisesRegex(ValueError, "UNBOUND"):
            c.accept(turn("turn/started", identifier="other"))

    def test_missing_previous_turn_usage_cannot_be_reassigned(self):
        bound = scope(); bound["turn_ids"].append("next")
        c = hosted.Collector(bound); c.accept(turn("turn/started")); c.accept(turn("turn/completed"))
        with self.assertRaisesRegex(ValueError, "BOUNDARY_USAGE_REQUIRED"):
            c.accept(turn("turn/started", identifier="next"))
        self.assertIsNone(usage.totals([c.record()])["token_usage"])

    def test_ignored_otlp_values_do_not_allow_duplicate_keys(self):
        with self.assertRaisesRegex(ValueError, "ATTRIBUTES"):
            hosted.otlp_attributes([{"key": "input_tokens", "value": {"boolValue": True}},
                                    {"key": "input_tokens", "value": {"intValue": "10"}}])

    def test_claude_exact_request_dedupe_and_no_content(self):
        c = hosted.Collector(scope("claude.otel.v1"))
        c.accept(otlp()); c.accept(otlp())
        record = c.record()
        self.assertNotIn("private prompt", json.dumps(record))
        self.assertEqual(usage.totals([record])["token_usage"]["input_tokens"], 40)
        with self.assertRaisesRegex(ValueError, "CONFLICT"):
            c.accept(otlp(incoming=11))
        self.assertEqual(c.record(), record)

    def test_unknown_prompt_coverage_and_missing_attributes(self):
        bound = scope("claude.otel.v1"); bound["prompt_ids"].append("missing")
        c = hosted.Collector(bound); c.accept(otlp())
        self.assertEqual(usage.totals([c.record()])["unknown_requests"], 1)
        value = otlp(); value["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]["attributes"].pop()
        with self.assertRaises(KeyError):
            c.accept(value)

    def test_otlp_numeric_integer_compatibility_and_strict_types(self):
        value = otlp()
        attrs = value["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]["attributes"]
        for attr in attrs:
            if "intValue" in attr["value"]:
                attr["value"]["intValue"] = int(attr["value"]["intValue"])
        c = hosted.Collector(scope("claude.otel.v1")); c.accept(value)
        self.assertEqual(usage.totals([c.record()])["requests"], 1)
        for invalid in (True, 1.5, "1e2", -1):
            with self.assertRaises(ValueError):
                hosted.otlp_attributes([{"key": "input_tokens", "value": {"intValue": invalid}}])

    def test_durable_scoped_bundle_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "record"; output.mkdir(mode=0o700)
            c = hosted.Collector(scope("claude.otel.v1")); c.accept(otlp())
            hosted.persist(output, c)
            records, _ = billing.load_records([output])
            self.assertEqual(records, [c.record()])
            import agent_io
            stdout = io.TextIOWrapper(io.BytesIO())
            with redirect_stdout(stdout):
                self.assertEqual(agent_io.main(["usage-total", str(output), str(output)]), 0)
            self.assertEqual(json.loads(stdout.buffer.getvalue())["aggregate"]["requests"], 1)
            stdout.close()
            (output / "usage.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "INTEGRITY"):
                billing.load_records([output])

    def test_http_auth_and_transactional_publication_failure(self):
        c = hosted.Collector(scope("claude.otel.v1")); token = "x" * 32
        def fail(trial):
            raise OSError("disk full")
        with hosted.server(c, token, publish=fail) as server:
            thread = threading.Thread(target=server.serve_forever); thread.start()
            try:
                url = "http://127.0.0.1:%d/v1/logs" % server.server_port
                for auth, expected in (("wrong", 403), (token, 503)):
                    request = Request(url, data=json.dumps(otlp()).encode(), headers={"Authorization": "Bearer " + auth})
                    with self.assertRaises(HTTPError) as error:
                        urlopen(request, timeout=3)
                    self.assertEqual(error.exception.code, expected)
                    error.exception.close()
                self.assertEqual(c.rows, {})
            finally:
                server.shutdown(); thread.join()


class BillingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.openssl = shutil.which("openssl")
        if not self.openssl:
            self.fail("OpenSSL is required by the product billing verification contract")
        subprocess.run([self.openssl, "genpkey", "-algorithm", "ED25519", "-out", str(self.root / "private.pem")], check=True, capture_output=True)
        subprocess.run([self.openssl, "pkey", "-in", str(self.root / "private.pem"), "-pubout", "-out", str(self.root / "key.pem")], check=True, capture_output=True)
        self.artifact = b"synthetic invoice fixture - not an actual provider bill"
        self.payload = {"schema": "golem.billing-export.v1", "issuer": "billing-authority",
            "provider": "openai.responses.v1", "account_id": "account", "currency": "USD",
            "period_start": 100, "period_end": 200, "invoice_id": "invoice-1",
            "artifact_sha256": hashlib.sha256(self.artifact).hexdigest(), "total_nano": 20,
            "unallocated_nano": 7, "entries": [{"request_id": "request", "timestamp": 150, "nano_cost": 13}]}
        self.policy = {"schema": "golem.billing-trust.v1", "issuer": "billing-authority",
            "provider": "openai.responses.v1", "account_id": "account",
            "public_key_sha256": hashlib.sha256((self.root / "key.pem").read_bytes()).hexdigest()}
        for name, data in (("export.json", json.dumps(self.payload).encode()), ("artifact.bin", self.artifact),
                           ("trust.json", json.dumps(self.policy).encode())):
            (self.root / name).write_bytes(data)
        subprocess.run([self.openssl, "pkeyutl", "-sign", "-rawin", "-inkey", str(self.root / "private.pem"),
            "-in", str(self.root / "export.json"), "-out", str(self.root / "signature.bin")], check=True, capture_output=True)
        for p in self.root.iterdir():
            p.chmod(0o600)

    def verify(self, name="verified"):
        return billing.verify(*(self.root / name for name in ("export.json", "signature.bin", "key.pem", "artifact.bin", "trust.json")),
                              self.root / name)

    def record(self):
        normalized = usage.event(test_provider_usage.sample(), "openai.responses.v1")
        return {"calls": [{"attribution": {k: v for k, v in test_provider_usage.attribution().items() if k != "request_ids"},
                           "request_id": "request", "observation": normalized, "status": "COMPLETE"}]}

    def test_signature_reconciliation_native_unknown_vs_verified(self):
        payload, receipt = self.verify()
        record = self.record(); original = copy.deepcopy(record)
        result = billing.reconcile([record, record], payload, receipt)
        self.assertEqual(result["totals"]["cost"], {"USD": 13})
        self.assertEqual(result["matched_requests"], ["request"])
        self.assertEqual(result["unallocated_nano"], 7)
        self.assertFalse(result["provider_bill_authenticated"])
        self.assertEqual(record, original)
        report = billing.native_report(record["calls"][0], "run", 1, "USD", tool_calls=0)
        self.assertFalse(report["cost_known"])
        with self.assertRaisesRegex(ValueError, "COUNTER"):
            billing.native_report(record["calls"][0], "run", 1, "USD", tool_calls=None)
        oversized = copy.deepcopy(record["calls"][0]); oversized["request_id"] = "r" * 96
        with self.assertRaisesRegex(ValueError, "TEXT_CAPACITY"):
            billing.native_report(oversized, "run", 1, "USD", tool_calls=0)
        reconciled = billing.native_report(result["usage_records"][0]["calls"][0], "run", 1, "USD", tool_calls=0)
        self.assertTrue(reconciled["cost_known"])
        self.assertEqual(reconciled["nano_cost"], "13")
        payload["entries"][0]["nano_cost"] = 99
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_SCOPE"):
            billing.reconcile([record], payload, receipt)

    def test_altered_signature_and_artifact_fail_closed(self):
        path = self.root / "signature.bin"; sig = bytearray(path.read_bytes()); sig[0] ^= 1; path.write_bytes(sig)
        with self.assertRaisesRegex(ValueError, "SIGNATURE_INVALID"):
            self.verify()
        (self.root / "artifact.bin").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "ARTIFACT"):
            self.verify("second")

    def test_non_ed25519_key_is_not_accepted_by_signature_length(self):
        key = self.root / "other.pem"
        subprocess.run([self.openssl, "genpkey", "-algorithm", "X25519", "-out", str(key)], check=True, capture_output=True)
        subprocess.run([self.openssl, "pkey", "-in", str(key), "-pubout", "-out", str(self.root / "key.pem")], check=True, capture_output=True)
        self.policy["public_key_sha256"] = hashlib.sha256((self.root / "key.pem").read_bytes()).hexdigest()
        (self.root / "trust.json").write_text(json.dumps(self.policy))
        with self.assertRaisesRegex(ValueError, "KEY_ALGORITHM"):
            self.verify()

    def test_scope_key_total_duplicate_period_and_overflow(self):
        for key, value in (("account_id", "other"), ("total_nano", 21), ("unallocated_nano", usage.MAX)):
            payload = dict(self.payload, **{key: value})
            with self.assertRaises(ValueError):
                billing.validate(payload, self.policy, self.artifact)
        payload = copy.deepcopy(self.payload); payload["entries"] *= 2
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            billing.validate(payload, self.policy, self.artifact)
        self.policy["public_key_sha256"] = "0" * 64
        (self.root / "trust.json").write_text(json.dumps(self.policy))
        with self.assertRaisesRegex(ValueError, "KEY_OR_SIGNATURE"):
            self.verify()

    def test_unmatched_billing_and_incomplete_native_are_not_invented(self):
        payload, receipt = self.verify()
        record = self.record(); record["calls"][0]["request_id"] = "other"
        result = billing.reconcile([record], payload, receipt)
        self.assertIsNone(result["totals"]["cost"])
        self.assertEqual(result["unmatched_invoice_requests"], ["request"])
        record["calls"][0]["status"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            billing.native_report(record["calls"][0], "run", 1, "USD", tool_calls=0)

    def test_cli_cost_comparison_keeps_request_billing_and_snapshot_separate(self):
        import provider_costs
        import test_provider_costs
        self.payload.update(period_start=172800, period_end=259200)
        self.payload["entries"][0]["timestamp"] = 200000
        (self.root / "export.json").write_bytes(json.dumps(self.payload).encode())
        subprocess.run([self.openssl, "pkeyutl", "-sign", "-rawin", "-inkey", str(self.root / "private.pem"),
            "-in", str(self.root / "export.json"), "-out", str(self.root / "signature.bin")], check=True, capture_output=True)
        source = self.root / "api-page.json"
        source.write_bytes(test_provider_costs.page(amount=0.00000002)); source.chmod(0o600)
        api = self.root / "api"
        provider_costs.collect(test_provider_costs.scope(), api, page_files=[source])
        output = self.root / "comparison"
        argv = ["billing_evidence.py", "reconcile", "--bundle", "explicit-fixture", "--output", str(output),
                "--cost-api-bundle", str(api), "--confirm-same-api-scope"]
        for option, name in (("--export", "export.json"), ("--signature", "signature.bin"), ("--public-key", "key.pem"),
                             ("--artifact", "artifact.bin"), ("--trust", "trust.json")):
            argv.extend((option, str(self.root / name)))
        original = self.record()
        with patch.object(sys, "argv", argv), patch.object(billing, "load_records", return_value=([original], ["fixture-source"])), redirect_stdout(io.StringIO()):
            self.assertEqual(billing.main(), 0)
        result = json.loads((output / "result.json").read_bytes())
        self.assertEqual(result["aggregate_api_comparison"]["status"], "MATCH")
        self.assertEqual(result["totals"]["cost"], {"USD": 13})
        self.assertEqual(result["unallocated_nano"], 7)
        self.assertFalse(result["provider_bill_authenticated"])
        self.assertIsNone(original["calls"][0]["observation"]["billing"])
        api.rename(self.root / "original-moved")
        copied = provider_costs.load(output / "provider-cost-api")
        self.assertEqual(copied["reported_totals"], {"USD": "0.00000002"})


if __name__ == "__main__":
    unittest.main()
