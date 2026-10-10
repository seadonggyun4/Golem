"""Owned Codex stdio sessions with automatic turn-to-Work usage delivery.

Prompts, responses, auth messages and stderr stay off disk. This is an owning
client, not an interceptor for unrelated desktop/browser conversations.
"""
import argparse
import json
import os
from pathlib import Path
import selectors
import sys
import time

import execution_record as records
import hosted_usage as hosted
import provider_usage as usage
import usage_pipeline as pipeline
from verify_agent import strict_json


class Transport:
    def __init__(self, child, deadline):
        self.deadline = deadline
        self.process = child
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        os.set_blocking(self.process.stdout.fileno(), False)
        os.set_blocking(self.process.stdin.fileno(), False)
        self.buffer, self.received, self.messages = b"", 0, 0

    def remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("CODEX_SESSION_TIMEOUT")
        return remaining

    def send(self, message):
        data = json.dumps(message, separators=(",", ":"), ensure_ascii=True).encode() + b"\n"
        if len(data) > usage.MAX_BYTES:
            raise ValueError("CODEX_FRAME_LIMIT")
        with selectors.DefaultSelector() as writable:
            writable.register(self.process.stdin, selectors.EVENT_WRITE)
            while data:
                if not writable.select(self.remaining()):
                    raise ValueError("CODEX_SESSION_TIMEOUT")
                try:
                    data = data[os.write(self.process.stdin.fileno(), data):]
                except BlockingIOError:
                    continue

    def receive(self):
        while b"\n" not in self.buffer:
            if len(self.buffer) > usage.MAX_BYTES:
                raise ValueError("CODEX_FRAME_LIMIT")
            if not self.selector.select(self.remaining()):
                raise ValueError("CODEX_SESSION_TIMEOUT")
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise ValueError("CODEX_SESSION_EOF")
            self.received += len(chunk)
            if self.received > 64 * usage.MAX_BYTES:
                raise ValueError("CODEX_STREAM_LIMIT")
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        self.messages += 1
        if len(line) > usage.MAX_BYTES or self.messages > 100000:
            raise ValueError("CODEX_STREAM_LIMIT")
        message = strict_json(line)
        if not isinstance(message, dict):
            raise ValueError("CODEX_PROTOCOL")
        # Approval, authentication refresh and arbitrary server requests must be
        # handled by an authorized interactive client, never silently accepted.
        if "method" in message and "id" in message:
            self.send({"id": message["id"], "error": {"code": -32601,
                       "message": "This usage client does not authorize server requests"}})
            raise ValueError("CODEX_INTERACTIVE_CLIENT_REQUIRED")
        return message

    def response(self, identifier):
        while True:
            message = self.receive()
            if message.get("id") == identifier:
                if "error" in message or not isinstance(message.get("result"), dict):
                    raise ValueError("CODEX_REQUEST_FAILED")
                return message["result"]

    def close(self):
        self.selector.close()


