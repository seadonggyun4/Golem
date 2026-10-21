"""Owner-only D5 staged pin updates. No native mutations or client config writes."""
import argparse
import os
from pathlib import Path
import stat
import sys
import tempfile

import execution_record as records
import integration_backend as backend
import integration_contract as c
import integration_registry as r
import integration_lifecycle as life
import integration_mutation_contract as mutation_contract
import integration_hook_contract as hook_contract

ACK = c.obj({"principal_id": c.ID, "client_id": c.ID, "state": {"const": "STOPPED_OWNER_ATTESTED"}})
ARTIFACT = c.obj({"name": c.ID, "role": c.enum("ENGINE", "SDK", "INTEGRATION", "MCP", "INSTRUCTIONS"),
                  "source": c.PIN, "mode": c.enum("READ", "EXECUTE")})
RELOAD = c.obj({"principal_id": c.ID, "client_id": c.ID, "state": {"const": "RELOADED_OWNER_ATTESTED"}, "probe": c.PIN})
RESTORE_REVIEW = c.obj({"schema": {"const": "golem.integration-restore-review.v1"}, "project_id": c.ID,
    "freeze_id": c.ID, "enrollment_sha256": c.DIGEST,
    "effects": {"const": "NONE_SINCE_SWITCH_OWNER_ATTESTED"}, "evidence": c.array(c.PIN), "reason": c.ID})
SPEC = {
    "freeze": c.obj({"project_id": c.ID, "freeze_id": c.ID}),
    "stage": c.obj({"project_id": c.ID, "destination": c.PATH, "artifacts": c.array(ARTIFACT, 32)}),
    "stage-repair": c.obj({"project_id": c.ID, "original_plan": c.PIN}),
    "verify": c.obj({"project_id": c.ID, "bundle": c.PIN, "enrollment": c.ENROLLMENT}),
    "switch": c.obj({"project_id": c.ID, "verification": c.PIN, "stopped": c.array(ACK)}),
    "repair-switch": c.obj({"project_id": c.ID, "stopped": c.array(ACK)}),
    "restore": c.obj({"project_id": c.ID, "stopped": c.array(ACK), "effect_review": c.PIN}),
    "thaw": c.obj({"project_id": c.ID, "stopped": c.array(ACK)}),
    "ready": c.obj({"project_id": c.ID, "reloads": c.array(RELOAD)}),
}


def producer():
    root = Path(__file__).resolve().parent
    names = ("integration_lifecycle.py", "integration_update.py", "integration_recovery.py", "integration_reload_probe.py")
    return {**mutation_contract.producer(), **hook_contract.producer(),
            **{name: c.sha(r.regular(root / name)) for name in names}}


def pinned(pin, limit=c.LIMIT):
    c._validate(pin, c.PIN)
    data = r.regular(Path(pin["path"]), limit, private=True)
    c.require(c.sha(data) == pin["sha256"], "PIN_MISMATCH")
    return data


def inventory(root):
    """Bounded complete selected directory inventory, never a truncating sample."""
    root = r.real_path(str(root))
    result, total = {}, 0
    pending = [root]
    while pending:
        for path in sorted(pending.pop().iterdir()):
            info = path.lstat()
            c.require(len(result) < 16384 and not stat.S_ISLNK(info.st_mode), "INVENTORY_LIMIT_OR_LINK")
            row = [info.st_mode, info.st_dev, info.st_ino]
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            else:
                c.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "UNSAFE_FILE")
                total += info.st_size
                c.require(total <= 268435456, "INVENTORY_LIMIT_OR_LINK")
                row += [info.st_size, c.sha(r.regular(path, 134217728))]
            result[str(path.relative_to(root))] = row
    return c.sha(c.encoded(result))


def acknowledge(enrollment, values, state):
    expected = {(g["principal_id"], g["client_id"]) for g in enrollment["grants"]}
    actual = {(v["principal_id"], v["client_id"]) for v in values}
    c.require(len(actual) == len(values) and actual == expected and all(v["state"] == state for v in values),
              "ALL_CLIENT_ACKNOWLEDGEMENTS_REQUIRED")


