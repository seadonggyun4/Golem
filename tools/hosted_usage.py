"""Explicitly scoped hosted usage: Codex notifications and Claude OTLP/JSON.

No account history scanning, prompt capture, global configuration, or billing
inference. A binding belongs to one Work; shared sessions need prompt/turn IDs.
"""
import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import time
import uuid

import provider_usage as usage
from verify_agent import strict_json
from execution_record import private_directory, save

COMMON = {"schema", "provider", "account_id", "project_id", "work_id", "attempt_id", "session_id"}
COUNTERS = {"inputTokens": "input_tokens", "cachedInputTokens": "cached_input_tokens",
            "outputTokens": "output_tokens", "reasoningOutputTokens": "reasoning_tokens"}


def binding(value):
    provider = value.get("provider")
    extra = {"turn_ids", "baseline"} if provider == "codex.app-server.v1" else {"prompt_ids", "session_owned"}
    if (set(value) != COMMON | extra or value["schema"] != "golem.hosted-usage-binding.v1"
            or provider not in ("codex.app-server.v1", "claude.otel.v1")):
        raise ValueError("HOSTED_BINDING")
    for key in COMMON - {"schema", "provider"}:
        usage.text(value[key])
    ids = value["turn_ids" if provider == "codex.app-server.v1" else "prompt_ids"]
    owned = value.get("session_owned", False)
    if type(owned) is not bool:
        raise ValueError("HOSTED_SCOPE")
    if not isinstance(ids, list) or not (0 if owned else 1) <= len(ids) <= 256 or len(set(ids)) != len(ids):
        raise ValueError("HOSTED_SCOPE")
    for identifier in ids:
        usage.text(identifier)
    if provider == "codex.app-server.v1":
        breakdown(value["baseline"])
    return value


def breakdown(value):
    if (not isinstance(value, dict) or set(value) - (set(COUNTERS) | {"totalTokens", "cacheWriteInputTokens"})
            or not set(COUNTERS) <= set(value)):
        raise ValueError("HOSTED_COUNTER_SCHEMA")
    result = {k: usage.count(value[k]) for k in COUNTERS}
    if result["cachedInputTokens"] > result["inputTokens"] or result["reasoningOutputTokens"] > result["outputTokens"]:
        raise ValueError("HOSTED_SUBTOTAL")
    if "totalTokens" in value and usage.count(value["totalTokens"]) != result["inputTokens"] + result["outputTokens"]:
        raise ValueError("HOSTED_TOTAL")
    if "cacheWriteInputTokens" in value:
        writes = usage.count(value["cacheWriteInputTokens"])
        if writes > result["inputTokens"] - result["cachedInputTokens"]:
            raise ValueError("HOSTED_SUBTOTAL")
    return result


def otlp_attributes(rows):
    if not isinstance(rows, list):
        raise ValueError("HOSTED_OTLP_ATTRIBUTES")
    result, seen = {}, set()
    for row in rows:
        if set(row) != {"key", "value"} or not isinstance(row["key"], str) or row["key"] in seen:
            raise ValueError("HOSTED_OTLP_ATTRIBUTES")
        seen.add(row["key"])
        value = row["value"]
        if not isinstance(value, dict) or len(value) != 1:
            raise ValueError("HOSTED_OTLP_VALUE")
        kind, value = next(iter(value.items()))
        if kind == "intValue":
            if isinstance(value, str) and value.isascii() and value.isdecimal():
                value = int(value)
            if type(value) is not int:
                raise ValueError("HOSTED_OTLP_INTEGER")
            value = usage.count(value)
        elif kind == "stringValue":
            if not isinstance(value, str):
                raise ValueError("HOSTED_OTLP_VALUE")
        else:
            # Other attributes are not usage evidence and are never persisted.
            continue
        result[row["key"]] = value
    return result


