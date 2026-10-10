"""Pinned Ed25519 billing-export verification and exact request reconciliation.

Trust is a caller-managed billing authority, NOT a claim that providers sign
invoices. Raw invoice, detached signature and scope are verified before deriving
new usage. Originals and CLI price estimates are never rewritten.
"""
import copy
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

import execution_record
import provider_usage as usage
from verify_agent import strict_json


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate(payload, policy, artifact):
    required = {"schema", "issuer", "provider", "account_id", "currency", "period_start",
                "period_end", "artifact_sha256", "invoice_id", "total_nano", "unallocated_nano", "entries"}
    if set(payload) != required or payload["schema"] != "golem.billing-export.v1":
        raise ValueError("BILLING_SCHEMA")
    if set(policy) != {"schema", "issuer", "provider", "account_id", "public_key_sha256"} or policy["schema"] != "golem.billing-trust.v1":
        raise ValueError("BILLING_TRUST_POLICY")
    for key in ("issuer", "provider", "account_id"):
        usage.text(payload[key])
        if policy[key] != payload[key]:
            raise ValueError("BILLING_SCOPE")
    usage.text(payload["invoice_id"])
    if not re.fullmatch(r"[A-Z]{3}", payload["currency"]) or payload["artifact_sha256"] != digest(artifact):
        raise ValueError("BILLING_ARTIFACT")
    start, end = usage.count(payload["period_start"]), usage.count(payload["period_end"])
    if start >= end:
        raise ValueError("BILLING_PERIOD")
    rows = payload["entries"]
    if not isinstance(rows, list) or len(rows) > usage.MAX_EVENTS:
        raise ValueError("BILLING_ENTRIES")
    total, ids = usage.count(payload["unallocated_nano"]), set()
    for row in rows:
        if set(row) != {"request_id", "nano_cost", "timestamp"}:
            raise ValueError("BILLING_ENTRY")
        request = usage.text(row["request_id"])
        if request in ids or not start <= usage.count(row["timestamp"]) < end:
            raise ValueError("BILLING_DUPLICATE_OR_PERIOD")
        ids.add(request)
        total = usage.add(total, usage.count(row["nano_cost"]))
    if total != usage.count(payload["total_nano"]):
        raise ValueError("BILLING_TOTAL_MISMATCH")
    return payload


def verify(export, signature, public_key, artifact, policy, output, openssl=None):
    """Verify exact bytes, not reserialized JSON. A failed check never grants trust."""
    raw, key, source = (usage.private_bytes(Path(p)) for p in (export, public_key, artifact))
    sig = usage.private_bytes(Path(signature))
    trust = strict_json(usage.private_bytes(Path(policy)))
    payload = validate(strict_json(raw), trust, source)
    if digest(key) != trust["public_key_sha256"] or len(sig) != 64:
        raise ValueError("BILLING_KEY_OR_SIGNATURE")
    directory = execution_record.private_directory(output)
    for name, data in (("export.json", raw), ("key.pem", key), ("signature.bin", sig), ("artifact.bin", source)):
        execution_record.save(directory / name, data)
    executable = Path(openssl or shutil.which("openssl") or "").resolve()
    if not executable.is_file():
        raise ValueError("BILLING_VERIFIER_UNAVAILABLE")
    key_check = execution_record.run([str(executable), "pkey", "-pubin", "-in",
        str(directory / "key.pem"), "-outform", "DER"], destination=directory / "key-check",
        cwd=directory, check=False)
    # RFC 8410 SubjectPublicKeyInfo: Ed25519 OID, absent parameters, 32-byte key.
    der = (directory / "key-check" / "stdout.log").read_bytes()
    if key_check.returncode != 0 or len(der) != 44 or not der.startswith(bytes.fromhex("302a300506032b6570032100")):
        raise ValueError("BILLING_KEY_ALGORITHM")
    result = execution_record.run([str(executable), "pkeyutl", "-verify", "-rawin", "-pubin",
        "-inkey", str(directory / "key.pem"), "-sigfile", str(directory / "signature.bin"),
        "-in", str(directory / "export.json")], destination=directory / "signature-check", cwd=directory, check=False)
    if result.returncode != 0:
        raise ValueError("BILLING_SIGNATURE_INVALID")
    receipt = {"schema": "golem.billing-verification.v1", "payload_sha256": digest(raw),
               "parsed_payload_sha256": digest(execution_record.encoded(payload)),
               "artifact_sha256": digest(source), "public_key_sha256": digest(key),
               "trust_level": "PINNED_DELEGATED_BILLING_AUTHORITY", "provider_attestation": False,
               "issuer": payload["issuer"], "provider": payload["provider"], "account_id": payload["account_id"]}
    execution_record.save(directory / "verification.json", execution_record.encoded(receipt))
    return payload, receipt


