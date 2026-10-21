"""D1 fixed, read-only native backend. No mutation requests or provider calls."""
from pathlib import Path
import stat
import tempfile

import execution_record as records
import integration_contract as contract
from integration_contract import IntegrationError, decode, encoded, require, sha, validate
from integration_registry import check_project, regular

ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin"}
TIMEOUT_SECONDS = 15


def _quota(root):
    entries, size, reads = 0, 0, 0
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            info = path.lstat()
            entries += 1
            require(entries <= 16384 and not stat.S_ISLNK(info.st_mode), "AUDIT_QUOTA")
            if path.parent == root and path.name.startswith("read-"):
                reads += 1
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            else:
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "AUDIT_QUOTA")
                size += info.st_size
            require(reads < 256 and size <= 134217728, "AUDIT_QUOTA")


def _native(project, work, operation, request, destination):
    destination.mkdir(mode=0o700)
    request_path = destination / "request.json"
    records.save(request_path, encoded(request))
    if operation in ("status", "next"):
        command = ["session", "call"]
    else:
        command = ["work", operation]
    argv = [project["cli"]["path"], "--output-mode", "full", *command, work["path"], str(request_path)]
    observation = records.capture(argv, destination, TIMEOUT_SECONDS, cwd=destination, observe_source=False,
                                  env=ENVIRONMENT, limit=contract.MAX_NATIVE)
    # Preserve failed native stdout/stderr before any interpretation. Never retry.
    require(observation["returncode"] == 0 and observation["reason"] == "EXIT" and
            observation["recording"] == "RECORDED", "NATIVE_FAILURE")
    data = regular(destination / "stdout.log", contract.MAX_NATIVE, private=True)
    value = decode(data, contract.MAX_NATIVE)
    require(isinstance(value, dict), "NATIVE_CONTRACT")
    require(value.get("execution_authorized") in (None, False) and value.get("committed") is not True,
            "NATIVE_CONTRACT")
    return value, {"path": str(destination), "stdout_sha256": sha(data), "returncode": 0}


def read(registry, request):
    validate("read", request)
    with registry.locked():
        project = registry.authorize(request["binding"], request["work_id"], request["operation"])
        work = next(w for w in project["works"] if w["work_id"] == request["work_id"])
        # A bounded private spool retains both successful observations and failures.
        _quota(registry.root)
        output = Path(tempfile.mkdtemp(prefix="read-", dir=registry.root))
        base = {"schema": "golem.integration-observation.v1", "state": "STARTED",
                "binding": request["binding"], "work_id": work["work_id"],
                "operation": request["operation"], "request_sha256": sha(encoded(request)),
                "native_state_changed": False, "integration_record_written": True,
                "execution_authorized": False, "product_acceptance": False,
                "assurance": "LOCAL_COOPERATIVE", "evidence_path": str(output)}
        records.save(output / "request.json", encoded(request))
        records.save(output / "started.json", encoded(base))
        try:
            # Verify the Work through its existing replay before any selected view.
            native_request = {"schema_version": 1, "work_id": work["work_id"],
                              "byte_budget": contract.MAX_NATIVE, "document_head": "", "agent_head": ""}
            record, record_ref = _native(project, work, "record", native_request, output / "record")
            require(record.get("schema") == "golem.work-record.v1" and
                    record.get("work_id") == work["work_id"] and
                    isinstance(record.get("work_specification"), dict) and
                    record["work_specification"].get("work_id") == work["work_id"] and
                    record.get("execution_authorized") is False, "WORK_IDENTITY")
            if request["operation"] == "record":
                result, result_ref = record, record_ref
            else:
                if request["operation"] == "history":
                    native_request = {"schema_version": 2, "work_id": work["work_id"],
                                      "limit": request["limit"], "cursor": request["cursor"]}
                else:
                    native_request = {"schema_version": 1, "work_id": work["work_id"],
                                      "operation": request["operation"]}
                result, result_ref = _native(project, work, request["operation"], native_request,
                                            output / request["operation"])
            check_project(project)
            observed = {**base, "state": "OBSERVED", "result": result, "native_observation": result_ref,
                        "identity_observation": record_ref, "observations_atomic": False}
            data = encoded(observed)
            require(len(data) <= contract.MAX_NATIVE, "NATIVE_OUTPUT_LIMIT")
            records.save(output / "result.json", data)
            return observed
        except (IntegrationError, OSError, ValueError) as error:
            code = error.code if isinstance(error, IntegrationError) else "IO_OR_CONTRACT_ERROR"
            records.save(output / "failure.json", encoded({**base, "state": "BLOCKED", "code": code,
                                                          "automatic_retry_allowed": False}))
            error.evidence_path = str(output)
            raise
