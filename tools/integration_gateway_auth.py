"""D6 strict RFC 9068 RS256 verification and live local revocation. No HTTP fetch."""
from pathlib import Path
import threading
import time

import integration_contract as c
import integration_registry as r
import integration_gateway_contract as contract


class Verifier:
    def __init__(self, policy):
        self.policy = policy
        self.anchor = (time.time(), time.monotonic())
        self.revocation_head = None
        self.lock = threading.Lock()
        self.keys = self.load_keys()

    def load_keys(self):
        import jwt
        pin = self.policy.value["jwks"]
        data = r.regular(Path(pin["path"]), private=True)
        c.require(c.sha(data) == pin["sha256"], "JWKS_CHANGED")
        value = c.decode(data)
        c.require(isinstance(value, dict) and set(value) == {"keys"} and isinstance(value["keys"], list) and
                  1 <= len(value["keys"]) <= 8, "JWKS_CONTRACT")
        keys = {}
        for item in value["keys"]:
            c.require(isinstance(item, dict) and set(item) == {"kty", "kid", "alg", "use", "n", "e"} and
                      item["kty"] == "RSA" and item["alg"] == "RS256" and item["use"] == "sig", "JWKS_CONTRACT")
            c._validate(item["kid"], c.ID)
            c.require(item["kid"] not in keys, "JWKS_CONTRACT")
            key = jwt.PyJWK.from_dict(item, algorithm="RS256").key
            c.require(2048 <= key.key_size <= 8192, "JWKS_KEY_SIZE")
            keys[item["kid"]] = key
        return keys

    def revocations(self):
        data = r.regular(Path(self.policy.value["revocation_file"]), private=True)
        value = c.decode(data)
        contract.validate_revocations(value)
        with self.lock:
            if self.revocation_head is not None:
                epoch, digest = self.revocation_head
                c.require(value["epoch"] > epoch or value["epoch"] == epoch and c.sha(data) == digest, "REVOCATION_ROLLBACK")
            self.revocation_head = value["epoch"], c.sha(data)
        c.require(not value["disabled"], "GATEWAY_REVOKED")
        return value

    def authenticate(self, token):
        import jwt
        self.policy.current()
        pin = self.policy.value["jwks"]
        c.require(c.sha(r.regular(Path(pin["path"]), private=True)) == pin["sha256"], "JWKS_CHANGED")
        c.require(isinstance(token, str) and 1 <= len(token) <= 8192 and token.isascii(), "INVALID_TOKEN")
        c.require(time.time() + 2 >= self.anchor[0] + time.monotonic() - self.anchor[1], "AUTH_CLOCK_UNSAFE")
        try:
            parts = token.split(".")
            c.require(len(parts) == 3, "INVALID_TOKEN")
            header = c.decode(jwt.utils.base64url_decode(parts[0].encode()), 8192)
            claims = c.decode(jwt.utils.base64url_decode(parts[1].encode()), 8192)
            c.require(isinstance(header, dict) and set(header) == {"alg", "kid", "typ"} and
                      header["typ"] == "at+jwt" and header["alg"] == "RS256" and header["kid"] in self.keys,
                      "INVALID_TOKEN")
            value = self.policy.value
            verified = jwt.decode(token, self.keys[header["kid"]], algorithms=["RS256"],
                issuer=value["issuer"], audience=value["resource"],
                options={"require": ["iss", "aud", "sub", "client_id", "exp", "iat", "nbf", "jti", "scope"],
                         "strict_aud": True})
            c.require(verified == claims and "cnf" not in claims, "INVALID_TOKEN")
            for key in ("sub", "client_id", "jti", "scope"):
                c._validate(claims[key], contract.TEXT if key != "scope" else
                            {"type": "string", "minLength": 1, "maxLength": 1024})
            c.require(all(type(claims[key]) is int for key in ("exp", "iat", "nbf")) and
                      0 < claims["exp"] - claims["iat"] <= value["max_token_seconds"] and
                      claims["iat"] <= claims["nbf"] < claims["exp"], "INVALID_TOKEN")
            delegate = next((d for d in value["delegates"] if d["subject"] == claims["sub"] and
                             d["oauth_client_id"] == claims["client_id"]), None)
            c.require(delegate is not None, "REMOTE_PRINCIPAL_NOT_APPROVED")
            revoked = self.revocations()
            c.require(claims["jti"] not in revoked["revoked_jtis"] and
                      delegate["delegate_id"] not in revoked["revoked_delegates"] and
                      claims["iat"] >= revoked["not_before"], "TOKEN_REVOKED")
            c.require("golem.read" in claims["scope"].split(), "INSUFFICIENT_SCOPE")
            return delegate, claims
        except (jwt.PyJWTError, KeyError, UnicodeError, TypeError):
            raise c.IntegrationError("INVALID_TOKEN") from None

    async def verify_token(self, token):
        from mcp.server.auth.provider import AccessToken
        import anyio
        try:
            _, claims = await anyio.to_thread.run_sync(self.authenticate, token)
            return AccessToken(token=token, client_id=claims["client_id"], subject=claims["sub"],
                scopes=claims["scope"].split(), expires_at=claims["exp"], resource=claims["aud"], claims={"iss": claims["iss"]})
        except (c.IntegrationError, OSError, ValueError):
            return None
