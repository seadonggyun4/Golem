"""Read-only preflight -> projection -> count -> fenced resume -> input handoff.

Only configured provider token-count endpoints are called, never generation.
No hidden conversation/history or credential-store access. Required facts are
retained by the native renderer; stale inputs or exceeded budgets stop resume.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler

import execution_record as records
import provider_usage as usage
from verify_agent import strict_json

ENDPOINTS = {"openai.responses.v1": "https://api.openai.com/v1/responses/input_tokens",
             "anthropic.messages.v1": "https://api.anthropic.com/v1/messages/count_tokens"}
MAX_INPUT = 8 * 1024 * 1024


def error_detail(error):
    code = (str(error) if isinstance(error, ValueError) and
            re.fullmatch(r"CONTEXT_[A-Z_]+", str(error)) else "CONTEXT_EXECUTION_OR_EVIDENCE_ERROR")
    operation, action = {
        "CONTEXT_PREFLIGHT_DONE_READ_NEXT": ("READ_NEXT", "Read native next and completion; do not session-resume DONE."),
        "CONTEXT_PREFLIGHT_LIVE_OWNER_WAIT": ("WAIT_OWNER", "Respect the live owner; wait for lawful handoff/expiry, never force takeover."),
        "CONTEXT_PREFLIGHT_STALE_OR_UNSUPPORTED": ("READ_STATUS_NEXT", "Inspect current full status/next and engine compatibility; review a fresh request explicitly."),
        "CONTEXT_PREFLIGHT_REVIEW_REQUIRED": ("REVIEW_PREFLIGHT", "Inspect preserved full status/next; do not infer permission or retry effects."),
        "CONTEXT_INCOMPLETE_SOURCE": ("REVIEW_ORIGINAL_CONTEXT", "Use explicit current-v1 or original-v1 with sufficient byte/token budgets; do not drop required source bodies."),
        "CONTEXT_PREFLIGHT_BINDING": ("READ_STATUS_NEXT", "Review fresh full status/next and count identical complete input; do not reuse old counts."),
        "CONTEXT_TOKEN_BUDGET_EXHAUSTED": ("REVIEW_BUDGET", "Review an adequate budget explicitly; do not truncate mandatory context or reuse counts."),
    }.get(code, ("INSPECT_ORIGINAL", "Inspect preserved logs and identical resume key; do not auto-retry or drop required facts."))
    return {"code": code, "error_type": type(error).__name__,
            "next_operation": operation, "next_action": action}


def config(value):
    fields = {"schema", "provider", "model", "credential_env", "token_budget", "reserve_tokens", "instructions"}
    if not isinstance(value, dict) or set(value) != fields or value["schema"] not in (
            "golem.context-provider.v1", "golem.context-provider.v2"):
        raise ValueError("CONTEXT_PROVIDER_SCHEMA")
    if not isinstance(value["provider"], str) or value["provider"] not in ENDPOINTS:
        raise ValueError("CONTEXT_PROVIDER_UNSUPPORTED")
    if not isinstance(value["model"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value["model"]):
        raise ValueError("CONTEXT_MODEL")
    if not isinstance(value["credential_env"], str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value["credential_env"]):
        raise ValueError("CONTEXT_CREDENTIAL_ENV")
    budget, reserve = usage.count(value["token_budget"]), usage.count(value["reserve_tokens"])
    if not 0 <= reserve < budget <= 1000000000:
        raise ValueError("CONTEXT_BUDGET")
    if not isinstance(value["instructions"], str) or len(value["instructions"].encode()) > 16384 or "\x00" in value["instructions"]:
        raise ValueError("CONTEXT_INSTRUCTIONS")
    return dict(value)


def tokenizer_id(settings, preflight=None):
    version = 2 if settings["schema"] == "golem.context-provider.v2" else 1
    identity = {"adapter": f"provider-input-count-v{version}", "provider": settings["provider"],
                "model": settings["model"], "instructions": settings["instructions"]}
    if version == 2:
        identity.update(adapter="provider-input-count-v2-preflight",
                        preflight_sha256=hashlib.sha256(records.encoded(preflight)).hexdigest())
    return f"count-v{version}-" + hashlib.sha256(records.encoded(identity)).hexdigest()[:32]


def provider_input(settings, candidate, preflight=None):
    text = candidate["candidate_json"]
    if (not isinstance(text, str) or len(text.encode()) > 2097152
        or hashlib.sha256(text.encode()).hexdigest() != candidate["projection_digest"]
        or strict_json(text.encode()) != candidate["candidate"] or candidate["budget_verified"] is not False):
        raise ValueError("CONTEXT_CANDIDATE_BINDING")
    version = 2 if settings["schema"] == "golem.context-provider.v2" else 1
    if (candidate["candidate"].get("schema_version") != version or
            candidate["candidate"].get("request", {}).get("renderer_version") != version):
        raise ValueError("CONTEXT_REPRESENTATION_VERSION")
    if version == 2:
        if (not isinstance(preflight, dict) or set(preflight) != {"status", "next"}
                or any(not isinstance(preflight[key], dict) for key in preflight)
                or type(preflight["status"].get("sequence")) is not int
                or type(preflight["next"].get("sequence")) is not int
                or preflight["status"]["sequence"] != preflight["next"]["sequence"]):
            raise ValueError("CONTEXT_PREFLIGHT_BINDING")
        projection = candidate["candidate"]
        if (projection["request"].get("recipe") not in ("original-v1", "current-v1")
                or not isinstance(projection.get("sources"), list)
                or not projection["sources"]
                or any(not isinstance(item, dict) or type(item.get("omitted_bytes")) is not int
                       or item["omitted_bytes"] != 0 for item in projection["sources"])):
            raise ValueError("CONTEXT_INCOMPLETE_SOURCE")
        if projection["request"].get("tokenizer_id") != tokenizer_id(settings, preflight):
            raise ValueError("CONTEXT_PREFLIGHT_BINDING")
        text = records.encoded({"schema": "golem.context-input.v2", "projection": projection,
            "preflight": preflight, "preflight_only": True, "execution_authorized": False,
            "next_action": "Inspect the post-resume native receipt and reconcile uncertain effects before execution."}).decode()
    common = {"model": settings["model"]}
    if settings["provider"] == "openai.responses.v1":
        common.update(input=[{"role": "user", "content": text}], instructions=settings["instructions"])
    else:
        common.update(messages=[{"role": "user", "content": text}], system=settings["instructions"])
    return common


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise ValueError("CONTEXT_COUNT_REDIRECT_DENIED")


def count_input(settings, payload):
    """Provider/model count of this complete input envelope, not billing usage."""
    credential = os.environ.get(settings["credential_env"])
    if not isinstance(credential, str) or not 16 <= len(credential) <= 4096 or not credential.isascii() or any(ord(c) <= 32 or ord(c) >= 127 for c in credential):
        raise ValueError("CONTEXT_COUNT_CREDENTIAL_UNAVAILABLE")
    raw = records.encoded(payload)
    if len(raw) > MAX_INPUT or credential.encode() in raw:
        raise ValueError("CONTEXT_COUNT_INPUT_LIMIT_OR_SECRET")
    headers = {"Content-Type": "application/json", "Accept": "application/json", "Accept-Encoding": "identity"}
    provider = settings["provider"]
    if provider == "openai.responses.v1":
        headers["Authorization"] = "Bearer " + credential
    else:
        headers.update({"x-api-key": credential, "anthropic-version": "2023-06-01"})
    url = ENDPOINTS[provider]
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    deadline = time.monotonic() + 30
    try:
        with opener.open(Request(url, data=raw, headers=headers, method="POST"), timeout=10) as response:
            if response.status != 200 or response.geturl() != url or response.headers.get_content_type() != "application/json" or response.headers.get("Content-Encoding", "identity") != "identity":
                raise ValueError("CONTEXT_COUNT_HTTP_RESPONSE")
            chunks, size = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise ValueError("CONTEXT_COUNT_DEADLINE")
                chunk = response.read1(min(65536, usage.MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk); size += len(chunk)
                if size > usage.MAX_BYTES:
                    raise ValueError("CONTEXT_COUNT_RESPONSE_LIMIT")
            body = b"".join(chunks)
            if credential.encode() in body:
                raise ValueError("CONTEXT_COUNT_SECRET_ECHO")
            value = strict_json(body)
            expected = {"object", "input_tokens"} if provider == "openai.responses.v1" else {"input_tokens"}
            if not isinstance(value, dict) or set(value) != expected or (provider == "openai.responses.v1" and value["object"] != "response.input_tokens"):
                raise ValueError("CONTEXT_COUNT_SCHEMA")
            tokens = usage.count(value["input_tokens"])
            if not 0 < tokens <= 1000000000:
                raise ValueError("CONTEXT_COUNT_RANGE")
            return {"schema": "golem.context-count-observation.v1", "provider": provider,
                    "model": settings["model"], "endpoint": url, "input_tokens": tokens,
                    "input_sha256": hashlib.sha256(raw).hexdigest(),
                    "response_sha256": hashlib.sha256(body).hexdigest(), "response": value,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "basis": "PROVIDER_COUNT_ESTIMATE" if provider == "anthropic.messages.v1" else "PROVIDER_INPUT_COUNT",
                    "credential_recorded": False, "billing_usage": False}
    except HTTPError as error:
        error.close()
        raise ValueError("CONTEXT_COUNT_HTTP_ERROR") from None
    except (URLError, OSError):
        raise ValueError("CONTEXT_COUNT_NETWORK_ERROR") from None


def resume(cli, work, request, context, settings, output, *, source=None):
    settings = config(settings)
    if not isinstance(request, dict) or request.get("operation") != "resume":
        raise ValueError("CONTEXT_RESUME_OPERATION")
    if not isinstance(context, dict):
        raise ValueError("CONTEXT_REQUEST")
    version = 2 if settings["schema"] == "golem.context-provider.v2" else 1
    if context.get("renderer_version") != version:
        raise ValueError("CONTEXT_REPRESENTATION_VERSION")
    context = dict(context)
    context.update(token_budget=settings["token_budget"] - settings["reserve_tokens"],
                   tokenizer_id=tokenizer_id(settings))
    cli, work = Path(cli).resolve(strict=True), Path(work).resolve(strict=True)
    directory = records.private_directory(output)
    records.save(directory / "resume-request.json", records.encoded(request))
    records.save(directory / "provider-config.json", records.encoded(settings))
    try:
        queries = {}
        for operation in ("status", "next"):
            query = {"schema_version": 1, "operation": operation,
                     "work_id": request.get("work_id")}
            path = directory / (operation + "-request.json")
            records.save(path, records.encoded(query))
            result = records.run([str(cli), "--output-mode", "full", "session", "call",
                                  str(work), str(path)], destination=directory / (operation + "-process"),
                                 timeout=90, source=source)
            if len(result.stdout) > MAX_INPUT:
                raise ValueError("CONTEXT_PREFLIGHT_LIMIT")
            queries[operation] = strict_json(result.stdout)
            records.save(directory / (operation + "-observation.json"), records.encoded(queries[operation]))
        status, following = queries["status"], queries["next"]
        hint = status.get("resume_preflight", {})
        sequence = status.get("sequence")
        if (hint.get("schema_version") != 1 or type(sequence) is not int or
                type(request.get("expected_sequence")) is not int or
                hint.get("expected_sequence") != sequence or
                following.get("sequence") != sequence or request.get("expected_sequence") != sequence):
            raise ValueError("CONTEXT_PREFLIGHT_STALE_OR_UNSUPPORTED")
        if hint.get("reason") == "DONE" or following.get("action") == "DONE":
            raise ValueError("CONTEXT_PREFLIGHT_DONE_READ_NEXT")
        if hint.get("next_operation") in ("REVIEW_POLICY", "SESSION_START", "INSPECT_WORKFLOW"):
            raise ValueError("CONTEXT_PREFLIGHT_REVIEW_REQUIRED")
        if following.get("action") == "BLOCKED" and following.get("reason") not in (
                "RESUME_REQUIRED", "RECONCILIATION_REQUIRED"):
            raise ValueError("CONTEXT_PREFLIGHT_REVIEW_REQUIRED")
        if hint.get("lease_live") is True and hint.get("owner_session_id") != request.get("session_id"):
            raise ValueError("CONTEXT_PREFLIGHT_LIVE_OWNER_WAIT")
        if version == 2:
            if context.get("recipe") not in ("original-v1", "current-v1"):
                raise ValueError("CONTEXT_INCOMPLETE_SOURCE")
            context["tokenizer_id"] = tokenizer_id(settings, queries)
        records.save(directory / "context-request.json", records.encoded(context))
        result = records.run([str(cli), "--output-mode", "full", "context", "candidate", str(work),
                              str(directory / "context-request.json")], destination=directory / "candidate-process",
                             timeout=90, source=source)
        if len(result.stdout) > MAX_INPUT:
            raise ValueError("CONTEXT_CANDIDATE_LIMIT")
        candidate = strict_json(result.stdout)
        bound_preflight = queries if version == 2 else None
        payload = provider_input(settings, candidate, bound_preflight)
        payload_bytes = records.encoded(payload)
        payload_digest = hashlib.sha256(payload_bytes).hexdigest()
        observation = count_input(settings, payload)
        if (observation.get("input_sha256") != payload_digest or
                records.encoded(payload) != payload_bytes or
                records.encoded(provider_input(settings, candidate, bound_preflight)) != payload_bytes or
                tokenizer_id(settings, bound_preflight) != context["tokenizer_id"]):
            raise ValueError("CONTEXT_COUNT_PAYLOAD_BINDING")
        if not 0 < usage.count(observation["input_tokens"]) <= 1000000000:
            raise ValueError("CONTEXT_COUNT_RANGE")
        records.save(directory / "provider-input.json", payload_bytes)
        records.save(directory / "token-count-observation.json", records.encoded(observation))
        if observation["input_tokens"] > context["token_budget"]:
            raise ValueError("CONTEXT_TOKEN_BUDGET_EXHAUSTED")
        proof = {"schema_version": 1, "tokenizer_id": context["tokenizer_id"],
                 "projection_digest": candidate["projection_digest"], "input_tokens": observation["input_tokens"]}
        records.save(directory / "token-count.json", records.encoded(proof))
        result = records.run([str(cli), "--output-mode", "full", "session", "resume", str(work),
                              str(directory / "resume-request.json"), str(directory / "context-request.json"),
                              str(directory / "token-count.json")], destination=directory / "resume-process",
                             timeout=90, source=source)
        if len(result.stdout) > MAX_INPUT:
            raise ValueError("CONTEXT_RESUME_REPLY_LIMIT")
        handoff = strict_json(result.stdout)
        if handoff["context_digest"] != candidate["projection_digest"] or handoff["context_projection"] != candidate["candidate"] or handoff["budget_verified"] is not True:
            raise ValueError("CONTEXT_HANDOFF_BINDING")
        if records.encoded(provider_input(settings, candidate, bound_preflight)) != payload_bytes:
            raise ValueError("CONTEXT_COUNT_PAYLOAD_BINDING")
        records.save(directory / "resume-handoff.json", records.encoded(handoff))
        summary = {"schema": "golem.context-resume-handoff.v1", "state": "RESUMED_INPUT_READY",
                   "context_digest": handoff["context_digest"], "input_sha256": observation["input_sha256"],
                   "input_tokens": observation["input_tokens"], "basis": observation["basis"],
                   "token_budget": settings["token_budget"], "reserve_tokens": settings["reserve_tokens"],
                   "provider_input": "provider-input.json", "receipt": "resume-handoff.json",
                   "generation_executed": False, "execution_authorized": False}
        if version == 2:
            summary.update(schema="golem.context-resume-handoff.v2", renderer_version=2,
                           preflight_sha256=hashlib.sha256(records.encoded(queries)).hexdigest())
        records.save(directory / "result.json", records.encoded(summary))
        from agent_io import file_inventory, producer
        records.save(directory / "manifest.json", records.encoded({"producer": producer(), "files": file_inventory(directory)}))
        return summary
    except Exception as error:
        # A failed resume subprocess may have committed; never retry mutations.
        records.save(directory / "failure.json", records.encoded({"state": "INCOMPLETE", **error_detail(error),
                    "resume_may_have_committed": (directory / "resume-process").exists()}))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cli", "work", "request", "context", "provider", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    try:
        result = resume(args.cli, args.work, strict_json(usage.private_bytes(args.request)),
                        strict_json(usage.private_bytes(args.context)), strict_json(usage.private_bytes(args.provider)),
                        args.output, source=args.source)
        print(json.dumps(result, sort_keys=True)); return 0
    except Exception as error:
        print(json.dumps({"state": "FAILED", **error_detail(error), "execution_authorized": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
