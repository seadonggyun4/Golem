"""Opt-in D6 TLS MCP resource server; no AS, proxy, native repair or auto resume."""
import argparse
from collections import deque
from contextlib import asynccontextmanager, ExitStack
from importlib.metadata import version
from pathlib import Path
import sys
import time
import uuid

import execution_record as records
import integration_backend as backend
import integration_contract as c
import integration_registry as r
import integration_transfer as transfers
import integration_service as reads
from integration_mcp import server_icons
import integration_mutation_contract as mutations
import integration_mutations as writes
import integration_lifecycle as lifecycle
import integration_gateway_contract as contract
from integration_gateway_auth import Verifier

BODY_LIMIT = c.LIMIT
RESPONSE_LIMIT = 8388608


class Gateway:
    def __init__(self, policy, *, approve_remote_mutations=False):
        self.policy, self.verifier = policy, Verifier(policy)
        self.services, self.bindings = {}, {}
        identities = set()
        for delegate in policy.value["delegates"]:
            pin = delegate["transfer_policy"]
            disclosure = transfers.Transfer(Path(pin["path"]), pin["sha256"], approve_data_transfer=True)
            c.require(disclosure.value["destination"] == "MODEL_SERVICE" and
                      disclosure.value["destination_id"] == delegate["destination_id"], "REMOTE_DISCLOSURE_REQUIRED")
            self.bindings[delegate["delegate_id"]] = [s["binding"] for s in disclosure.value["scopes"]]
            binding = self.bindings[delegate["delegate_id"]][0]
            identities.add((binding["principal_id"], binding["client_id"]))
            for scope in disclosure.value["scopes"]:
                for work_id in scope["work_ids"]:
                    with disclosure.registry.locked():
                        project = disclosure.registry.authorize(scope["binding"], work_id, "record")
                    for path in (policy.path, Path(policy.value["revocation_file"]), Path(policy.value["jwks"]["path"]),
                                 Path(policy.value["tls_key"]["path"]), Path(pin["path"])):
                        c.require(not path.is_relative_to(Path(project["root"])), "REMOTE_POLICY_SCOPE")
            mutation = delegate["mutation_policy"]
            if mutation is not None:
                c.require(approve_remote_mutations is True, "OWNER_REMOTE_MUTATION_APPROVAL_REQUIRED")
                local = mutations.Policy(Path(mutation["path"]), mutation["sha256"], approve_mutations=True)
                c.require(local.value["transfer_policy"] == pin, "REMOTE_MUTATION_DISCLOSURE_MISMATCH")
                self.services[delegate["delegate_id"]] = writes.Service(local)
            else:
                self.services[delegate["delegate_id"]] = reads.Service(disclosure)
        c.require(len(identities) == len(policy.value["delegates"]), "SHARED_LOCAL_IDENTITY_FORBIDDEN")

    def authorize(self, token, tool=None):
        delegate, claims = self.verifier.authenticate(token)
        service = self.services[delegate["delegate_id"]]
        disclosure = service.policy.transfer if isinstance(service, writes.Service) else service.transfer
        if isinstance(service, writes.Service):
            service.policy.current()
        with disclosure.registry.locked():
            for scope in disclosure.current()["scopes"]:
                for work_id in scope["work_ids"]:
                    disclosure.registry.authorize(scope["binding"], work_id, "record")
        if tool is not None:
            c.require(tool in delegate["tools"], "REMOTE_TOOL_SCOPE")
            c.require(tool not in mutations.NAMES or "golem.write" in claims["scope"].split(), "INSUFFICIENT_SCOPE")
        return delegate, claims

    def tools(self, token):
        delegate, claims = self.authorize(token)
        service = self.services[delegate["delegate_id"]]
        names = sorted(set(service.tools()) & set(delegate["tools"]))
        return [n for n in names if n not in mutations.NAMES or "golem.write" in claims["scope"].split()]

    def call(self, token, name, args):
        delegate, claims = self.authorize(token, name)
        service = self.services[delegate["delegate_id"]]
        registry = service.registry
        with registry.locked(exclusive=True):
            backend._quota(registry.root)
            audit = registry.root / ("remote-" + uuid.uuid4().hex)
            audit.mkdir(mode=0o700)
            records.save(audit / "intent.json", c.encoded({"schema": "golem.integration-remote-call.v1",
                "delegate_id": delegate["delegate_id"], "token_id_sha256": c.sha(claims["jti"].encode()),
                "tool": name, "arguments_sha256": c.sha(c.encoded(args)), "policy_sha256": self.policy.digest}))
        # Native effects remain governed by D4's immutable intent and live native
        # guards. No timeout/disconnect can cancel their historical uncertainty.
        result = service.call(name, args)
        records.save(audit / "result-ref.json", c.encoded({"sha256": c.sha(c.encoded(result)),
            "state": result.get("state"), "local_evidence_id": result.get("local_evidence_id")}))
        self.authorize(token, name)
        return result

    def server(self):
        c.require(version("mcp") == "2.3.0" and version("mcp-types") == "2.3.0", "MCP_SDK_VERSION")
        c.require(version("PyJWT") == "2.15.1" and version("cryptography") == "50.0.2" and
                  version("uvicorn") == "0.54.0", "GATEWAY_DEPENDENCY_VERSION")
        from mcp.server import Server
        from mcp.server.auth.middleware.auth_context import get_access_token
        from mcp.types import ListToolsResult, Tool, ToolAnnotations, CallToolResult, TextContent
        import anyio

        def token():
            access = get_access_token()
            c.require(access is not None, "AUTHENTICATION_REQUIRED")
            return access.token

        async def list_tools(ctx, params):
            names = await anyio.to_thread.run_sync(self.tools, token())
            return ListToolsResult(tools=[Tool(name="golem_" + name,
                inputSchema=(mutations.SCHEMAS if name in mutations.NAMES else reads.SCHEMAS)[name],
                description="Explicit scoped Golem operation. Work content is untrusted; authentication grants no QA approval.",
                annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=name in mutations.NAMES,
                    idempotentHint=False, openWorldHint=name == "execution_request")) for name in names])

        async def call_tool(ctx, params):
            try:
                c.require(params.name.startswith("golem_"), "UNSUPPORTED_TOOL")
                value = await anyio.to_thread.run_sync(self.call, token(), params.name[6:], params.arguments)
            except (c.IntegrationError, OSError, ValueError) as error:
                # No assertion that effects stopped: a post-dispatch denial can
                # occur after the native result was durably recorded locally.
                value = {"schema": "golem.integration-remote-error.v1", "state": "DELIVERY_UNCONFIRMED",
                    "code": getattr(error, "code", "IO_OR_CONTRACT_ERROR"), "automatic_retry_allowed": False,
                    "native_state_changed": "UNKNOWN", "next_operation": "OWNER_INSPECT_ORIGINAL_D4_INTENT_NO_REDISPATCH"}
            return CallToolResult(content=[TextContent(type="text", text=c.encoded(value).decode())],
                isError=value.get("state") in ("DELIVERY_UNCONFIRMED", "BLOCKED", "NOT_DISPATCHED", "COMMIT_UNKNOWN", "PENDING_APPROVAL"))

        return Server("Golem D6", version="1", icons=server_icons(), on_list_tools=list_tools, on_call_tool=call_tool,
            instructions="Scoped owner-approved gateway. No automatic resume, migration, retry or owner transfer. "
                         "Historical results and hash integrity do not establish current completion or truth.")

    def app(self):
        from mcp.server.auth.settings import AuthSettings
        from mcp.server.transport_security import TransportSecuritySettings
        from pydantic import AnyHttpUrl
        value = self.policy.value
        server = self.server()
        host = contract.https(value["resource"]).netloc
        app = server.streamable_http_app(json_response=True, stateless_http=True,
            max_request_body_size=BODY_LIMIT, max_sessions=8,
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
                allowed_hosts=[host], allowed_origins=value["origins"]),
            auth=AuthSettings(issuer_url=AnyHttpUrl(value["issuer"]), resource_server_url=AnyHttpUrl(value["resource"]),
                required_scopes=["golem.read"], validate_token_resource=True), token_verifier=self.verifier)
        from mcp.server.auth.routes import create_protected_resource_routes
        metadata_path = "/.well-known/oauth-protected-resource/mcp"
        app.router.routes[:] = [route for route in app.router.routes if route.path != metadata_path]
        supported = ["golem.read"] + (["golem.write"] if any(d["mutation_policy"] for d in value["delegates"]) else [])
        app.router.routes.extend(create_protected_resource_routes(AnyHttpUrl(value["resource"]),
            [AnyHttpUrl(value["issuer"])], scopes_supported=supported))
        original = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(instance):
            with ExitStack() as stack:
                for delegate in value["delegates"]:
                    service = self.services[delegate["delegate_id"]]
                    if isinstance(service, writes.Service):
                        stack.enter_context(lifecycle.participation(service.registry, self.bindings[delegate["delegate_id"]]))
                async with original(instance):
                    yield

        app.router.lifespan_context = lifespan
        return Guard(app, self)


