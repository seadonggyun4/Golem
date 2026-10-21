"""Independent D4 JSON Schema checks, without client/native execution."""
from jsonschema import Draft202012Validator, ValidationError

import integration_contract as c
import integration_mutation_contract as contract
from test_integration_mutations import D4


def main():
    fixture = D4()
    assertions = 0
    try:
        fixture.setUp()
        values = [(contract.POLICY, fixture.mutation_policy), (contract.ACTION, fixture.action),
            (contract.DECISION, {"schema": "golem.integration-local-decision.v1", "operation": "approve",
                "action_digest": "0" * 64, "issuer": "1" * 64, "policy_epoch": 1}),
            (contract.ARGS, fixture.args)]
        for rule, value in values:
            Draft202012Validator.check_schema(rule)
            validator = Draft202012Validator(rule)
            validator.validate(value)
            assertions += 1
            for broken in [{**value, "unknown": True}, *({k: v for k, v in value.items() if k != key} for key in value)]:
                try:
                    validator.validate(broken)
                except ValidationError:
                    assertions += 1
                else:
                    raise AssertionError("open or optional D4 field")
        approval = {"host": fixture.entry["action"], "decision": fixture.entry["action"],
                    "request_receipt": "0" * 64, "contract": "1" * 64, "shell_contract": ""}
        validator = Draft202012Validator(contract.ACTION)
        validator.validate({**fixture.action, "approval": approval})
        assertions += 1
        for bad in ({**approval, "approve": True}, {**approval, "shell_contract": "shell"}):
            try:
                validator.validate({**fixture.action, "approval": bad})
            except ValidationError:
                assertions += 1
            else:
                raise AssertionError("open approval contract")
    finally:
        fixture.doCleanups()
    print(c.encoded({"schema": "golem.integration-d4-schema-check.v1", "assertions": assertions, "status": "PASS"}).decode(), end="")


if __name__ == "__main__":
    main()