class Collector:
    def __init__(self, scope):
        self.scope = binding(scope)
        self.rows = {}
        self.completed = set()
        self.active = None
        self.baseline = breakdown(scope["baseline"]) if "baseline" in scope else None
        self.current = self.baseline
        self.events = 0
        self.seen_prompts = set()

    def accept(self, message, publish=None):
        """All changes are transactional; reject an entire conflicting batch."""
        import copy
        trial = copy.deepcopy(self)
        trial.events += 1
        if trial.events > usage.MAX_EVENTS:
            raise ValueError("HOSTED_LIMIT")
        if trial.scope["provider"] == "codex.app-server.v1":
            trial.codex(message)
        else:
            trial.claude(message)
        if publish is not None:
            publish(trial)
        self.__dict__.update(trial.__dict__)

    def codex(self, message):
        method, params = message.get("method"), message.get("params", {})
        if method not in ("turn/started", "turn/completed", "thread/tokenUsage/updated"):
            return
        if params.get("threadId") != self.scope["session_id"]:
            return
        turn = params.get("turnId") if method == "thread/tokenUsage/updated" else params["turn"]["id"]
        if turn not in self.scope["turn_ids"]:
            raise ValueError("HOSTED_UNBOUND_TURN")
        if method == "turn/started":
            if self.active == turn:
                return
            if self.active is not None and self.active not in self.completed:
                raise ValueError("HOSTED_OVERLAPPING_TURN")
            if self.active is not None and self.active not in self.rows:
                raise ValueError("HOSTED_BOUNDARY_USAGE_REQUIRED")
            if turn in self.completed:
                raise ValueError("HOSTED_REPLAY_ORDER")
            self.active, self.baseline = turn, self.current
        elif method == "thread/tokenUsage/updated":
            if self.active != turn:
                raise ValueError("HOSTED_BASELINE_REQUIRED")
            total = breakdown(params["tokenUsage"]["total"])
            if any(total[k] < self.current[k] for k in COUNTERS):
                raise ValueError("HOSTED_COUNTER_RESET")
            delta = {k: total[k] - self.baseline[k] for k in COUNTERS}
            breakdown(delta)
            incoming, cached = delta["inputTokens"], delta["cachedInputTokens"]
            outgoing, reasoning = delta["outputTokens"], delta["reasoningOutputTokens"]
            self.rows[turn] = {"request_id": turn, "model": "unreported",
                "tokens": dict(zip(usage.BUCKETS, (incoming - cached, cached, outgoing - reasoning, reasoning))),
                "cache_write_tokens": 0, "final": turn in self.completed, "billing": None}
            self.current = total
        else:
            if self.active != turn:
                raise ValueError("HOSTED_BASELINE_REQUIRED")
            # Failed/interrupted turns may have partial usage, never complete coverage.
            if params["turn"].get("status") == "completed":
                self.completed.add(turn)
                if turn in self.rows:
                    self.rows[turn]["final"] = True

    def claude(self, message):
        for resource in message["resourceLogs"]:
            common = otlp_attributes(resource.get("resource", {}).get("attributes", []))
            for scope in resource.get("scopeLogs", []):
                for log in scope.get("logRecords", []):
                    attrs = dict(common)
                    attrs.update(otlp_attributes(log.get("attributes", [])))
                    if attrs.get("event.name") not in ("api_request", "claude_code.api_request"):
                        continue
                    if attrs.get("session.id") != self.scope["session_id"]:
                        continue
                    if not self.scope["session_owned"] and attrs.get("prompt.id") not in self.scope["prompt_ids"]:
                        continue
                    request, model = usage.text(attrs["request_id"]), usage.model_name(attrs["model"])
                    counters = {"input_tokens": attrs["input_tokens"], "output_tokens": attrs["output_tokens"],
                                "cache_read_input_tokens": attrs["cache_read_tokens"],
                                "cache_creation_input_tokens": attrs["cache_creation_tokens"]}
                    tokens, writes = usage.anthropic(counters)
                    current = {"request_id": request, "model": model, "tokens": tokens,
                               "cache_write_tokens": writes, "final": True, "billing": None}
                    if request in self.rows and self.rows[request] != current:
                        raise ValueError("HOSTED_REQUEST_CONFLICT")
                    self.rows[request] = current
                    if "prompt.id" in attrs:
                        self.seen_prompts.add(attrs["prompt.id"])
                    if len(self.rows) > usage.MAX_EVENTS:
                        raise ValueError("HOSTED_LIMIT")

    def record(self):
        a = {k: self.scope[k] for k in COMMON - {"schema"}}
        expected = self.scope.get("turn_ids", list(self.rows))
        # Explicit unknown coverage for a bound scope with no observed requests.
        if "prompt_ids" in self.scope:
            expected += ["unobserved:" + p for p in self.scope["prompt_ids"] if p not in self.seen_prompts]
        expected = expected or ["unobserved:" + self.scope["session_id"]]
        calls = [{"attribution": a, "request_id": request, "observation": self.rows.get(request),
                  "status": "COMPLETE" if self.rows.get(request, {}).get("final") else "UNKNOWN"}
                 for request in expected]
        return {"schema": "golem.work-usage.v1", "calls": calls, "source_sha256": None,
                "attribution_basis": "EXPLICIT_HOSTED_SCOPE", "independently_verified": False,
                "coverage": "OBSERVED_PROVIDER_EVENTS_ONLY"}


def persist(output, collector):
    record = collector.record()
    payload = (json.dumps(record, sort_keys=True) + "\n").encode()
    if len(payload) > usage.MAX_BYTES:
        raise ValueError("HOSTED_LIMIT")
    save(output / "usage.json", payload)
    save(output / "binding.json", (json.dumps(collector.scope, sort_keys=True) + "\n").encode())
    from agent_io import file_inventory, producer
    save(output / "manifest.json", (json.dumps({"schema": "golem.hosted-usage-manifest.v1",
         "producer": producer(), "files": file_inventory(output)}) + "\n").encode())
    return usage.totals([record])


