"""Real stdio transport with a synthetic provider, never a billed model test."""
import json
from pathlib import Path
import sys
import time
import tempfile
import unittest

import codex_hosted as owned
import usage_pipeline as pipeline


def fake(mode):
    total = 0
    for raw in sys.stdin:
        request = json.loads(raw)
        identifier, method = request.get("id"), request["method"]
        def send(value):
            print(json.dumps(value), flush=True)
        if method == "initialize":
            send({"id": identifier, "result": {}})
        elif method == "thread/start":
            send({"id": identifier, "result": {"thread": {"id": "session"}}})
        elif method == "turn/start":
            turn = "turn-" + str(identifier)
            if mode == "approval":
                send({"id": 100, "method": "item/commandExecution/requestApproval", "params": {}})
                continue
            if mode == "eof":
                return
            if mode == "timeout":
                time.sleep(60)
                return
            if mode == "oversize":
                print("x" * (1024 * 1024 + 1), flush=True)
                return
            send({"method": "turn/started", "params": {"threadId": "session", "turn": {"id": turn}}})
            if mode != "late-wrong":
                send({"id": identifier, "result": {"turn": {"id": turn if mode != "wrong" else "wrong"}}})
            send({"method": "item/agentMessage/delta", "params": {"delta": "PRIVATE_SENTINEL"}})
            total += 20
            if mode != "missing":
                send({"method": "thread/tokenUsage/updated", "params": {"threadId": "session", "turnId": turn,
                    "tokenUsage": {"total": {"inputTokens": total, "cachedInputTokens": 0,
                        "outputTokens": total // 2, "reasoningOutputTokens": 0}}}})
            send({"method": "turn/completed", "params": {"threadId": "session",
                "turn": {"id": turn, "status": "failed" if mode == "failed" else "completed"}}})
            if mode == "late-wrong":
                send({"id": identifier, "result": {"turn": {"id": "wrong"}}})


class OwnedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.inbox = self.root / "inbox"; self.inbox.mkdir(mode=0o700)
        self.mapping = {"schema": "golem.usage-route.v1", "run_id": "run", "sequence": 1,
            "currency": "USD", "tool_calls": {}, "inbox": str(self.inbox), "require_billed": False}
        self.scope = dict(zip(("account_id", "project_id", "work_id", "attempt_id"), ("a", "p", "w", "t")))

    def run_owned(self, mode="normal", prompts=None, timeout=10):
        return owned.run(self.root / "owned", self.scope, self.mapping, prompts or ["PRIVATE_SENTINEL"],
            cwd=Path(__file__).resolve().parents[1],
            command=[sys.executable, str(Path(__file__).resolve()), "--fake", mode], timeout=timeout)

    def test_multi_turn_automatic_binding_and_baseline(self):
        result = self.run_owned(prompts=["one", "two"])
        self.assertEqual(result["native_delivery"], "PUBLISHED")
        self.assertEqual(len(result["turns"]), 2)
        self.assertEqual(result["turns"][0]["totals"]["token_usage"], result["turns"][1]["totals"]["token_usage"])
        self.assertEqual(len(list(self.inbox.glob("*.json"))), 2)
        self.assertFalse(result["turns"][0]["tool_usage_complete"])
        for path in self.root.rglob("*.json"):
            self.assertNotIn("PRIVATE_SENTINEL", path.read_text())
        p = pipeline.Pipeline(self.root / "owned" / "turn-0001")
        self.assertEqual(p.sync()["native_delivery"], "PUBLISHED")

    def test_missing_usage_and_failed_turn_never_publish(self):
        for mode in ("missing", "failed", "wrong", "late-wrong", "approval", "eof", "oversize"):
            with self.subTest(mode=mode):
                with tempfile.TemporaryDirectory() as temporary:
                    self.root = Path(temporary).resolve()
                    self.inbox = self.root / "inbox"; self.inbox.mkdir(mode=0o700)
                    self.mapping["inbox"] = str(self.inbox)
                    with self.assertRaises((ValueError, KeyError)):
                        self.run_owned(mode)
                    self.assertEqual(list(self.inbox.glob("*.json")), [])
                    self.assertTrue((self.root / "owned" / "exit.json").exists())

    def test_timeout_reaps_child_without_publishing(self):
        with self.assertRaisesRegex(ValueError, "TIMEOUT"):
            self.run_owned("timeout", timeout=1)
        self.assertEqual(list(self.inbox.glob("*.json")), [])

    def test_invalid_arguments_do_not_start_provider(self):
        with self.assertRaises(ValueError):
            self.run_owned(prompts=[""])
        self.assertFalse((self.root / "owned").exists())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fake":
        fake(sys.argv[2])
    else:
        unittest.main()
