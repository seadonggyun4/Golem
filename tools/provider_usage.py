"""Bounded provider usage snapshots, explicitly attributed to one agent command.

Adapters emit usage-only JSON lines; no prompt/content or global account totals.
Amounts are provider/billing observations, never inferred from token prices.
"""
import hashlib
import json
import re
from pathlib import Path
import os
import stat
from decimal import Decimal, ROUND_HALF_EVEN

MAX = (1 << 64) - 1
MAX_BYTES = 1024 * 1024
MAX_EVENTS = 4096
BUCKETS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")
TEXT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}\Z")
FIELDS = {"schema", "request_id", "model", "usage", "final", "billing"}


def count(value):
    if type(value) is not int or not 0 <= value <= MAX:
        raise ValueError("USAGE_COUNTER")
    return value


def add(a, b):
    return count(a + b)


def text(value):
    if not isinstance(value, str) or not TEXT.fullmatch(value):
        raise ValueError("USAGE_IDENTITY")
    return value


def model_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/\[\]-]{0,95}", value):
        raise ValueError("USAGE_MODEL")
    return value


def binding(value):
    if not isinstance(value, dict) or set(value) != {
            "provider", "account_id", "project_id", "work_id", "attempt_id", "session_id", "request_ids"}:
        raise ValueError("USAGE_BINDING")
    for key in ("account_id", "project_id", "work_id", "attempt_id", "session_id"):
        text(value[key])
    if value["provider"] not in ADAPTERS:
        raise ValueError("USAGE_PROVIDER")
    ids = value["request_ids"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= 256:
        raise ValueError("USAGE_REQUESTS")
    for request in ids:
        text(request)
    if len(set(ids)) != len(ids):
        raise ValueError("USAGE_REQUESTS")
    return value


def openai(usage):
    allowed = {"input_tokens", "output_tokens", "total_tokens", "input_tokens_details", "output_tokens_details"}
    if not isinstance(usage, dict) or set(usage) - allowed:
        raise ValueError("USAGE_SCHEMA")
    incoming, outgoing = count(usage["input_tokens"]), count(usage["output_tokens"])
    details, output = usage["input_tokens_details"], usage["output_tokens_details"]
    if set(details) - {"cached_tokens", "cache_write_tokens"} or set(output) != {"reasoning_tokens"}:
        raise ValueError("USAGE_SCHEMA")
    cached, reasoning = count(details["cached_tokens"]), count(output["reasoning_tokens"])
    writes = count(details.get("cache_write_tokens", 0))
    if cached > incoming or writes > incoming - cached or reasoning > outgoing:
        raise ValueError("USAGE_SUBTOTAL")
    if "total_tokens" in usage and count(usage["total_tokens"]) != incoming + outgoing:
        raise ValueError("USAGE_TOTAL")
    return dict(zip(BUCKETS, (incoming - cached, cached, outgoing - reasoning, reasoning))), writes


def anthropic(usage):
    allowed = {"input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"}
    if not isinstance(usage, dict) or set(usage) - allowed:
        raise ValueError("USAGE_SCHEMA")
    incoming, outgoing = count(usage["input_tokens"]), count(usage["output_tokens"])
    cached, writes = count(usage.get("cache_read_input_tokens", 0)), count(usage.get("cache_creation_input_tokens", 0))
    # Claude does not report a separate billed reasoning count in this contract.
    return dict(zip(BUCKETS, (add(incoming, writes), cached, outgoing, 0))), writes


def codex(usage):
    if (not isinstance(usage, dict) or set(usage) - {"input_tokens", "cached_input_tokens",
            "output_tokens", "reasoning_output_tokens"}):
        raise ValueError("USAGE_SCHEMA")
    incoming, cached, outgoing = (count(usage[k]) for k in
                                  ("input_tokens", "cached_input_tokens", "output_tokens"))
    reasoning = count(usage.get("reasoning_output_tokens", 0))
    if cached > incoming or reasoning > outgoing:
        raise ValueError("USAGE_SUBTOTAL")
    return dict(zip(BUCKETS, (incoming - cached, cached, outgoing - reasoning, reasoning))), 0


ADAPTERS = {"openai.responses.v1": openai, "anthropic.messages.v1": anthropic,
            "codex.exec.v1": codex, "claude.code.v1": anthropic}


def private_bytes(path):
    """Bound both allocation and trust for usage and captured provider streams."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
            raise ValueError("USAGE_PRIVATE_STREAM")
        chunks, size = [], 0
        while size <= MAX_BYTES:
            chunk = os.read(fd, min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk); size += len(chunk)
        data = b"".join(chunks)
    finally:
        os.close(fd)
    if len(data) > MAX_BYTES:
        raise ValueError("USAGE_LIMIT")
    return data


def collect_cli(stdout, path, attribution):
    """Convert a dedicated fresh CLI invocation, not an account/session total.

    Terminal counters cover the invocation; they are not HTTP request counters.
    Raw output remains in the private execution bundle, never in usage.log.
    """
    binding(attribution)
    if attribution["provider"] not in ("codex.exec.v1", "claude.code.v1"):
        raise ValueError("USAGE_PROVIDER")
    if len(attribution["request_ids"]) != 1:
        raise ValueError("USAGE_CLI_INVOCATION_BINDING")
    from verify_agent import strict_json
    data = private_bytes(stdout)
    lines = data.splitlines()
    if len(lines) > MAX_EVENTS:
        raise ValueError("USAGE_LIMIT")
    terminal, session, model = None, None, "unreported"
    for line in lines:
        row = strict_json(line, parse_float=Decimal)
        if not isinstance(row, dict):
            raise ValueError("USAGE_CLI_SCHEMA")
        if attribution["provider"] == "codex.exec.v1":
            if row.get("type") == "thread.started":
                if session is not None:
                    raise ValueError("USAGE_CLI_SESSION_CONFLICT")
                session = text(row["thread_id"])
            final = row.get("type") == "turn.completed"
        else:
            if row.get("type") == "system" and row.get("subtype") == "init":
                if session is not None:
                    raise ValueError("USAGE_CLI_SESSION_CONFLICT")
                session = text(row["session_id"])
                model = model_name(row["model"])
            final = row.get("type") == "result"
        if final:
            if terminal is not None:
                raise ValueError("USAGE_CLI_MULTIPLE_TERMINALS")
            terminal = row
    metadata = {"granularity": "CLI_INVOCATION", "provider_session_id": session,
                "estimated_cost": None, "billing_verified": False}
    if terminal is None:
        return metadata
    if session is None:
        raise ValueError("USAGE_CLI_MISSING_SESSION")
    if "usage" not in terminal:
        raise ValueError("USAGE_CLI_MISSING_USAGE")
    if (attribution["provider"] == "codex.exec.v1" and "thread_id" in terminal
            and terminal["thread_id"] != session):
        raise ValueError("USAGE_CLI_SESSION_CONFLICT")
    usage = terminal["usage"]
    if attribution["provider"] == "claude.code.v1":
        if terminal.get("session_id") != session:
            raise ValueError("USAGE_CLI_SESSION_CONFLICT")
        usage = {k: usage[k] for k in ("input_tokens", "output_tokens",
                  "cache_read_input_tokens", "cache_creation_input_tokens") if k in usage}
        anthropic(usage)
        model_usage = terminal.get("modelUsage", {})
        if not isinstance(model_usage, dict) or len(model_usage) > 256:
            raise ValueError("USAGE_CLI_MODELS")
        models = [model_name(k) for k in model_usage]
        metadata["reported_models"] = models
        metadata["token_scope"] = "TERMINAL_USAGE_ONLY"
        if models:
            fields = {"input_tokens": "inputTokens", "output_tokens": "outputTokens",
                      "cache_read_input_tokens": "cacheReadInputTokens",
                      "cache_creation_input_tokens": "cacheCreationInputTokens"}
            aggregate = {k: 0 for k in fields}
            for counters in model_usage.values():
                if not isinstance(counters, dict):
                    raise ValueError("USAGE_CLI_MODELS")
                for key, source in fields.items():
                    aggregate[key] = add(aggregate[key], count(counters[source]))
            if any(aggregate[k] < usage.get(k, 0) for k in fields):
                raise ValueError("USAGE_CLI_MODEL_SUBTOTAL")
            metadata["terminal_usage"] = usage
            metadata["token_scope"] = "MODEL_USAGE_AGGREGATE"
            usage = aggregate
            model = models[0] if len(models) == 1 else "multiple"
        if "total_cost_usd" in terminal:
            if type(terminal["total_cost_usd"]) not in (int, Decimal):
                raise ValueError("USAGE_CLI_COST_TYPE")
            amount = Decimal(str(terminal["total_cost_usd"])) * 1000000000
            if not amount.is_finite() or not 0 <= amount <= MAX:
                raise ValueError("USAGE_CLI_COST_PRECISION")
            metadata["estimated_cost"] = {"currency": "USD", "nano_cost": count(int(
                amount.to_integral_value(rounding=ROUND_HALF_EVEN))),
                "reported_usd": str(terminal["total_cost_usd"]),
                "rounding": "HALF_EVEN_NANO", "basis": "CLI_REPORTED_NOT_INVOICE"}
    emit(path, request_id=attribution["request_ids"][0], model=model,
         usage=usage, final=True, provider=attribution["provider"])
    return metadata


def event(value, adapter):
    if not isinstance(value, dict) or set(value) != FIELDS or value["schema"] != "golem.provider-usage.v1":
        raise ValueError("USAGE_SCHEMA")
    text(value["request_id"]); model_name(value["model"])
    if type(value["final"]) is not bool:
        raise ValueError("USAGE_FINAL")
    tokens, writes = ADAPTERS[adapter](value["usage"])
    bill = value["billing"]
    if bill is not None:
        if not isinstance(bill, dict) or set(bill) != {"currency", "nano_cost", "evidence_sha256"}:
            raise ValueError("USAGE_BILLING")
        if not re.fullmatch(r"[A-Z]{3}", bill["currency"]) or not re.fullmatch(r"[0-9a-f]{64}", bill["evidence_sha256"]):
            raise ValueError("USAGE_BILLING")
        count(bill["nano_cost"])
    return {"request_id": value["request_id"], "model": value["model"],
            "tokens": tokens, "cache_write_tokens": writes,
            "final": value["final"], "billing": bill}


def merge(previous, current):
    if previous == current:
        return previous
    if (previous["final"] or previous["model"] != current["model"] or
            any(current["tokens"][key] < previous["tokens"][key] for key in BUCKETS) or
            current["cache_write_tokens"] < previous["cache_write_tokens"] or
            (previous["billing"] is not None and current["billing"] != previous["billing"])):
        raise ValueError("USAGE_CONFLICT")
    return current


def collect(path, attribution):
    """Only the explicit usage stream is parsed; unexpected data fails closed."""
    binding(attribution)
    rows = {}
    data = None
    if path.exists() or path.is_symlink():
        data = private_bytes(path)
        from verify_agent import strict_json
        lines = data.splitlines()
        if len(lines) > MAX_EVENTS:
            raise ValueError("USAGE_LIMIT")
        for line in lines:
            current = event(strict_json(line), attribution["provider"])
            request = current["request_id"]
            if request not in attribution["request_ids"]:
                raise ValueError("USAGE_UNATTRIBUTED_REQUEST")
            rows[request] = merge(rows[request], current) if request in rows else current
    calls = []
    for request in attribution["request_ids"]:
        current = rows.get(request)
        calls.append({"attribution": {k: v for k, v in attribution.items() if k != "request_ids"},
                      "request_id": request, "observation": current,
                      "status": "COMPLETE" if current and current["final"] else "UNKNOWN"})
    return {"schema": "golem.work-usage.v1", "calls": calls,
            "source_sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
            "attribution_basis": "EXPLICIT_CALLER_BINDING", "independently_verified": False}


def totals(records):
    """Union by provider/account/request, rejecting reassignment across Works."""
    calls = {}
    for record in records:
        for call in record["calls"]:
            a = call["attribution"]
            key = (a["provider"], a["account_id"], call["request_id"])
            if key in calls:
                previous = calls[key]
                if previous["attribution"] != a:
                    raise ValueError("USAGE_CONFLICT")
                old, new = previous["observation"], call["observation"]
                if old and new:
                    chosen = merge(new, old) if old["final"] and not new["final"] else merge(old, new)
                    calls[key] = dict(call, observation=chosen,
                                      status="COMPLETE" if chosen["final"] else "UNKNOWN")
                elif new:
                    calls[key] = call
            else:
                calls[key] = call
    tokens = {key: 0 for key in BUCKETS}
    money = {}
    complete = bool(calls) and all(c["status"] == "COMPLETE" for c in calls.values())
    billed = complete
    for call in calls.values():
        observation = call["observation"]
        if observation:
            for key in BUCKETS:
                tokens[key] = add(tokens[key], observation["tokens"][key])
            bill = observation["billing"]
            if bill:
                currency = bill["currency"]
                money[currency] = add(money.get(currency, 0), bill["nano_cost"])
            else:
                billed = False
        else:
            billed = False
    return {"token_usage": tokens if any(c["observation"] for c in calls.values()) else None,
            "usage_complete": complete,
            "reasoning_breakdown_known": complete and all(
                c["attribution"]["provider"] in ("openai.responses.v1", "codex.app-server.v1") for c in calls.values()),
            "cost": money if money else None, "cost_complete": billed,
            "billing_independently_verified": False,
            "requests": len(calls), "unknown_requests": sum(c["status"] != "COMPLETE" for c in calls.values()),
            "basis": "PROVIDER_REPORTED_SNAPSHOTS; BILLING_REPORTED_AMOUNTS; NO_PRICE_ESTIMATE"}


def emit(path, *, request_id, model, usage, final, provider, billing=None):
    """SDK adapters call this after extracting usage; never pass response content."""
    value = {"schema": "golem.provider-usage.v1", "request_id": request_id,
             "model": model, "usage": usage, "final": final, "billing": billing}
    event(value, provider)
    payload = (json.dumps(value, sort_keys=True) + "\n").encode()
    # One adapter owns a stream; concurrent calls use distinct stream files.
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
            raise ValueError("USAGE_PRIVATE_STREAM")
        while payload:
            written = os.write(fd, payload)
            if written == 0:
                raise OSError("usage write made no progress")
            payload = payload[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