def reconcile(records, payload, receipt):
    """Exact join only. Aggregated invoice remainder is NOT allocated to Works."""
    if (receipt.get("trust_level") != "PINNED_DELEGATED_BILLING_AUTHORITY"
            or receipt.get("parsed_payload_sha256") != digest(execution_record.encoded(payload))
            or any(receipt.get(k) != payload[k] for k in ("issuer", "provider", "account_id"))):
        raise ValueError("BILLING_UNVERIFIED_SCOPE")
    usage.totals(records)  # reject conflicting original observations first
    rows = {row["request_id"]: row for row in payload["entries"]}
    output, matched = copy.deepcopy(records), set()
    for record in output:
        for call in record["calls"]:
            a, observation = call["attribution"], call["observation"]
            if (a["provider"], a["account_id"]) != (payload["provider"], payload["account_id"]):
                continue
            request = call["request_id"]
            if request not in rows or observation is None:
                continue
            bill = {"currency": payload["currency"], "nano_cost": rows[request]["nano_cost"],
                    "evidence_sha256": receipt["payload_sha256"]}
            if observation["billing"] is not None and observation["billing"] != bill:
                raise ValueError("BILLING_EXISTING_CONFLICT")
            observation["billing"] = bill
            call["billing_verification"] = receipt
            matched.add(request)
    total = usage.totals(output)
    return {"schema": "golem.billing-reconciliation.v1", "usage_records": output, "totals": total,
            "matched_requests": sorted(matched), "unmatched_invoice_requests": sorted(set(rows) - matched),
            "unallocated_nano": payload["unallocated_nano"], "verification": receipt,
            "provider_bill_authenticated": False}


def native_report(call, run_id, sequence, currency, *, tool_calls):
    """Bound native interchange. Only FINAL usage and verified billed amounts."""
    usage.text(run_id); usage.count(sequence)
    if sequence == 0 or not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("NATIVE_BINDING")
    observation = call["observation"]
    if not observation or not observation["final"] or call["status"] != "COMPLETE":
        raise ValueError("NATIVE_USAGE_INCOMPLETE")
    bill = observation["billing"]
    verification = call.get("billing_verification", {})
    known = bool(bill and verification.get("trust_level") == "PINNED_DELEGATED_BILLING_AUTHORITY"
                 and verification.get("payload_sha256") == bill["evidence_sha256"]
                 and all(verification.get(k) == call["attribution"][k] for k in ("provider", "account_id")))
    if bill and bill["currency"] != currency:
        raise ValueError("NATIVE_CURRENCY")
    report = {"schema": "golem.native-cost-report.v1", "run_id": run_id,
              "sequence": str(sequence), "request_id": call["request_id"],
              "provider": call["attribution"]["provider"], "model": observation["model"],
              "price_revision": "verified-export-v1" if known else "provider-unpriced-v1",
              "currency": currency, "usage_known": True, "cost_known": known,
              "nano_cost": str(bill["nano_cost"] if known else 0),
              "usage": {k: str(usage.count(v)) for k, v in observation["tokens"].items()}}
    report["usage"]["tool_calls"] = str(usage.count(tool_calls))
    if any(len(report[k]) >= 96 for k in ("request_id", "provider", "model", "price_revision")):
        raise ValueError("NATIVE_TEXT_CAPACITY")
    return report


