"""D6 security contracts. Optional crypto/SDK deps; native TLS gate is separate."""
import asyncio
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import ipaddress
from pathlib import Path
import time
import unittest
from unittest.mock import patch

import integration_contract as c
import integration_registry as r
import integration_gateway_contract as contract
import integration_gateway as gateway
import test_integration_mutations as fixture

AVAILABLE = all(importlib.util.find_spec(name) for name in ("jwt", "cryptography", "mcp"))


def private(root, name, value):
    path = root / name
    path.write_bytes(value if isinstance(value, bytes) else c.encoded(value))
    path.chmod(0o600)
    return r.file_pin(path)


def credentials(root, transfer_pin, destination, *, mutation_pin=None, resource="https://localhost:9443/mcp"):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import jwt
    signing = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key = c.decode(jwt.algorithms.RSAAlgorithm.to_jwk(signing.public_key()).encode())
    key = {**{name: key[name] for name in ("kty", "n", "e")}, "kid": "test-key", "alg": "RS256", "use": "sig"}
    jwks = private(root, "jwks.json", {"keys": [key]})
    tls = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "localhost")])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(tls.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .sign(tls, hashes.SHA256()))
    cert_pin = private(root, "tls-cert.pem", cert.public_bytes(serialization.Encoding.PEM))
    key_pin = private(root, "tls-key.pem", tls.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    revoked = private(root, "revocations.json", {"schema": "golem.integration-remote-revocations.v1", "epoch": 1,
        "disabled": False, "not_before": 0, "revoked_jtis": [], "revoked_delegates": []})
    value = {"schema": "golem.integration-gateway.v1", "issuer": "https://issuer.example.test", "resource": resource,
        "jwks": jwks, "tls_cert": cert_pin, "tls_key": key_pin, "revocation_file": revoked["path"],
        "origins": ["https://client.example.test"], "max_token_seconds": 300, "requests_per_minute": 120, "max_inflight": 2,
        "delegates": [{"delegate_id": "remote-a", "subject": "user-a", "oauth_client_id": "oauth-a",
            "destination_id": destination, "transfer_policy": transfer_pin, "mutation_policy": mutation_pin,
            "tools": ["projects_list", "work_inspect", "history_read", "context_get", "handoff_prepare"] +
                     (["session_claim"] if mutation_pin else [])}], "producer": contract.producer()}
    return value, signing


def token(signing, policy, **changes):
    import jwt
    now = int(time.time())
    value = {"iss": policy["issuer"], "aud": policy["resource"], "sub": "user-a", "client_id": "oauth-a",
        "iat": now, "nbf": now, "exp": now + 240, "jti": "token-a", "scope": "golem.read golem.write", **changes}
    return jwt.encode(value, signing, algorithm="RS256", headers={"kid": "test-key", "typ": "at+jwt"})


@unittest.skipUnless(AVAILABLE, "optional tools/requirements-gateway.txt required")
class D6(unittest.TestCase):
    for name in ("approve", "query", "expect", "inventory", "save_policy", "adapter", "repin"):
        locals()[name] = getattr(fixture.D4, name)

    def setUp(self):
        fixture.D4.setUp(self)
        self.value, self.signing = credentials(self.root, r.file_pin(self.policy_path), "synthetic-client")
        self.pin = private(self.root, "gateway.json", self.value)
        self.api = gateway.Gateway(self.owner_policy())
        self.bearer = token(self.signing, self.value)

    def owner_policy(self):
        return contract.Policy(Path(self.pin["path"]), self.pin["sha256"], approve_remote_gateway=True)

    def repolicy(self):
        self.pin = private(self.root, "gateway.json", self.value)
        return self.owner_policy()

    def revoke(self, **values):
        path = Path(self.value["revocation_file"])
        current = c.decode(path.read_bytes())
        private(self.root, path.name, {**current, "epoch": current["epoch"] + 1, **values})

    def test_owner_intent_closed_schema_and_https(self):
        self.expect("OWNER_REMOTE_GATEWAY_APPROVAL_REQUIRED", lambda: contract.Policy(Path(self.pin["path"]), self.pin["sha256"]))
        for key in self.value:
            value = copy.deepcopy(self.value)
            del value[key]
            self.expect("SCHEMA", lambda: contract.validate(value))
        for url in ("http://localhost/mcp", "https://user:secret@host/mcp", "https://host/mcp?token=secret", "https://host/*"):
            with self.assertRaises(ValueError):
                contract.validate({**self.value, "resource": url})
        self.expect("SCHEMA", lambda: contract.validate({**self.value, "approve": True}))

    def test_valid_access_token_does_not_supply_native_or_cloud_authority(self):
        before = self.inventory()
        self.assertIn("work_inspect", self.api.tools(self.bearer))
        self.assertNotIn("session_resume", self.api.tools(self.bearer))
        self.expect("REMOTE_TOOL_SCOPE", lambda: self.api.call(self.bearer, "session_claim", {}))
        self.expect("TRANSFER_SCOPE", lambda: self.api.call(self.bearer, "work_inspect", {
            "project_id": "p", "work_id": "foreign", "view": "status"}))
        self.assertEqual(before, self.inventory())

    def test_issuer_audience_subject_client_expiry_and_scope(self):
        cases = [{"iss": "https://foreign.test"}, {"aud": "https://provider.test/api"}, {"aud": [self.value["resource"]]},
            {"sub": "foreign"}, {"client_id": "foreign"}, {"exp": int(time.time()) - 1},
            {"exp": int(time.time()) + 600}, {"scope": "golem.write"}, {"iat": True}, {"nbf": int(time.time()) + 100},
            {"cnf": {"jkt": "unsupported"}}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.api.authorize(token(self.signing, self.value, **changes))

    def test_algorithm_typ_key_confusion_and_token_url_headers(self):
        import jwt
        now = int(time.time())
        for headers in ({"kid": "test-key", "typ": "JWT"}, {"kid": "foreign", "typ": "at+jwt"},
                        {"kid": "test-key", "typ": "at+jwt", "jku": "https://attacker.test/keys"}):
            with self.assertRaises(ValueError):
                self.api.authorize(jwt.encode({"exp": now + 60}, self.signing, algorithm="RS256", headers=headers))
        with self.assertRaises(ValueError):
            self.api.authorize(jwt.encode({"exp": now + 60}, "synthetic-key-with-at-least-32-bytes", algorithm="HS256", headers={"kid": "test-key", "typ": "at+jwt"}))

    def test_live_revocation_and_rollback_are_fail_closed(self):
        self.api.authorize(self.bearer)
        self.revoke(revoked_jtis=["token-a"])
        self.expect("TOKEN_REVOKED", lambda: self.api.authorize(self.bearer))
        self.revoke(revoked_jtis=[])
        self.api.authorize(self.bearer)
        self.revoke(epoch=1)
        self.expect("REVOCATION_ROLLBACK", lambda: self.api.authorize(self.bearer))

    def test_policy_jwks_or_transfer_drift_blocks_existing_service(self):
        path = Path(self.value["jwks"]["path"])
        path.write_bytes(path.read_bytes() + b" ")
        self.expect("JWKS_CHANGED", lambda: self.api.authorize(self.bearer))

    def test_local_read_is_not_remote_disclosure_consent(self):
        self.policy["destination"] = "LOCAL_HOST"
        self.save_policy()
        self.value["delegates"][0]["transfer_policy"] = r.file_pin(self.policy_path)
        self.expect("REMOTE_DISCLOSURE_REQUIRED", lambda: gateway.Gateway(self.repolicy()))

    def test_remote_mutation_needs_separate_owner_approval_and_token_scope(self):
        self.value["delegates"][0].update(mutation_policy=r.file_pin(self.mutation_path), tools=["work_inspect", "session_claim"])
        policy = self.repolicy()
        self.expect("OWNER_REMOTE_MUTATION_APPROVAL_REQUIRED", lambda: gateway.Gateway(policy))
        api = gateway.Gateway(policy, approve_remote_mutations=True)
        read_token = token(self.signing, self.value, scope="golem.read")
        self.expect("INSUFFICIENT_SCOPE", lambda: api.call(read_token, "session_claim", {}))
        self.assertNotIn("session_claim", api.tools(read_token))

    def test_distinct_remote_clients_cannot_share_one_native_identity(self):
        self.value["delegates"].append({**self.value["delegates"][0], "delegate_id": "remote-b",
            "subject": "user-b", "oauth_client_id": "oauth-b"})
        self.expect("SHARED_LOCAL_IDENTITY_FORBIDDEN", lambda: gateway.Gateway(self.repolicy()))

    def test_duplicate_signed_claims_and_missing_revocations_are_rejected(self):
        import jwt
        malformed = jwt.api_jws.encode(b'{"iss":"a","iss":"b"}', self.signing, algorithm="RS256",
            headers={"kid": "test-key", "typ": "at+jwt"})
        self.expect("JSON_INVALID", lambda: self.api.authorize(malformed))
        Path(self.value["revocation_file"]).unlink()
        with self.assertRaises(OSError):
            self.api.authorize(self.bearer)

    def test_d1_revocation_still_blocks_authenticated_request(self):
        self.approve("revoke")
        self.expect("PROJECT_APPROVAL_REQUIRED", lambda: self.api.call(self.bearer, "work_inspect", {
            "project_id": "p", "work_id": "a", "view": "status"}))

    def test_wall_clock_regression_and_credential_pins(self):
        self.api.verifier.anchor = time.time() + 100, time.monotonic()
        self.expect("AUTH_CLOCK_UNSAFE", lambda: self.api.authorize(self.bearer))
        gateway.tls(self.owner_policy())
        Path(self.value["tls_key"]["path"]).write_bytes(b"changed")
        self.expect("TLS_PIN_CHANGED", lambda: gateway.tls(self.owner_policy()))

    async def request(self, guard, *, headers=None, scheme="https", path="/mcp", query=b"", body=b"{}"):
        raw = [(b"host", b"localhost:9443"), (b"authorization", ("Bearer " + self.bearer).encode())]
        if headers is not None:
            raw = headers
        scope = {"type": "http", "scheme": scheme, "headers": raw, "path": path, "query_string": query,
                 "method": "POST", "http_version": "1.1", "server": ("localhost", 9443), "client": ("127.0.0.1", 1234)}
        messages = []
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}
        async def send(message):
            messages.append(message)
        await guard(scope, receive, send)
        return next(m["status"] for m in messages if m["type"] == "http.response.start"), messages

    def guard(self, effect=None):
        async def echo(scope, receive, send):
            if effect:
                effect()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})
        return gateway.Guard(echo, self.api)

    def test_http_security_precedes_any_backend_work(self):
        guard = self.guard()
        valid = [(b"host", b"localhost:9443"), (b"authorization", ("Bearer " + self.bearer).encode())]
        cases = [{"scheme": "http"}, {"query": b"access_token=secret"}, {"headers": valid + [(b"origin", b"https://evil.test")]},
            {"headers": valid + [(b"x-forwarded-proto", b"https")]}, {"headers": valid + [(b"cookie", b"token=secret")]},
            {"headers": valid + [(b"host", b"evil.test")]}, {"headers": [(b"host", b"evil.test")]},
            {"headers": valid + [(b"mcp-session-id", b"copied")]}, {"body": b'[{}]'}, {"body": b'{"x":1,"x":2}'}]
        for case in cases:
            with self.subTest(case=case):
                self.assertNotEqual(asyncio.run(self.request(guard, **case))[0], 200)
        self.assertEqual(asyncio.run(self.request(guard))[0], 200)

    def test_response_revocation_size_and_busy_never_report_success(self):
        guard = self.guard(lambda: self.revoke(disabled=True))
        self.assertNotEqual(asyncio.run(self.request(guard))[0], 200)
        self.revoke(disabled=False)
        guard = self.guard()
        guard.inflight = self.value["max_inflight"]
        self.assertEqual(asyncio.run(self.request(guard))[0], 503)
        guard.inflight = 0
        self.assertEqual(asyncio.run(self.request(guard, body=b"x" * (c.LIMIT + 1)))[0], 413)
        with patch.object(gateway, "RESPONSE_LIMIT", 1):
            self.assertEqual(asyncio.run(self.request(guard))[0], 403)

    def test_late_local_grant_revocation_discards_buffered_response(self):
        guard = self.guard(lambda: self.approve("revoke"))
        self.assertEqual(asyncio.run(self.request(guard))[0], 403)

    def test_rate_limit_and_redacted_private_audit(self):
        self.value["requests_per_minute"] = 1
        self.api = gateway.Gateway(self.repolicy())
        guard = self.guard()
        self.assertEqual(asyncio.run(self.request(guard))[0], 200)
        self.assertEqual(asyncio.run(self.request(guard))[0], 429)
        self.api.call(self.bearer, "projects_list", {})
        for path in self.registry.root.glob("remote-*/*.json"):
            self.assertNotIn(self.bearer.encode(), path.read_bytes())
            self.assertEqual(path.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
