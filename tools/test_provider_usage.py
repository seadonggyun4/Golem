import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import provider_usage as usage
import test_agent_io
import agent_io


def attribution(provider="openai.responses.v1"):
    return {"provider": provider, "account_id": "account", "project_id": "project", "work_id": "work",
            "attempt_id": "attempt", "session_id": "session", "request_ids": ["request"]}


def sample(output=10, final=True, billing=None):
    return {"schema": "golem.provider-usage.v1", "request_id": "request", "model": "model",
            "usage": {"input_tokens": 100, "output_tokens": output,
                      "input_tokens_details": {"cached_tokens": 20},
                      "output_tokens_details": {"reasoning_tokens": 2}},
            "final": final, "billing": billing}


class UsageTests(unittest.TestCase):
    def cli(self, rows, provider):
        with tempfile.TemporaryDirectory() as root:
            stdout, stream = Path(root) / "stdout", Path(root) / "usage"
            stdout.write_text("".join(json.dumps(row) + "\n" for row in rows))
            stdout.chmod(0o600)
            scope = attribution(provider)
            metadata = usage.collect_cli(stdout, stream, scope)
            return metadata, usage.totals([usage.collect(stream, scope)])

    def test_codex_cli_invocation_and_reasoning(self):
        rows = [{"type": "thread.started", "thread_id": "thread"},
                {"type": "item.completed", "item": {"text": "private response"}},
                {"type": "turn.completed", "usage": {"input_tokens": 100,
                 "cached_input_tokens": 20, "output_tokens": 10, "reasoning_output_tokens": 3}}]
        meta, total = self.cli(rows, "codex.exec.v1")
        self.assertEqual(total["token_usage"], dict(zip(usage.BUCKETS, [80, 20, 7, 3])))
        self.assertEqual(meta["provider_session_id"], "thread")
        self.assertIsNone(total["cost"])
        with self.assertRaisesRegex(ValueError, "MULTIPLE_TERMINALS"):
            self.cli(rows + rows[-1:], "codex.exec.v1")

    def test_claude_cli_estimate_is_not_billing(self):
        rows = [{"type": "system", "subtype": "init", "session_id": "session", "model": "claude-opus-4-8[1m]"},
                {"type": "result", "session_id": "session", "total_cost_usd": 0.001234567891,
                 "usage": {"input_tokens": 10, "output_tokens": 5,
                           "cache_read_input_tokens": 20, "cache_creation_input_tokens": 30,
                           "server_tool_use": {"web_search_requests": 0}}}]
        meta, total = self.cli(rows, "claude.code.v1")
        self.assertEqual(meta["estimated_cost"]["nano_cost"], 1234568)
        self.assertEqual(total["token_usage"]["input_tokens"], 40)
        self.assertIsNone(total["cost"])
        self.assertFalse(total["cost_complete"])
        rows[-1]["session_id"] = "other"
        with self.assertRaisesRegex(ValueError, "SESSION_CONFLICT"):
            self.cli(rows, "claude.code.v1")

    def test_cli_missing_terminal_is_unknown(self):
        meta, total = self.cli([{"type": "thread.started", "thread_id": "thread"},
                                {"type": "turn.failed", "error": "failure"}], "codex.exec.v1")
        self.assertFalse(total["usage_complete"])
        self.assertEqual(total["unknown_requests"], 1)
        self.assertIsNone(total["token_usage"])

    def test_cli_terminal_requires_usage_and_consistent_optional_thread(self):
        rows = [{"type": "thread.started", "thread_id": "thread"}, {"type": "turn.completed"}]
        with self.assertRaisesRegex(ValueError, "MISSING_USAGE"):
            self.cli(rows, "codex.exec.v1")
        rows[-1].update(thread_id="other", usage={"input_tokens": 1,
                       "cached_input_tokens": 0, "output_tokens": 1})
        with self.assertRaisesRegex(ValueError, "SESSION_CONFLICT"):
            self.cli(rows, "codex.exec.v1")

    def test_cli_json_validation_preserves_decimals_and_rejects_duplicates(self):
        from decimal import Decimal
        from verify_agent import strict_json
        self.assertEqual(strict_json(b'{"amount":0.017745999999999998}', parse_float=Decimal)["amount"],
                         Decimal("0.017745999999999998"))
        for raw in (b'{"amount":1,"amount":2}', b'{"amount":NaN}'):
            with self.assertRaises(ValueError):
                strict_json(raw, parse_float=Decimal)

    def test_claude_auxiliary_models_count_once(self):
        primary = {"inputTokens": 10, "outputTokens": 5,
                   "cacheReadInputTokens": 20, "cacheCreationInputTokens": 30}
        auxiliary = dict(primary, inputTokens=7, outputTokens=2,
                         cacheReadInputTokens=0, cacheCreationInputTokens=0)
        rows = [{"type": "system", "subtype": "init", "session_id": "session", "model": "primary"},
                {"type": "result", "session_id": "session", "usage": {
                    "input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 20,
                    "cache_creation_input_tokens": 30}, "modelUsage": {
                    "primary": primary, "auxiliary": auxiliary}}]
        meta, total = self.cli(rows, "claude.code.v1")
        self.assertEqual(total["token_usage"], dict(zip(usage.BUCKETS, [47, 20, 7, 0])))
        self.assertEqual(meta["token_scope"], "MODEL_USAGE_AGGREGATE")
        self.assertEqual(meta["terminal_usage"]["output_tokens"], 5)
        rows[-1]["modelUsage"]["primary"]["cacheReadInputTokens"] = 0
        with self.assertRaisesRegex(ValueError, "MODEL_SUBTOTAL"):
            self.cli(rows, "claude.code.v1")

    def test_duplicate_invocation_ids_rejected(self):
        command = {"id": "one", "argv": ["/bin/provider"], "timeout": 1,
                   "usage": attribution("codex.exec.v1")}
        plan = {"schema": agent_io.PLAN_SCHEMA, "task": "code", "commands": [
            command, dict(command, id="two")]}
        with self.assertRaises(agent_io.ObservationError) as error:
            agent_io.validate_plan(plan)
        self.assertEqual(error.exception.code, "USAGE_DUPLICATE_CALL_ID")

    def test_cli_resume_is_rejected_before_execution(self):
        for provider, arg in (("codex.exec.v1", "resume"), ("claude.code.v1", "--resume=old")):
            plan = {"schema": agent_io.PLAN_SCHEMA, "task": "code", "commands": [
                {"id": "probe", "argv": ["/bin/provider", arg], "timeout": 1,
                 "usage": attribution(provider)}]}
            with self.assertRaises(agent_io.ObservationError) as error:
                agent_io.validate_plan(plan)
            self.assertEqual(error.exception.code, "USAGE_CLI_FRESH_INVOCATION_REQUIRED")

    def collect(self, events, scope=None):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "usage.jsonl"
            path.write_text("".join(json.dumps(e) + "\n" for e in events))
            path.chmod(0o600)
            return usage.collect(path, scope or attribution())

    def test_stream_snapshots_and_duplicate_delivery(self):
        record = self.collect([sample(4, False), sample(), sample()])
        total = usage.totals([record, record])
        self.assertEqual(total["requests"], 1)
        self.assertEqual(total["token_usage"], dict(zip(usage.BUCKETS, [80, 20, 8, 2])))
        self.assertTrue(total["usage_complete"])
        self.assertFalse(total["cost_complete"])
        self.assertIsNone(total["cost"])

    def test_missing_and_partial_never_become_zero_cost(self):
        scope = attribution(); scope["request_ids"].append("missing")
        total = usage.totals([self.collect([sample(4, False)], scope)])
        self.assertEqual(total["unknown_requests"], 2)
        self.assertFalse(total["usage_complete"])
        self.assertIsNone(total["cost"])

    def test_billed_zero_and_currency_separation(self):
        bill = {"currency": "USD", "nano_cost": 0, "evidence_sha256": "a" * 64}
        record = self.collect([sample(billing=bill)])
        self.assertEqual(usage.totals([record])["cost"], {"USD": 0})
        self.assertTrue(usage.totals([record])["cost_complete"])
        second = copy.deepcopy(record)
        second["calls"][0]["request_id"] = "retry"
        second["calls"][0]["observation"]["billing"] = dict(bill, currency="EUR", nano_cost=9)
        self.assertEqual(usage.totals([record, second])["cost"], {"USD": 0, "EUR": 9})

    def test_work_reassignment_is_rejected(self):
        record = self.collect([sample()]); second = copy.deepcopy(record)
        second["calls"][0]["attribution"]["work_id"] = "another-work"
        with self.assertRaisesRegex(ValueError, "CONFLICT"):
            usage.totals([record, second])

    def test_regression_or_conflicting_final_is_rejected(self):
        for events in ([sample(), sample(12)], [sample(8, False), sample(4, False)]):
            with self.assertRaisesRegex(ValueError, "CONFLICT"):
                self.collect(events)

    def test_unsupported_or_unattributed_data_is_rejected(self):
        for value in (dict(sample(), request_id="other"), dict(sample(), prompt="private")):
            with self.assertRaises(ValueError):
                self.collect([value])

    def test_counter_types_subtotals_and_overflow(self):
        for invalid in (-1, True, usage.MAX + 1, 1.5):
            value = sample(); value["usage"]["input_tokens"] = invalid
            with self.assertRaises(ValueError):
                self.collect([value])
        with self.assertRaises(ValueError):
            usage.add(usage.MAX, 1)

    def test_claude_cache_write_normalization(self):
        value = sample()
        value["usage"] = {"input_tokens": 10, "output_tokens": 5,
                          "cache_read_input_tokens": 20, "cache_creation_input_tokens": 30}
        total = usage.totals([self.collect([value], attribution("anthropic.messages.v1"))])
        self.assertEqual(total["token_usage"], dict(zip(usage.BUCKETS, [40, 20, 5, 0])))

    def test_partial_final_union_is_order_independent(self):
        partial, final = self.collect([sample(4, False)]), self.collect([sample()])
        self.assertEqual(usage.totals([partial, final]), usage.totals([final, partial]))

    def test_private_stream_rejects_links_and_public_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "usage"
            path.write_text(json.dumps(sample()) + "\n")
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "PRIVATE_STREAM"):
                usage.collect(path, attribution())
            link = Path(root) / "link"; link.symlink_to(path)
            with self.assertRaises(OSError):
                usage.collect(link, attribution())

    def test_cache_subtotal_and_fractional_billing_rejected(self):
        value = sample(); value["usage"]["input_tokens_details"]["cached_tokens"] = 101
        with self.assertRaisesRegex(ValueError, "SUBTOTAL"):
            self.collect([value])
        value = sample(billing={"currency": "USD", "nano_cost": 0.5, "evidence_sha256": "a" * 64})
        with self.assertRaises(ValueError):
            self.collect([value])

    def test_known_zero_usage_is_complete(self):
        value = sample(output=0)
        value["usage"]["input_tokens"] = 0
        value["usage"]["input_tokens_details"]["cached_tokens"] = 0
        value["usage"]["output_tokens_details"]["reasoning_tokens"] = 0
        total = usage.totals([self.collect([value])])
        self.assertTrue(total["usage_complete"])
        self.assertEqual(sum(total["token_usage"].values()), 0)


