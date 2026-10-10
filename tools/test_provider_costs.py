"""Provider adapter contracts, exact amounts and no invoice/Work inference."""
from decimal import Decimal
from email.message import Message
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

import execution_record as records
import provider_costs as costs


def scope(provider="openai.costs.v1", days=1):
    return {"schema": "golem.provider-cost-query.v1", "provider": provider, "account_id": "account",
            "start_time": 172800, "end_time": 172800 + 86400 * days}


def page(provider="openai.costs.v1", *, day=172800, amount=0.06, cursor=None):
    if provider == "openai.costs.v1":
        bucket = {"object": "bucket", "start_time": day, "end_time": day + 86400,
                  "results": [{"object": "organization.costs.result", "project_id": "project",
                              "line_item": "input", "amount": {"value": amount, "currency": "usd"}}]}
        result = {"object": "page"}
    else:
        bucket = {"starting_at": costs.iso(day), "ending_at": costs.iso(day + 86400),
                  "results": [{"amount": str(amount), "currency": "USD", "workspace_id": "workspace",
                              "description": "input", "cost_type": "tokens"}]}
        result = {}
    result.update(data=[bucket], has_more=cursor is not None, next_page=cursor)
    return json.dumps(result).encode()


class Response(io.BytesIO):
    def __init__(self, url, body, *, status=200, content_type="application/json"):
        super().__init__(body)
        self.url, self.status, self.headers = url, status, Message()
        self.headers["Content-Type"] = content_type

    def geturl(self):
        return self.url


class CostAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def file(self, name, data):
        path = self.root / name; records.save(path, data); return path

    def test_provider_units_and_subnano_precision_are_preserved(self):
        for provider, amount, expected in (("openai.costs.v1", 0.06, "0.06"),
                                           ("anthropic.costs.v1", "123.78912", "1.2378912")):
            report = costs.normalize_report(scope(provider), [page(provider, amount=amount)], "FILE_UNAUTHENTICATED")
            self.assertEqual(report["reported_totals"], {"USD": expected})
            self.assertTrue(report["api_window_complete"])
            self.assertFalse(report["provider_bill_authenticated"])
            self.assertIsNone(report["work_cost"])
        precise = page().replace(b"0.06", b"0.000000000123456789")
        self.assertEqual(costs.normalize_report(scope(), [precise], "FILE_UNAUTHENTICATED")["reported_totals"],
                         {"USD": "0.000000000123456789"})

    def test_decimal_invalid_refund_float_and_exponent_are_rejected(self):
        for value in (True, 0.1, Decimal("NaN"), Decimal("Infinity"), Decimal("-0"), Decimal("-1"), Decimal("1e65")):
            with self.assertRaises(ValueError):
                costs.decimal_amount(value)
        for value in (1, "1e2", "-1", "+1", "NaN"):
            with self.assertRaises(ValueError):
                costs.decimal_amount(value, cents=True)

    def test_day_window_and_provider_query_contract(self):
        for invalid in (dict(scope(), provider="unknown"), dict(scope(), start_time=172801),
                        dict(scope(), end_time=172800), scope(days=367), dict(scope(), extra=True)):
            with self.assertRaises(ValueError):
                costs.query(invalid)
        self.assertEqual(costs.query(scope()), scope())

    def test_pagination_duplicate_bucket_and_cursor_loop(self):
        first = page(cursor="page=/x"); second = page(day=259200)
        result = costs.normalize_report(scope(days=2), [first, second], "FILE_UNAUTHENTICATED")
        self.assertEqual(result["reported_totals"], {"USD": "0.12"})
        for pages in ([first], [page(), second], [first, page()],
                      [first, page(day=259200, cursor="page=/x")]):
            with self.assertRaises(ValueError):
                costs.normalize_report(scope(days=2), pages, "FILE_UNAUTHENTICATED")

    def test_missing_day_missing_amount_and_empty_rows_are_not_free(self):
        result = costs.normalize_report(scope(days=2), [page()], "FILE_UNAUTHENTICATED")
        self.assertFalse(result["api_window_complete"])
        value = json.loads(page()); value["data"][0]["results"][0].pop("amount")
        result = costs.normalize_report(scope(), [json.dumps(value).encode()], "FILE_UNAUTHENTICATED")
        self.assertFalse(result["api_amount_complete"]); self.assertIsNone(result["reported_totals"])
        value["data"][0]["results"] = []
        result = costs.normalize_report(scope(), [json.dumps(value).encode()], "FILE_UNAUTHENTICATED")
        self.assertIsNone(result["reported_totals"]); self.assertIsNone(result["work_cost"])

    def test_duplicate_rows_unknown_fields_and_window_are_rejected(self):
        value = json.loads(page()); value["data"][0]["results"] *= 2
        with self.assertRaisesRegex(ValueError, "DUPLICATE_ROW"):
            costs.normalize_report(scope(), [json.dumps(value).encode()], "FILE_UNAUTHENTICATED")
        value = json.loads(page()); value["data"][0]["results"][0]["new_pricing"] = "unsupported"
        with self.assertRaisesRegex(ValueError, "ROW_SCHEMA"):
            costs.normalize_report(scope(), [json.dumps(value).encode()], "FILE_UNAUTHENTICATED")
        with self.assertRaisesRegex(ValueError, "WINDOW"):
            costs.normalize_report(scope(), [page(day=259200)], "FILE_UNAUTHENTICATED")

    def test_private_capture_rederivation_and_tamper_detection(self):
        source = self.file("source.json", page())
        output = self.root / "captured"
        result = costs.collect(scope(), output, page_files=[source])
        self.assertEqual(costs.load(output), result)
        copied = self.root / "copied"
        self.assertEqual(costs.load(output, snapshot=copied), result)
        self.assertEqual(costs.load(copied), result)
        self.assertEqual(result["transport_observation"], "FILE_UNAUTHENTICATED")
        self.assertNotIn("credential", (output / "result.json").read_text())
        (output / "page-0000.json").write_bytes(page(amount=1))
        with self.assertRaisesRegex(ValueError, "INTEGRITY"):
            costs.load(output)

    def test_fetch_records_queries_request_ids_and_never_copies_admin_secret(self):
        secret, calls = "synthetic-admin-credential-not-real", []
        def respond(req, timeout):
            calls.append(req.full_url)
            result = Response(req.full_url, page(day=172800 if len(calls) == 1 else 259200,
                                               cursor="next" if len(calls) == 1 else None))
            result.headers["x-request-id"] = "provider-request-%d" % len(calls)
            return result
        output = self.root / "fetch-fixture"
        with patch.dict(os.environ, {"OPENAI_ADMIN_KEY": secret}), patch.object(costs, "build_opener") as build:
            build.return_value.open.side_effect = respond
            result = costs.collect(scope(days=2), output)
        self.assertEqual(len(calls), 2); self.assertIn("page=next", calls[1])
        self.assertEqual(costs.load(output), result)
        metadata = json.loads((output / "request-0001.json").read_bytes())
        self.assertEqual(metadata["provider_request_id"], "provider-request-2")
        self.assertEqual(metadata["http_status"], 200)
        self.assertTrue(all(secret.encode() not in p.read_bytes() for p in output.iterdir()))

    def test_unknown_request_fields_are_not_copied_into_comparison_snapshots(self):
        source = self.file("source.json", page()); output = self.root / "capture"
        costs.collect(scope(), output, page_files=[source])
        value = json.loads((output / "request-0000.json").read_bytes()); value["authorization"] = "untrusted"
        (output / "request-0000.json").write_bytes(records.encoded(value))
        from agent_io import file_inventory
        manifest = json.loads((output / "manifest.json").read_bytes()); manifest["files"] = file_inventory(output)
        (output / "manifest.json").write_bytes(records.encoded(manifest))
        with self.assertRaisesRegex(ValueError, "REQUEST_BINDING"):
            costs.load(output, snapshot=self.root / "not-copied")
        self.assertFalse((self.root / "not-copied").exists())

    def test_edited_derived_report_cannot_replace_raw_costs(self):
        source = self.file("source.json", page()); output = self.root / "capture"
        costs.collect(scope(), output, page_files=[source])
        result = json.loads((output / "result.json").read_bytes()); result["reported_totals"] = {"USD": "0"}
        (output / "result.json").write_bytes(records.encoded(result))
        from agent_io import file_inventory
        manifest = json.loads((output / "manifest.json").read_bytes())
        manifest["files"] = file_inventory(output)
        (output / "manifest.json").write_bytes(records.encoded(manifest))
        with self.assertRaisesRegex(ValueError, "DERIVATION_CONFLICT"):
            costs.load(output)

    def test_failed_pagination_preserves_partial_evidence_without_complete_report(self):
        source = self.file("source.json", page(cursor="next")); output = self.root / "failed"
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            costs.collect(scope(days=2), output, page_files=[source])
        self.assertEqual((output / "page-0000.json").read_bytes(), source.read_bytes())
        failure = json.loads((output / "failure.json").read_bytes())
        self.assertEqual(failure["state"], "INCOMPLETE"); self.assertIsNone(failure["work_cost"])
        self.assertFalse((output / "manifest.json").exists())

    def test_missing_credentials_never_trigger_network_or_create_bundle(self):
        env = "GOLEM_TEST_UNCONFIGURED_ADMIN"
        with patch.dict(os.environ, {}, clear=True), patch.object(costs, "request") as request:
            with self.assertRaisesRegex(ValueError, "CREDENTIAL_UNAVAILABLE"):
                costs.collect(scope(), self.root / "no-network", credential_env=env)
            request.assert_not_called()
        self.assertFalse((self.root / "no-network").exists())

    def test_https_headers_fixed_origin_and_no_secret_capture(self):
        secret = "private-admin-test-key-not-real"
        for provider, header in (("openai.costs.v1", "Authorization"), ("anthropic.costs.v1", "X-api-key")):
            responses = []
            def open_request(req, timeout):
                self.assertEqual(req.get_method(), "GET")
                self.assertTrue(req.full_url.startswith(costs.ADAPTERS[provider][0] + "?"))
                self.assertNotIn(secret, req.full_url)
                self.assertIn(secret, req.get_header(header))
                result = Response(req.full_url, page(provider, amount=1)); responses.append(result); return result
            with patch.object(costs, "build_opener") as build:
                build.return_value.open.side_effect = open_request
                raw = costs.request(scope(provider), "page=/x", secret, timeout=1, deadline=time.monotonic() + 2)
                handlers = build.call_args.args
                https = next(h for h in handlers if isinstance(h, costs.HTTPSHandler))
                self.assertTrue(https._context.check_hostname)
                self.assertEqual(https._context.verify_mode, costs.ssl.CERT_REQUIRED)
                self.assertEqual(next(h for h in handlers if isinstance(h, costs.ProxyHandler)).proxies, {})
                self.assertEqual(raw, page(provider, amount=1))
                self.assertTrue(responses[0].closed)

    def test_redirect_denied_and_error_body_not_propagated(self):
        body = io.BytesIO(b"secret")
        with self.assertRaisesRegex(ValueError, "REDIRECT_DENIED"):
            costs.NoRedirect().redirect_request(Request(costs.ADAPTERS["openai.costs.v1"][0]), body, 302,
                "redirect", {}, "https://attacker.invalid/")
        self.assertTrue(body.closed)
        error = HTTPError("https://api.openai.com/", 401, "private error", {}, io.BytesIO(b"private-key"))
        with patch.object(costs, "build_opener") as build:
            build.return_value.open.side_effect = error
            with self.assertRaises(costs.CostError) as caught:
                costs.request(scope(), None, "x" * 32, timeout=1, deadline=time.monotonic() + 2)
            self.assertEqual(caught.exception.http_status, 401)
            self.assertNotIn("private", str(caught.exception))

    def test_response_limits_content_type_deadline_and_secret_echo(self):
        secret = "x" * 32
        cases = ((b"a" * (costs.usage.MAX_BYTES + 1), "application/json", 10, "PAGE_LIMIT"),
                 (secret.encode(), "application/json", 10, "SECRET_ECHO"),
                 (page(), "text/html", 10, "ENCODING"), (page(), "application/json", -1, "DEADLINE"))
        for raw, content_type, remaining, code in cases:
            with patch.object(costs, "build_opener") as build:
                build.return_value.open.side_effect = lambda req, timeout: Response(req.full_url, raw, content_type=content_type)
                with self.assertRaisesRegex(ValueError, code):
                    costs.request(scope(), None, secret, timeout=1, deadline=time.monotonic() + remaining)
        response = Response(costs.ADAPTERS["openai.costs.v1"][0] + "?" + costs.urlencode(costs.params(scope())), page())
        response.headers["x-request-id"] = "echo-" + secret
        observation = {}
        with patch.object(costs, "build_opener") as build:
            build.return_value.open.return_value = response
            with self.assertRaisesRegex(ValueError, "SECRET_ECHO"):
                costs.request(scope(), None, secret, timeout=1, deadline=time.monotonic() + 2, observation=observation)
        self.assertEqual(observation, {})
        self.assertTrue(response.closed)

    def test_invoice_comparison_requires_scope_and_never_allocates_work_cost(self):
        result = costs.normalize_report(scope(), [page()], "FILE_UNAUTHENTICATED")
        payload = {"provider": "openai.responses.v1", "account_id": "account", "period_start": 172800,
                   "period_end": 259200, "currency": "USD", "total_nano": 60000000}
        self.assertEqual(costs.compare(result, payload)["status"], "UNKNOWN_COVERAGE")
        compared = costs.compare(result, payload, same_api_scope=True)
        self.assertEqual(compared["status"], "MATCH")
        self.assertFalse(compared["provider_bill_authenticated"]); self.assertFalse(compared["work_cost_assigned"])
        self.assertEqual(costs.compare(result, dict(payload, total_nano=1), same_api_scope=True)["status"], "DIFFERENCE")
        for change in ({"account_id": "other"}, {"provider": "codex.exec.v1"}, {"period_end": 345600}):
            with self.assertRaises(ValueError):
                costs.compare(result, dict(payload, **change), same_api_scope=True)
        result["api_window_complete"] = False
        self.assertEqual(costs.compare(result, payload, same_api_scope=True)["status"], "UNKNOWN_COVERAGE")


if __name__ == "__main__":
    unittest.main()
