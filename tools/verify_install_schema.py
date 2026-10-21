"""Independent installer-request schema validation; no installations performed."""
import copy
import json
from jsonschema import Draft202012Validator, ValidationError

import integration_install as install


def main():
    count = 0
    runtime = {"python": {"path": "/private/python", "sha256": "0" * 64}, "sdk_root": "/private/sdk",
               "sdk_identity": {"device": 1, "inode": 2}, "files": {"mcp/a.py": "1" * 64}}
    values = {"bootstrap": {"bootstrap_id": "new", "project_id": "p", "root": "/private/project"},
              "remove": {"installation_id": "first", "clients_stopped": "STOPPED_OWNER_ATTESTED"},
              "install": {"installation_id": "first", "clients_stopped": "STOPPED_OWNER_ATTESTED", "targets": [{"client": "codex-config", "config": "/private/config.toml",
                  "server_name": "golem", "runtime": runtime, "transfer_policy": {"path": "/private/policy", "sha256": "2" * 64}}]}}
    for operation, schema in install.SPECS.items():
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        validator.validate(values[operation])
        count += 1
        for key in values[operation]:
            invalid = copy.deepcopy(values[operation])
            del invalid[key]
            try:
                validator.validate(invalid)
            except ValidationError:
                count += 1
            else:
                raise AssertionError("missing field accepted")
        invalid = {**values[operation], "unknown": True}
        try:
            validator.validate(invalid)
        except ValidationError:
            count += 1
        else:
            raise AssertionError("unknown field accepted")
    print(json.dumps({"status": "PASS", "assertions": count, "native_or_client_execution": False}))


if __name__ == "__main__":
    main()
