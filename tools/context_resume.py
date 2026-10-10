"""Explicit projection -> provider count -> fenced resume -> provider input handoff.

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


def config(value):
    fields = {"schema", "provider", "model", "credential_env", "token_budget", "reserve_tokens", "instructions"}
    if not isinstance(value, dict) or set(value) != fields or value["schema"] != "golem.context-provider.v1":
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


def tokenizer_id(settings):
    identity = {"adapter": "provider-input-count-v1", "provider": settings["provider"],
                "model": settings["model"], "instructions": settings["instructions"]}
    return "count-v1-" + hashlib.sha256(records.encoded(identity)).hexdigest()[:32]


def provider_input(settings, candidate):
    text = candidate["candidate_json"]
    if (not isinstance(text, str) or len(text.encode()) > 2097152
        or hashlib.sha256(text.encode()).hexdigest() != candidate["projection_digest"]
        or strict_json(text.encode()) != candidate["candidate"] or candidate["budget_verified"] is not False):
        raise ValueError("CONTEXT_CANDIDATE_BINDING")
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
    context = dict(context)
    context.update(token_budget=settings["token_budget"] - settings["reserve_tokens"],
                   tokenizer_id=tokenizer_id(settings))
    cli, work = Path(cli).resolve(strict=True), Path(work).resolve(strict=True)
    directory = records.private_directory(output)
    records.save(directory / "context-request.json", records.encoded(context))
    records.save(directory / "resume-request.json", records.encoded(request))
    records.save(directory / "provider-config.json", records.encoded(settings))
    try:
        result = records.run([str(cli), "--output-mode", "full", "context", "candidate", str(work),
                              str(directory / "context-request.json")], destination=directory / "candidate-process",
                             timeout=90, source=source)
        if len(result.stdout) > MAX_INPUT:
            raise ValueError("CONTEXT_CANDIDATE_LIMIT")
        candidate = strict_json(result.stdout)
        payload = provider_input(settings, candidate)
        observation = count_input(settings, payload)
        records.save(directory / "provider-input.json", records.encoded(payload))
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
        records.save(directory / "resume-handoff.json", records.encoded(handoff))
        summary = {"schema": "golem.context-resume-handoff.v1", "state": "RESUMED_INPUT_READY",
                   "context_digest": handoff["context_digest"], "input_sha256": observation["input_sha256"],
                   "input_tokens": observation["input_tokens"], "basis": observation["basis"],
                   "token_budget": settings["token_budget"], "reserve_tokens": settings["reserve_tokens"],
                   "provider_input": "provider-input.json", "receipt": "resume-handoff.json",
                   "generation_executed": False, "execution_authorized": False}
        records.save(directory / "result.json", records.encoded(summary))
        from agent_io import file_inventory, producer
        records.save(directory / "manifest.json", records.encoded({"producer": producer(), "files": file_inventory(directory)}))
        return summary
    except Exception as error:
        # A failed resume subprocess may have committed; never retry mutations.
        records.save(directory / "failure.json", records.encoded({"state": "INCOMPLETE", "error_type": type(error).__name__,
                    "code": str(error) if isinstance(error, ValueError) and re.fullmatch(r"CONTEXT_[A-Z_]+", str(error)) else "CONTEXT_EXECUTION_OR_EVIDENCE_ERROR",
                    "resume_may_have_committed": (directory / "resume-process").exists(),
                    "next_action": "Inspect preserved logs and identical resume key; do not auto-retry or drop required facts."}))
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
        print(json.dumps({"state": "FAILED", "error_type": type(error).__name__,
                          "code": str(error) if isinstance(error, ValueError) and re.fullmatch(r"CONTEXT_[A-Z_]+", str(error)) else "CONTEXT_EXECUTION_OR_EVIDENCE_ERROR",
                          "next_action": "Inspect private evidence; no automatic retry, summary fallback or generation."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
