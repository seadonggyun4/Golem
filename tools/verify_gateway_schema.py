"""Independent D6 policy and revocation schemas, without optional HTTP/crypto."""
import copy
from jsonschema import Draft202012Validator, ValidationError

import integration_contract as c
import integration_gateway_contract as gateway


def main():
    pin = {"path": "/private/synthetic-fixture", "sha256": "0" * 64}
    value = {"schema": "golem.integration-gateway.v1", "issuer": "https://issuer.example.test",
        "resource": "https://gateway.example.test/mcp", "jwks": pin, "tls_cert": pin, "tls_key": pin,
        "revocation_file": "/private/revocations.json", "origins": [], "max_token_seconds": 300,
        "requests_per_minute": 60, "max_inflight": 1, "producer": gateway.producer(),
        "delegates": [{"delegate_id": "remote-a", "subject": "user-a", "oauth_client_id": "client-a",
            "destination_id": "destination-a", "transfer_policy": pin, "mutation_policy": None, "tools": ["work_inspect"]}]}
    revoked = {"schema": "golem.integration-remote-revocations.v1", "epoch": 1, "disabled": False,
        "not_before": 0, "revoked_jtis": [], "revoked_delegates": []}
    assertions = 0
    for rule, item, validate in ((gateway.POLICY, value, gateway.validate),
                                  (gateway.REVOCATIONS, revoked, gateway.validate_revocations)):
        Draft202012Validator.check_schema(rule)
        validator = Draft202012Validator(rule)
        validator.validate(item)
        validate(item)
        assertions += 2
        for fields in ((), ("delegates", 0), ("producer",)) if item is value else ((),):
            target = item
            for field in fields:
                target = target[field]
            for key in (*target, "unexpected"):
                bad = copy.deepcopy(item)
                changed = bad
                for field in fields:
                    changed = changed[field]
                if key == "unexpected":
                    changed[key] = True
                else:
                    del changed[key]
                try:
                    validator.validate(bad)
                except ValidationError:
                    assertions += 1
                else:
                    raise AssertionError("open D6 contract")
    print(c.encoded({"schema": "golem.integration-d6-schema-check.v1", "status": "PASS", "assertions": assertions}).decode(), end="")


if __name__ == "__main__":
    main()