def server(collector, token, port=0, publish=None):
    if not isinstance(token, str) or len(token) < 32 or not token.isascii():
        raise ValueError("HOSTED_AUTH_TOKEN")
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.connection.settimeout(2)
            self.server.requests += 1
            if self.path != "/v1/logs" or not hmac.compare_digest(
                    self.headers.get("Authorization", "").encode("utf-8"), ("Bearer " + token).encode("ascii")):
                self.send_error(403); return
            try:
                data = http_body(self.headers, self.rfile)
                collector.accept(strict_json(data), publish)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
                code = str(error)
                if len(self.server.errors) < 32:
                    self.server.errors.append(code if code.startswith("HOSTED_") else type(error).__name__)
                self.send_error(503 if isinstance(error, OSError) else 400); return
            self.send_response(200); self.send_header("Content-Length", "2")
            self.end_headers(); self.wfile.write(b"{}")
    http = HTTPServer(("127.0.0.1", port), Handler)
    http.requests, http.errors = 0, []
    return http


def http_body(headers, stream):
    """Bounded HTTP framing, including pre-2.1.212 Claude chunked exports."""
    lengths, transfer = headers.get_all("Content-Length", []), headers.get_all("Transfer-Encoding", [])
    if headers.get("Content-Encoding") or len(lengths) > 1 or len(transfer) > 1 or (lengths and transfer):
        raise ValueError("HOSTED_HTTP_FRAMING")
    if transfer:
        if transfer[0].lower() != "chunked":
            raise ValueError("HOSTED_HTTP_FRAMING")
        chunks, size = [], 0
        for _ in range(4096):
            line = stream.readline(128)
            if not line.endswith(b"\r\n") or not 1 <= len(line[:-2]) <= 8 or any(c not in b"0123456789abcdefABCDEF" for c in line[:-2]):
                raise ValueError("HOSTED_CHUNKED")
            length = int(line[:-2], 16)
            if length == 0:
                # No trailer semantics are accepted for an authenticated usage body.
                if stream.readline(128) != b"\r\n":
                    raise ValueError("HOSTED_CHUNKED_TRAILER")
                return b"".join(chunks)
            if size + length > usage.MAX_BYTES:
                raise ValueError("HOSTED_LIMIT")
            data = stream.read(length)
            if len(data) != length or stream.read(2) != b"\r\n":
                raise ValueError("HOSTED_TRUNCATED")
            chunks.append(data); size += length
        raise ValueError("HOSTED_LIMIT")
    if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal() or not 1 <= int(lengths[0]) <= usage.MAX_BYTES:
        raise ValueError("HOSTED_HTTP_LENGTH")
    data = stream.read(int(lengths[0]))
    if len(data) != int(lengths[0]):
        raise ValueError("HOSTED_TRUNCATED")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("ingest", "listen"))
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()
    try:
        collector = Collector(strict_json(usage.private_bytes(args.binding)))
        output = private_directory(args.output)
        if args.mode == "ingest":
            if args.source is None:
                raise ValueError("HOSTED_SOURCE_REQUIRED")
            data = usage.private_bytes(args.source)
            messages = data.splitlines() if collector.scope["provider"] == "codex.app-server.v1" else [data]
            for message in messages:
                collector.accept(strict_json(message))
        else:
            if not 1 <= args.seconds <= 3600 or not 0 <= args.port <= 65535:
                raise ValueError("HOSTED_LISTEN_LIMIT")
            checkpoints = private_directory(output / "checkpoints")
            def checkpoint(trial):
                # New sealed checkpoint per accepted batch; never overwrite evidence.
                if sum(p.stat().st_size for p in checkpoints.rglob("*") if p.is_file()) > 32 * usage.MAX_BYTES:
                    raise ValueError("HOSTED_STORAGE_LIMIT")
                persist(private_directory(checkpoints / ("%04d-%s" % (trial.events, uuid.uuid4().hex))), trial)
            with server(collector, os.environ.get("GOLEM_USAGE_INGEST_TOKEN"), args.port, checkpoint) as http:
                http.timeout = 1
                print(json.dumps({"endpoint": "http://127.0.0.1:%s/v1/logs" % http.server_port}), flush=True)
                end = time.monotonic() + args.seconds
                while time.monotonic() < end:
                    http.handle_request()
        print(json.dumps(persist(output, collector), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({"schema": "golem.hosted-usage-error.v1", "code": str(error)[:96],
                          "next_action": "Inspect explicit scope and supported provider event schema."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