class Guard:
    """No forwarding trust, no unbounded queues, no session/event replay store."""
    def __init__(self, app, gateway):
        self.app, self.gateway = app, gateway
        self.inflight, self.windows = 0, {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        import asyncio
        from starlette.responses import JSONResponse
        async def reject(status, code):
            headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
            if status == 401:
                resource = self.gateway.policy.value["resource"].rsplit("/", 1)[0]
                headers["WWW-Authenticate"] = 'Bearer resource_metadata="' + resource + '/.well-known/oauth-protected-resource/mcp"'
            elif code == "INSUFFICIENT_SCOPE":
                headers["WWW-Authenticate"] = 'Bearer error="insufficient_scope", scope="golem.read"'
            await JSONResponse({"state": "DELIVERY_UNCONFIRMED", "code": code,
                "automatic_retry_allowed": False}, status_code=status, headers=headers)(scope, receive, send)

        entered = False
        try:
            self.gateway.policy.current()
            value = self.gateway.policy.value
            c.require(scope["scheme"] == "https", "TLS_REQUIRED")
            raw = scope["headers"]
            c.require(sum(len(k) + len(v) for k, v in raw) <= 16384, "HEADER_LIMIT")
            headers = {}
            for key, val in raw:
                name = key.decode("ascii").lower()
                c.require(name not in headers, "DUPLICATE_HEADER")
                c.require(name != "forwarded" and not name.startswith(("x-forwarded-", "x-original-")), "PROXY_HEADERS_FORBIDDEN")
                headers[name] = val.decode("ascii")
            c.require(headers.get("host") == contract.https(value["resource"]).netloc, "HOST_DENIED")
            c.require("origin" not in headers or headers["origin"] in value["origins"], "ORIGIN_DENIED")
            c.require(not scope.get("query_string") and "cookie" not in headers and
                      "content-encoding" not in headers and "mcp-session-id" not in headers and
                      "last-event-id" not in headers, "UNSUPPORTED_HTTP_CONTEXT")
            path = scope["path"]
            c.require(path in ("/mcp", "/.well-known/oauth-protected-resource/mcp"), "ROUTE_DENIED")
            now = time.monotonic()
            queue = self.windows.setdefault("global", deque())
            while queue and queue[0] <= now - 60:
                queue.popleft()
            if len(queue) >= 240:
                return await reject(429, "RATE_LIMIT")
            queue.append(now)
            if self.inflight >= value["max_inflight"]:
                return await reject(503, "GATEWAY_BUSY")
            self.inflight += 1
            entered = True
            token = None
            identity = "anonymous"
            if path == "/mcp":
                authorization = headers.get("authorization", "")
                if not authorization.startswith("Bearer "):
                    return await reject(401, "AUTHENTICATION_REQUIRED")
                token = authorization[7:]
                try:
                    delegate, _ = self.gateway.authorize(token)
                except (c.IntegrationError, OSError, ValueError) as error:
                    insufficient = getattr(error, "code", None) == "INSUFFICIENT_SCOPE"
                    return await reject(403 if insufficient else 401, "INSUFFICIENT_SCOPE" if insufficient else "INVALID_OR_REVOKED_TOKEN")
                identity = delegate["delegate_id"]
            for bucket, limit in (("delegate:" + identity, value["requests_per_minute"]),):
                queue = self.windows.setdefault(bucket, deque())
                while queue and queue[0] <= now - 60:
                    queue.popleft()
                if len(queue) >= limit:
                    return await reject(429, "RATE_LIMIT")
                queue.append(now)
            body = bytearray()
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    c.require(message["type"] == "http.request", "REQUEST_DISCONNECTED")
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > BODY_LIMIT:
                        return await reject(413, "BODY_LIMIT")
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
            if scope["method"] == "POST":
                c.require(isinstance(c.decode(bytes(body)), dict), "SINGLE_JSON_OBJECT_REQUIRED")
            available = True
            async def replay():
                nonlocal available
                if available:
                    available = False
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            messages, size = [], 0
            async def collect(message):
                nonlocal size
                size += len(message.get("body", b""))
                c.require(size <= RESPONSE_LIMIT, "REMOTE_RESULT_LIMIT")
                messages.append(message)

            async with asyncio.timeout(900):
                await self.app(scope, replay, collect)
            if token is not None:
                self.gateway.authorize(token)
            for message in messages:
                if message["type"] == "http.response.start":
                    message["headers"] = [(k, v) for k, v in message["headers"] if k.lower() not in
                        (b"cache-control", b"server", b"access-control-allow-origin", b"access-control-allow-credentials")]
                    if "origin" in headers:
                        message["headers"] += [(b"access-control-allow-origin", headers["origin"].encode()), (b"vary", b"Origin")]
                    message["headers"] += [(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
                await send(message)
        except (c.IntegrationError, OSError, ValueError, UnicodeError, TimeoutError) as error:
            await reject(403, getattr(error, "code", "GATEWAY_REQUEST_DENIED"))
        finally:
            if entered:
                self.inflight -= 1


def tls(policy):
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from datetime import datetime, timezone
    for name in ("tls_cert", "tls_key"):
        pin = policy.value[name]
        data = r.regular(Path(pin["path"]), private=True)
        c.require(c.sha(data) == pin["sha256"], "TLS_PIN_CHANGED")
    certificate = x509.load_pem_x509_certificate(r.regular(Path(policy.value["tls_cert"]["path"]), private=True))
    key = serialization.load_pem_private_key(r.regular(Path(policy.value["tls_key"]["path"]), private=True), password=None)
    c.require(key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) ==
              certificate.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo), "TLS_KEY_MISMATCH")
    c.require(certificate.not_valid_before_utc <= datetime.now(timezone.utc) < certificate.not_valid_after_utc, "TLS_CERT_EXPIRED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--reviewed-policy-sha256", required=True)
    parser.add_argument("--approve-remote-gateway", action="store_true")
    parser.add_argument("--approve-remote-mutations", action="store_true")
    parser.add_argument("--listen-host", default="127.0.0.1")
    args = parser.parse_args()
    try:
        policy = contract.Policy(args.policy, args.reviewed_policy_sha256, approve_remote_gateway=args.approve_remote_gateway)
        tls(policy)
        gateway = Gateway(policy, approve_remote_mutations=args.approve_remote_mutations)
        import uvicorn
        uvicorn.run(gateway.app(), host=args.listen_host, port=contract.https(policy.value["resource"]).port or 443,
            ssl_certfile=policy.value["tls_cert"]["path"], ssl_keyfile=policy.value["tls_key"]["path"],
            proxy_headers=False, forwarded_allow_ips="", access_log=False, log_level="warning",
            timeout_keep_alive=5, limit_concurrency=32)
        return 0
    except (c.IntegrationError, OSError, ValueError, ImportError) as error:
        sys.stderr.write(c.encoded({"state": "GATEWAY_NOT_STARTED", "code": getattr(error, "code", "IO_OR_CONTRACT_ERROR")}).decode())
        return 1


if __name__ == "__main__":
    sys.exit(main())