class Manager:
    def __init__(self, registry):
        self.registry = registry

    def enrollment(self, project_id):
        record, pointer = self.registry._load(project_id)
        c.require(record is not None and record["state"] == "ACTIVE", "PROJECT_APPROVAL_REQUIRED")
        c.require(record["producer"] == r.producer(), "PRODUCER_CHANGED")
        r.check_project(record["enrollment"]["project"])
        return record["enrollment"], pointer

    def frozen(self, project_id, phases=("FROZEN",)):
        state, digest = life.current(self.registry, project_id)
        c.require(state is not None and state["phase"] in phases, "MAINTENANCE_PHASE")
        return state, digest

    def quiet(self, enrollment):
        life.quiet(self.registry, enrollment["project"]["project_id"])

    def observe(self, project):
        """Original read-only parser/status/next, with before/after full inventory."""
        r.check_project(project)
        result = {}
        backend._quota(self.registry.root)
        output = Path(tempfile.mkdtemp(prefix="read-d5-", dir=self.registry.root))
        doctor = records.capture([project["cli"]["path"], "--output-mode", "full", "doctor", "clock"],
            output, backend.TIMEOUT_SECONDS, cwd=output, observe_source=False, env=backend.ENVIRONMENT, limit=8192)
        c.require(doctor["returncode"] == 0 and doctor["recording"] == "RECORDED", "DOCTOR_UNSUPPORTED_ENVIRONMENT")
        for work in project["works"]:
            before = inventory(Path(work["path"]))
            request = {"schema_version": 1, "work_id": work["work_id"], "byte_budget": c.MAX_NATIVE,
                       "document_head": "", "agent_head": ""}
            record, _ = backend._native(project, work, "record", request, output / (work["work_id"] + "-record"))
            c.require(record.get("schema") == "golem.work-record.v1" and record.get("work_id") == work["work_id"], "WORK_IDENTITY")
            views = {}
            for operation in ("status", "next"):
                query = {"schema_version": 1, "work_id": work["work_id"], "operation": operation}
                views[operation], _ = backend._native(project, work, operation, query, output / (work["work_id"] + "-" + operation))
            status = views["status"]
            c.require(status["sequence"] == views["next"]["sequence"] and (status.get("state") or {}).get("active") is None,
                      "NATIVE_OWNER_OR_RECOVERY_REQUIRED")
            c.require(status["resume_preflight"]["reason"] in ("CURRENT", "DONE", "START_REQUIRED"),
                      "NATIVE_OWNER_OR_RECOVERY_REQUIRED")
            c.require(inventory(Path(work["path"])) == before, "READ_ONLY_INVENTORY_CHANGED")
            result[work["work_id"]] = {"inventory": before, "sequence": status["sequence"],
                "document_head": record["document_head"], "agent_head": record["agent_head"]}
        return result

    def unresolved(self, project):
        from integration_mutations import Service
        for path in self.registry.root.glob("mutation-*"):
            intent = c.decode(r.regular(path / "intent.json", private=True))
            if intent["binding"]["project_id"] == project["project_id"]:
                if life.clearance(path, intent) is not None:
                    continue
                try:
                    result = Service._result(path)
                    c.require(result["state"] != "COMMIT_UNKNOWN", "WORK_MUTATION_UNRESOLVED")
                except (OSError, ValueError):
                    raise c.IntegrationError("WORK_MUTATION_UNRESOLVED") from None

    def bundle(self, pin):
        value = c.decode(pinned(pin))
        c.require(isinstance(value, dict) and set(value) == {"schema", "root", "identity", "artifacts", "producer"} and
                  value["schema"] == "golem.integration-staged-bundle.v1" and value["producer"] == producer(), "BUNDLE_CONTRACT")
        root = r.real_path(value["root"])
        c.require(r.identity(root) == value["identity"] and root == Path(pin["path"]).parent, "BUNDLE_CHANGED")
        r.Registry._private(root)
        roles = set()
        names = set()
        c._validate(value["artifacts"], c.array(ARTIFACT, 32))
        for item in value["artifacts"]:
            c._validate(item, ARTIFACT)
            path = root / item["name"]
            c.require(item["name"] not in names and r.file_pin(path)["sha256"] == item["source"]["sha256"], "BUNDLE_CHANGED")
            c.require(stat.S_IMODE(path.stat().st_mode) == (0o500 if item["mode"] == "EXECUTE" else 0o400), "BUNDLE_CHANGED")
            names.add(item["name"])
            roles.add(item["role"])
        c.require(roles == {"ENGINE", "SDK", "INTEGRATION", "MCP", "INSTRUCTIONS"} and
                  {p.name for p in root.iterdir()} == names | {"bundle.json"} and
                  sum(i["role"] == "ENGINE" for i in value["artifacts"]) == 1 and
                  all(i["mode"] == "EXECUTE" for i in value["artifacts"] if i["role"] == "ENGINE"), "BUNDLE_INCOMPLETE")
        return value

    def stage_facts(self, request, *, repair=False):
        destination = Path(request["destination"])
        c.require(destination.is_absolute() and str(destination) == request["destination"] and
                  ".." not in destination.parts and not destination.is_symlink(), "PATH")
        parent = r.real_path(str(destination.parent))
        r.Registry._private(parent)
        enrollment, _ = self.enrollment(request["project_id"])
        project = Path(enrollment["project"]["root"])
        c.require(not destination.is_relative_to(project) and not project.is_relative_to(destination) and
                  not destination.is_relative_to(self.registry.root) and not self.registry.root.is_relative_to(destination), "STAGE_SCOPE")
        names, roles, total = set(), set(), 0
        for item in request["artifacts"]:
            c.require(item["name"] not in names, "DUPLICATE_ARTIFACT")
            c.require(r.file_pin(Path(item["source"]["path"])) == item["source"], "PIN_MISMATCH")
            names.add(item["name"])
            roles.add(item["role"])
            total += Path(item["source"]["path"]).stat().st_size
        c.require(total <= 134217728 and roles == {"ENGINE", "SDK", "INTEGRATION", "MCP", "INSTRUCTIONS"}, "BUNDLE_INCOMPLETE")
        engines = [i for i in request["artifacts"] if i["role"] == "ENGINE"]
        c.require(len(engines) == 1 and engines[0]["mode"] == "EXECUTE", "BUNDLE_ENGINE")
        if destination.exists():
            c.require(repair, "STAGE_DESTINATION_EXISTS")
            r.real_path(str(destination))
            r.Registry._private(destination)
            c.require({p.name for p in destination.iterdir()} <= names | {"bundle.json"}, "STAGE_DRIFT")
            for item in request["artifacts"]:
                path = destination / item["name"]
                if path.exists() or path.is_symlink():
                    c.require(r.file_pin(path)["sha256"] == item["source"]["sha256"] and
                              stat.S_IMODE(path.stat().st_mode) == (0o500 if item["mode"] == "EXECUTE" else 0o400), "STAGE_DRIFT")
        return inventory(destination) if destination.exists() else None

    def facts(self, operation, request):
        c.require(operation in SPEC, "UNSUPPORTED_OPERATION")
        c.bounded(request)
        c.require(len(c.encoded(request)) <= c.LIMIT, "JSON_SIZE")
        c._validate(request, SPEC[operation])
        enrollment, before = self.enrollment(request["project_id"])
        state, lifecycle_sha = life.current(self.registry, request["project_id"])
        facts = {"before": before, "lifecycle_sha256": lifecycle_sha}
        if operation == "freeze":
            c.require(state is None or state["phase"] == "OPEN", "MAINTENANCE_PHASE")
            return facts
        state, _ = self.frozen(request["project_id"], ("FROZEN", "SWITCH_INTENT", "RELOAD_REQUIRED"))
        if operation in ("stage", "stage-repair"):
            c.require(state["phase"] == "FROZEN", "MAINTENANCE_PHASE")
            stage = request
            if operation == "stage-repair":
                old = c.decode(pinned(request["original_plan"]))
                c.require(old["operation"] == "stage" and old["producer"] == producer() and
                          old["request"]["project_id"] == request["project_id"] and
                          old["facts"]["lifecycle_sha256"] == lifecycle_sha, "STAGE_PLAN_STALE")
                stage = old["request"]
                c._validate(stage, SPEC["stage"])
            facts["stage_inventory"] = self.stage_facts(stage, repair=operation == "stage-repair")
        elif operation == "verify":
            c.require(state["phase"] == "FROZEN", "MAINTENANCE_PHASE")
            bundle = self.bundle(request["bundle"])
            desired = request["enrollment"]
            c.require(desired["grants"] == enrollment["grants"], "UPDATE_CANNOT_CHANGE_GRANTS")
            for key in enrollment["project"]:
                if key not in ("cli", "sdk_pins"):
                    c.require(desired["project"][key] == enrollment["project"][key], "UPDATE_CANNOT_MOVE_OR_MIGRATE")
            root = Path(bundle["root"])
            engine = next(i for i in bundle["artifacts"] if i["role"] == "ENGINE" and i["mode"] == "EXECUTE")
            c.require(desired["project"]["cli"] == r.file_pin(root / engine["name"]), "BUNDLE_ENGINE")
            sdks = [r.file_pin(root / item["name"]) for item in bundle["artifacts"] if item["role"] == "SDK"]
            c.require(desired["project"]["sdk_pins"] == sdks, "BUNDLE_SDK")
            r.check_project(desired["project"])
            self.quiet(enrollment)
            self.unresolved(enrollment["project"])
            facts["inventories"] = {w["work_id"]: inventory(Path(w["path"])) for w in enrollment["project"]["works"]}
        elif operation in ("switch", "restore", "repair-switch", "thaw"):
            acknowledge(enrollment, request["stopped"], "STOPPED_OWNER_ATTESTED")
            self.quiet(enrollment)
            if operation == "repair-switch":
                c.require(state["phase"] == "SWITCH_INTENT", "MAINTENANCE_PHASE")
                body = state["body"]
                record, _ = self.registry._load(request["project_id"])
                c.require(before == body["before"] or (record["enrollment"] == body["target_enrollment"] and
                    record["reviewed_plan_sha256"] == body["d1_plan_sha256"]), "SWITCH_DRIFT")
            else:
                self.unresolved(enrollment["project"])
                facts["inventories"] = {w["work_id"]: inventory(Path(w["path"])) for w in enrollment["project"]["works"]}
                if operation == "switch":
                    c.require(state["phase"] == "FROZEN", "MAINTENANCE_PHASE")
                    report = c.decode(pinned(request["verification"]))
                    c.require(Path(request["verification"]["path"]) == self.registry.root /
                              ("d5-verification-" + request["verification"]["sha256"] + ".json"), "VERIFICATION_NOT_ISSUED")
                    c.require(report["schema"] == "golem.integration-update-verification.v1" and
                        report["registry"] == str(self.registry.root) and report["registry_identity"] == self.registry.root_identity and
                        report["producer"] == producer() and report["lifecycle_sha256"] == lifecycle_sha and
                        report["before"] == before and report["inventories"] == facts["inventories"], "VERIFICATION_STALE")
                    c.require(report.get("native_state_changed") is False and
                              report["target_enrollment"]["grants"] == enrollment["grants"], "VERIFICATION_STALE")
                    for key in enrollment["project"]:
                        if key not in ("cli", "sdk_pins"):
                            c.require(report["target_enrollment"]["project"][key] == enrollment["project"][key], "VERIFICATION_STALE")
                    self.bundle(report["bundle"])
                    r.check_project(report["target_enrollment"]["project"])
                elif operation == "restore":
                    c.require(state["phase"] == "RELOAD_REQUIRED" and
                              facts["inventories"] == state["body"]["inventories"], "POST_SWITCH_NATIVE_CHANGE")
                    review = c.decode(pinned(request["effect_review"]))
                    c._validate(review, RESTORE_REVIEW)
                    c.require(review["project_id"] == request["project_id"] and review["freeze_id"] == state["freeze_id"] and
                              review["enrollment_sha256"] == c.sha(c.encoded(enrollment)), "RESTORE_REVIEW_STALE")
                    for pin in review["evidence"]:
                        pinned(pin, c.MAX_NATIVE)
                    self.observe(state["body"]["previous_enrollment"]["project"])
                else:
                    c.require(state["phase"] == "FROZEN", "MAINTENANCE_PHASE")
        else:
            c.require(state["phase"] == "RELOAD_REQUIRED", "MAINTENANCE_PHASE")
            self.quiet(enrollment)
            self.unresolved(enrollment["project"])
            acknowledge(enrollment, request["reloads"], "RELOADED_OWNER_ATTESTED")
            facts["inventories"] = {w["work_id"]: inventory(Path(w["path"])) for w in enrollment["project"]["works"]}
            c.require(facts["inventories"] == state["body"]["inventories"], "POST_SWITCH_NATIVE_CHANGE")
            for item in request["reloads"]:
                probe = c.decode(pinned(item["probe"]))
                probe_root = Path(item["probe"]["path"]).parent
                c.require(records.check(probe_root)["integrity"] == "PASS" and
                          r.regular(probe_root / "stdout.log", private=True) == c.encoded(probe), "RELOAD_PROBE_RECORDING")
                from integration_reload_probe import command, validate_runtime, worker_args
                from integration_transfer import Transfer
                validate_runtime(probe["runtime"])
                started = c.decode(r.regular(probe_root / "execution/started.json", private=True))
                expected = command(Path(__file__).resolve().with_name("integration_reload_probe.py"),
                    worker_args(probe["policy"], request["project_id"], probe["mode"], probe_root), probe["runtime"])
                c.require(started["argv"] == expected and started["cwd"] == str(probe_root) and
                          started["extra_logs"] == ["probe.log"], "RELOAD_PROBE_COMMAND")
                disclosure = Transfer(Path(probe["policy"]["path"]), probe["policy"]["sha256"], approve_data_transfer=True)
                c.require(disclosure.registry.root == self.registry.root and
                          disclosure.scope(request["project_id"], probe["work_ids"][0], "work_inspect")["binding"] == probe["binding"],
                          "RELOAD_PROBE_STALE")
                binding = probe["binding"]
                grant = next(g for g in enrollment["grants"] if g["principal_id"] == item["principal_id"] and g["client_id"] == item["client_id"])
                c.require(probe["schema"] == "golem.integration-reload-probe.v1" and probe["state"] == "READ_OBSERVED" and
                    binding["principal_id"] == item["principal_id"] and binding["client_id"] == item["client_id"] and
                    binding["project_id"] == request["project_id"] and probe["registry_identity"] == self.registry.root_identity and
                    probe["before"] == before and probe["lifecycle_sha256"] == lifecycle_sha and probe["producer"] == producer() and
                    set(probe["work_ids"]) == set(grant["work_ids"]), "RELOAD_PROBE_STALE")
                for work_id in probe["work_ids"]:
                    self.registry.authorize(binding, work_id, "record")
        return facts

    def plan(self, operation, request):
        with self.registry.locked():
            value = {"schema": "golem.integration-maintenance-plan.v1", "operation": operation,
                "request": request, "facts": self.facts(operation, request), "registry": str(self.registry.root),
                "registry_identity": self.registry.root_identity, "producer": producer()}
            c.require(len(c.encoded(value)) <= c.LIMIT, "JSON_SIZE")
            return value

    def apply(self, plan, reviewed_sha256, *, approve_maintenance=False):
        c.require(approve_maintenance is True, "OWNER_MAINTENANCE_APPROVAL_REQUIRED")
        c.require(c.sha(c.encoded(plan)) == reviewed_sha256, "PLAN_DIGEST")
        operation, request = plan["operation"], plan["request"]
        with self.registry.locked(exclusive=True):
            expected = {"schema": "golem.integration-maintenance-plan.v1", "operation": operation,
                "request": request, "facts": self.facts(operation, request), "registry": str(self.registry.root),
                "registry_identity": self.registry.root_identity, "producer": producer()}
            c.require(plan == expected, "MAINTENANCE_PLAN_STALE")
            backend._quota(self.registry.root)
            retained = self.registry.root / ("d5-plan-" + reviewed_sha256 + ".json")
            if retained.exists():
                c.require(r.regular(retained, private=True) == c.encoded(plan), "MAINTENANCE_PLAN_CORRUPT")
            else:
                self.registry._publish(retained, c.encoded(plan))
            enrollment, _ = self.enrollment(request["project_id"])
            state, _ = life.current(self.registry, request["project_id"])
            if operation == "freeze":
                return life.publish(self.registry, request["project_id"], "FROZEN", request["freeze_id"],
                                    {"previous_enrollment": enrollment, "before": plan["facts"]["before"]})
            if operation in ("stage", "stage-repair"):
                stage = request if operation == "stage" else c.decode(pinned(request["original_plan"]))["request"]
                destination = Path(stage["destination"])
                if not destination.exists():
                    destination.mkdir(mode=0o700)
                for item in stage["artifacts"]:
                    path = destination / item["name"]
                    if not path.exists():
                        records.save(path, r.regular(Path(item["source"]["path"]), 134217728))
                        path.chmod(0o500 if item["mode"] == "EXECUTE" else 0o400)
                        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                        try:
                            os.fsync(fd)
                        finally:
                            os.close(fd)
                manifest = {"schema": "golem.integration-staged-bundle.v1", "root": str(destination),
                    "identity": r.identity(destination), "artifacts": stage["artifacts"], "producer": producer()}
                path = destination / "bundle.json"
                if path.exists():
                    c.require(r.regular(path, private=True) == c.encoded(manifest), "STAGE_DRIFT")
                else:
                    records.save(path, c.encoded(manifest))
                    path.chmod(0o400)
                pin = r.file_pin(path)
                self.bundle(pin)
                return {"state": "STAGED", "bundle": pin, "native_state_changed": False}
            if operation == "verify":
                old = self.observe(enrollment["project"])
                new = self.observe(request["enrollment"]["project"])
                c.require(old == new, "NATIVE_COMPATIBILITY_DIFFERENCE")
                report = {"schema": "golem.integration-update-verification.v1", **plan["facts"],
                    "bundle": request["bundle"], "target_enrollment": request["enrollment"],
                    "registry": str(self.registry.root), "registry_identity": self.registry.root_identity,
                    "native_views": new, "producer": producer(), "native_state_changed": False}
                path = self.registry.root / ("d5-verification-" + c.sha(c.encoded(report)) + ".json")
                if not path.exists():
                    self.registry._publish(path, c.encoded(report))
                return {"state": "VERIFIED_READ_ONLY", "verification": r.file_pin(path)}
            if operation in ("thaw", "ready"):
                self.observe(enrollment["project"])
                return life.publish(self.registry, request["project_id"], "OPEN", state["freeze_id"],
                    {**state["body"], "reload_assurance": "SDK_READ_OBSERVED_OWNER_RELOAD_REPORTED" if operation == "ready" else "NO_SWITCH_OWNER_REVIEWED"})
            if operation == "repair-switch":
                body = state["body"]
                actual, before = self.registry._load(request["project_id"])
                phase = "FROZEN" if before == body["before"] else "RELOAD_REQUIRED"
                return life.publish(self.registry, request["project_id"], phase, state["freeze_id"], body)
            target = (c.decode(pinned(request["verification"]))["target_enrollment"] if operation == "switch" else
                      state["body"]["previous_enrollment"])
            d1 = self.registry._plan(target, "approve")
            body = {"previous_enrollment": enrollment, "target_enrollment": target,
                "before": plan["facts"]["before"], "d1_plan_sha256": c.sha(c.encoded(d1)),
                "inventories": plan["facts"]["inventories"]}
            life.publish(self.registry, request["project_id"], "SWITCH_INTENT", state["freeze_id"], body)
        # D1 owns its transaction. A crash here remains fenced SWITCH_INTENT;
        # explicit repair observes before/after, never guesses or repeats writes.
        self.registry.apply(target, body["d1_plan_sha256"], approve_local_owner=True)
        with self.registry.locked(exclusive=True):
            actual, _ = self.registry._load(request["project_id"])
            c.require(actual["enrollment"] == target and actual["reviewed_plan_sha256"] == body["d1_plan_sha256"], "SWITCH_DRIFT")
            return life.publish(self.registry, request["project_id"], "RELOAD_REQUIRED", state["freeze_id"], body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("schema", "plan", "apply", "inspect"))
    parser.add_argument("--operation", choices=tuple(SPEC))
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--project-id")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--reviewed-plan-sha256")
    parser.add_argument("--approve-maintenance", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "schema":
            c.require(args.operation in SPEC, "OPERATION_REQUIRED")
            result = {"$schema": "https://json-schema.org/draft/2020-12/schema", **SPEC[args.operation]}
        else:
            c.require(args.registry is not None, "REGISTRY_REQUIRED")
            manager = Manager(r.Registry(args.registry))
            if args.command == "inspect":
                with manager.registry.locked():
                    result = {"lifecycle": life.current(manager.registry, args.project_id)[0], "native_state_changed": False}
            else:
                c.require(args.input is not None, "INPUT_REQUIRED")
                value = c.decode(r.regular(args.input, private=True))
                result = manager.plan(args.operation, value) if args.command == "plan" else manager.apply(
                    value, args.reviewed_plan_sha256, approve_maintenance=args.approve_maintenance)
        sys.stdout.buffer.write(c.encoded(result))
        return 0
    except (c.IntegrationError, OSError, ValueError, KeyError, TypeError) as error:
        sys.stderr.write(c.encoded({"state": "BLOCKED", "code": getattr(error, "code", "IO_OR_CONTRACT_ERROR"),
            "automatic_retry_allowed": False, "next_operation": "INSPECT_PRESERVED_STAGE_OR_LIFECYCLE_NO_AUTOMATIC_ROLLBACK"}).decode())
        return 1


if __name__ == "__main__":
    sys.exit(main())