def run(directory, attribution, mapping, prompts, *, cwd, command=None, timeout=300, model=None):
    """Fresh owned thread only; unknown baselines are never assigned to a Work.

    Each sequential turn has an immutable scope and a distinct inbox sequence.
    Failure keeps accepted events for inspection/retry, but stops later turns.
    """
    cwd = Path(cwd).resolve()
    keys = {"account_id", "project_id", "work_id", "attempt_id"}
    if not isinstance(attribution, dict) or set(attribution) != keys:
        raise ValueError("CODEX_ATTRIBUTION_REQUIRED")
    for value in attribution.values():
        usage.text(value)
    pipeline.route(mapping)
    if (not isinstance(prompts, list) or not 1 <= len(prompts) <= 32
            or any(not isinstance(p, str) or not p or len(p.encode()) > 65536 for p in prompts)
            or type(timeout) is not int or not 1 <= timeout <= 3600):
        raise ValueError("CODEX_SESSION_ARGUMENTS")
    usage.add(mapping["sequence"], len(prompts) - 1)
    if model is not None:
        usage.model_name(model)
    command = command or ["codex", "app-server", "--listen", "stdio://"]
    root = records.private_directory(directory)
    records.save(root / "launch.json", records.encoded({"schema": "golem.owned-codex-launch.v1",
        "attribution": attribution, "model_override": model,
        "prompt_count": len(prompts), "raw_streams_persisted": False}))
    results = []
    def session_protocol(child, deadline):
        transport = Transport(child, deadline)
        try:
            return collect(transport)
        finally:
            transport.close()

    def collect(transport):
        transport.send({"id": 1, "method": "initialize", "params": {
            "clientInfo": {"name": "golem_usage", "version": "1.0.0"}}})
        transport.response(1)
        transport.send({"method": "initialized", "params": {}})
        options = {"cwd": str(cwd), "approvalPolicy": "never", "sandbox": "read-only"}
        if model is not None:
            options["model"] = model
        transport.send({"id": 2, "method": "thread/start", "params": options})
        session = usage.text(transport.response(2)["thread"]["id"])
        baseline = dict.fromkeys(hosted.COUNTERS, 0)
        for index, prompt in enumerate(prompts):
            identifier = 3 + index
            transport.send({"id": identifier, "method": "turn/start", "params": {
                "threadId": session, "input": [{"type": "text", "text": prompt}]}})
            current, response_turn, turn_id, completed = None, None, None, False
            while not completed or response_turn is None:
                message = transport.receive()
                if message.get("id") == identifier:
                    if "error" in message:
                        raise ValueError("CODEX_REQUEST_FAILED")
                    response_turn = usage.text(message["result"]["turn"]["id"])
                if message.get("method") == "turn/started":
                    params = message["params"]
                    if params["threadId"] != session or current is not None:
                        raise ValueError("CODEX_UNEXPECTED_TURN")
                    turn_id = usage.text(params["turn"]["id"])
                    scope = {"schema": "golem.hosted-usage-binding.v1", **attribution,
                        "provider": "codex.app-server.v1", "session_id": session,
                        "turn_ids": [turn_id], "baseline": baseline}
                    current = pipeline.Pipeline.create(root / f"turn-{index + 1:04d}", scope,
                        {**mapping, "sequence": mapping["sequence"] + index})
                if current:
                    current.accept(message)
                    if response_turn is not None and response_turn != turn_id:
                        raise ValueError("CODEX_TURN_RESPONSE_MISMATCH")
                    if message.get("method") == "turn/completed":
                        completed = True
                elif message.get("method") in ("thread/tokenUsage/updated", "turn/completed"):
                    raise ValueError("CODEX_USAGE_BEFORE_TURN")
            # Response correlation is required before closing/publishing, even
            # when notifications arrive before the turn/start response.
            _, _, collector = current.load()
            result = current.close()
            results.append(result)
            if not result["totals"]["usage_complete"]:
                raise ValueError("CODEX_USAGE_INCOMPLETE")
            baseline = collector.current
        return {"schema": "golem.owned-codex-result.v1", "turns": results,
                "native_delivery": "PUBLISHED" if all(r["native_delivery"] == "PUBLISHED" for r in results) else "PENDING",
                "native_application": "OWNER_NOT_OBSERVED", "external_conversations_collected": False}
    diagnostic = "CODEX_SESSION_FAILED_PRESERVE_ACCEPTED_EVENTS"
    try:
        result = records.run_private(command, destination=root / "process", timeout=timeout,
                                     cwd=cwd, source=cwd, protocol=session_protocol)
        diagnostic = None
        return result
    except ValueError as error:
        if str(error).startswith("CODEX_"):
            diagnostic = str(error)
        raise
    finally:
        records.save(root / "exit.json", records.encoded({"schema": "golem.owned-codex-exit.v1",
            "observed_turns": len(results),
            "completed_turns": sum(r["totals"]["usage_complete"] for r in results),
            "diagnostic": diagnostic}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--attribution", type=Path, required=True)
    parser.add_argument("--route", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--model", help="Explicit model override; never silently fall back")
    args = parser.parse_args(argv)
    try:
        prompts = strict_json(sys.stdin.buffer.read(usage.MAX_BYTES + 1))
        result = run(args.directory, strict_json(usage.private_bytes(args.attribution)),
                     strict_json(usage.private_bytes(args.route)), prompts,
                     cwd=args.cwd, timeout=args.timeout, model=args.model)
        sys.stdout.buffer.write(records.encoded(result))
        return 0 if result["native_delivery"] == "PUBLISHED" else 2
    except (ValueError, OSError, KeyError, TypeError):
        sys.stderr.write('CODEX_SESSION_FAILED: preserve accepted events; check owned session and route.\n')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