def load_records(paths):
    from agent_io import load_bundle, file_inventory
    records, sources = [], []
    for path in paths:
        if (path / "usage.json").is_file():
            manifest = strict_json(usage.private_bytes(path / "manifest.json"))
            if manifest.get("schema") != "golem.hosted-usage-manifest.v1" or manifest.get("files") != file_inventory(path):
                raise ValueError("HOSTED_INTEGRITY")
            data = usage.private_bytes(path / "usage.json")
            record = strict_json(data)
            if record.get("schema") != "golem.work-usage.v1":
                raise ValueError("HOSTED_SCHEMA")
            records.append(record); sources.append(digest(data))
        else:
            record, sha = load_bundle(path)
            if record["status"] == "INCOMPLETE" or any(s.get("usage_error") for s in record["steps"]):
                raise ValueError("USAGE_INVALID_EVIDENCE")
            records.extend(s["usage"] for s in record["steps"] if "usage" in s)
            sources.append(sha)
    usage.totals(records)
    return records, sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("reconcile", "native-export"))
    parser.add_argument("--bundle", type=Path, action="append", required=True)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--signature", type=Path)
    parser.add_argument("--public-key", type=Path)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--trust", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--work-id")
    parser.add_argument("--request-id")
    parser.add_argument("--sequence", type=int)
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--tool-calls", type=int)
    parser.add_argument("--cost-api-bundle", type=Path)
    parser.add_argument("--confirm-same-api-scope", action="store_true")
    args = parser.parse_args()
    try:
        records, sources = load_records(args.bundle)
        evidence = [args.export, args.signature, args.public_key, args.artifact, args.trust]
        if (any(evidence) and not all(evidence)) or (args.mode == "reconcile" and not all(evidence)):
            raise ValueError("BILLING_ALL_EVIDENCE_REQUIRED")
        if (args.cost_api_bundle and (args.mode != "reconcile" or not all(evidence))) or (args.confirm_same_api_scope and not args.cost_api_bundle):
            raise ValueError("BILLING_COST_COMPARISON_ARGUMENTS")
        directory = execution_record.private_directory(args.output)
        if all(evidence):
            payload, receipt = verify(*evidence, directory / "billing")
            result = reconcile(records, payload, receipt)
            if args.cost_api_bundle:
                import provider_costs
                api = provider_costs.load(args.cost_api_bundle, snapshot=directory / "provider-cost-api")
                result["aggregate_api_comparison"] = provider_costs.compare(api, payload,
                    same_api_scope=args.confirm_same_api_scope)
                sources.extend(api["page_sha256"])
            records = result["usage_records"]
        if args.mode == "native-export":
            usage.text(args.work_id)
            usage.text(args.request_id)
            candidates = [call for record in records for call in record["calls"]
                          if call["request_id"] == args.request_id and call["attribution"]["work_id"] == args.work_id]
            if not candidates or any(call != candidates[0] for call in candidates):
                raise ValueError("NATIVE_AMBIGUOUS_BINDING")
            result = native_report(candidates[0], args.run_id, args.sequence, args.currency, tool_calls=args.tool_calls)
        execution_record.save(directory / "result.json", execution_record.encoded(result))
        execution_record.save(directory / "sources.json", execution_record.encoded({"record_sha256": sources}))
        from agent_io import file_inventory, producer
        execution_record.save(directory / "manifest.json", execution_record.encoded({
            "schema": "golem.usage-integration-manifest.v1", "producer": producer(), "files": file_inventory(directory)}))
        print(json.dumps({"status": "RECORDED", "result": str(directory / "result.json"),
                          "provider_bill_authenticated": False}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
        print(json.dumps({"schema": "golem.usage-integration-error.v1", "code": str(error)[:96],
                          "next_action": "Inspect scoped evidence and pinned trust; never replace estimates with invented billing."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
