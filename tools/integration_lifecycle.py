"""D5 shared admission, kernel-held participation and immutable clearance reads."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import uuid

import execution_record as records
import integration_contract as c
import integration_registry as r
import integration_task_actions as tasks
import integration_quality_actions as quality
import integration_parallel_actions as parallel

PHASES = ("OPEN", "FROZEN", "SWITCH_INTENT", "RELOAD_REQUIRED")
STATE = c.obj({"schema": {"const": "golem.integration-lifecycle.v1"}, "project_id": c.ID,
    "phase": c.enum(*PHASES), "freeze_id": c.ID, "previous_sha256": {"type": "string", "maxLength": 64},
    "body": {"type": ["object", "null"]}})
RESOLUTION = c.obj({"schema": {"const": "golem.integration-resolution.v1"}, "intent_sha256": c.DIGEST,
    "retired": c.DIGEST, "freeze_id": c.ID, "lineage": c.DIGEST, "work_id": c.ID,
    "owner_review": c.PIN, "audit_sha256": c.DIGEST, "native_views_sha256": c.DIGEST,
    "approval_observation_sha256": c.DIGEST, "plan_sha256": c.DIGEST,
    "native_result_promoted": {"const": False}, "execution_authorized": {"const": False}})


def pointer(registry, project_id):
    c._validate(project_id, c.ID)
    return registry.root / (".d5-" + project_id + ".current")


def current(registry, project_id, *, max_history=256):
    path = pointer(registry, project_id)
    if not path.exists() and not path.is_symlink():
        return None, None
    ref = c.decode(r.regular(path, private=True))
    c._validate(ref, c.obj({"sha256": c.DIGEST}))
    data = r.regular(registry.root / ("d5-state-" + ref["sha256"] + ".json"), private=True)
    c.require(c.sha(data) == ref["sha256"], "LIFECYCLE_CORRUPT")
    value = c.decode(data)
    c._validate(value, STATE)
    c.require(value["project_id"] == project_id and isinstance(value["body"], dict), "LIFECYCLE_CORRUPT")
    if value["previous_sha256"]:
        c._validate(value["previous_sha256"], c.DIGEST)
    child, seen = value, {ref["sha256"]}
    allowed = {"OPEN": ("FROZEN",), "FROZEN": ("OPEN", "FROZEN", "SWITCH_INTENT"),
               "SWITCH_INTENT": ("FROZEN", "RELOAD_REQUIRED"), "RELOAD_REQUIRED": ("OPEN", "SWITCH_INTENT")}
    while child["previous_sha256"]:
        digest = child["previous_sha256"]
        c._validate(digest, c.DIGEST)
        c.require(digest not in seen and len(seen) < max_history, "LIFECYCLE_HISTORY_LIMIT_OR_CYCLE")
        seen.add(digest)
        data = r.regular(registry.root / ("d5-state-" + digest + ".json"), private=True)
        c.require(c.sha(data) == digest, "LIFECYCLE_CORRUPT")
        parent = c.decode(data)
        c._validate(parent, STATE)
        c.require(isinstance(parent["body"], dict) and parent["project_id"] == project_id and child["phase"] in allowed[parent["phase"]] and
                  (parent["phase"] == "OPEN" or parent["freeze_id"] == child["freeze_id"]), "LIFECYCLE_CORRUPT")
        child = parent
    c.require(child["phase"] == "FROZEN", "LIFECYCLE_CORRUPT")
    return value, ref["sha256"]


def publish(registry, project_id, phase, freeze_id, body):
    from integration_backend import _quota
    _quota(registry.root)
    _, previous = current(registry, project_id, max_history=255)
    value = {"schema": "golem.integration-lifecycle.v1", "project_id": project_id, "phase": phase,
             "freeze_id": freeze_id, "previous_sha256": previous or "", "body": body}
    c._validate(value, STATE)
    data = c.encoded(value)
    c.require(len(data) <= c.LIMIT, "JSON_SIZE")
    path = registry.root / ("d5-state-" + c.sha(data) + ".json")
    if path.exists():
        c.require(r.regular(path, private=True) == data, "LIFECYCLE_CORRUPT")
    else:
        registry._publish(path, data)
    registry._publish(pointer(registry, project_id), c.encoded({"sha256": c.sha(data)}), replace=True)
    return value


def fence(registry, project_id):
    value, _ = current(registry, project_id)
    c.require(value is None or value["phase"] == "OPEN", "PROJECT_MAINTENANCE")


def lock(path, *, create=False):
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        info = os.fstat(fd)
        c.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                  info.st_nlink == 1 and info.st_mode & 0o077 == 0, "UNSAFE_PARTICIPATION")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise c.IntegrationError("PARTICIPANT_OR_WRITER_LIVE") from None
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def participation(registry, bindings):
    """Only our own descriptor is released; no PID probing or process killing."""
    path = None
    fd = None
    with registry.locked(exclusive=True):
        from integration_backend import _quota
        _quota(registry.root)
        c.require(len(list(registry.root.glob("d5-client-*"))) < 128, "PARTICIPATION_QUOTA")
        for binding in bindings:
            c.validate("binding", binding)
            fence(registry, binding["project_id"])
        path = registry.root / ("d5-client-" + uuid.uuid4().hex)
        path.mkdir(mode=0o700)
        fd = lock(path / "live.lock", create=True)
        try:
            records.save(path / "participant.json", c.encoded({"bindings": bindings}))
        except BaseException:
            os.close(fd)
            raise
    try:
        yield path.name
    finally:
        os.close(fd)


def quiet(registry, project_id):
    clients = list(registry.root.glob("d5-client-*"))
    writers = list(registry.root.glob("mutation-*"))
    c.require(len(clients) <= 128 and len(writers) <= 128, "PARTICIPATION_QUOTA")
    for path in clients:
        value = c.decode(r.regular(path / "participant.json", private=True))
        c._validate(value, c.obj({"bindings": c.array(c.BINDING)}))
        if any(b["project_id"] == project_id for b in value["bindings"]):
            os.close(lock(path / "live.lock"))
    for path in writers:
        intent = c.decode(r.regular(path / "intent.json", private=True))
        if intent["binding"]["project_id"] == project_id and (path / "writer.lock").exists():
            os.close(lock(path / "writer.lock"))


def retired_identity(tool, request):
    if tool in (*tasks.NAMES,*quality.NAMES,*parallel.NAMES):
        return c.sha(c.encoded({"tool": tool, "native_request": request}))
    fields = ("operation", "key") if tool.startswith("session_") else (
        ("document_id", "revision") if tool == "document_submit" else ("operation", "attempt_id", "checkpoint", "contract"))
    return c.sha(c.encoded({"tool": tool, **{key: request[key] for key in fields if key in request}}))


def clearance(path, intent):
    target = path / "d5-resolution.json"
    if not target.exists() and not target.is_symlink():
        return None
    data = r.regular(target, private=True)
    ref = c.decode(r.regular(path / "d5-resolution-ref.json", private=True))
    c.require(ref == {"sha256": c.sha(data)}, "RESOLUTION_CORRUPT")
    value = c.decode(data)
    c._validate(value, RESOLUTION)
    c.require(value["intent_sha256"] == c.sha(c.encoded(intent)) and value["lineage"] == intent["lineage"] and
              value["work_id"] == intent["work_id"], "RESOLUTION_CORRUPT")
    plan_bytes = r.regular(path.parent / ("d5-recovery-plan-" + value["plan_sha256"] + ".json"), private=True)
    c.require(c.sha(plan_bytes) == value["plan_sha256"], "RESOLUTION_CORRUPT")
    plan = c.decode(plan_bytes)
    from integration_recovery import audit_inventory
    c.require(plan["schema"] == "golem.integration-recovery-plan.v1" and
              plan["request"]["evidence_id"] == path.name and plan["request"]["work_id"] == intent["work_id"] and
              plan["request"]["owner_review"] == value["owner_review"] and
              plan["facts"]["intent_sha256"] == value["intent_sha256"] and
              plan["facts"]["retired"] == value["retired"] and
              plan["facts"]["audit_sha256"] == value["audit_sha256"] == audit_inventory(path), "RESOLUTION_CORRUPT")
    return value
