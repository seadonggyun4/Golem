"""Durable, explicitly routed hosted usage delivery to a native WorkRun inbox.

The owning Codex client forwards notifications; Claude exports authenticated OTLP.
No account discovery, conversation scraping, pricing inference or global settings.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import threading
import tempfile
import time

import billing_evidence as billing
import hosted_usage as hosted
import provider_usage as usage
from execution_record import encoded, private_directory, save, run_private
from verify_agent import strict_json


def private_dir(path):
    path = Path(path).absolute()
    if ".." in path.parts:
        raise ValueError("PIPELINE_DIRECTORY")
    for part in (path, *path.parents):
        s = part.lstat()
        if not stat.S_ISDIR(s.st_mode):
            raise ValueError("PIPELINE_DIRECTORY")
    s = path.stat()
    if s.st_uid != os.geteuid() or s.st_mode & 0o077:
        raise ValueError("PIPELINE_PRIVATE_DIRECTORY")
    return path


def atomic(path, data):
    if len(data) > usage.MAX_BYTES:
        raise ValueError("PIPELINE_CAPACITY")
    parent = private_dir(path.parent)
    fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    name = ".pending-" + secrets.token_hex(16)
    try:
        out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(out, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try:
            os.unlink(name, dir_fd=fd)
        except FileNotFoundError:
            pass
        os.close(fd)


def route(value):
    if (not isinstance(value, dict) or set(value) != {"schema", "run_id", "sequence",
            "currency", "tool_calls", "inbox", "require_billed"}
            or value["schema"] != "golem.usage-route.v1"):
        raise ValueError("PIPELINE_ROUTE")
    usage.text(value["run_id"])
    if len(value["run_id"]) >= 96 or not usage.count(value["sequence"]):
        raise ValueError("PIPELINE_SEQUENCE")
    if not isinstance(value["currency"], str) or not re.fullmatch(r"[A-Z]{3}", value["currency"]):
        raise ValueError("PIPELINE_CURRENCY")
    if type(value["require_billed"]) is not bool or not isinstance(value["tool_calls"], dict):
        raise ValueError("PIPELINE_ROUTE")
    if len(value["tool_calls"]) > 256:
        raise ValueError("PIPELINE_CAPACITY")
    for key, count in value["tool_calls"].items():
        usage.text(key)
        usage.count(count)
    if not isinstance(value["inbox"], str) or not Path(value["inbox"]).is_absolute():
        raise ValueError("PIPELINE_INBOX")
    private_dir(value["inbox"])
    return value


def sanitized(collector, message):
    """Retain only parser-consumed usage metadata, never bodies or arbitrary attrs."""
    if collector.scope["provider"] == "codex.app-server.v1":
        method = message.get("method")
        p = message.get("params", {})
        if method not in ("turn/started", "turn/completed", "thread/tokenUsage/updated") or p.get("threadId") != collector.scope["session_id"]:
            return None
        if method == "thread/tokenUsage/updated":
            return {"method": method, "params": {"threadId": p["threadId"], "turnId": p["turnId"],
                    "tokenUsage": {"total": hosted.breakdown(p["tokenUsage"]["total"])}}}
        return {"method": method, "params": {"threadId": p["threadId"],
                "turn": {"id": p["turn"]["id"], "status": p["turn"].get("status")}}}
    logs = []
    # Rebuild OTLP from normalized observations; ignore all non-usage events.
    for resource in message["resourceLogs"]:
        common = hosted.otlp_attributes(resource.get("resource", {}).get("attributes", []))
        for scope in resource.get("scopeLogs", []):
            for log in scope.get("logRecords", []):
                attrs = dict(common)
                attrs.update(hosted.otlp_attributes(log.get("attributes", [])))
                if (attrs.get("event.name") not in ("api_request", "claude_code.api_request")
                        or attrs.get("session.id") != collector.scope["session_id"]
                        or (not collector.scope["session_owned"] and attrs.get("prompt.id") not in collector.scope["prompt_ids"])):
                    continue
                keys = {"event.name", "session.id", "prompt.id", "request_id", "model", "input_tokens",
                        "output_tokens", "cache_read_tokens", "cache_creation_tokens"}
                values = [{"key": k, "value": {"intValue": str(v)} if type(v) is int else {"stringValue": v}}
                          for k, v in sorted(attrs.items()) if k in keys]
                logs.append({"attributes": values})
    return {"resourceLogs": [{"scopeLogs": [{"logRecords": logs}]}]} if logs else None


class Pipeline:
    def __init__(self, directory):
        self.directory = private_dir(directory)

    @classmethod
    def create(cls, directory, scope, mapping):
        hosted.binding(scope)
        route(mapping)
        directory = private_directory(directory)
        save(directory / "config.json", encoded({"binding": scope, "route": mapping}))
        save(directory / "lock", b"")
        atomic(directory / "state.json", encoded({"schema": "golem.usage-pipeline.v1",
            "config_sha256": hashlib.sha256(encoded({"binding": scope, "route": mapping})).hexdigest(),
            "events": [], "closed": False}))
        return cls(directory)

    @contextmanager
    def locked(self):
        fd = os.open(self.directory / "lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            s = os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or s.st_mode & 0o077 or s.st_nlink != 1:
                raise ValueError("PIPELINE_LOCK")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def load(self):
        config_raw = usage.private_bytes(self.directory / "config.json")
        config = strict_json(config_raw)
        if set(config) != {"binding", "route"}:
            raise ValueError("PIPELINE_CONFIG")
        hosted.binding(config["binding"])
        route(config["route"])
        state = strict_json(usage.private_bytes(self.directory / "state.json"))
        if (set(state) - {"schema", "config_sha256", "events", "closed", "billing"}
                or not {"schema", "config_sha256", "events", "closed"} <= set(state)
                or state["schema"] != "golem.usage-pipeline.v1"
                or state["config_sha256"] != hashlib.sha256(config_raw).hexdigest()
                or type(state["closed"]) is not bool or not isinstance(state["events"], list)
                or len(state["events"]) > usage.MAX_EVENTS):
            raise ValueError("PIPELINE_STATE")
        if "billing" in state and (not isinstance(state["billing"], str) or
                not re.fullmatch(r"billing-[a-f0-9]{32}", state["billing"])):
            raise ValueError("PIPELINE_BILLING_STATE")
        collector = hosted.Collector(config["binding"])
        for event in state["events"]:
            if sanitized(collector, event) != event:
                raise ValueError("PIPELINE_EVENT")
            collector.accept(event)
        return config, state, collector

    def accept(self, message, publish=None):
        if publish is not None:
            raise ValueError("PIPELINE_EXTERNAL_PUBLICATION")
        with self.locked():
            config, state, collector = self.load()
            event = sanitized(collector, message)
            # Provider retries of a previously accepted exact event are harmless.
            if event is None or event in state["events"]:
                return
            if state["closed"]:
                raise ValueError("PIPELINE_CLOSED")
            collector.accept(event)
            if len(state["events"]) >= usage.MAX_EVENTS:
                raise ValueError("PIPELINE_CAPACITY")
            state["events"].append(event)
            atomic(self.directory / "state.json", encoded(state))

    def close(self):
        with self.locked():
            _, state, _ = self.load()
            state["closed"] = True
            atomic(self.directory / "state.json", encoded(state))
        return self.sync()

    def sync(self, billing_inputs=None):
        """Re-verify supplied billing artifacts on every attempt, never trust a receipt alone."""
        with self.locked():
            config, state, collector = self.load()
            record, mapping = collector.record(), config["route"]
            if billing_inputs is not None:
                if len(list(self.directory.glob("billing-*"))) >= 32:
                    raise ValueError("PIPELINE_BILLING_CAPACITY")
                destination = self.directory / ("billing-" + secrets.token_hex(16))
                payload, receipt = billing.verify(*billing_inputs, destination)
                save(destination / "trust.json", usage.private_bytes(billing_inputs[4]))
                state["billing"] = destination.name
                atomic(self.directory / "state.json", encoded(state))
                record = billing.reconcile([record], payload, receipt)["usage_records"][0]
            elif "billing" in state:
                evidence = private_dir(self.directory / state["billing"])
                inputs = [evidence / name for name in ("export.json", "signature.bin", "key.pem", "artifact.bin", "trust.json")]
                with tempfile.TemporaryDirectory(prefix=".verify-", dir=self.directory) as temporary:
                    payload, receipt = billing.verify(*inputs, Path(temporary) / "verified")
                record = billing.reconcile([record], payload, receipt)["usage_records"][0]
            totals = usage.totals([record])
            result = {"schema": "golem.usage-delivery.v1", "work_id": config["binding"]["work_id"],
                "run_id": mapping["run_id"], "sequence": mapping["sequence"],
                "collection": "CLOSED" if state["closed"] else "OPEN", "totals": totals,
                "tool_usage_complete": all(c["request_id"] in mapping["tool_calls"] for c in record["calls"]),
                "native_delivery": "PENDING", "native_application": "OWNER_NOT_OBSERVED"}
            if not state["closed"] or not totals["usage_complete"]:
                result["reason"] = "COLLECTION_OPEN_OR_USAGE_INCOMPLETE"
                return result
            reports = []
            if len(record["calls"]) > 256:
                raise ValueError("PIPELINE_CAPACITY")
            for call in record["calls"]:
                request = call["request_id"]
                report = billing.native_report(call, mapping["run_id"], mapping["sequence"],
                    mapping["currency"], tool_calls=mapping["tool_calls"].get(request, 0))
                # The native v1 aggregate has one completeness bit for tokens AND tools.
                # Preserve token partial sums but never assert an unknown tool count is zero.
                report["usage_known"] = request in mapping["tool_calls"]
                if not report["usage_known"]:
                    # v1 forbids nonzero fields when usage is incomplete. Only
                    # the explicit v2 import path can retain observed partials.
                    report["schema"] = "golem.native-cost-report.v2"
                # Native IDs include account + Work + attempt + session, not just provider IDs.
                report["request_id"] = hashlib.sha256(encoded([call["attribution"], request])).hexdigest()
                if mapping["require_billed"] and not report["cost_known"]:
                    result["reason"] = "VERIFIED_BILLING_REQUIRED"
                    return result
                reports.append(report)
            batch = encoded({"schema": "golem.native-cost-inbox.v1", "run_id": mapping["run_id"],
                             "sequence": str(mapping["sequence"]), "sealed": True, "reports": reports})
            target = Path(mapping["inbox"]) / ("%020d.json" % mapping["sequence"])
            if target.exists() or target.is_symlink():
                if usage.private_bytes(target) != batch:
                    raise ValueError("PIPELINE_NATIVE_CONFLICT")
            else:
                # Serialize independent producers using the inbox itself; no silent overwrite.
                fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    if target.exists() or target.is_symlink():
                        if usage.private_bytes(target) != batch:
                            raise ValueError("PIPELINE_NATIVE_CONFLICT")
                    else:
                        atomic(target, batch)
                finally:
                    os.close(fd)
            result["native_delivery"] = "PUBLISHED"
            result["snapshot_sha256"] = hashlib.sha256(batch).hexdigest()
            return result


def claude_environment(endpoint, token, inherited=None):
    env = dict(os.environ if inherited is None else inherited)
    for key in list(env):
        if key.startswith("OTEL_") or key == "BETA_TRACING_ENDPOINT":
            del env[key]
    env.update(CLAUDE_CODE_ENABLE_TELEMETRY="1", OTEL_LOGS_EXPORTER="otlp",
        OTEL_METRICS_EXPORTER="none", OTEL_TRACES_EXPORTER="none",
        OTEL_EXPORTER_OTLP_PROTOCOL="http/json", OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=endpoint,
        OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer " + token,
        OTEL_LOGS_EXPORT_INTERVAL="1000", OTEL_LOG_USER_PROMPTS="0",
        OTEL_LOG_ASSISTANT_RESPONSES="0", OTEL_LOG_TOOL_DETAILS="0",
        OTEL_LOG_TOOL_CONTENT="0", OTEL_LOG_RAW_API_BODIES="0")
    return env


def deliver(pipeline, duration, billing_inputs=None, interval=2):
    """Bounded local outbox drain; authentication/schema errors are never retried."""
    if not 1 <= duration <= 3600 or not 0 < interval <= 60:
        raise ValueError("PIPELINE_DELIVERY_ARGUMENTS")
    deadline = time.monotonic() + duration
    for _ in range(64):
        _, state, collector = pipeline.load()
        ready = state["closed"] and usage.totals([collector.record()])["usage_complete"]
        evidence = billing_inputs if ready and billing_inputs and all(p.exists() for p in billing_inputs) else None
        result = pipeline.sync(evidence)
        if result["native_delivery"] == "PUBLISHED" or time.monotonic() >= deadline:
            return result
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
    return result


def run_claude(pipeline, command, timeout, flush=2):
    """Own one explicitly bound child; managed provider policy still takes precedence."""
    config, state, _ = pipeline.load()
    scope = config["binding"]
    if (scope["provider"] != "claude.otel.v1" or not scope["session_owned"] or state["closed"]
            or not command or not 1 <= timeout <= 3600 or not 0 <= flush <= 10):
        raise ValueError("PIPELINE_CHILD_SCOPE")
    session_args = [command[i + 1] for i, item in enumerate(command[:-1]) if item == "--session-id"]
    if session_args != [scope["session_id"]] or any(x.startswith("--session-id=") for x in command):
        raise ValueError("PIPELINE_CHILD_SESSION_REQUIRED")
    token = secrets.token_hex(32)
    with hosted.server(pipeline, token) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1})
        thread.start()
        try:
            endpoint = "http://127.0.0.1:%d/v1/logs" % server.server_port
            try:
                process = run_private(command, env=claude_environment(endpoint, token), timeout=timeout,
                    destination=pipeline.directory / ("child-" + secrets.token_hex(16)),
                    source=Path(__file__).resolve().parents[1])
                code = process.returncode
            except subprocess.TimeoutExpired:
                raise ValueError("PIPELINE_CHILD_TIMEOUT")
            time.sleep(flush)
            if server.errors:
                raise ValueError("PIPELINE_EXPORT_ERRORS")
            result = pipeline.close()
            result["child_exit_code"] = code
            return result
        finally:
            server.shutdown()
            thread.join()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("init", "pump", "listen", "run-claude", "deliver", "close", "sync"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--binding", type=Path)
    parser.add_argument("--route", type=Path)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--flush", type=int, default=2)
    for key in ("export", "signature", "public-key", "artifact", "trust"):
        parser.add_argument("--billing-" + key, type=Path)
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:
        split = argv.index("--")
        command, argv = argv[split + 1:], argv[:split]
    args = parser.parse_args(argv)
    try:
        evidence = [args.billing_export, args.billing_signature, args.billing_public_key, args.billing_artifact, args.billing_trust]
        if any(evidence) and (not all(evidence) or args.mode not in ("sync", "deliver")):
            raise ValueError("PIPELINE_BILLING_ARGUMENTS")
        if args.mode == "init":
            if not args.binding or not args.route:
                raise ValueError("PIPELINE_BINDING_AND_ROUTE_REQUIRED")
            pipeline = Pipeline.create(args.directory, strict_json(usage.private_bytes(args.binding)),
                                       strict_json(usage.private_bytes(args.route)))
        else:
            pipeline = Pipeline(args.directory)
        if args.mode == "run-claude":
            result = run_claude(pipeline, command, args.timeout, args.flush)
        elif args.mode == "pump":
            while True:
                line = sys.stdin.buffer.readline(usage.MAX_BYTES + 1)
                if not line:
                    break
                if len(line) > usage.MAX_BYTES:
                    raise ValueError("PIPELINE_CAPACITY")
                pipeline.accept(strict_json(line))
            result = pipeline.close()
        elif args.mode == "listen":
            if not args.token_file or not 1 <= args.duration <= 3600:
                raise ValueError("PIPELINE_LISTEN_ARGUMENTS")
            token = usage.private_bytes(args.token_file).decode("ascii").strip()
            with hosted.server(pipeline, token) as server:
                server.timeout = 0.5
                print(json.dumps({"endpoint": "http://127.0.0.1:%d/v1/logs" % server.server_port}), flush=True)
                deadline = time.monotonic() + args.duration
                while time.monotonic() < deadline:
                    server.handle_request()
                if server.errors:
                    raise ValueError("PIPELINE_EXPORT_ERRORS")
            # Duration expiry is not proof that the owning session has ended.
            result = pipeline.sync()
        elif args.mode == "close":
            result = pipeline.close()
        elif args.mode == "deliver":
            result = deliver(pipeline, args.duration, evidence if all(evidence) else None)
        else:
            result = pipeline.sync(evidence if all(evidence) else None)
        print(json.dumps(result, sort_keys=True))
        return 0 if args.mode == "init" or (result["native_delivery"] == "PUBLISHED" and result.get("child_exit_code", 0) == 0) else 2
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({"schema": "golem.usage-pipeline-error.v1", "code": type(error).__name__,
            "diagnostic": str(error) if str(error).startswith("PIPELINE_") else "COLLECTION_OR_DELIVERY_FAILED",
            "recovery": "Preserve directory; check binding, permissions and provider export; retry sync."
        }), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
