"""Independent JSON Schema validation gate; jsonschema is test-only, not runtime."""
import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

import integration_contract as contract
from test_integration import Integration


def main():
    fixture = Integration()
    fixture.setUp()
    try:
        values = {"project": fixture.enrollment["project"], "grant": fixture.enrollment["grants"][0],
                  "binding": fixture.query()["binding"], "enrollment": fixture.enrollment,
                  "read": fixture.query(), "description": {"schema": "golem.integration-description.v1",
                      "project_id": "p", "root": str(fixture.project), "cli": str(fixture.cli),
                      "sdk_files": [str(fixture.sdk)], "works": [{"work_id": "a", "path": str(fixture.work)}]}}
        assertions = 0
        for kind, value in values.items():
            schema = json.loads((Path(__file__).resolve().parents[1] /
                                 "samples/integration" / (kind + ".schema.json")).read_bytes())
            assert schema == contract.schema(kind)
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema)
            validator.validate(value)
            contract.validate(kind, value)
            assertions += 2
            for key in value:
                missing = copy.deepcopy(value)
                del missing[key]
                assert not validator.is_valid(missing)
                assertions += 1
            assert not validator.is_valid({**value, "unknown": True})
            assertions += 1
        print(json.dumps({"status": "PASS", "schemas": len(values), "assertions": assertions,
                          "native_or_client_execution": False}))
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
