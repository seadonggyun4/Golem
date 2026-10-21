"""Independent D5 closed request/state/certificate schema verification."""
from jsonschema import Draft202012Validator, ValidationError

import integration_contract as c
import integration_lifecycle as life
import integration_recovery as recovery
import integration_update as update
from test_integration_update import D5


def main():
    fixture, assertions = D5(), 0
    try:
        fixture.setUp()
        fixture.freeze()
        review = fixture.review("mutation-" + "0" * 64)
        examples = {
            "freeze": {"project_id": "p", "freeze_id": "f"}, "stage": fixture.stage_request(),
            "stage-repair": {"project_id": "p", "original_plan": review["owner_review"]},
            "verify": {"project_id": "p", "bundle": review["owner_review"], "enrollment": fixture.enrollment},
            "switch": {"project_id": "p", "verification": review["owner_review"], "stopped": fixture.stopped},
            "repair-switch": {"project_id": "p", "stopped": fixture.stopped},
            "restore": {"project_id": "p", "stopped": fixture.stopped, "effect_review": review["owner_review"]},
            "thaw": {"project_id": "p", "stopped": fixture.stopped},
            "ready": {"project_id": "p", "reloads": [{"principal_id": "owner", "client_id": "client-a",
                "state": "RELOADED_OWNER_ATTESTED", "probe": review["owner_review"]}]}}
        cases = [(update.SPEC[key], value) for key, value in examples.items()]
        cases += [(recovery.SPEC, review), (life.STATE, life.current(fixture.registry, "p")[0])]
        for rule, value in cases:
            Draft202012Validator.check_schema(rule)
            validator = Draft202012Validator(rule)
            validator.validate(value)
            assertions += 1
            for bad in [{**value, "approve": True}, *({k: v for k, v in value.items() if k != key} for key in value)]:
                try:
                    validator.validate(bad)
                except ValidationError:
                    assertions += 1
                else:
                    raise AssertionError("open/optional D5 request field")
        Draft202012Validator.check_schema(life.RESOLUTION)
    finally:
        fixture.doCleanups()
    print(c.encoded({"schema": "golem.integration-d5-schema-check.v1", "status": "PASS", "assertions": assertions}).decode(), end="")


if __name__ == "__main__":
    main()
