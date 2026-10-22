"""Explicit same-authority reapproval and approved D01 recovery.

No Work APIs, native retries, rollback, authority moves or reactivation.
All entry points require the same cooperative common-dir lock as enrollment.
"""
import os
from pathlib import Path
import stat
import subprocess
import struct

import intent_authority as host
from integration_contract import require, encoded, decode, sha

CANDIDATE = "golem-intent-authority.candidate.json"


def _locator(record):
    return {"schema": "golem.intent-authority-locator.v1", "record": record,
            "registration_sha256": sha(encoded(record))}


def _validate_locator(value, repository):
    host.validate_locator(value)
    require(value == _locator(value["record"]), "LOCATOR_DIGEST_MISMATCH")
    registered = value["record"]["repository"]
    for key in ("common_dir", "common_identity"):
        require(registered[key] == repository[key], "COMMON_DIR_CHANGED")


def _same_identity(old, new):
    for key in ("root", "root_identity", "common_dir", "common_identity"):
        require(old["repository"][key] == new["repository"][key], "REGISTRATION_MOVE_DENIED")
    for key in ("path", "identity"):
        require(old["authority"][key] == new["authority"][key], "REGISTRATION_MOVE_DENIED")


def _native(repository, value, bridge, *, previous=None, verify=False, check=False):
    record = value["record"]
    require(host.file_pin(bridge) in record["authority"]["pins"], "NATIVE_BRIDGE_PIN_REQUIRED")
    host.verify_observation(record["repository"], record["authority"])
    fd = os.open(record["authority"]["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require({"device": info.st_dev, "inode": info.st_ino} == record["authority"]["identity"], "AUTHORITY_CHANGED")
        mode = "--inspect-fd" if previous is None else ("--verify-change-fd" if verify else "--change-fd")
        if check:
            mode = "--check-change-fd"
        args = [str(bridge), mode, str(fd)]
        args += [value["registration_sha256"]] if previous is None else [previous, value["registration_sha256"]]
        result = subprocess.run(args, input=encoded(record), pass_fds=(fd,), capture_output=True,
                                timeout=15, check=False, env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"})
        require(result.returncode == 0, "NATIVE_BINDING_UNCONFIRMED")
        require(len(result.stdout) <= host.contract.LIMIT, "NATIVE_OUTPUT_LIMIT")
        observed = decode(result.stdout)
        require(observed.get("schema") == "golem.intent-journal-inspection.v1" and
                observed.get("execution_authorized") is False and observed.get("pending") is False and
                observed.get("registration_sha256") == (previous if check else value["registration_sha256"]), "NATIVE_CONTRACT")
    finally:
        os.close(fd)
    host.verify_observation(record["repository"], record["authority"])
    require(host.repository_identity(Path(repository["root"]), git=Path(repository["git"]["path"])) == repository,
            "REPOSITORY_IDENTITY_CHANGED")
    return observed


def _change(repository, pins, expected):
    old = host._load(repository)
    require(old is not None, "AUTHORITY_REGISTRATION_REQUIRED")
    require(old["registration_sha256"] == expected, "REGISTRATION_PIN_MISMATCH")
    record = {"schema": "golem.intent-authority-registration.v1", "repository": repository,
              "authority": host.authority_identity(Path(old["record"]["authority"]["path"]), repository, pins),
              "producer": host._producer()}
    host.contract._validate(record, host.REGISTRATION)
    _same_identity(old["record"], record)
    new = _locator(record)
    require(new != old, "REGISTRATION_UNCHANGED")
    # Native transition payload includes the predecessor's 32-byte digest.
    require(len(encoded(record)) + 32 <= host.contract.LIMIT, "REGISTRATION_LIMIT")
    plan = {"schema": "golem.intent-authority-change-plan.v1", "before": old, "after": new}
    require(len(encoded(plan)) <= host.contract.LIMIT, "REGISTRATION_LIMIT")
    return plan


def change_plan(root, expected_registration_sha256, pins, *, git):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository):
        plan = _change(repository, pins, expected_registration_sha256)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def _archive(fd, common, name, data):
    path = common / name
    if os.path.lexists(path):
        require(_read_recovery(path, common) == data, "HISTORY_CONFLICT")
    else:
        host._publish(fd, name, data)


def _finish(fd, common, old, new, intent=None):
    if old is not None:
        _archive(fd, common, host.HISTORY + old["registration_sha256"] + ".json", encoded(old))
    if (common / host.LOCATOR).exists() and host.regular(common / host.LOCATOR, private=True) == encoded(new):
        pass
    elif old is None:
        host._publish(fd, host.LOCATOR, encoded(new))
    else:
        require(host.regular(common / host.LOCATOR, private=True) == encoded(old), "LOCATOR_CHANGED")
        _archive(fd, common, CANDIDATE, encoded(new))
        os.replace(CANDIDATE, host.LOCATOR, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    if intent is not None:
        _archive(fd, common, host.HISTORY + "change-" + sha(encoded(intent)) + ".json", encoded(intent))
        if os.path.lexists(common / host.CHANGE):
            os.unlink(host.CHANGE, dir_fd=fd)
        os.fsync(fd)


def change(root, expected_registration_sha256, pins, reviewed_plan_sha256, *, git, bridge,
           approve_local_owner=False):
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, exclusive=True) as fd:
        plan = _change(repository, pins, expected_registration_sha256)
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        require(host.file_pin(bridge) in plan["after"]["record"]["authority"]["pins"], "NATIVE_BRIDGE_PIN_REQUIRED")
        intent = {"schema": "golem.intent-authority-change.v1", "plan": plan,
                  "plan_sha256": reviewed_plan_sha256}
        _native(repository, plan["after"], bridge, previous=expected_registration_sha256, check=True)
        host._publish(fd, host.CHANGE, encoded(intent))
        _native(repository, plan["after"], bridge, previous=expected_registration_sha256)
        _finish(fd, Path(repository["common_dir"]), plan["before"], plan["after"], intent)
        return plan["after"]


def _read_recovery(path, common):
    """A published file and its pending hardlink are a supported crash boundary.
    Reject external hardlinks, symlinks and unrelated aliases rather than relaxing
    the normal registry regular-file check."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                info.st_mode & 0o077 == 0 and info.st_size <= host.contract.LIMIT, "RECOVERY_FILE_INVALID")
        if info.st_nlink != 1:
            aliases = [p for p in common.iterdir() if p.lstat().st_ino == info.st_ino and
                       p.lstat().st_dev == info.st_dev]
            require(info.st_nlink == 2 and len(aliases) == 2 and
                    any(p.name.startswith(host.PENDING) for p in aliases) and
                    all(p.name.startswith((host.PENDING, host.HISTORY)) or
                        p.name in (host.LOCATOR, host.CHANGE, CANDIDATE) for p in aliases), "RECOVERY_HARDLINK")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(host.contract.LIMIT + 1)
        after = os.fstat(fd)
        require(len(data) <= host.contract.LIMIT and
                (after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns, after.st_nlink) ==
                (info.st_ino, info.st_dev, info.st_size, info.st_mtime_ns, info.st_nlink), "RECOVERY_FILE_CHANGED")
        return data
    finally:
        os.close(fd)


def _recovery(repository, expected, bridge):
    common = Path(repository["common_dir"])
    require(not os.path.lexists(common / host.DAMAGE_RECOVERY), "DAMAGE_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.FRAGMENT_RECOVERY), "FRAGMENT_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.HOST_PUBLICATION), "HOST_PUBLICATION_REQUIRED")
    require(not os.path.lexists(common / host.HOST_ALIAS_RECOVERY), "HOST_ALIAS_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.TOMBSTONE), "AUTHORITY_REVOKED")
    require(not os.path.lexists(common / host.NATIVE_RECOVERY), "NATIVE_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.ALIAS_RECOVERY), "ALIAS_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.PARTIAL_RECOVERY), "PARTIAL_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.ENVELOPE_RECOVERY), "ENVELOPE_RECOVERY_REQUIRED")
    files = {p.name: _read_recovery(p, common) for p in common.iterdir()
             if p.name.startswith(host.PENDING) or p.name in (host.CHANGE, CANDIDATE, host.LOCATOR)}
    pending = {name: data for name, data in files.items() if name.startswith(host.PENDING)}
    intent = decode(files[host.CHANGE]) if host.CHANGE in files else None
    old = None
    if intent is not None:
        require(set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-authority-change.v1", "RECOVERY_INTENT_INVALID")
        plan = intent["plan"]
        require(isinstance(plan, dict) and set(plan) == {"schema", "before", "after"} and
                plan["schema"] == "golem.intent-authority-change-plan.v1" and
                sha(encoded(plan)) == intent["plan_sha256"], "RECOVERY_INTENT_INVALID")
        old, new = plan["before"], plan["after"]
        _validate_locator(old, repository)
        _validate_locator(new, repository)
        _same_identity(old["record"], new["record"])
        require(old != new, "RECOVERY_INTENT_INVALID")
        allowed = [encoded(old), encoded(new), encoded(intent)]
    else:
        require(CANDIDATE not in files, "RECOVERY_AMBIGUOUS")
        candidates = [decode(data) for data in pending.values()]
        if host.LOCATOR in files:
            candidates.append(decode(files[host.LOCATOR]))
        require(bool(pending) and bool(candidates), "RECOVERY_NOT_REQUIRED")
        new = candidates[0]
        _validate_locator(new, repository)
        require(all(value == new for value in candidates), "RECOVERY_AMBIGUOUS")
        allowed = [encoded(new)]
    require(new["registration_sha256"] == expected, "REGISTRATION_PIN_MISMATCH")
    require(new["record"]["producer"] == host._producer(), "PRODUCER_CHANGED")
    require(new["record"]["repository"]["git"] == repository["git"], "GIT_PIN_MISMATCH")
    require(all(data in allowed for data in files.values()), "RECOVERY_AMBIGUOUS")
    observed = _native(repository, new, bridge,
                       previous=old["registration_sha256"] if old is not None else None, verify=True)
    snapshot = {name: sha(data) for name, data in sorted(files.items())}
    plan = {"schema": "golem.intent-authority-recovery-plan.v1", "files": snapshot,
            "registration_sha256": expected, "native_head": observed["head"],
            "native_sequence": observed["committed"], "repository": repository}
    return plan, files, old, new, intent


def recovery_plan(root, expected_registration_sha256, *, git, bridge):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository):
        plan, *_ = _recovery(repository, expected_registration_sha256, bridge)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def recover(root, expected_registration_sha256, reviewed_plan_sha256, *, git, bridge,
            approve_local_owner=False):
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, exclusive=True) as fd:
        plan, files, old, new, intent = _recovery(repository, expected_registration_sha256, bridge)
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        common = Path(repository["common_dir"])
        # Retain exact pending bytes before removing their active quarantine names.
        # At least CHANGE or one pending remains until locator publication finishes.
        anchor = None
        for name, data in files.items():
            if name.startswith(host.PENDING):
                _archive(fd, common, host.HISTORY + "pending-" + sha(data) + ".json", data)
                if intent is None and anchor is None:
                    anchor = name
                else:
                    os.unlink(name, dir_fd=fd)
        os.fsync(fd)
        if anchor is not None:
            # Exact bytes are already archived and the native-confirmed locator
            # is published. Only its pending alias remains to be detached.
            if (common / anchor).stat().st_nlink == 2:
                os.unlink(anchor, dir_fd=fd)
                try:
                    _finish(fd, common, old, new, intent)
                finally:
                    os.fsync(fd)
                return new
        _finish(fd, common, old, new, intent)
        if anchor is not None:
            os.unlink(anchor, dir_fd=fd)
            os.fsync(fd)
        return new


def _pending_native(repository, value, previous, bridge, snapshot=None):
    record = value["record"]
    host.verify_observation(record["repository"], record["authority"])
    require(host.file_pin(bridge) in record["authority"]["pins"], "NATIVE_BRIDGE_PIN_REQUIRED")
    fd = os.open(record["authority"]["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require({"device": info.st_dev, "inode": info.st_ino} == record["authority"]["identity"], "AUTHORITY_CHANGED")
        args = [str(bridge), "--plan-pending-fd" if snapshot is None else "--recover-pending-fd",
                str(fd), value["registration_sha256"], previous or "-"]
        if snapshot is not None:
            args.append(snapshot)
        result = subprocess.run(args, input=encoded(record), pass_fds=(fd,), capture_output=True,
                                timeout=15, check=False, env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"})
        require(result.returncode == 0, "NATIVE_PENDING_NOT_RECOVERABLE")
        require(len(result.stdout) <= host.contract.LIMIT, "NATIVE_OUTPUT_LIMIT")
        observed = decode(result.stdout)
        rule = host.contract.obj({"schema": host.contract.enum("golem.intent-native-recovery.v1"),
            "execution_authorized": {"const": False}, "sequence": host.contract.INTEGER,
            "payload_bytes": host.contract.INTEGER,
            **{key: host.contract.DIGEST for key in ("operation", "request", "head", "preparation", "payload", "snapshot")}})
        host.contract._validate(observed, rule)
        require(observed["request"] == value["registration_sha256"] and observed["sequence"] > 0, "NATIVE_CONTRACT")
    finally:
        os.close(fd)
    host.verify_observation(record["repository"], record["authority"])
    return observed


def _confirm_finished(repository, value, previous, bridge, native):
    observed = _native(repository, value, bridge, previous=previous, verify=True)
    frame = b"GIQEV001" + struct.pack("<Q", native["sequence"]) + bytes.fromhex(native["head"]) + bytes.fromhex(native["preparation"])
    require(observed["committed"] == native["sequence"] and observed["head"] == sha(frame), "NATIVE_RECOVERY_HEAD_CHANGED")


def _native_recovery(repository, record, bridge):
    common = Path(repository["common_dir"])
    require(not os.path.lexists(common / host.DAMAGE_RECOVERY), "DAMAGE_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.FRAGMENT_RECOVERY), "FRAGMENT_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.HOST_PUBLICATION), "HOST_PUBLICATION_REQUIRED")
    require(not os.path.lexists(common / host.HOST_ALIAS_RECOVERY), "HOST_ALIAS_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.TOMBSTONE), "AUTHORITY_REVOKED")
    require(not os.path.lexists(common / host.ALIAS_RECOVERY), "ALIAS_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.PARTIAL_RECOVERY), "PARTIAL_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.ENVELOPE_RECOVERY), "ENVELOPE_RECOVERY_REQUIRED")
    require(not any(p.name.startswith(host.PENDING) for p in common.iterdir()), "NATIVE_RECOVERY_HOST_PENDING")
    host.contract._validate(record, host.REGISTRATION)
    require(record["repository"] == repository and record["producer"] == host._producer(), "RECOVERY_BINDING_CHANGED")
    host.verify_observation(repository, record["authority"])
    value = _locator(record)
    locator = host._read_locator(repository)
    intent_path = common / host.NATIVE_RECOVERY
    intent = decode(host.regular(intent_path, private=True)) if intent_path.exists() else None
    if intent is not None:
        require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-native-recovery-intent.v1" and
                isinstance(intent["plan"], dict) and sha(encoded(intent["plan"])) == intent["plan_sha256"], "RECOVERY_INTENT_INVALID")
    change = decode(host.regular(common / host.CHANGE, private=True)) if (common / host.CHANGE).exists() else None
    if change is None and intent is not None:
        change = intent["plan"].get("change")
    previous, old = None, None
    if change is not None:
        require(isinstance(change, dict) and set(change) == {"schema", "plan", "plan_sha256"} and
                change["schema"] == "golem.intent-authority-change.v1", "RECOVERY_INTENT_INVALID")
        plan = change["plan"]
        require(isinstance(plan, dict) and set(plan) == {"schema", "before", "after"} and
                plan["schema"] == "golem.intent-authority-change-plan.v1" and
                sha(encoded(plan)) == change["plan_sha256"] and plan["after"] == value, "RECOVERY_INTENT_INVALID")
        old = plan["before"]
        _validate_locator(old, repository)
        _same_identity(old["record"], record)
        previous = old["registration_sha256"]
    require(locator == old or locator == value, "LOCATOR_CHANGED")
    native, phase = None, "PREPARED"
    if intent is not None:
        require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-native-recovery-intent.v1" and
                sha(encoded(intent["plan"])) == intent["plan_sha256"], "RECOVERY_INTENT_INVALID")
        original = intent["plan"]
        require(original["target"] == value and original["previous"] == previous and
                original["phase"] == "PREPARED", "RECOVERY_INTENT_INVALID")
        native = original["native"]
        try:
            _confirm_finished(repository, value, previous, bridge, native)
            phase = "COMMITTED"
        except host.IntegrationError as error:
            if error.code != "NATIVE_BINDING_UNCONFIRMED":
                raise
    if phase == "PREPARED":
        current = _pending_native(repository, value, previous, bridge)
        require(native is None or current == native, "NATIVE_RECOVERY_SNAPSHOT_CHANGED")
        native = current
        require(locator == old, "LOCATOR_CHANGED")
    files = {name: sha(host.regular(common / name, private=True)) for name in
             (host.LOCATOR, host.CHANGE, host.NATIVE_RECOVERY, CANDIDATE) if os.path.lexists(common / name)}
    plan = {"schema": "golem.intent-native-recovery-plan.v1", "target": value,
            "previous": previous, "native": native, "phase": phase, "files": files, "change": change}
    require(len(encoded(plan)) <= host.contract.LIMIT, "REGISTRATION_LIMIT")
    return plan, intent, old, value, change


def native_recovery_plan(root, target_record, *, git, bridge):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository):
        plan, *_ = _native_recovery(repository, target_record, bridge)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def recover_native(root, target_record, reviewed_plan_sha256, *, git, bridge, approve_local_owner=False):
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, exclusive=True) as fd:
        plan, intent, old, value, change = _native_recovery(repository, target_record, bridge)
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        common = Path(repository["common_dir"])
        if intent is None:
            intent = {"schema": "golem.intent-native-recovery-intent.v1", "plan": plan,
                      "plan_sha256": reviewed_plan_sha256}
            host._publish(fd, host.NATIVE_RECOVERY, encoded(intent))
        else:
            # Each explicit retry/finalization approval remains an immutable fact.
            _archive(fd, common, host.HISTORY + "native-approval-" + reviewed_plan_sha256 + ".json", encoded(plan))
        if plan["phase"] == "PREPARED":
            result = _pending_native(repository, value, plan["previous"], bridge, plan["native"]["snapshot"])
            require(result == plan["native"], "NATIVE_CONTRACT")
        _confirm_finished(repository, value, plan["previous"], bridge, plan["native"])
        _finish(fd, common, old, value, change)
        _archive(fd, common, host.HISTORY + "native-recovery-" + sha(encoded(intent)) + ".json", encoded(intent))
        os.unlink(host.NATIVE_RECOVERY, dir_fd=fd)
        os.fsync(fd)
        return value


def _alias_native(value, previous, kind, bridge, snapshot=None, *, partial=False, replace=False, approval=None,
                  envelope=False, fragment=False, fragment_action="preserve", preservation=None, damage=False):
    record = value["record"]
    host.verify_observation(record["repository"], record["authority"])
    require(host.file_pin(bridge) in record["authority"]["pins"], "NATIVE_BRIDGE_PIN_REQUIRED")
    fd = os.open(record["authority"]["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require({"device": info.st_dev, "inode": info.st_ino} == record["authority"]["identity"], "AUTHORITY_CHANGED")
        mode = "--plan-alias-fd" if snapshot is None else "--remove-alias-fd"
        if partial:
            mode = "--plan-partial-fd" if snapshot is None else ("--replace-payload-fd" if replace else "--quarantine-partial-fd")
        if envelope:
            mode = "--plan-envelope-fd" if snapshot is None else "--finish-envelope-fd"
        if fragment:
            require(fragment_action in ("preserve", "finish", "detach"), "FRAGMENT_ACTION")
            family = "damage" if damage else "fragment"
            mode = "--plan-" + family + "-fd" if snapshot is None else "--" + fragment_action + "-" + family + "-fd"
        args = [str(bridge), mode, str(fd),
                value["registration_sha256"], previous or "-", str(kind)]
        if snapshot is not None:
            args.append(snapshot)
            if partial and not replace:
                require(approval is not None, "RECOVERY_APPROVAL_REQUIRED")
                args.append(approval)
            if fragment:
                require(preservation is not None, "RECOVERY_APPROVAL_REQUIRED")
                args.append(preservation)
        result = subprocess.run(args, input=encoded(record), pass_fds=(fd,), capture_output=True,
                                timeout=15, check=False, env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"})
        require(result.returncode == 0, "NATIVE_PARTIAL_NOT_RECOVERABLE" if partial else "NATIVE_ALIAS_NOT_RECOVERABLE")
        require(len(result.stdout) <= host.contract.LIMIT, "NATIVE_OUTPUT_LIMIT")
        value = decode(result.stdout)
        numbers = ("kind", "sequence", "device", "inode", "bytes", "committed")
        digests = ("operation", "request", "preparation", "payload", "final_digest", "snapshot", "head")
        keys = set(numbers + digests + ("schema", "execution_authorized", "present", "pending", "usage"))
        if partial:
            numbers += ("payload_bytes",)
            digests += ("approval",)
            keys.update(("payload_bytes", "approval", "archived", "payload_ready", "directory_present"))
        if envelope:
            numbers += ("envelope_device", "envelope_inode", "envelope_bytes")
            digests += ("envelope_digest",)
            keys.update(("envelope_device", "envelope_inode", "envelope_bytes", "envelope_digest",
                         "envelope_final", "envelope_pending"))
        schema = "golem.intent-envelope.v1" if envelope else ("golem.intent-partial.v1" if partial else "golem.intent-alias.v1")
        if fragment:
            numbers += ("truncated_device", "truncated_inode", "truncated_bytes", "object_device", "object_inode", "object_bytes")
            digests += ("truncated_digest", "object_digest", "preservation_approval")
            keys.update(numbers + digests + ("truncated_present", "fragment_final", "fragment_pending"))
            schema = "golem.intent-fragment.v1"
        if damage:
            numbers += ("ancestor_device", "ancestor_inode", "ancestor_bytes")
            digests += ("ancestor_digest", "fragment_approval")
            keys.update(numbers + digests)
            schema = "golem.intent-damage.v1"
        require(isinstance(value, dict) and set(value) == keys and value["schema"] == schema and
                value["execution_authorized"] is False, "NATIVE_CONTRACT")
        for key in numbers:
            host.contract._validate(value[key], host.contract.INTEGER)
        for key in digests:
            host.contract._validate(value[key], host.contract.DIGEST)
        require(type(value["present"]) is bool and type(value["pending"]) is bool and value["kind"] == kind,
                "NATIVE_CONTRACT")
        if partial:
            require(all(type(value[key]) is bool for key in ("archived", "payload_ready", "directory_present")),
                    "NATIVE_CONTRACT")
        if envelope:
            require(type(value["envelope_final"]) is bool and type(value["envelope_pending"]) is bool and
                    value["envelope_bytes"] == value["bytes"] + 320, "NATIVE_CONTRACT")
        require(value["request"] == sha(encoded(record)), "NATIVE_CONTRACT")
        if fragment:
            require(all(type(value[k]) is bool for k in ("truncated_present", "fragment_final", "fragment_pending")), "NATIVE_CONTRACT")
        usage = value["usage"]
        require(isinstance(usage, list) and len(usage) == 3 and
                all(isinstance(row, list) and len(row) == 4 for row in usage), "NATIVE_CONTRACT")
        for row in usage:
            for number in row:
                host.contract._validate(number, host.contract.INTEGER)
    finally:
        os.close(fd)
    host.verify_observation(record["repository"], record["authority"])
    return value


def _removed_alias(before, after):
    require(before["present"] is True and after["present"] is False, "ALIAS_STATE_CHANGED")
    for key in ("kind", "sequence", "device", "inode", "bytes", "committed", "operation", "request",
                "preparation", "payload", "final_digest", "head"):
        require(before[key] == after[key], "ALIAS_STATE_CHANGED")
    expected = [row[:] for row in before["usage"]]
    expected[0][2] -= before["bytes"]
    expected[0][3] -= 1
    require(expected == after["usage"], "ALIAS_ACCOUNTING_CHANGED")


def _alias_recovery(repository, record, previous, kind, bridge):
    require(type(kind) is int and 0 <= kind <= 2, "ALIAS_KIND")
    if previous is not None:
        host.contract._validate(previous, host.contract.DIGEST)
    common = Path(repository["common_dir"])
    require(not os.path.lexists(common / host.DAMAGE_RECOVERY), "DAMAGE_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.FRAGMENT_RECOVERY), "FRAGMENT_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.HOST_PUBLICATION), "HOST_PUBLICATION_REQUIRED")
    require(not os.path.lexists(common / host.HOST_ALIAS_RECOVERY), "HOST_ALIAS_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.PARTIAL_RECOVERY), "PARTIAL_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.ENVELOPE_RECOVERY), "ENVELOPE_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.TOMBSTONE), "AUTHORITY_REVOKED")
    require(not any(p.name.startswith(host.PENDING) for p in common.iterdir()), "ALIAS_HOST_PENDING")
    host.contract._validate(record, host.REGISTRATION)
    require(record["repository"] == repository and record["producer"] == host._producer(), "RECOVERY_BINDING_CHANGED")
    value = _locator(record)
    locator = host._read_locator(repository)
    if locator is not None:
        require(locator["registration_sha256"] in (previous, value["registration_sha256"]), "REGISTRATION_PIN_MISMATCH")
        _same_identity(locator["record"], record)
    path = common / host.ALIAS_RECOVERY
    intent = decode(host.regular(path, private=True)) if os.path.lexists(path) else None
    current = _alias_native(value, previous, kind, bridge)
    before = current
    if intent is not None:
        require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-alias-intent.v1" and isinstance(intent["plan"], dict) and
                sha(encoded(intent["plan"])) == intent["plan_sha256"], "RECOVERY_INTENT_INVALID")
        original = intent["plan"]
        require(original["target"] == value and original["previous"] == previous and original["kind"] == kind,
                "RECOVERY_INTENT_INVALID")
        before = original["before"]
        if current["present"]:
            require(current == before, "ALIAS_STATE_CHANGED")
        else:
            _removed_alias(before, current)
    else:
        require(current["present"], "ALIAS_RECOVERY_NOT_REQUIRED")
    files = {name: sha(host.regular(common / name, private=True)) for name in
             (host.LOCATOR, host.CHANGE, host.NATIVE_RECOVERY, host.ALIAS_RECOVERY) if os.path.lexists(common / name)}
    plan = {"schema": "golem.intent-alias-plan.v1", "target": value, "previous": previous,
            "kind": kind, "before": before, "current": current, "files": files}
    require(len(encoded(plan)) <= host.contract.LIMIT, "REGISTRATION_LIMIT")
    return plan, intent


def alias_recovery_plan(root, target_record, kind, *, git, bridge, previous=None):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository):
        plan, _ = _alias_recovery(repository, target_record, previous, kind, bridge)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def recover_alias(root, target_record, kind, reviewed_plan_sha256, *, git, bridge, previous=None,
                  approve_local_owner=False):
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, exclusive=True) as fd:
        plan, intent = _alias_recovery(repository, target_record, previous, kind, bridge)
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        common = Path(repository["common_dir"])
        prospective = intent or {"schema": "golem.intent-alias-intent.v1", "plan": plan, "plan_sha256": reviewed_plan_sha256}
        require(len(encoded({"schema": "golem.intent-alias-receipt.v1", "intent": prospective,
                             "after": plan["before"]})) + 8 <= host.contract.LIMIT, "REGISTRATION_LIMIT")
        if intent is None:
            intent = {"schema": "golem.intent-alias-intent.v1", "plan": plan, "plan_sha256": reviewed_plan_sha256}
            host._publish(fd, host.ALIAS_RECOVERY, encoded(intent))
        else:
            _archive(fd, common, host.HISTORY + "alias-approval-" + reviewed_plan_sha256 + ".json", encoded(plan))
        after = plan["current"]
        if after["present"]:
            after = _alias_native(plan["target"], previous, kind, bridge, after["snapshot"])
        _removed_alias(plan["before"], after)
        result = {"schema": "golem.intent-alias-receipt.v1", "intent": intent, "after": after}
        _archive(fd, common, host.HISTORY + "alias-recovery-" + sha(encoded(intent)) + ".json", encoded(result))
        os.unlink(host.ALIAS_RECOVERY, dir_fd=fd)
        os.fsync(fd)
        return result


def _partial_transition(before, current, action, approval):
    """Only the exact approved storage transition may finalize an interrupted receipt."""
    for key in ("kind", "sequence", "device", "inode", "bytes", "committed", "operation", "request",
                "preparation", "payload", "payload_bytes", "final_digest", "head"):
        require(before[key] == current[key], "PARTIAL_STATE_CHANGED")
    expected = [row[:] for row in before["usage"]]
    if action == "quarantine":
        require(current["archived"] and current["approval"] == approval and current["directory_present"] and
                before["payload_ready"] == current["payload_ready"], "QUARANTINE_STATE_CHANGED")
        if not before["archived"]:
            expected[0][2] += 320 + before["bytes"]
            expected[0][3] += 1 + int(not before["directory_present"])
        if before["present"] and not current["present"]:
            expected[0][2] -= before["bytes"]
            expected[0][3] -= 1
        require(before["present"], "QUARANTINE_STATE_CHANGED")
    else:
        require(current["archived"] and not current["present"] and current["payload_ready"] and
                current["approval"] == before["approval"] and current["directory_present"] == before["directory_present"] and
                current["pending"] == before["pending"], "PAYLOAD_STATE_CHANGED")
        expected[0][2] += before["payload_bytes"]
        expected[0][3] += 1
    require(expected == current["usage"], "PARTIAL_ACCOUNTING_CHANGED")


def _partial_recovery(repository, record, previous, kind, action, bridge, *, envelope=False):
    require(type(kind) is int and 0 <= kind <= 2 and action in ("quarantine", "replace"), "PARTIAL_ACTION")
    require(action != "replace" or kind == 1, "PAYLOAD_REPLACEMENT_ONLY")
    if previous is not None:
        host.contract._validate(previous, host.contract.DIGEST)
    common = Path(repository["common_dir"])
    require(not os.path.lexists(common / host.DAMAGE_RECOVERY), "DAMAGE_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.FRAGMENT_RECOVERY), "FRAGMENT_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.HOST_PUBLICATION), "HOST_PUBLICATION_REQUIRED")
    require(not os.path.lexists(common / host.HOST_ALIAS_RECOVERY), "HOST_ALIAS_RECOVERY_REQUIRED")
    require(envelope or not os.path.lexists(common / host.ENVELOPE_RECOVERY), "ENVELOPE_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.TOMBSTONE), "AUTHORITY_REVOKED")
    require(not os.path.lexists(common / host.ALIAS_RECOVERY) and
            not os.path.lexists(common / host.NATIVE_RECOVERY), "OTHER_RECOVERY_PENDING")
    require(not any(p.name.startswith(host.PENDING) for p in common.iterdir()), "PARTIAL_HOST_PENDING")
    host.contract._validate(record, host.REGISTRATION)
    require(record["repository"] == repository and record["producer"] == host._producer(), "RECOVERY_BINDING_CHANGED")
    value = _locator(record)
    locator = host._read_locator(repository)
    if locator is not None:
        require(locator["registration_sha256"] in (previous, value["registration_sha256"]), "REGISTRATION_PIN_MISMATCH")
        _same_identity(locator["record"], record)
    change_path = common / host.CHANGE
    if os.path.lexists(change_path):
        change = decode(host.regular(change_path, private=True))
        require(change.get("schema") == "golem.intent-authority-change.v1" and
                set(change) == {"schema", "plan", "plan_sha256"} and
                isinstance(change.get("plan"), dict) and sha(encoded(change["plan"])) == change["plan_sha256"],
                "CHANGE_INTENT_INVALID")
        require(change["plan"]["after"] == value and
                change["plan"]["before"]["registration_sha256"] == previous, "CHANGE_INTENT_INVALID")
    path = common / host.PARTIAL_RECOVERY
    intent = decode(host.regular(path, private=True)) if os.path.lexists(path) else None
    require(not envelope or intent is not None, "ORIGINAL_QUARANTINE_APPROVAL_REQUIRED")
    current = _alias_native(value, previous, kind, bridge, partial=True, envelope=envelope)
    before = current
    if intent is not None:
        require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-partial-intent.v1" and isinstance(intent["plan"], dict) and
                sha(encoded(intent["plan"])) == intent["plan_sha256"], "RECOVERY_INTENT_INVALID")
        original = intent["plan"]
        require(original["target"] == value and original["previous"] == previous and
                original["kind"] == kind and original["action"] == action, "RECOVERY_INTENT_INVALID")
        before = original["before"]
        if current != before:
            normalized = {**current, "usage": [row[:] for row in current["usage"]]}
            if envelope and current["envelope_final"] and current["envelope_pending"]:
                normalized["usage"][0][2] -= current["envelope_bytes"]
                normalized["usage"][0][3] -= 1
            _partial_transition(before, normalized, action, intent["plan_sha256"])
    elif action == "quarantine":
        require(current["present"] and not current["archived"], "QUARANTINE_NOT_REQUIRED")
    else:
        require(current["archived"] and not current["present"] and not current["payload_ready"] and
                current["committed"] + 1 == current["sequence"], "PAYLOAD_REPLACEMENT_NOT_ALLOWED")
    files = {name: sha(host.regular(common / name, private=True)) for name in
             (host.LOCATOR, host.CHANGE, host.PARTIAL_RECOVERY, host.ENVELOPE_RECOVERY) if os.path.lexists(common / name)}
    plan = {"schema": "golem.intent-partial-plan.v1", "action": action, "target": value,
            "previous": previous, "kind": kind, "before": before, "current": current, "files": files}
    require(len(encoded(plan)) <= host.contract.LIMIT, "REGISTRATION_LIMIT")
    return plan, intent


def partial_recovery_plan(root, target_record, kind, *, action, git, bridge, previous=None):
    """Read-only plan. Explicit target_record supplies the exact replacement source."""
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository):
        plan, _ = _partial_recovery(repository, target_record, previous, kind, action, bridge)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def recover_partial(root, target_record, kind, reviewed_plan_sha256, *, action, git, bridge, previous=None,
                    approve_local_owner=False):
    """Quarantine OR replace payload; never finish native event or locator."""
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, exclusive=True) as fd:
        plan, intent = _partial_recovery(repository, target_record, previous, kind, action, bridge)
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        common = Path(repository["common_dir"])
        prospective = intent or {"schema": "golem.intent-partial-intent.v1", "plan": plan,
                                 "plan_sha256": reviewed_plan_sha256}
        require(len(encoded({"schema": "golem.intent-partial-receipt.v1", "intent": prospective,
                             "after": plan["before"]})) + 128 <= host.contract.LIMIT, "REGISTRATION_LIMIT")
        if intent is None:
            intent = prospective
            host._publish(fd, host.PARTIAL_RECOVERY, encoded(intent))
        else:
            _archive(fd, common, host.HISTORY + "partial-approval-" + reviewed_plan_sha256 + ".json", encoded(plan))
        after = plan["current"]
        if (action == "quarantine" and after["present"]) or (action == "replace" and not after["payload_ready"]):
            after = _alias_native(plan["target"], previous, kind, bridge, after["snapshot"], partial=True,
                                  replace=action == "replace", approval=intent["plan_sha256"])
        _partial_transition(plan["before"], after, action, intent["plan_sha256"])
        require(action != "quarantine" or not after["present"], "QUARANTINE_INCOMPLETE")
        result = {"schema": "golem.intent-partial-receipt.v1", "intent": intent, "after": after}
        _archive(fd, common, host.HISTORY + "partial-recovery-" + sha(encoded(intent)) + ".json", encoded(result))
        os.unlink(host.PARTIAL_RECOVERY, dir_fd=fd)
        os.fsync(fd)
        return result


def _envelope_transition(before, current):
    for key in ("kind", "sequence", "device", "inode", "bytes", "committed", "operation", "request",
                "preparation", "payload", "payload_bytes", "final_digest", "head", "approval", "present",
                "payload_ready", "archived", "directory_present", "pending", "envelope_device",
                "envelope_inode", "envelope_bytes", "envelope_digest"):
        require(before[key] == current[key], "ENVELOPE_STATE_CHANGED")
    require(before["envelope_pending"] and current["envelope_final"], "ENVELOPE_STATE_CHANGED")
    expected = [row[:] for row in before["usage"]]
    difference = int(current["envelope_pending"]) - int(before["envelope_final"])
    expected[0][2] += difference * before["envelope_bytes"]
    expected[0][3] += difference
    require(expected == current["usage"], "ENVELOPE_ACCOUNTING_CHANGED")


def _envelope_recovery(repository, record, previous, kind, bridge):
    plan, original = _partial_recovery(repository, record, previous, kind, "quarantine", bridge, envelope=True)
    require(plan["current"]["present"], "ORIGINAL_STAGING_REQUIRED")
    plan["schema"] = "golem.intent-envelope-plan.v1"
    plan["original_approval"] = original["plan_sha256"]
    plan["partial_intent_sha256"] = sha(encoded(original))
    path = Path(repository["common_dir"]) / host.ENVELOPE_RECOVERY
    intent = decode(host.regular(path, private=True)) if os.path.lexists(path) else None
    if intent is not None:
        require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-envelope-intent.v1" and isinstance(intent["plan"], dict) and
                sha(encoded(intent["plan"])) == intent["plan_sha256"], "RECOVERY_INTENT_INVALID")
        prior = intent["plan"]
        for key in ("target", "previous", "kind", "original_approval", "partial_intent_sha256"):
            require(prior[key] == plan[key], "RECOVERY_INTENT_INVALID")
        if prior["current"] != plan["current"]:
            _envelope_transition(prior["current"], plan["current"])
    else:
        require(plan["current"]["envelope_pending"], "ENVELOPE_RECOVERY_NOT_REQUIRED")
    require(len(encoded(plan)) <= host.contract.LIMIT, "REGISTRATION_LIMIT")
    return plan, intent


def envelope_recovery_plan(root, target_record, kind, *, git, bridge, previous=None):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository):
        plan, _ = _envelope_recovery(repository, target_record, previous, kind, bridge)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def finish_envelope(root, target_record, kind, reviewed_plan_sha256, *, git, bridge, previous=None,
                    approve_local_owner=False):
    """Finish quarantine publication only; leave original staging and its intent."""
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, exclusive=True) as fd:
        plan, intent = _envelope_recovery(repository, target_record, previous, kind, bridge)
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        common = Path(repository["common_dir"])
        prospective = intent or {"schema": "golem.intent-envelope-intent.v1", "plan": plan,
                                 "plan_sha256": reviewed_plan_sha256}
        require(len(encoded({"schema": "golem.intent-envelope-receipt.v1", "intent": prospective,
                             "after": plan["current"]})) + 128 <= host.contract.LIMIT, "REGISTRATION_LIMIT")
        if intent is None:
            intent = prospective
            host._publish(fd, host.ENVELOPE_RECOVERY, encoded(intent))
        else:
            _archive(fd, common, host.HISTORY + "envelope-approval-" + reviewed_plan_sha256 + ".json", encoded(plan))
        after = plan["current"]
        if after["envelope_pending"]:
            after = _alias_native(plan["target"], previous, kind, bridge, after["snapshot"], partial=True,
                                  envelope=True, approval=plan["original_approval"])
        _envelope_transition(intent["plan"]["current"], after)
        require(after["envelope_final"] and not after["envelope_pending"], "ENVELOPE_INCOMPLETE")
        result = {"schema": "golem.intent-envelope-receipt.v1", "intent": intent, "after": after}
        _archive(fd, common, host.HISTORY + "envelope-recovery-" + sha(encoded(intent)) + ".json", encoded(result))
        os.unlink(host.ENVELOPE_RECOVERY, dir_fd=fd)
        os.fsync(fd)
        return result


_HOST_RECOVERY_TARGETS = {
    "native-recovery": host.NATIVE_RECOVERY, "alias": host.ALIAS_RECOVERY,
    "partial": host.PARTIAL_RECOVERY, "envelope": host.ENVELOPE_RECOVERY,
    "fragment": host.FRAGMENT_RECOVERY, "damage": host.DAMAGE_RECOVERY,
}


def _host_observation(value, family, target, previous, kind=None):
    c = host.contract
    fields = {"schema": c.enum("golem.intent-" + family + ".v1"), "execution_authorized": {"const": False}}
    if family == "native-recovery":
        numbers = ("sequence", "payload_bytes")
        digests = ("operation", "request", "head", "preparation", "payload", "snapshot")
    else:
        numbers = ("kind", "sequence", "device", "inode", "bytes", "committed")
        digests = ("operation", "request", "preparation", "payload", "final_digest", "snapshot", "head")
        fields.update({key: {"type": "boolean"} for key in ("present", "pending")})
        fields["usage"] = {"type": "array", "minItems": 3, "maxItems": 3,
                           "items": {"type": "array", "minItems": 4, "maxItems": 4, "items": c.INTEGER}}
        if family in ("partial", "envelope", "fragment", "damage"):
            numbers += ("payload_bytes",)
            digests += ("approval",)
            fields.update({key: {"type": "boolean"} for key in ("archived", "payload_ready", "directory_present")})
        if family == "envelope":
            numbers += ("envelope_device", "envelope_inode", "envelope_bytes")
            digests += ("envelope_digest",)
            fields.update({key: {"type": "boolean"} for key in ("envelope_final", "envelope_pending")})
        if family in ("fragment", "damage"):
            numbers += ("truncated_device", "truncated_inode", "truncated_bytes", "object_device", "object_inode", "object_bytes")
            digests += ("truncated_digest", "object_digest", "preservation_approval")
            fields.update({key: {"type": "boolean"} for key in ("truncated_present", "fragment_final", "fragment_pending")})
        if family == "damage":
            numbers += ("ancestor_device", "ancestor_inode", "ancestor_bytes")
            digests += ("ancestor_digest", "fragment_approval")
    fields.update({key: c.INTEGER for key in numbers})
    fields.update({key: c.DIGEST for key in digests})
    require(isinstance(value, dict) and set(value) == set(fields), "HOST_RECOVERY_RECORD_INVALID")
    for key, rule in fields.items():
        if rule.get("type") == "boolean":
            require(type(value[key]) is bool, "HOST_RECOVERY_RECORD_INVALID")
        elif key == "usage":
            require(isinstance(value[key], list) and len(value[key]) == 3, "HOST_RECOVERY_RECORD_INVALID")
            for row in value[key]:
                require(isinstance(row, list) and len(row) == 4, "HOST_RECOVERY_RECORD_INVALID")
                for count in row:
                    c._validate(count, c.INTEGER)
        else:
            c._validate(value[key], rule)
    raw = encoded(target["record"])
    operation = b"golem.intent.authority-registration.v1"
    if previous is not None:
        raw = bytes.fromhex(previous) + raw
        operation = b"golem.intent.authority-change.v1\0" + bytes.fromhex(previous)
    require(value["request"] == target["registration_sha256"] and value["operation"] == sha(operation) and
            value["payload"] == sha(raw), "HOST_RECOVERY_BINDING")
    if "payload_bytes" in value:
        require(value["payload_bytes"] == len(raw), "HOST_RECOVERY_BINDING")
    if kind is not None:
        require(value["kind"] == kind, "HOST_RECOVERY_BINDING")


def _host_recovery_record(data, final_name, target, repository):
    value = decode(data)
    require(isinstance(value, dict) and data == encoded(value), "HOST_RECOVERY_RECORD_INVALID")
    receipt = "intent" in value
    intent = value.get("intent") if receipt else value
    require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
            isinstance(intent["plan"], dict), "HOST_RECOVERY_RECORD_INVALID")
    family = next((key for key in _HOST_RECOVERY_TARGETS
                   if intent["schema"] == "golem.intent-" + key + "-intent.v1"), None)
    require(family is not None, "HOST_RECOVERY_SCHEMA_UNSUPPORTED")
    if family in ("fragment", "damage"):
        return _host_preservation_record(value, final_name, target, repository, family)
    plan = intent["plan"]
    require(sha(encoded(plan)) == intent["plan_sha256"], "HOST_RECOVERY_PLAN_DIGEST")
    expected_keys = {"schema", "target", "previous", "files"}
    if family == "native-recovery":
        expected_keys.update(("native", "phase", "change"))
    else:
        expected_keys.update(("kind", "before", "current"))
        if family in ("partial", "envelope"):
            expected_keys.add("action")
        if family == "envelope":
            expected_keys.update(("original_approval", "partial_intent_sha256"))
    require(set(plan) == expected_keys and plan["schema"] == "golem.intent-" + family + "-plan.v1" and
            plan["target"] == target, "HOST_RECOVERY_BINDING")
    previous = plan["previous"]
    if previous is not None:
        host.contract._validate(previous, host.contract.DIGEST)
    require(isinstance(plan["files"], dict), "HOST_RECOVERY_RECORD_INVALID")
    allowed_files = {host.LOCATOR, host.CHANGE, host.NATIVE_RECOVERY, host.ALIAS_RECOVERY,
                     host.PARTIAL_RECOVERY, host.ENVELOPE_RECOVERY, CANDIDATE}
    for name, digest in plan["files"].items():
        require(name in allowed_files, "HOST_RECOVERY_RECORD_INVALID")
        host.contract._validate(digest, host.contract.DIGEST)
    if family == "native-recovery":
        require(plan["phase"] == "PREPARED", "HOST_RECOVERY_RECORD_INVALID")
        _host_observation(plan["native"], family, target, previous)
        change = plan["change"]
        if change is not None:
            require(isinstance(change, dict) and set(change) == {"schema", "plan", "plan_sha256"} and
                    change["schema"] == "golem.intent-authority-change.v1" and isinstance(change["plan"], dict) and
                    set(change["plan"]) == {"schema", "before", "after"} and
                    change["plan"]["schema"] == "golem.intent-authority-change-plan.v1" and
                    sha(encoded(change["plan"])) == change["plan_sha256"], "HOST_RECOVERY_RECORD_INVALID")
            _validate_locator(change["plan"]["before"], repository)
            require(change["plan"]["after"] == target and
                    change["plan"]["before"]["registration_sha256"] == previous, "HOST_RECOVERY_BINDING")
            _same_identity(change["plan"]["before"]["record"], target["record"])
        else:
            require(previous is None, "HOST_RECOVERY_BINDING")
    else:
        require(type(plan["kind"]) is int and 0 <= plan["kind"] <= 2, "HOST_RECOVERY_RECORD_INVALID")
        _host_observation(plan["before"], "partial" if family == "envelope" else family, target, previous, plan["kind"])
        _host_observation(plan["current"], family, target, previous, plan["kind"])
        if family in ("partial", "envelope"):
            require(plan["action"] in ("quarantine", "replace") and
                    (plan["action"] != "replace" or plan["kind"] == 1), "HOST_RECOVERY_RECORD_INVALID")
        if family == "envelope":
            require(plan["action"] == "quarantine", "HOST_RECOVERY_RECORD_INVALID")
            for key in ("original_approval", "partial_intent_sha256"):
                host.contract._validate(plan[key], host.contract.DIGEST)
            require(plan["current"]["approval"] == plan["original_approval"], "HOST_RECOVERY_BINDING")
    prefix = "native-recovery-" if family == "native-recovery" else family + "-recovery-"
    history_name = host.HISTORY + prefix + sha(encoded(intent)) + ".json"
    if receipt:
        require(family != "native-recovery" and set(value) == {"schema", "intent", "after"} and
                value["schema"] == "golem.intent-" + family + "-receipt.v1" and
                final_name == history_name, "HOST_RECOVERY_RECORD_INVALID")
        _host_observation(value["after"], family, target, previous, plan["kind"])
        if family == "alias":
            _removed_alias(plan["before"], value["after"])
        elif family == "partial":
            _partial_transition(plan["before"], value["after"], plan["action"], intent["plan_sha256"])
            require(not value["after"]["present"], "HOST_RECOVERY_RECORD_INVALID")
        else:
            _envelope_transition(plan["current"], value["after"])
            require(not value["after"]["envelope_pending"], "HOST_RECOVERY_RECORD_INVALID")
    else:
        require(final_name == _HOST_RECOVERY_TARGETS[family] or
                (family == "native-recovery" and final_name == history_name), "HOST_RECOVERY_TARGET_UNSUPPORTED")
    return value["schema"], previous


def _preservation_intent(intent, family, target):
    require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
            intent["schema"] == "golem.intent-" + family + "-intent.v1" and isinstance(intent["plan"], dict) and
            sha(encoded(intent["plan"])) == intent["plan_sha256"], "HOST_RECOVERY_PLAN_DIGEST")
    plan = intent["plan"]
    keys = {"schema", "target", "previous", "kind", "action", "original_intent", "current"}
    if family == "damage":
        keys.add("parent_intent")
        host.contract._validate(plan.get("parent_intent"), host.contract.DIGEST)
    require(set(plan) == keys and plan["schema"] == "golem.intent-" + family + "-plan.v1" and
            plan["target"] == target and type(plan["kind"]) is int and 0 <= plan["kind"] <= 2 and
            plan["action"] in ("preserve", "finish", "detach"), "HOST_RECOVERY_BINDING")
    if plan["previous"] is not None:
        host.contract._validate(plan["previous"], host.contract.DIGEST)
    host.contract._validate(plan["original_intent"], host.contract.DIGEST)
    _host_observation(plan["current"], family, target, plan["previous"], plan["kind"])
    current = plan["current"]
    require(current["present"] is True and current["directory_present"] is True and
            current["archived"] is False and current["truncated_bytes"] >= 320, "HOST_RECOVERY_RECORD_INVALID")
    if current["fragment_final"] or current["fragment_pending"]:
        require(current["object_bytes"] == current["truncated_bytes"] + (384 if family == "damage" else 320),
                "HOST_RECOVERY_RECORD_INVALID")
    return plan


def _host_preservation_record(value, final_name, target, repository, family):
    receipt = "intent" in value
    intent = value["intent"] if receipt else value
    plan = _preservation_intent(intent, family, target)
    if receipt:
        require(set(value) == {"schema", "intent", "approved", "after"} and
                value["schema"] == "golem.intent-" + family + "-receipt.v1", "HOST_RECOVERY_RECORD_INVALID")
        approved = _preservation_intent(value["approved"], family, target)
        for key in set(plan) - {"current", "action"}:
            require(plan[key] == approved[key], "HOST_RECOVERY_BINDING")
        require(plan["action"] == approved["action"] or
                (plan["action"] == "preserve" and approved["action"] == "finish"), "HOST_RECOVERY_BINDING")
        _host_observation(value["after"], family, target, plan["previous"], plan["kind"])
        preservation = intent["plan_sha256"] if plan["action"] == "preserve" else plan["current"]["preservation_approval"]
        _fragment_transition(plan["current"], value["after"], plan["action"], preservation, damage=family == "damage")
        current = approved["current"]
        done = (approved["action"] != "detach" and current["fragment_final"] and not current["fragment_pending"]) or (
            approved["action"] == "detach" and not current["truncated_present"])
        if done:
            require(current == value["after"], "HOST_RECOVERY_BINDING")
        elif value["approved"] != intent:
            _fragment_transition(current, value["after"], approved["action"], preservation, damage=family == "damage")
        require(final_name == host.HISTORY + family + "-recovery-" + sha(encoded(value["approved"])) + ".json",
                "HOST_RECOVERY_TARGET_UNSUPPORTED")
    else:
        require(final_name in (_HOST_RECOVERY_TARGETS[family],
                host.HISTORY + family + "-approval-" + intent["plan_sha256"] + ".json"), "HOST_RECOVERY_TARGET_UNSUPPORTED")
    return value["schema"], plan["previous"]


def _preservation_host_bindings(data, final_name, target, repository):
    """Bounded ancestry checks only. Never execute or observe native recovery."""
    value = decode(data)
    intent = value.get("intent", value)
    family = next((f for f in ("fragment", "damage") if
        intent.get("schema") == "golem.intent-" + f + "-intent.v1"), None)
    common = Path(repository["common_dir"])
    if family is None:
        require(not os.path.lexists(common / host.DAMAGE_RECOVERY), "DAMAGE_RECOVERY_REQUIRED")
        require(not os.path.lexists(common / host.FRAGMENT_RECOVERY), "FRAGMENT_RECOVERY_REQUIRED")
        return None
    plan = intent["plan"]
    bindings = {}
    def ancestor(name):
        raw = host.regular(common / name, private=True)
        bindings[name] = sha(raw)
        parsed = decode(raw)
        require(encoded(parsed) == raw, "HOST_RECOVERY_RECORD_INVALID")
        return raw, parsed
    raw, original = ancestor(host.PARTIAL_RECOVERY)
    _host_recovery_record(raw, host.PARTIAL_RECOVERY, target, repository)
    require(sha(raw) == plan["original_intent"] and original["plan"]["previous"] == plan["previous"] and
            original["plan"]["kind"] == plan["kind"] and original["plan"]["action"] == "quarantine" and
            original["plan_sha256"] == plan["current"]["approval"], "HOST_RECOVERY_BINDING")
    for key in ("kind", "sequence", "device", "inode", "bytes", "operation", "request", "preparation", "payload",
                "payload_bytes", "final_digest", "head", "committed", "payload_ready"):
        require(original["plan"]["before"][key] == plan["current"][key], "HOST_RECOVERY_BINDING")
    if family == "damage":
        raw, parent = ancestor(host.FRAGMENT_RECOVERY)
        pp = _preservation_intent(parent, "fragment", target)
        require(sha(raw) == plan["parent_intent"] and pp["action"] == "preserve" and
                pp["original_intent"] == plan["original_intent"] and pp["previous"] == plan["previous"] and
                pp["kind"] == plan["kind"] and parent["plan_sha256"] == plan["current"]["fragment_approval"], "HOST_RECOVERY_BINDING")
        for key in ("sequence", "device", "inode", "bytes", "preparation", "final_digest", "head", "committed", "approval"):
            require(pp["current"][key] == plan["current"][key], "HOST_RECOVERY_BINDING")
        for suffix in ("device", "inode", "bytes", "digest"):
            require(pp["current"]["truncated_" + suffix] == plan["current"]["ancestor_" + suffix], "HOST_RECOVERY_BINDING")
    else:
        require(not os.path.lexists(common / host.DAMAGE_RECOVERY), "DAMAGE_RECOVERY_REQUIRED")
    marker = _HOST_RECOVERY_TARGETS[family]
    if final_name != marker and os.path.lexists(common / marker):
        _, active = ancestor(marker)
        ap = _preservation_intent(active, family, target)
        if "intent" in value:
            require(active == intent, "HOST_RECOVERY_BINDING")
        else:
            for key in set(plan) - {"current", "action"}:
                require(ap[key] == plan[key], "HOST_RECOVERY_BINDING")
            require(ap["action"] == plan["action"] or (ap["action"] == "preserve" and plan["action"] == "finish"),
                    "HOST_RECOVERY_BINDING")
            stable = ("sequence", "device", "inode", "bytes", "preparation", "final_digest", "head", "committed", "approval",
                      "truncated_device", "truncated_inode", "truncated_bytes", "truncated_digest", "payload_ready")
            if family == "damage":
                stable += ("ancestor_device", "ancestor_inode", "ancestor_bytes", "ancestor_digest", "fragment_approval")
            require(all(ap["current"][key] == plan["current"][key] for key in stable), "HOST_RECOVERY_BINDING")
            if ap["action"] != "preserve":
                require(all(ap["current"][key] == plan["current"][key] for key in
                    ("object_device", "object_inode", "object_bytes", "object_digest", "preservation_approval")), "HOST_RECOVERY_BINDING")
            elif plan["current"]["fragment_final"] or plan["current"]["fragment_pending"]:
                require(plan["current"]["preservation_approval"] == active["plan_sha256"], "HOST_RECOVERY_BINDING")
    elif final_name != marker and "intent" not in value:
        require(False, "HOST_RECOVERY_APPROVAL_REQUIRED")
    return bindings


def _host_record_target(final_name):
    return isinstance(final_name, str) and Path(final_name).name == final_name and (
        final_name in _HOST_RECOVERY_TARGETS.values() or any(final_name.startswith(host.HISTORY + prefix) for prefix in
        ("native-recovery-", "alias-recovery-", "partial-recovery-", "envelope-recovery-",
         "fragment-recovery-", "damage-recovery-", "fragment-approval-", "damage-approval-")))


def _host_alias_observe(common_fd, final_name):
    require(_host_record_target(final_name), "HOST_RECOVERY_TARGET_UNSUPPORTED")
    fd = os.open(final_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=common_fd)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_mode & 0o777 == 0o400 and
                info.st_nlink in (1, 2) and 0 <= info.st_size <= host.contract.LIMIT, "HOST_ALIAS_FILE_INVALID")
        pending = [name for name in os.listdir(common_fd) if name.startswith(host.PENDING)]
        require(len(pending) == info.st_nlink - 1, "HOST_ALIAS_AMBIGUOUS")
        alias = pending[0] if pending else None
        if alias is not None:
            suffix = alias[len(host.PENDING):]
            require(len(suffix) == 32 and all(c in "0123456789abcdef" for c in suffix), "HOST_ALIAS_AMBIGUOUS")
            link = os.stat(alias, dir_fd=common_fd, follow_symlinks=False)
            require(stat.S_ISREG(link.st_mode) and (link.st_dev, link.st_ino, link.st_nlink) ==
                    (info.st_dev, info.st_ino, 2), "HOST_ALIAS_NOT_IDENTICAL")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(host.contract.LIMIT + 1)
        def identity(s):
            return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(len(data) == info.st_size and identity(os.fstat(fd)) == identity(info) and
                identity(os.stat(final_name, dir_fd=common_fd, follow_symlinks=False)) == identity(info), "HOST_ALIAS_CHANGED")
        if alias is not None:
            require(identity(os.stat(alias, dir_fd=common_fd, follow_symlinks=False)) == identity(info), "HOST_ALIAS_CHANGED")
        return data, {"device": info.st_dev, "inode": info.st_ino, "bytes": len(data), "sha256": sha(data), "pending": alias}
    finally:
        os.close(fd)


def _host_alias_plan(repository, record, final_name, common_fd):
    host.contract._validate(record, host.REGISTRATION)
    require(record["repository"] == repository and record["producer"] == host._producer(), "RECOVERY_BINDING_CHANGED")
    host.verify_observation(repository, record["authority"])
    common = Path(repository["common_dir"])
    require(not os.path.lexists(common / host.HOST_PUBLICATION), "HOST_PUBLICATION_REQUIRED")
    require(not os.path.lexists(common / host.TOMBSTONE), "AUTHORITY_REVOKED")
    target = _locator(record)
    data, current = _host_alias_observe(common_fd, final_name)
    schema, previous = _host_recovery_record(data, final_name, target, repository)
    bindings = _preservation_host_bindings(data, final_name, target, repository)
    locator = host._read_locator(repository)
    if locator is not None:
        require(locator["registration_sha256"] in (previous, target["registration_sha256"]), "REGISTRATION_PIN_MISMATCH")
        _same_identity(locator["record"], record)
    path = common / host.HOST_ALIAS_RECOVERY
    intent = decode(host.regular(path, private=True)) if os.path.lexists(path) else None
    before = current
    if intent is not None:
        require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-host-alias-intent.v1" and isinstance(intent["plan"], dict) and
                sha(encoded(intent["plan"])) == intent["plan_sha256"], "RECOVERY_INTENT_INVALID")
        original = intent["plan"]
        keys = {"schema", "target", "final", "record_schema", "before", "current"}
        if bindings is not None:
            keys.add("bindings")
            require(original.get("bindings") == bindings, "HOST_RECOVERY_BINDING")
        require(set(original) == keys and
                original["schema"] == "golem.intent-host-alias-plan.v1" and original["target"] == target and
                original["final"] == final_name and original["record_schema"] == schema, "RECOVERY_INTENT_INVALID")
        before = original["before"]
        host.contract._validate(before, host.contract.obj({
            "device": host.contract.INTEGER, "inode": host.contract.INTEGER,
            "bytes": host.contract.INTEGER, "sha256": host.contract.DIGEST,
            "pending": {"type": "string", "pattern": "^" + host.PENDING.replace(".", "\\.") + "[0-9a-f]{32}$"}}))
        require(original["current"] == before, "RECOVERY_INTENT_INVALID")
        require(before["pending"] is not None and current == {**before, "pending": current["pending"]} and
                current["pending"] in (before["pending"], None), "HOST_ALIAS_CHANGED")
    else:
        require(current["pending"] is not None, "HOST_ALIAS_RECOVERY_NOT_REQUIRED")
    plan = {"schema": "golem.intent-host-alias-plan.v1", "target": target, "final": final_name,
            "record_schema": schema, "before": before, "current": current}
    if bindings is not None:
        plan["bindings"] = bindings
    require(len(encoded(plan)) <= host.contract.LIMIT, "REGISTRATION_LIMIT")
    return plan, intent


def host_alias_recovery_plan(root, target_record, final_name, *, git):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository) as fd, host._authority_owner_lock(target_record):
        plan, _ = _host_alias_plan(repository, target_record, final_name, fd)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def recover_host_alias(root, target_record, final_name, reviewed_plan_sha256, *, git, approve_local_owner=False):
    """Remove only the verified host pending name. No native API invocation."""
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, exclusive=True) as fd, host._authority_owner_lock(target_record):
        plan, intent = _host_alias_plan(repository, target_record, final_name, fd)
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        common = Path(repository["common_dir"])
        prospective = intent or {"schema": "golem.intent-host-alias-intent.v1", "plan": plan,
                                 "plan_sha256": reviewed_plan_sha256}
        require(len(encoded({"schema": "golem.intent-host-alias-receipt.v1", "intent": prospective,
                             "after": plan["current"]})) <= host.contract.LIMIT, "REGISTRATION_LIMIT")
        if intent is None:
            intent = prospective
            host._publish(fd, host.HOST_ALIAS_RECOVERY, encoded(intent))
        else:
            _archive(fd, common, host.HISTORY + "host-alias-approval-" + reviewed_plan_sha256 + ".json", encoded(plan))
        checked, _ = _host_alias_plan(repository, target_record, final_name, fd)
        require(checked == plan, "PLAN_STALE")
        if plan["current"]["pending"] is not None:
            os.unlink(plan["current"]["pending"], dir_fd=fd)
            os.fsync(fd)
        after_plan, _ = _host_alias_plan(repository, target_record, final_name, fd)
        after = after_plan["current"]
        require(after == {**plan["before"], "pending": None}, "HOST_ALIAS_CHANGED")
        result = {"schema": "golem.intent-host-alias-receipt.v1", "intent": intent, "after": after}
        _archive(fd, common, host.HISTORY + "host-alias-recovery-" + sha(encoded(intent)) + ".json", encoded(result))
        os.unlink(host.HOST_ALIAS_RECOVERY, dir_fd=fd)
        os.fsync(fd)
        return result


_TERMINAL_TARGETS = {"host-publication": host.HOST_PUBLICATION, "host-alias": host.HOST_ALIAS_RECOVERY}


def _terminal_target(name):
    return isinstance(name, str) and Path(name).name == name and (name in _TERMINAL_TARGETS.values() or
        any(name.startswith(host.HISTORY + family + suffix) for family in _TERMINAL_TARGETS
            for suffix in ("-approval-", "-recovery-")))


def _final_target(name):
    return isinstance(name, str) and Path(name).name == name and (name == host.HOST_TERMINAL or
        any(name.startswith(host.HISTORY + "host-terminal-" + suffix) for suffix in ("approval-", "recovery-")))


def _terminal_candidate(fd, pending, final, *, final_recovery=False):
    require((_final_target(final) if final_recovery else _terminal_target(final)) and isinstance(pending, str) and pending.startswith(host.PENDING) and
            len(pending) == len(host.PENDING) + 32 and
            all(c in "0123456789abcdef" for c in pending[len(host.PENDING):]), "HOST_RECOVERY_TARGET_UNSUPPORTED")
    try:
        source = os.open(pending, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
    except FileNotFoundError:
        source = os.open(final, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
    with os.fdopen(source, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_mode & 0o777 == 0o400 and
                0 <= info.st_size <= host.contract.LIMIT, "HOST_PUBLICATION_FILE_INVALID")
        raw = stream.read(host.contract.LIMIT + 1)
        require(len(raw) == info.st_size, "HOST_PUBLICATION_CHANGED")
        return raw


def _terminal_step_plan(plan, family, target, *, final_recovery=False):
    keys = {"schema", "target", "final", "record_schema", "before", "current"}
    if family != "host-alias":
        keys.add("pending")
    require(isinstance(plan, dict), "HOST_RECOVERY_RECORD_INVALID")
    if "bindings" in plan:
        keys.add("bindings")
        require(isinstance(plan["bindings"], dict), "HOST_RECOVERY_RECORD_INVALID")
        for name, digest in (() if final_recovery else plan["bindings"].items()):
            require(name in (host.PARTIAL_RECOVERY, host.FRAGMENT_RECOVERY, host.DAMAGE_RECOVERY), "HOST_RECOVERY_BINDING")
            host.contract._validate(digest, host.contract.DIGEST)
    require(set(plan) == keys and plan["schema"] == "golem.intent-" + family + "-plan.v1" and
            plan["target"] == target and (_terminal_target(plan["final"]) if final_recovery else
            _host_record_target(plan["final"])), "HOST_RECOVERY_BINDING")
    require(isinstance(plan["before"], dict), "HOST_RECOVERY_RECORD_INVALID")
    fields = {"device": host.contract.INTEGER, "inode": host.contract.INTEGER,
              "bytes": host.contract.INTEGER, "sha256": host.contract.DIGEST}
    if family != "host-alias":
        fields["state"] = host.contract.enum("PENDING", "PAIR") if "bindings" in plan else host.contract.enum("PENDING")
        pending = plan["pending"]
    else:
        fields["pending"] = {"type": "string"}
        pending = plan.get("before", {}).get("pending")
    host.contract._validate(plan["before"], host.contract.obj(fields))
    require(isinstance(pending, str) and pending.startswith(host.PENDING) and
            len(pending) == len(host.PENDING) + 32 and
            all(c in "0123456789abcdef" for c in pending[len(host.PENDING):]), "HOST_PENDING_NAME")
    current = plan["current"]
    if family != "host-alias":
        require(isinstance(current, dict) and current.get("state") in ("PENDING", "PAIR", "FINAL") and
                current == {**plan["before"], "state": current["state"]}, "HOST_RECOVERY_RECORD_INVALID")
    else:
        require(isinstance(current, dict) and current.get("pending") in (pending, None) and
                current == {**plan["before"], "pending": current["pending"]}, "HOST_RECOVERY_RECORD_INVALID")
    return pending


def _terminal_record(raw, final_name, target, repository, fd, outer_pending, *, extra_pending=()):
    value = decode(raw)
    require(isinstance(value, dict) and encoded(value) == raw, "HOST_RECOVERY_RECORD_INVALID")
    schema = value.get("schema")
    family = next((f for f in _TERMINAL_TARGETS if schema in
        ("golem.intent-" + f + "-intent.v1", "golem.intent-" + f + "-plan.v1", "golem.intent-" + f + "-receipt.v1")), None)
    require(family is not None, "HOST_RECOVERY_SCHEMA_UNSUPPORTED")
    receipt = schema.endswith("-receipt.v1")
    reapproval = schema.endswith("-plan.v1")
    intent = value.get("intent") if receipt else None if reapproval else value
    if intent is not None:
        require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-" + family + "-intent.v1" and
                sha(encoded(intent["plan"])) == intent["plan_sha256"], "HOST_RECOVERY_PLAN_DIGEST")
        plan = intent["plan"]
    else:
        require(reapproval, "HOST_RECOVERY_RECORD_INVALID")
        plan = value
    original_pending = _terminal_step_plan(plan, family, target)
    require(original_pending != outer_pending, "HOST_PENDING_AMBIGUOUS")
    if not reapproval:
        require(plan["before"] == plan["current"], "HOST_RECOVERY_RECORD_INVALID")
    marker = _TERMINAL_TARGETS[family]
    if receipt:
        require(set(value) == {"schema", "intent", "after"} and final_name ==
                host.HISTORY + family + "-recovery-" + sha(encoded(intent)) + ".json", "HOST_RECOVERY_TARGET_UNSUPPORTED")
        after = {**plan["before"], **({"state": "FINAL"} if family == "host-publication" else {"pending": None})}
        require(value["after"] == after, "HOST_RECOVERY_RECORD_INVALID")
    elif reapproval:
        require(final_name == host.HISTORY + family + "-approval-" + sha(encoded(plan)) + ".json", "HOST_RECOVERY_TARGET_UNSUPPORTED")
    else:
        require(final_name == marker, "HOST_RECOVERY_TARGET_UNSUPPORTED")
    common = Path(repository["common_dir"])
    opposite = host.HOST_ALIAS_RECOVERY if family == "host-publication" else host.HOST_PUBLICATION
    require(not os.path.lexists(common / opposite), "OTHER_RECOVERY_PENDING")
    require(original_pending not in extra_pending, "HOST_PENDING_AMBIGUOUS")
    raw_source, observed = _host_publication_observe(fd, original_pending, plan["final"], other_pending=(outer_pending,) + extra_pending)
    actual_schema, previous = _host_recovery_record(raw_source, plan["final"], target, repository)
    ancestry = _preservation_host_bindings(raw_source, plan["final"], target, repository)
    require(actual_schema == plan["record_schema"] and plan.get("bindings") == ancestry, "HOST_RECOVERY_BINDING")
    for key in ("device", "inode", "bytes", "sha256"):
        require(plan["before"][key] == observed[key], "HOST_RECOVERY_BINDING")
    if family == "host-alias":
        require(observed["state"] in ("PAIR", "FINAL"), "HOST_RECOVERY_BINDING")
        require(plan["current"]["pending"] is not None or observed["state"] == "FINAL", "HOST_RECOVERY_BINDING")
    else:
        phases = {"PENDING": 0, "PAIR": 1, "FINAL": 2}
        require(phases[observed["state"]] >= phases[plan["current"]["state"]] >= phases[plan["before"]["state"]],
                "HOST_RECOVERY_BINDING")
    if receipt:
        require(observed["state"] == "FINAL", "HOST_RECOVERY_BINDING")
    dependencies = {"source": {"final": plan["final"], "pending": original_pending, "observed": observed},
                    "ancestry": ancestry}
    if final_name != marker:
        if os.path.lexists(common / marker):
            active_raw = host.regular(common / marker, private=True)
            active = decode(active_raw)
            require(encoded(active) == active_raw and isinstance(active, dict) and
                    set(active) == {"schema", "plan", "plan_sha256"} and
                    active["schema"] == "golem.intent-" + family + "-intent.v1" and
                    sha(encoded(active["plan"])) == active["plan_sha256"], "HOST_RECOVERY_PLAN_DIGEST")
            _terminal_step_plan(active["plan"], family, target)
            require(active["plan"]["current"] == active["plan"]["before"], "HOST_RECOVERY_BINDING")
            if receipt:
                require(active == intent, "HOST_RECOVERY_BINDING")
            else:
                require({**plan, "current": active["plan"]["current"]} == active["plan"], "HOST_RECOVERY_BINDING")
            dependencies["approval"] = sha(active_raw)
        else:
            require(not reapproval, "HOST_RECOVERY_APPROVAL_REQUIRED")
    return schema, previous, dependencies, original_pending


def _final_record(raw, final_name, target, repository, fd, outer_pending):
    """One fixed terminal-record exception. Never dispatch on an arbitrary depth."""
    value = decode(raw)
    require(isinstance(value, dict) and encoded(value) == raw, "HOST_RECOVERY_RECORD_INVALID")
    schema = value.get("schema")
    require(schema in ("golem.intent-host-terminal-intent.v1", "golem.intent-host-terminal-plan.v1",
                       "golem.intent-host-terminal-receipt.v1"), "HOST_RECOVERY_SCHEMA_UNSUPPORTED")
    receipt, reapproval = schema.endswith("-receipt.v1"), schema.endswith("-plan.v1")
    intent = value.get("intent") if receipt else None if reapproval else value
    if intent is not None:
        require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-host-terminal-intent.v1" and
                sha(encoded(intent["plan"])) == intent["plan_sha256"], "HOST_RECOVERY_PLAN_DIGEST")
        plan = intent["plan"]
    else:
        require(reapproval, "HOST_RECOVERY_RECORD_INVALID")
        plan = value
    pending = _terminal_step_plan(plan, "host-terminal", target, final_recovery=True)
    require(pending != outer_pending and "bindings" in plan, "HOST_RECOVERY_BINDING")
    if not reapproval:
        require(plan["current"] == plan["before"], "HOST_RECOVERY_BINDING")
    if receipt:
        require(set(value) == {"schema", "intent", "after"} and
                value["after"] == {**plan["before"], "state": "FINAL"} and final_name ==
                host.HISTORY + "host-terminal-recovery-" + sha(encoded(intent)) + ".json", "HOST_RECOVERY_BINDING")
    elif reapproval:
        require(final_name == host.HISTORY + "host-terminal-approval-" + sha(encoded(plan)) + ".json", "HOST_RECOVERY_BINDING")
    else:
        require(final_name == host.HOST_TERMINAL, "HOST_RECOVERY_BINDING")
    source = _terminal_candidate(fd, pending, plan["final"])
    source_schema, previous, ancestry, original_pending = _terminal_record(source, plan["final"], target,
        repository, fd, pending, extra_pending=(outer_pending,))
    source_checked, observed = _host_publication_observe(fd, pending, plan["final"], terminal=True,
        other_pending=(outer_pending, original_pending))
    require(source == source_checked and source_schema == plan["record_schema"] and ancestry == plan["bindings"],
            "HOST_RECOVERY_BINDING")
    require(all(observed[k] == plan["before"][k] for k in ("device", "inode", "bytes", "sha256")), "HOST_RECOVERY_BINDING")
    rank = {"PENDING": 0, "PAIR": 1, "FINAL": 2}
    require(rank[observed["state"]] >= rank[plan["current"]["state"]] >= rank[plan["before"]["state"]], "HOST_RECOVERY_BINDING")
    if receipt:
        require(observed["state"] == "FINAL", "HOST_RECOVERY_BINDING")
    dependencies = {"source": {"final": plan["final"], "pending": pending, "observed": observed}, "ancestry": ancestry}
    common = Path(repository["common_dir"])
    if final_name != host.HOST_TERMINAL:
        if os.path.lexists(common / host.HOST_TERMINAL):
            active_raw = host.regular(common / host.HOST_TERMINAL, private=True)
            active = decode(active_raw)
            require(encoded(active) == active_raw and isinstance(active, dict) and
                    set(active) == {"schema", "plan", "plan_sha256"} and
                    active["schema"] == "golem.intent-host-terminal-intent.v1" and
                    sha(encoded(active["plan"])) == active["plan_sha256"], "HOST_RECOVERY_PLAN_DIGEST")
            _terminal_step_plan(active["plan"], "host-terminal", target, final_recovery=True)
            require(active["plan"]["before"] == active["plan"]["current"] and
                    (active == intent if receipt else {**plan, "current": active["plan"]["current"]} == active["plan"]),
                    "HOST_RECOVERY_BINDING")
            dependencies["approval"] = sha(active_raw)
        else:
            require(not reapproval, "HOST_RECOVERY_APPROVAL_REQUIRED")
    return schema, previous, dependencies, (pending, original_pending)


def _host_publication_observe(fd, pending_name, final_name, *, terminal=False, final_recovery=False, other_pending=()):
    require(isinstance(pending_name, str) and pending_name.startswith(host.PENDING) and
            len(pending_name) == len(host.PENDING) + 32 and
            all(c in "0123456789abcdef" for c in pending_name[len(host.PENDING):]), "HOST_PENDING_NAME")
    require(_final_target(final_name) if final_recovery else _terminal_target(final_name) if terminal else
            _host_record_target(final_name), "HOST_RECOVERY_TARGET_UNSUPPORTED")
    names = [name for name in os.listdir(fd) if name.startswith(host.PENDING) and name not in other_pending]
    require(names in ([], [pending_name]), "HOST_PENDING_AMBIGUOUS")
    def info(name):
        try:
            return os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
    p, f = info(pending_name), info(final_name)
    require(p is not None or f is not None, "HOST_PUBLICATION_MISSING")
    selected = p if p is not None else f
    def identity(s):
        return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    require(stat.S_ISREG(selected.st_mode) and selected.st_uid == os.getuid() and
            selected.st_mode & 0o777 == 0o400 and selected.st_nlink == int(p is not None) + int(f is not None) and
            0 <= selected.st_size <= host.contract.LIMIT, "HOST_PUBLICATION_FILE_INVALID")
    require(p is None or f is None or identity(p) == identity(f), "HOST_PUBLICATION_NOT_IDENTICAL")
    source = os.open(pending_name if p is not None else final_name,
                     os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
    try:
        require(identity(os.fstat(source)) == identity(selected), "HOST_PUBLICATION_CHANGED")
        with os.fdopen(source, "rb", closefd=False) as stream:
            raw = stream.read(host.contract.LIMIT + 1)
        require(len(raw) == selected.st_size and identity(os.fstat(source)) == identity(selected),
                "HOST_PUBLICATION_CHANGED")
        for name, original in ((pending_name, p), (final_name, f)):
            current = info(name)
            require((current is None and original is None) or
                    (current is not None and original is not None and identity(current) == identity(original)),
                    "HOST_PUBLICATION_CHANGED")
    finally:
        os.close(source)
    return raw, {"device": selected.st_dev, "inode": selected.st_ino, "bytes": len(raw), "sha256": sha(raw),
                 "state": "PAIR" if p is not None and f is not None else "PENDING" if p is not None else "FINAL"}


def _host_publication_plan(repository, record, pending_name, final_name, fd, *, terminal=False, final_recovery=False):
    host.contract._validate(record, host.REGISTRATION)
    require(record["repository"] == repository and record["producer"] == host._producer(), "RECOVERY_BINDING_CHANGED")
    host.verify_observation(repository, record["authority"])
    common = Path(repository["common_dir"])
    require(not os.path.lexists(common / host.TOMBSTONE), "AUTHORITY_REVOKED")
    if not terminal and not final_recovery:
        require(not os.path.lexists(common / host.HOST_TERMINAL), "HOST_TERMINAL_REQUIRED")
        require(not os.path.lexists(common / host.HOST_ALIAS_RECOVERY), "HOST_ALIAS_RECOVERY_REQUIRED")
    target = _locator(record)
    if final_recovery:
        raw = _terminal_candidate(fd, pending_name, final_name, final_recovery=True)
        schema, previous, bindings, allowed = _final_record(raw, final_name, target, repository, fd, pending_name)
        checked_raw, current = _host_publication_observe(fd, pending_name, final_name, final_recovery=True, other_pending=allowed)
        require(raw == checked_raw, "HOST_PUBLICATION_CHANGED")
    elif terminal:
        # Discover only the explicitly named record; its validated plan names the
        # sole additional pending allowed below. All other names remain blocked.
        raw = _terminal_candidate(fd, pending_name, final_name)
        schema, previous, bindings, original_pending = _terminal_record(raw, final_name, target, repository, fd, pending_name)
        checked_raw, current = _host_publication_observe(fd, pending_name, final_name,
            terminal=True, other_pending=(original_pending,))
        require(raw == checked_raw, "HOST_PUBLICATION_CHANGED")
    else:
        raw, current = _host_publication_observe(fd, pending_name, final_name)
        schema, previous = _host_recovery_record(raw, final_name, target, repository)
        bindings = _preservation_host_bindings(raw, final_name, target, repository)
    locator = host._read_locator(repository)
    if locator is not None:
        require(locator["registration_sha256"] in (previous, target["registration_sha256"]), "REGISTRATION_PIN_MISMATCH")
        _same_identity(locator["record"], record)
    family = "host-final" if final_recovery else "host-terminal" if terminal else "host-publication"
    marker = common / (host.HOST_FINAL if final_recovery else host.HOST_TERMINAL if terminal else host.HOST_PUBLICATION)
    intent = decode(host.regular(marker, private=True)) if os.path.lexists(marker) else None
    before = current
    if intent is not None:
        require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-" + family + "-intent.v1" and
                isinstance(intent["plan"], dict) and sha(encoded(intent["plan"])) == intent["plan_sha256"],
                "RECOVERY_INTENT_INVALID")
        original = intent["plan"]
        keys = {"schema", "target", "pending", "final", "record_schema", "before", "current"}
        if bindings is not None:
            keys.add("bindings")
            require(original.get("bindings") == bindings, "HOST_RECOVERY_BINDING")
        require(set(original) == keys and
                original["schema"] == "golem.intent-" + family + "-plan.v1" and original["target"] == target and
                original["pending"] == pending_name and original["final"] == final_name and
                original["record_schema"] == schema, "RECOVERY_INTENT_INVALID")
        before = original["before"]
        host.contract._validate(before, host.contract.obj({"device": host.contract.INTEGER,
            "inode": host.contract.INTEGER, "bytes": host.contract.INTEGER, "sha256": host.contract.DIGEST,
            "state": host.contract.enum("PENDING", "PAIR") if bindings is not None else host.contract.enum("PENDING")}))
        require(original["current"] == before and current == {**before, "state": current["state"]},
                "HOST_PUBLICATION_CHANGED")
    else:
        require(current["state"] in (("PENDING", "PAIR") if bindings is not None else ("PENDING",)), "HOST_PUBLICATION_APPROVAL_REQUIRED")
    plan = {"schema": "golem.intent-" + family + "-plan.v1", "target": target, "pending": pending_name,
            "final": final_name, "record_schema": schema, "before": before, "current": current}
    if bindings is not None:
        plan["bindings"] = bindings
    require(len(encoded(plan)) <= host.contract.LIMIT, "REGISTRATION_LIMIT")
    return plan, intent


def host_publication_plan(root, target_record, pending_name, final_name, *, git):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository) as fd, host._authority_owner_lock(target_record):
        plan, _ = _host_publication_plan(repository, target_record, pending_name, final_name, fd)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def finish_host_publication(root, target_record, pending_name, final_name, reviewed_plan_sha256, *, git,
                            approve_local_owner=False):
    """Publish exact approved host bytes only; never execute the contained recovery."""
    return _finish_host_publication(root, target_record, pending_name, final_name, reviewed_plan_sha256,
        git=git, approve_local_owner=approve_local_owner, terminal=False)


def host_terminal_plan(root, target_record, pending_name, final_name, *, git):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, terminal_recovery=True) as fd, host._authority_owner_lock(target_record):
        plan, _ = _host_publication_plan(repository, target_record, pending_name, final_name, fd, terminal=True)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def finish_host_terminal(root, target_record, pending_name, final_name, reviewed_plan_sha256, *, git,
                         approve_local_owner=False):
    return _finish_host_publication(root, target_record, pending_name, final_name, reviewed_plan_sha256,
        git=git, approve_local_owner=approve_local_owner, terminal=True)


def host_final_plan(root, target_record, pending_name, final_name, *, git):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, terminal_recovery=True, final_recovery=True) as fd, host._authority_owner_lock(target_record):
        plan, _ = _host_publication_plan(repository, target_record, pending_name, final_name, fd, final_recovery=True)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def finish_host_final(root, target_record, pending_name, final_name, reviewed_plan_sha256, *, git,
                      approve_local_owner=False):
    return _finish_host_publication(root, target_record, pending_name, final_name, reviewed_plan_sha256,
        git=git, approve_local_owner=approve_local_owner, terminal=True, final_recovery=True)


def _finish_host_publication(root, target_record, pending_name, final_name, reviewed_plan_sha256, *, git,
                             approve_local_owner, terminal, final_recovery=False):
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    family = "host-final" if final_recovery else "host-terminal" if terminal else "host-publication"
    marker = host.HOST_FINAL if final_recovery else host.HOST_TERMINAL if terminal else host.HOST_PUBLICATION
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, exclusive=True, terminal_recovery=terminal, final_recovery=final_recovery) as fd, host._authority_owner_lock(target_record):
        plan, intent = _host_publication_plan(repository, target_record, pending_name, final_name, fd, terminal=terminal, final_recovery=final_recovery)
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        common = Path(repository["common_dir"])
        prospective = intent or {"schema": "golem.intent-" + family + "-intent.v1", "plan": plan,
                                 "plan_sha256": reviewed_plan_sha256}
        require(len(encoded({"schema": "golem.intent-" + family + "-receipt.v1", "intent": prospective,
                             "after": plan["current"]})) <= host.contract.LIMIT, "REGISTRATION_LIMIT")
        if intent is None:
            intent = prospective
            host._publish(fd, marker, encoded(intent))
        else:
            _archive(fd, common, host.HISTORY + family + "-approval-" + reviewed_plan_sha256 + ".json", encoded(plan))
        checked, _ = _host_publication_plan(repository, target_record, pending_name, final_name, fd, terminal=terminal, final_recovery=final_recovery)
        require(checked == plan, "PLAN_STALE")
        if checked["current"]["state"] == "PENDING":
            source = os.open(pending_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            try:
                os.fsync(source)
            finally:
                os.close(source)
            os.link(pending_name, final_name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
            os.fsync(fd)
        checked, _ = _host_publication_plan(repository, target_record, pending_name, final_name, fd, terminal=terminal, final_recovery=final_recovery)
        if checked["current"]["state"] == "PAIR":
            os.unlink(pending_name, dir_fd=fd)
            os.fsync(fd)
        after, _ = _host_publication_plan(repository, target_record, pending_name, final_name, fd, terminal=terminal, final_recovery=final_recovery)
        require(after["current"] == {**plan["before"], "state": "FINAL"}, "HOST_PUBLICATION_CHANGED")
        receipt = {"schema": "golem.intent-" + family + "-receipt.v1", "intent": intent, "after": after["current"]}
        _archive(fd, common, host.HISTORY + family + "-recovery-" + sha(encoded(intent)) + ".json", encoded(receipt))
        os.unlink(marker, dir_fd=fd)
        os.fsync(fd)
        return receipt


def _fragment_transition(before, after, action, preservation, *, damage=False):
    header = 384 if damage else 320
    if damage:
        require(all(before[k] == after[k] for k in ("ancestor_device", "ancestor_inode", "ancestor_bytes",
                "ancestor_digest", "fragment_approval")), "DAMAGE_ANCESTRY_CHANGED")
    for key in ("kind", "sequence", "device", "inode", "bytes", "committed", "operation", "request",
                "preparation", "payload", "payload_bytes", "final_digest", "head", "approval",
                "truncated_device", "truncated_inode", "truncated_bytes", "truncated_digest", "payload_ready"):
        require(before[key] == after[key], "FRAGMENT_STATE_CHANGED")
    require(after["present"] and after["fragment_final"] and not after["fragment_pending"] and
            after["preservation_approval"] == preservation and
            after["truncated_present"] == (action != "detach"), "FRAGMENT_STATE_CHANGED")
    expected = [row[:] for row in before["usage"]]
    if action == "preserve":
        require(not before["fragment_final"] and not before["fragment_pending"], "FRAGMENT_STATE_CHANGED")
        expected[0][2] += header + before["truncated_bytes"]
        expected[0][3] += 1
    elif action == "finish":
        require(before["fragment_pending"], "FRAGMENT_STATE_CHANGED")
        if before["fragment_final"]:
            expected[0][2] -= before["object_bytes"]
            expected[0][3] -= 1
    else:
        require(before["truncated_present"] and before["fragment_final"] and not before["fragment_pending"], "FRAGMENT_STATE_CHANGED")
        expected[0][2] -= before["truncated_bytes"]
        expected[0][3] -= 1
    if action != "preserve":
        require(all(before[k] == after[k] for k in ("object_device", "object_inode", "object_bytes", "object_digest")),
                "FRAGMENT_OBJECT_CHANGED")
    require(after["object_bytes"] == header + after["truncated_bytes"] and after["usage"] == expected, "FRAGMENT_ACCOUNTING_CHANGED")


def _fragment_recovery(repository, record, previous, kind, action, bridge, *, damage=False):
    family = "damage" if damage else "fragment"
    require(type(kind) is int and 0 <= kind <= 2 and action in ("preserve", "finish", "detach"), "FRAGMENT_ACTION")
    if previous is not None:
        host.contract._validate(previous, host.contract.DIGEST)
    host.contract._validate(record, host.REGISTRATION)
    require(record["repository"] == repository and record["producer"] == host._producer(), "RECOVERY_BINDING_CHANGED")
    common = Path(repository["common_dir"])
    if not damage:
        require(not os.path.lexists(common / host.DAMAGE_RECOVERY), "DAMAGE_RECOVERY_REQUIRED")
    require(not os.path.lexists(common / host.TOMBSTONE), "AUTHORITY_REVOKED")
    require(not any(p.name.startswith(host.PENDING) for p in common.iterdir()), "FRAGMENT_HOST_PENDING")
    require(not any(os.path.lexists(common / name) for name in (host.HOST_ALIAS_RECOVERY, host.HOST_PUBLICATION,
            host.NATIVE_RECOVERY, host.ALIAS_RECOVERY, host.ENVELOPE_RECOVERY)), "OTHER_RECOVERY_PENDING")
    target = _locator(record)
    locator = host._read_locator(repository)
    if locator is not None:
        require(locator["registration_sha256"] in (previous, target["registration_sha256"]), "REGISTRATION_PIN_MISMATCH")
        _same_identity(locator["record"], record)
    original_bytes = host.regular(common / host.PARTIAL_RECOVERY, private=True)
    if os.path.lexists(common / host.CHANGE):
        change = decode(host.regular(common / host.CHANGE, private=True))
        require(isinstance(change, dict) and set(change) == {"schema", "plan", "plan_sha256"} and
                change["schema"] == "golem.intent-authority-change.v1" and isinstance(change["plan"], dict) and
                set(change["plan"]) == {"schema", "before", "after"} and
                change["plan"]["schema"] == "golem.intent-authority-change-plan.v1" and
                sha(encoded(change["plan"])) == change["plan_sha256"], "CHANGE_INTENT_INVALID")
        _validate_locator(change["plan"]["before"], repository)
        require(change["plan"]["after"] == target and
                change["plan"]["before"]["registration_sha256"] == previous, "CHANGE_INTENT_INVALID")
        _same_identity(change["plan"]["before"]["record"], record)
    _host_recovery_record(original_bytes, host.PARTIAL_RECOVERY, target, repository)
    original = decode(original_bytes)
    require(original["plan"]["previous"] == previous and original["plan"]["kind"] == kind and
            original["plan"]["action"] == "quarantine", "ORIGINAL_QUARANTINE_APPROVAL_REQUIRED")
    current = _alias_native(target, previous, kind, bridge, partial=True, fragment=True, damage=damage)
    parent_digest = None
    if damage:
        parent_bytes = host.regular(common / host.FRAGMENT_RECOVERY, private=True)
        parent = decode(parent_bytes)
        require(encoded(parent) == parent_bytes and isinstance(parent, dict) and
                set(parent) == {"schema", "plan", "plan_sha256"} and
                parent["schema"] == "golem.intent-fragment-intent.v1" and isinstance(parent["plan"], dict) and
                sha(encoded(parent["plan"])) == parent["plan_sha256"], "DAMAGE_PARENT_INVALID")
        pp = parent["plan"]
        require(set(pp) == {"schema", "target", "previous", "kind", "action", "original_intent", "current"} and
                pp["schema"] == "golem.intent-fragment-plan.v1" and pp["target"] == target and
                pp["previous"] == previous and pp["kind"] == kind and pp["action"] == "preserve" and
                pp["original_intent"] == sha(original_bytes) and isinstance(pp["current"], dict), "DAMAGE_PARENT_INVALID")
        pc = pp["current"]
        parent_keys = set(current) - {"ancestor_device", "ancestor_inode", "ancestor_bytes", "ancestor_digest", "fragment_approval"}
        require(set(pc) == parent_keys and pc["schema"] == "golem.intent-fragment.v1" and
                pc["truncated_present"] is True and pc["fragment_final"] is False and pc["fragment_pending"] is False and
                pc["execution_authorized"] is False and current["fragment_approval"] == parent["plan_sha256"], "DAMAGE_PARENT_INVALID")
        for key in ("kind", "sequence", "device", "inode", "bytes", "operation", "request", "preparation", "payload",
                    "payload_bytes", "final_digest", "head", "committed", "payload_ready", "approval"):
            require(pc[key] == current[key], "DAMAGE_PARENT_CHANGED")
        for suffix in ("device", "inode", "bytes", "digest"):
            require(pc["truncated_" + suffix] == current["ancestor_" + suffix], "DAMAGE_ANCESTRY_CHANGED")
        parent_digest = sha(parent_bytes)
    base = original["plan"]["before"]
    require(current["approval"] == original["plan_sha256"], "FRAGMENT_ORIGINAL_APPROVAL")
    for key in ("kind", "sequence", "device", "inode", "bytes", "operation", "request", "preparation",
                "payload", "payload_bytes", "final_digest", "head", "committed", "payload_ready"):
        require(current[key] == base[key], "FRAGMENT_SOURCE_CHANGED")
    expected = [row[:] for row in base["usage"]]
    expected[0][3] += int(not base["directory_present"])
    count = int(current["fragment_final"]) + int(current["fragment_pending"])
    expected[0][2] += count * current["object_bytes"] + (current["truncated_bytes"] if current["truncated_present"] else 0)
    expected[0][3] += count + int(current["truncated_present"])
    if damage:
        expected[0][2] += current["ancestor_bytes"]
        expected[0][3] += 1
        parent_usage = [row[:] for row in base["usage"]]
        parent_usage[0][2] += current["ancestor_bytes"]
        parent_usage[0][3] += 1 + int(not base["directory_present"])
        require(pc["usage"] == parent_usage, "DAMAGE_PARENT_ACCOUNTING_CHANGED")
    require(current["usage"] == expected, "FRAGMENT_ACCOUNTING_CHANGED")
    marker = common / (host.DAMAGE_RECOVERY if damage else host.FRAGMENT_RECOVERY)
    intent = decode(host.regular(marker, private=True)) if os.path.lexists(marker) else None
    if intent is not None:
        require(isinstance(intent, dict) and set(intent) == {"schema", "plan", "plan_sha256"} and
                intent["schema"] == "golem.intent-" + family + "-intent.v1" and isinstance(intent["plan"], dict) and
                sha(encoded(intent["plan"])) == intent["plan_sha256"], "RECOVERY_INTENT_INVALID")
        prior = intent["plan"]
        plan_keys = {"schema", "target", "previous", "kind", "action", "original_intent", "current"}
        if damage:
            plan_keys.add("parent_intent")
            require(prior.get("parent_intent") == parent_digest, "DAMAGE_PARENT_CHANGED")
        require(set(prior) == plan_keys and
                prior["schema"] == "golem.intent-" + family + "-plan.v1" and prior["target"] == target and
                prior["previous"] == previous and prior["kind"] == kind and prior["original_intent"] == sha(original_bytes) and
                (prior["action"] == action or (prior["action"] == "preserve" and action == "finish")), "RECOVERY_INTENT_INVALID")
        require(isinstance(prior["current"], dict) and set(prior["current"]) == set(current), "RECOVERY_INTENT_INVALID")
        for key in ("kind", "sequence", "device", "inode", "bytes", "preparation", "operation", "request",
                    "payload", "payload_bytes", "final_digest", "head", "committed", "approval", "payload_ready",
                    "truncated_device", "truncated_inode", "truncated_bytes", "truncated_digest"):
            require(current[key] == prior["current"][key], "FRAGMENT_STATE_CHANGED")
        if damage:
            require(all(current[k] == prior["current"][k] for k in ("ancestor_device", "ancestor_inode", "ancestor_bytes",
                    "ancestor_digest", "fragment_approval")), "DAMAGE_ANCESTRY_CHANGED")
        if count:
            preserved_approval = intent["plan_sha256"] if prior["action"] == "preserve" else prior["current"]["preservation_approval"]
            require(current["preservation_approval"] == preserved_approval, "FRAGMENT_APPROVAL_CHANGED")
        if prior["action"] != "preserve":
            require(all(current[k] == prior["current"][k] for k in
                ("object_device", "object_inode", "object_bytes", "object_digest")), "FRAGMENT_OBJECT_CHANGED")
    if action == "preserve":
        require(intent is not None or (current["truncated_present"] and not count), "FRAGMENT_ALREADY_EXISTS")
        require(not current["fragment_pending"], "FRAGMENT_FINISH_REQUIRED")
    elif action == "finish":
        require(current["truncated_present"] and (current["fragment_pending"] or intent is not None), "FRAGMENT_FINISH_NOT_REQUIRED")
    else:
        require(current["fragment_final"] and not current["fragment_pending"] and
                (current["truncated_present"] or intent is not None), "FRAGMENT_DETACH_NOT_ALLOWED")
    plan = {"schema": "golem.intent-" + family + "-plan.v1", "target": target, "previous": previous,
            "kind": kind, "action": action, "original_intent": sha(original_bytes), "current": current}
    if damage:
        plan["parent_intent"] = parent_digest
    require(len(encoded(plan)) <= host.contract.LIMIT, "REGISTRATION_LIMIT")
    return plan, intent


def fragment_recovery_plan(root, record, kind, action, *, git, bridge, previous=None):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository):
        plan, _ = _fragment_recovery(repository, record, previous, kind, action, bridge)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def recover_fragment(root, record, kind, action, reviewed_plan_sha256, *, git, bridge, previous=None,
                     approve_local_owner=False):
    return _recover_preservation(root, record, kind, action, reviewed_plan_sha256, git=git, bridge=bridge,
        previous=previous, approve_local_owner=approve_local_owner, damage=False)


def damage_recovery_plan(root, record, kind, action, *, git, bridge, previous=None):
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository):
        plan, _ = _fragment_recovery(repository, record, previous, kind, action, bridge, damage=True)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def recover_damage(root, record, kind, action, reviewed_plan_sha256, *, git, bridge, previous=None,
                   approve_local_owner=False):
    return _recover_preservation(root, record, kind, action, reviewed_plan_sha256, git=git, bridge=bridge,
        previous=previous, approve_local_owner=approve_local_owner, damage=True)


def _recover_preservation(root, record, kind, action, reviewed_plan_sha256, *, git, bridge, previous,
                          approve_local_owner, damage):
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    family = "damage" if damage else "fragment"
    marker = host.DAMAGE_RECOVERY if damage else host.FRAGMENT_RECOVERY
    repository = host.repository_identity(root, git=git)
    with host._common_lock(repository, exclusive=True) as fd:
        plan, intent = _fragment_recovery(repository, record, previous, kind, action, bridge, damage=damage)
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        common = Path(repository["common_dir"])
        new = {"schema": "golem.intent-" + family + "-intent.v1", "plan": plan, "plan_sha256": reviewed_plan_sha256}
        prospective = intent or new
        require(len(encoded({"schema": "golem.intent-" + family + "-receipt.v1", "intent": prospective,
                             "approved": new, "after": plan["current"]})) + 512 <= host.contract.LIMIT, "REGISTRATION_LIMIT")
        if intent is None:
            intent = new
            host._publish(fd, marker, encoded(intent))
        else:
            _archive(fd, common, host.HISTORY + family + "-approval-" + reviewed_plan_sha256 + ".json", encoded(new))
        before = plan["current"]
        preservation = intent["plan_sha256"] if intent["plan"]["action"] == "preserve" else before["preservation_approval"]
        done = (action != "detach" and before["fragment_final"] and not before["fragment_pending"]) or (
            action == "detach" and not before["truncated_present"])
        after = before
        if not done:
            after = _alias_native(plan["target"], previous, kind, bridge, before["snapshot"], partial=True,
                fragment=True, fragment_action=action, approval=before["approval"], preservation=preservation, damage=damage)
            _fragment_transition(before, after, action, preservation, damage=damage)
        elif intent["plan"]["action"] == action:
            _fragment_transition(intent["plan"]["current"], after, action, preservation, damage=damage)
        else:
            _fragment_transition(intent["plan"]["current"], after, "preserve", preservation, damage=damage)
        receipt = {"schema": "golem.intent-" + family + "-receipt.v1", "intent": intent, "approved": new, "after": after}
        _archive(fd, common, host.HISTORY + family + "-recovery-" + sha(encoded(new)) + ".json", encoded(receipt))
        os.unlink(marker, dir_fd=fd)
        os.fsync(fd)
        return receipt