class UsageIntegration(unittest.TestCase):
    setUp = test_agent_io.AgentIO.setUp
    git = test_agent_io.AgentIO.git
    plan = test_agent_io.AgentIO.plan
    run_plan = test_agent_io.AgentIO.run_plan
    def usage_plan(self, exit_code=0):
        module = str(Path(usage.__file__).resolve().parent)
        script = (f"import sys,os;sys.path.insert(0,{module!r});"
                  "from provider_usage import emit;"
                  f"v={sample()!r};"
                  "emit(os.environ['GOLEM_USAGE_STREAM'], provider='openai.responses.v1',"
                  "request_id=v['request_id'], model=v['model'], usage=v['usage'], final=True);"
                  f"sys.exit({exit_code})")
        plan = self.plan(script)
        plan["commands"][0]["usage"] = attribution()
        return plan

    def test_usage_survives_failed_process_and_reaches_views(self):
        output = self.run_plan(self.usage_plan(7))
        view = agent_io.view(output)
        self.assertEqual(view["status"], "FAILED")
        self.assertEqual(view["token_usage"]["input_tokens"], 80)
        self.assertEqual(agent_io.measure(output)["token_usage"], view["token_usage"])
        record, _ = agent_io.load_bundle(output)
        self.assertEqual(record["steps"][0]["usage"]["calls"][0]["attribution"]["work_id"], "work")
        self.assertIn("Usage accounting", agent_io.report(output))

    def test_cli_capture_normalizes_usage_and_preserves_real_exit(self):
        for incoming in (100, True):
            rows = [{"type": "thread.started", "thread_id": "thread"},
                    {"type": "turn.completed", "usage": {"input_tokens": incoming,
                     "cached_input_tokens": 20, "output_tokens": 5}}]
            script = "import sys; print(" + repr("\n".join(json.dumps(r) for r in rows)) + "); sys.exit(7)"
            plan = self.plan(script)
            plan["commands"][0]["usage"] = attribution("codex.exec.v1")
            output = self.run_plan(plan)
            record, _ = agent_io.load_bundle(output)
            import execution_record
            self.assertEqual(execution_record.check(output / "check")["integrity"], "PASS")
            import execution_record
            self.assertEqual(execution_record.check(output / "check")["integrity"], "PASS")
            self.assertEqual(record["steps"][0]["returncode"], 7)
            self.assertEqual(record["status"], "FAILED")
            if incoming is True:
                self.assertIsNone(record["token_usage"])
                self.assertIn("usage_error", agent_io.view(output)["steps"][0])
            else:
                self.assertEqual(record["token_usage"]["input_tokens"], 80)
                self.assertEqual(agent_io.view(output)["steps"][0]["cli_usage"]["granularity"], "CLI_INVOCATION")

    def test_expected_but_unreported_usage_is_unknown(self):
        plan = self.plan(); plan["commands"][0]["usage"] = attribution()
        view = agent_io.view(self.run_plan(plan))
        self.assertEqual(view["usage_accounting"]["unknown_requests"], 1)
        self.assertFalse(view["usage_accounting"]["usage_complete"])

    def test_stopped_commands_preserve_unmeasured_requests(self):
        plan = self.usage_plan(7)
        later = copy.deepcopy(plan["commands"][0]); later["id"] = "later"
        later["usage"]["request_ids"] = ["fallback"]
        plan["commands"].append(later)
        view = agent_io.view(self.run_plan(plan))
        self.assertEqual(view["usage_accounting"]["requests"], 2)
        self.assertEqual(view["usage_accounting"]["unknown_requests"], 1)

    def test_usage_total_cli_deduplicates_bundles(self):
        output = self.run_plan(self.usage_plan())
        import subprocess
        result = subprocess.run([sys.executable, agent_io.__file__, "usage-total", str(output), str(output)],
                                check=True, capture_output=True)
        value = json.loads(result.stdout)
        self.assertEqual(value["works"][0]["totals"]["requests"], 1)


if __name__ == "__main__":
    unittest.main()
