"""Read-only provider cost adapters. Aggregates are never Work invoices.

Fixed HTTPS endpoints, explicit admin credential environment names, bounded
pagination, exact decimal money and immutable private captures. Ingested files
are not authenticated network responses; neither route attests paid invoices.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler

import execution_record as records
import provider_usage as usage
from verify_agent import strict_json

ADAPTERS = {
    "openai.costs.v1": ("https://api.openai.com/v1/organization/costs", "OPENAI_ADMIN_KEY"),
    "anthropic.costs.v1": ("https://api.anthropic.com/v1/organizations/cost_report", "ANTHROPIC_ADMIN_KEY"),
}
MAX_PAGES, MAX_ROWS, MAX_CAPTURE = 32, 4096, 32 * usage.MAX_BYTES


class CostError(ValueError):
    def __init__(self, code, *, http_status=None):
        super().__init__(code)
        self.code, self.http_status = code, http_status


def query(value):
    if (not isinstance(value, dict) or set(value) != {"schema", "provider", "account_id", "start_time", "end_time"}
            or value["schema"] != "golem.provider-cost-query.v1" or not isinstance(value["provider"], str) or value["provider"] not in ADAPTERS):
        raise CostError("COST_QUERY_SCHEMA")
    usage.text(value["account_id"])
    start, end = usage.count(value["start_time"]), usage.count(value["end_time"])
    if start % 86400 or end % 86400 or not 0 < end - start <= 366 * 86400 or end > 253402214400:
        raise CostError("COST_DAY_WINDOW")
    return dict(value)


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        raise CostError("COST_TIMESTAMP")
    return int(datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def decimal_amount(value, *, cents=False):
    if cents:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,64}(?:\.[0-9]{1,64})?", value):
            raise CostError("COST_AMOUNT")
        value = Decimal(value)
    elif type(value) is int:
        value = Decimal(value)
    elif not isinstance(value, Decimal):
        raise CostError("COST_AMOUNT")
    parts = value.as_tuple()
    if not value.is_finite() or value.is_signed() or len(parts.digits) > 64 or not -64 <= parts.exponent <= 64:
        raise CostError("COST_PRECISION_OR_REFUND")
    with localcontext() as ctx:
        ctx.prec = 256
        return value / 100 if cents else value


def params(scope, page=None):
    if scope["provider"] == "openai.costs.v1":
        result = [("start_time", scope["start_time"]), ("end_time", scope["end_time"]),
                  ("bucket_width", "1d"), ("limit", 180),
                  ("group_by", "project_id"), ("group_by", "line_item")]
    else:
        result = [("starting_at", iso(scope["start_time"])), ("ending_at", iso(scope["end_time"])),
                  ("bucket_width", "1d"), ("limit", 31),
                  ("group_by[]", "workspace_id"), ("group_by[]", "description")]
    return result + ([("page", page)] if page is not None else [])


def parse_page(raw, scope):
    if not isinstance(raw, bytes) or len(raw) > usage.MAX_BYTES:
        raise CostError("COST_PAGE_LIMIT")
    value = strict_json(raw, parse_float=Decimal)
    openai = scope["provider"] == "openai.costs.v1"
    fields = {"data", "has_more", "next_page"} | ({"object"} if openai else set())
    if (not isinstance(value, dict) or set(value) != fields or type(value["has_more"]) is not bool
            or not isinstance(value["data"], list) or (openai and value["object"] != "page")):
        raise CostError("COST_PAGE_SCHEMA")
    cursor = value["next_page"]
    if value["has_more"]:
        if not isinstance(cursor, str) or not 1 <= len(cursor) <= 1024 or not cursor.isascii() or any(ord(c) < 33 for c in cursor):
            raise CostError("COST_CURSOR")
    elif cursor is not None:
        raise CostError("COST_CURSOR")
    rows, buckets = [], []
    for bucket in value["data"]:
        expected = {"start_time", "end_time", "object", "results"} if openai else {"starting_at", "ending_at", "results"}
        if not isinstance(bucket, dict) or set(bucket) != expected or not isinstance(bucket["results"], list):
            raise CostError("COST_BUCKET_SCHEMA")
        if openai:
            if bucket["object"] != "bucket":
                raise CostError("COST_BUCKET_SCHEMA")
            start, end = usage.count(bucket["start_time"]), usage.count(bucket["end_time"])
        else:
            start, end = timestamp(bucket["starting_at"]), timestamp(bucket["ending_at"])
        if start % 86400 or end - start != 86400 or not scope["start_time"] <= start < end <= scope["end_time"]:
            raise CostError("COST_BUCKET_WINDOW")
        buckets.append((start, end))
        identities = set()
        for item in bucket["results"]:
            if not isinstance(item, dict):
                raise CostError("COST_ROW_SCHEMA")
            if openai:
                allowed = {"object", "amount", "line_item", "project_id", "api_key_id", "api_source", "user_id",
                           "quantity", "quantity_unit", "organization_id"}
                if set(item) - allowed or item.get("object") != "organization.costs.result":
                    raise CostError("COST_ROW_SCHEMA")
                amount = item.get("amount")
                if amount is not None and (not isinstance(amount, dict) or set(amount) - {"value", "currency"}):
                    raise CostError("COST_AMOUNT")
                amount = amount or {}
                currency, number = amount.get("currency"), amount.get("value")
                dimensions = {k: item.get(k) for k in ("project_id", "line_item", "api_key_id", "api_source", "user_id", "organization_id")}
            else:
                allowed = {"amount", "currency", "workspace_id", "description", "model", "service_tier", "cost_type",
                           "token_type", "context_window", "inference_geo"}
                if set(item) - allowed:
                    raise CostError("COST_ROW_SCHEMA")
                currency, number = item.get("currency"), item.get("amount")
                dimensions = {k: item.get(k) for k in allowed - {"amount", "currency"}}
                if currency not in (None, "USD"):
                    raise CostError("COST_CURRENCY")
            if currency is not None and (not isinstance(currency, str) or not re.fullmatch(r"[A-Za-z]{3}", currency)):
                raise CostError("COST_CURRENCY")
            if any(v is not None and (not isinstance(v, str) or len(v) > 512 or any(ord(c) < 32 for c in v)) for v in dimensions.values()):
                raise CostError("COST_DIMENSION")
            identity = json.dumps(dimensions, sort_keys=True)
            if identity in identities:
                raise CostError("COST_DUPLICATE_ROW")
            identities.add(identity)
            reported = None if number is None or currency is None else format(decimal_amount(number, cents=not openai), "f")
            rows.append({"start_time": start, "end_time": end, "dimensions": dimensions,
                         "currency": currency.upper() if currency else None, "reported_amount": reported})
            if len(rows) > MAX_ROWS:
                raise CostError("COST_ROW_LIMIT")
    return rows, buckets, cursor


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        fp.close()
        raise CostError("COST_REDIRECT_DENIED", http_status=code)


def request(scope, cursor, credential, *, timeout, deadline, observation=None):
    """Only this function may establish the authenticated HTTPS observation."""
    url = ADAPTERS[scope["provider"]][0] + "?" + urlencode(params(scope, cursor))
    headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
    if scope["provider"] == "openai.costs.v1":
        headers["Authorization"] = "Bearer " + credential
    else:
        headers.update({"x-api-key": credential, "anthropic-version": "2023-06-01"})
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    try:
        with opener.open(Request(url, headers=headers, method="GET"), timeout=timeout) as response:
            if response.status != 200 or response.geturl() != url:
                raise CostError("COST_HTTP_RESPONSE", http_status=response.status)
            if response.headers.get_content_type() != "application/json" or response.headers.get("Content-Encoding", "identity") != "identity":
                raise CostError("COST_HTTP_ENCODING")
            chunks, length = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise CostError("COST_DEADLINE")
                data = response.read1(min(65536, usage.MAX_BYTES + 1 - length))
                if not data:
                    break
                chunks.append(data); length += len(data)
                if length > usage.MAX_BYTES:
                    raise CostError("COST_PAGE_LIMIT")
            raw = b"".join(chunks)
            if credential.encode("ascii") in raw:
                raise CostError("COST_SECRET_ECHO")
            if observation is not None:
                identifier = response.headers.get("x-request-id" if scope["provider"] == "openai.costs.v1" else "request-id")
                if identifier is not None and credential in identifier:
                    raise CostError("COST_SECRET_ECHO")
                if identifier is not None and (len(identifier) > 256 or not identifier.isascii() or any(ord(c) < 33 for c in identifier)):
                    identifier = None
                observation.update(http_status=200, url=url, provider_request_id=identifier)
            return raw
    except HTTPError as error:
        status = error.code
        error.close()
        raise CostError("COST_HTTP_ERROR", http_status=status) from None
    except (URLError, OSError):
        raise CostError("COST_NETWORK_ERROR") from None


def normalize_report(scope, pages, transport):
    """Validate accounting observations, independent of human report rendering."""
    scope = query(scope)
    if transport not in ("FILE_UNAUTHENTICATED", "AUTHENTICATED_HTTPS_RESPONSE"):
        raise CostError("COST_TRANSPORT_OBSERVATION")
    rows, seen_buckets, seen_cursors = [], set(), set()
    cursor = None
    if not 1 <= len(pages) <= MAX_PAGES:
        raise CostError("COST_PAGE_LIMIT")
    for index, raw in enumerate(pages):
        incoming, buckets, cursor = parse_page(raw, scope)
        if len(set(buckets)) != len(buckets) or seen_buckets.intersection(buckets):
            raise CostError("COST_DUPLICATE_BUCKET")
        seen_buckets.update(buckets); rows.extend(incoming)
        if len(rows) > MAX_ROWS:
            raise CostError("COST_ROW_LIMIT")
        if cursor is not None:
            if cursor in seen_cursors:
                raise CostError("COST_PAGINATION_LOOP")
            seen_cursors.add(cursor)
        if (index < len(pages) - 1) != (cursor is not None):
            raise CostError("COST_INCOMPLETE_OR_EXTRA_PAGES")
    totals = {}
    with localcontext() as ctx:
        ctx.prec = 256
        for row in rows:
            if row["reported_amount"] is not None:
                currency = row["currency"]
                totals[currency] = totals.get(currency, Decimal(0)) + Decimal(row["reported_amount"])
    return {"schema": "golem.provider-cost-observation.v1", "query": scope, "rows": rows,
            "reported_totals": {k: format(v, "f") for k, v in sorted(totals.items())} or None,
            "api_amount_complete": bool(rows) and all(row["reported_amount"] is not None for row in rows),
            "api_window_complete": seen_buckets == {(day, day + 86400) for day in range(scope["start_time"], scope["end_time"], 86400)},
            "scope": "PROVIDER_API_ENDPOINT_ONLY", "attribution_basis": "CALLER_ACCOUNT_ALIAS",
            "transport_observation": transport, "independently_verified": False,
            "provider_bill_authenticated": False, "work_cost": None,
            "page_sha256": [hashlib.sha256(p).hexdigest() for p in pages]}


def collect(scope, output, *, page_files=None, credential_env=None, timeout=10, deadline_seconds=120):
    scope = query(scope)
    if type(timeout) not in (int, float) or type(deadline_seconds) not in (int, float) or not 1 <= timeout <= 60 or not 1 <= deadline_seconds <= 600:
        raise CostError("COST_TIMEOUT_OPTIONS")
    if page_files is None:
        credential_env = credential_env or ADAPTERS[scope["provider"]][1]
        if not isinstance(credential_env, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", credential_env):
            raise CostError("COST_CREDENTIAL_ENV")
        credential = os.environ.get(credential_env)
        if not isinstance(credential, str) or not 16 <= len(credential) <= 4096 or not credential.isascii() or any(ord(c) <= 32 or ord(c) >= 127 for c in credential):
            raise CostError("COST_ADMIN_CREDENTIAL_UNAVAILABLE")
    elif not 1 <= len(page_files) <= MAX_PAGES:
        raise CostError("COST_PAGE_LIMIT")
    directory = records.private_directory(output)
    records.save(directory / "query.json", records.encoded(scope))
    from agent_io import file_inventory, producer
    started = {"schema": "golem.provider-cost-capture.v1", "state": "STARTED", "endpoint": ADAPTERS[scope["provider"]][0],
               "started_at": datetime.now(timezone.utc).isoformat(),
               "producer": producer(), "credential_recorded": False, "credential_env": credential_env if page_files is None else None}
    records.save(directory / "started.json", records.encoded(started))
    pages, cursor, seen, size = [], None, set(), 0
    end = time.monotonic() + deadline_seconds
    try:
        for index in range(MAX_PAGES):
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise CostError("COST_DEADLINE")
            observation = {}
            raw = (request(scope, cursor, credential, timeout=min(timeout, remaining), deadline=end, observation=observation)
                   if page_files is None else usage.private_bytes(page_files[index]))
            size += len(raw)
            if size > MAX_CAPTURE:
                raise CostError("COST_CAPTURE_LIMIT")
            records.save(directory / ("page-%04d.json" % index), raw)
            records.save(directory / ("request-%04d.json" % index), records.encoded({
                "schema": "golem.provider-cost-request.v1", "index": index, "method": "GET" if page_files is None else "PRIVATE_FILE",
                "query_parameters": params(scope, cursor), "received_at": datetime.now(timezone.utc).isoformat(),
                "payload_sha256": hashlib.sha256(raw).hexdigest(), "credential_recorded": False, **observation}))
            pages.append(raw)
            _, _, cursor = parse_page(raw, scope)
            if cursor is None:
                if page_files is not None and index != len(page_files) - 1:
                    raise CostError("COST_INCOMPLETE_OR_EXTRA_PAGES")
                break
            if cursor in seen:
                raise CostError("COST_PAGINATION_LOOP")
            seen.add(cursor)
            if page_files is not None and index + 1 == len(page_files):
                raise CostError("COST_INCOMPLETE_OR_EXTRA_PAGES")
        else:
            raise CostError("COST_PAGE_LIMIT")
        result = normalize_report(scope, pages, "AUTHENTICATED_HTTPS_RESPONSE" if page_files is None else "FILE_UNAUTHENTICATED")
        derived = records.encoded(result)
        if len(derived) > usage.MAX_BYTES:
            raise CostError("COST_DERIVED_LIMIT")
        records.save(directory / "result.json", derived)
        records.save(directory / "manifest.json", records.encoded({"schema": "golem.provider-cost-manifest.v1",
                     "producer": producer(), "files": file_inventory(directory)}))
        return result
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        records.save(directory / "failure.json", records.encoded({"state": "INCOMPLETE",
            "code": getattr(error, "code", "COST_INVALID_OR_UNAVAILABLE"), "http_status": getattr(error, "http_status", None),
            "completed_pages": len(pages), "work_cost": None}))
        raise


def load(directory, *, snapshot=None):
    """Reconstruct from bounded raw pages; optionally copy this verified snapshot."""
    manifest_raw = usage.private_bytes(directory / "manifest.json")
    manifest = strict_json(manifest_raw)
    files = manifest.get("files")
    if manifest.get("schema") != "golem.provider-cost-manifest.v1" or not isinstance(files, dict) or len(files) > MAX_PAGES * 2 + 3:
        raise CostError("COST_CAPTURE_INTEGRITY")
    names = sorted(n for n in files if re.fullmatch(r"page-\d{4}\.json", n))
    if names != ["page-%04d.json" % i for i in range(len(names))]:
        raise CostError("COST_CAPTURE_PAGES")
    expected = {"query.json", "started.json", "result.json", *names,
                *("request-%04d.json" % i for i in range(len(names)))}
    if set(files) != expected or any(p.name not in expected | {"manifest.json"} or p.is_symlink() or not p.is_file() for p in directory.iterdir()):
        raise CostError("COST_CAPTURE_INTEGRITY")
    contents = {name: usage.private_bytes(directory / name) for name in sorted(files)}
    if any(hashlib.sha256(data).hexdigest() != files[name] for name, data in contents.items()):
        raise CostError("COST_CAPTURE_INTEGRITY")
    stored = strict_json(contents["result.json"])
    scope = query(strict_json(contents["query.json"]))
    cursor = None
    for index, name in enumerate(names):
        observation = strict_json(contents["request-%04d.json" % index])
        method = "GET" if stored["transport_observation"] == "AUTHENTICATED_HTTPS_RESPONSE" else "PRIVATE_FILE"
        fields = {"schema", "index", "method", "query_parameters", "received_at", "payload_sha256", "credential_recorded"}
        if method == "GET":
            fields |= {"http_status", "url", "provider_request_id"}
        if (set(observation) != fields or observation.get("schema") != "golem.provider-cost-request.v1" or type(observation.get("index")) is not int
                or observation["index"] != index or observation.get("method") != method
                or observation.get("credential_recorded") is not False
                or observation.get("payload_sha256") != files[name]
                or observation.get("query_parameters") != [[k, v] for k, v in params(scope, cursor)]):
            raise CostError("COST_REQUEST_BINDING")
        if method == "GET" and (observation.get("http_status") != 200 or observation.get("url") != ADAPTERS[scope["provider"]][0] + "?" + urlencode(params(scope, cursor))):
            raise CostError("COST_REQUEST_BINDING")
        _, _, cursor = parse_page(contents[name], scope)
    result = normalize_report(scope, [contents[name] for name in names], stored["transport_observation"])
    if result != stored:
        raise CostError("COST_DERIVATION_CONFLICT")
    if snapshot is not None:
        target = records.private_directory(snapshot)
        for name, data in contents.items():
            records.save(target / name, data)
        records.save(target / "manifest.json", manifest_raw)
    return result


def compare(result, payload, *, same_api_scope=False):
    """Comparison is not authentication, allocation, invoice finality or payment."""
    if type(same_api_scope) is not bool:
        raise CostError("COST_COMPARISON_SCOPE")
    expected = "openai.responses.v1" if result["query"]["provider"] == "openai.costs.v1" else "anthropic.messages.v1"
    if payload["provider"] != expected or payload["account_id"] != result["query"]["account_id"]:
        raise CostError("COST_COMPARISON_SCOPE")
    if (payload["period_start"], payload["period_end"]) != (result["query"]["start_time"], result["query"]["end_time"]):
        raise CostError("COST_COMPARISON_PERIOD")
    state, delta = "UNKNOWN_COVERAGE", None
    amounts = result["reported_totals"] or {}
    if same_api_scope and result["api_amount_complete"] and result["api_window_complete"] and set(amounts) == {payload["currency"]}:
        with localcontext() as ctx:
            ctx.prec = 256
            difference = Decimal(amounts[payload["currency"]]) - Decimal(payload["total_nano"]) / 1000000000
        state, delta = ("MATCH" if difference == 0 else "DIFFERENCE"), format(difference, "f")
    return {"schema": "golem.provider-cost-comparison.v1", "status": state, "difference_amount": delta,
            "basis": "CALLER_ASSERTED_SAME_API_SCOPE" if same_api_scope else "SCOPE_NOT_CONFIRMED",
            "provider_bill_authenticated": False, "work_cost_assigned": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("fetch", "ingest", "view"))
    parser.add_argument("--query", type=Path)
    parser.add_argument("--page", type=Path, action="append")
    parser.add_argument("--credential-env")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    try:
        if args.mode == "view":
            if args.bundle is None or any((args.query, args.page, args.output, args.credential_env)):
                raise CostError("COST_VIEW_ARGUMENTS")
            result = load(args.bundle)
        else:
            if args.query is None or args.output is None or args.bundle is not None or (args.mode == "fetch" and args.page) or (args.mode == "ingest" and (not args.page or args.credential_env)):
                raise CostError("COST_CAPTURE_ARGUMENTS")
            result = collect(strict_json(usage.private_bytes(args.query)), args.output,
                             page_files=args.page if args.mode == "ingest" else None, credential_env=args.credential_env)
        print(json.dumps({"status": "RECORDED", "reported_totals": result["reported_totals"],
            "api_amount_complete": result["api_amount_complete"], "provider_bill_authenticated": False,
            "work_cost": None}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({"schema": "golem.provider-cost-error.v1", "code": getattr(error, "code", "COST_INVALID_OR_UNAVAILABLE"),
            "http_status": getattr(error, "http_status", None),
            "next_action": "Check explicit admin access, UTC day window and private evidence; no automatic retry or cost allocation."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
