"""Independent D3 JSON Schema gate; optional jsonschema dependency, no clients."""
import copy
import json

from jsonschema import Draft202012Validator, ValidationError

import integration_hook_contract as contract
from test_integration_hooks import Hooks


def main():
    fixture = Hooks("test_closed_schema_and_unknown_client_versions")
    try:
        fixture.setUp()
        Draft202012Validator.check_schema(contract.PROFILE)
        validator = Draft202012Validator(contract.PROFILE)
        value = fixture.value
        validator.validate(value)
        assertions = 1
        for fields in ((), ("context",), ("producer",), ("client_pin",), ("python_pin",), ("transfer_policy",)):
            target = value
            for field in fields:
                target = target[field]
            for key in (*target, "extra"):
                broken = copy.deepcopy(value)
                current = broken
                for field in fields:
                    current = current[field]
                if key == "extra":
                    current[key] = True
                else:
                    del current[key]
                try:
                    validator.validate(broken)
                except ValidationError:
                    assertions += 1
                else:
                    raise AssertionError("D3 schema accepted missing/extra field")
        print(json.dumps({"schema": "golem.integration-hook-schema-check.v1", "status": "PASS",
                          "assertions": assertions, "native_or_client_execution": False}))
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
