"""Explicit D01 enrollment, read-only handoff and approved proposal storage.

Reuses integration registry path, inode and pin checks. A descriptor is an
observation, never owner approval or a substitute for native owner flock.
"""
from pathlib import Path
from contextlib import contextmanager, ExitStack
import fcntl
import os
import stat
import subprocess
import uuid
import select
import tempfile
import time

import integration_contract as contract
from integration_contract import require, encoded, decode, sha, IntegrationError
from integration_registry import file_pin, identity, real_path, regular

LOCATOR = "golem-intent-authority.json"
PENDING = "golem-intent-authority.pending-"
TOMBSTONE = "golem-intent-authority.revoked.json"
CHANGE = "golem-intent-authority.change.json"
NATIVE_RECOVERY = "golem-intent-authority.native-recovery.json"
ALIAS_RECOVERY = "golem-intent-authority.alias-recovery.json"
PARTIAL_RECOVERY = "golem-intent-authority.partial-recovery.json"
ENVELOPE_RECOVERY = "golem-intent-authority.envelope-recovery.json"
HOST_ALIAS_RECOVERY = "golem-intent-authority.host-alias-recovery.json"
HOST_PUBLICATION = "golem-intent-authority.host-publication.json"
HOST_TERMINAL = "golem-intent-authority.host-terminal.json"
HOST_FINAL = "golem-intent-authority.host-final.json"
FRAGMENT_RECOVERY = "golem-intent-authority.fragment-recovery.json"
DAMAGE_RECOVERY = "golem-intent-authority.damage-recovery.json"
HISTORY = "golem-intent-authority.history-"
REPOSITORY = contract.obj({
    "root": contract.PATH, "root_identity": contract.IDENTITY,
    "common_dir": contract.PATH, "common_identity": contract.IDENTITY,
    "worktree_roots": contract.array(contract.PATH, maximum=1024), "git": contract.PIN,
})
AUTHORITY = contract.obj({"path": contract.PATH, "identity": contract.IDENTITY,
                          "pins": contract.array(contract.PIN, maximum=32)})
REGISTRATION = contract.obj({"schema": contract.enum("golem.intent-authority-registration.v1"),
    "repository": REPOSITORY, "authority": AUTHORITY,
    "producer": contract.obj({name: contract.DIGEST for name in
        ("intent_authority.py", "intent_authority_lifecycle.py", "integration_registry.py", "integration_contract.py", "verify_agent.py")})})
LOCATOR_SCHEMA = contract.obj({"schema": contract.enum("golem.intent-authority-locator.v1"),
                              "record": REGISTRATION, "registration_sha256": contract.DIGEST})
LEGACY_REGISTRATION = contract.obj({**REGISTRATION["properties"], "producer": contract.obj({
    name: contract.DIGEST for name in
    ("intent_authority.py", "integration_registry.py", "integration_contract.py", "verify_agent.py")})})
LEGACY_LOCATOR_SCHEMA = contract.obj({**LOCATOR_SCHEMA["properties"], "record": LEGACY_REGISTRATION})


def validate_locator(value):
    # Explicit legacy shape is readable for reviewed reapproval, never silently
    # upgraded or accepted as the current producer by authorized_root().
    producer = value.get("record", {}).get("producer", {}) if isinstance(value, dict) and isinstance(value.get("record"), dict) else {}
    legacy = isinstance(producer, dict) and set(producer) == set(LEGACY_REGISTRATION["properties"]["producer"]["required"])
    contract._validate(value, LEGACY_LOCATOR_SCHEMA if legacy else LOCATOR_SCHEMA)


GIT_ENVIRONMENT = {
    "PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
}


def repository_identity(root, *, git):
    """Resolve linked worktrees to one common-dir using a fixed read-only call.

    git is a trusted host dependency, not a model-selected executable. Inherited
    GIT_DIR/worktree/config/pager variables are deliberately not forwarded.
    """
    root = real_path(str(root))
    root_identity = identity(root)
    executable = file_pin(git)
    result = subprocess.run(
        [str(git), "-C", str(root), "rev-parse", "--path-format=absolute",
         "--show-toplevel", "--git-common-dir"],
        env=GIT_ENVIRONMENT, stdin=subprocess.DEVNULL, capture_output=True,
        timeout=10, check=False,
    )
    require(result.returncode == 0, "GIT_IDENTITY_UNAVAILABLE")
    require(len(result.stdout) <= 32768 and len(result.stderr) <= 32768, "GIT_IDENTITY_LIMIT")
    lines = result.stdout.decode("utf-8", errors="strict").splitlines()
    require(len(lines) == 2 and all(lines), "GIT_IDENTITY_FORMAT")
    top, common = (real_path(value) for value in lines)
    require(top == root, "REPOSITORY_ROOT_REQUIRED")
    worktrees = subprocess.run(
        [str(git), "-C", str(root), "worktree", "list", "--porcelain", "-z"],
        env=GIT_ENVIRONMENT, stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=False,
    )
    require(worktrees.returncode == 0 and len(worktrees.stdout) <= 262144, "WORKTREE_IDENTITY_UNAVAILABLE")
    roots = sorted({str(real_path(item[9:].decode("utf-8", errors="strict")))
                    for item in worktrees.stdout.split(b"\0") if item.startswith(b"worktree ")})
    require(str(root) in roots, "WORKTREE_IDENTITY_UNAVAILABLE")
    require(identity(root) == root_identity and file_pin(git) == executable, "GIT_IDENTITY_CHANGED")
    return {"root": str(root), "root_identity": root_identity,
            "common_dir": str(common), "common_identity": identity(common),
            "worktree_roots": roots, "git": executable}


def authority_identity(authority, repository, pins):
    """Observe an explicitly selected existing private directory and dependencies."""
    authority = real_path(str(authority))
    info = authority.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and
            info.st_mode & 0o077 == 0, "PRIVATE_AUTHORITY_REQUIRED")
    for value in (*repository["worktree_roots"], repository["common_dir"]):
        path = real_path(value)
        require(not authority.is_relative_to(path) and not path.is_relative_to(authority), "AUTHORITY_SCOPE")
    require(bool(pins), "AUTHORITY_PINS_REQUIRED")
    observed = [file_pin(Path(path)) for path in pins]
    require(len({pin["path"] for pin in observed}) == len(observed), "DUPLICATE_PIN")
    return {"path": str(authority), "identity": identity(authority), "pins": observed}


def verify_observation(repository, authority):
    """Reobserve exact root/common-dir/authority/pins. No automatic repinning."""
    require(repository_identity(Path(repository["root"]), git=Path(repository["git"]["path"])) == repository,
            "REPOSITORY_IDENTITY_CHANGED")
    require(authority_identity(Path(authority["path"]), repository,
                               [Path(pin["path"]) for pin in authority["pins"]]) == authority,
            "AUTHORITY_IDENTITY_OR_PIN_CHANGED")


def _producer():
    here = Path(__file__).resolve().parent
    return {name: sha(regular(here / name)) for name in
            ("intent_authority.py", "intent_authority_lifecycle.py", "integration_registry.py", "integration_contract.py", "verify_agent.py")}


@contextmanager
def _common_lock(repository, *, exclusive=False, terminal_recovery=False, final_recovery=False):
    common = real_path(repository["common_dir"])
    fd = os.open(common, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require({"device": info.st_dev, "inode": info.st_ino} == repository["common_identity"], "COMMON_DIR_CHANGED")
        require(info.st_uid == os.getuid() and info.st_mode & 0o022 == 0, "COMMON_DIR_OWNER_REQUIRED")
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise IntegrationError("AUTHORITY_REGISTRATION_BUSY") from None
        require(identity(common) == repository["common_identity"], "COMMON_DIR_CHANGED")
        require(terminal_recovery or not os.path.lexists(common / HOST_TERMINAL), "HOST_TERMINAL_REQUIRED")
        require(final_recovery or not os.path.lexists(common / HOST_FINAL), "HOST_FINAL_REQUIRED")
        yield fd
        require(identity(common) == repository["common_identity"], "COMMON_DIR_CHANGED")
    finally:
        os.close(fd)


def _load(repository):
    common = real_path(repository["common_dir"])
    # Even a malformed marker must never reactivate a revoked registration.
    require(not os.path.lexists(common / TOMBSTONE), "AUTHORITY_REVOKED")
    require(not os.path.lexists(common / CHANGE), "LOCATOR_COMMIT_UNKNOWN")
    require(not os.path.lexists(common / NATIVE_RECOVERY), "LOCATOR_COMMIT_UNKNOWN")
    require(not os.path.lexists(common / ALIAS_RECOVERY), "LOCATOR_COMMIT_UNKNOWN")
    require(not os.path.lexists(common / PARTIAL_RECOVERY), "LOCATOR_COMMIT_UNKNOWN")
    require(not os.path.lexists(common / ENVELOPE_RECOVERY), "LOCATOR_COMMIT_UNKNOWN")
    require(not os.path.lexists(common / HOST_ALIAS_RECOVERY), "LOCATOR_COMMIT_UNKNOWN")
    require(not os.path.lexists(common / HOST_PUBLICATION), "LOCATOR_COMMIT_UNKNOWN")
    require(not os.path.lexists(common / HOST_TERMINAL), "LOCATOR_COMMIT_UNKNOWN")
    require(not os.path.lexists(common / HOST_FINAL), "LOCATOR_COMMIT_UNKNOWN")
    require(not os.path.lexists(common / FRAGMENT_RECOVERY), "LOCATOR_COMMIT_UNKNOWN")
    require(not os.path.lexists(common / DAMAGE_RECOVERY), "LOCATOR_COMMIT_UNKNOWN")
    # Uncertain registration is preserved for explicit recovery, never retried.
    require(not any(p.name.startswith(PENDING) for p in common.iterdir()), "LOCATOR_COMMIT_UNKNOWN")
    return _read_locator(repository)


@contextmanager
def _authority_owner_lock(record):
    """Cooperative authority lock for host-only changes; never opens native files."""
    contract._validate(record, REGISTRATION)
    authority = record["authority"]
    verify_observation(record["repository"], authority)
    fd = os.open(authority["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require({"device": info.st_dev, "inode": info.st_ino} == authority["identity"] and
                info.st_uid == os.getuid() and info.st_mode & 0o077 == 0, "AUTHORITY_CHANGED")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise IntegrationError("AUTHORITY_OWNER_BUSY") from None
        verify_observation(record["repository"], authority)
        yield fd
    finally:
        os.close(fd)


def _read_locator(repository):
    path = Path(repository["common_dir"]) / LOCATOR
    if not path.exists() and not path.is_symlink():
        return None
    value = decode(regular(path, private=True))
    validate_locator(value)
    require(sha(encoded(value["record"])) == value["registration_sha256"], "LOCATOR_DIGEST_MISMATCH")
    require(value["record"]["repository"]["common_dir"] == repository["common_dir"] and
            value["record"]["repository"]["common_identity"] == repository["common_identity"], "COMMON_DIR_CHANGED")
    return value


def _revocation(repository, registration_sha256):
    contract._validate(registration_sha256, contract.DIGEST)
    value = _load(repository)
    require(value is not None, "AUTHORITY_REGISTRATION_REQUIRED")
    require(value["registration_sha256"] == registration_sha256, "REGISTRATION_PIN_MISMATCH")
    record = value["record"]
    require(record["producer"] == _producer(), "PRODUCER_CHANGED")
    require(record["repository"]["git"] == repository["git"], "GIT_PIN_MISMATCH")
    verify_observation(record["repository"], record["authority"])
    plan = {"schema": "golem.intent-authority-revoke-plan.v1",
            "registration_sha256": registration_sha256,
            "locator_sha256": sha(encoded(value)), "repository": repository,
            "authority": record["authority"], "reactivation_allowed": False}
    return value, plan


def revocation_plan(root, registration_sha256, *, git):
    """Observe a revocation plan; never remove or rewrite registration evidence."""
    repository = repository_identity(root, git=git)
    with _common_lock(repository):
        _, plan = _revocation(repository, registration_sha256)
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def revoke(root, registration_sha256, reviewed_plan_sha256, *, git, approve_local_owner=False):
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    contract._validate(reviewed_plan_sha256, contract.DIGEST)
    repository = repository_identity(root, git=git)
    with _common_lock(repository, exclusive=True) as common_fd:
        value, plan = _revocation(repository, registration_sha256)
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        authority = value["record"]["authority"]
        fd = os.open(authority["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            require({"device": info.st_dev, "inode": info.st_ino} == authority["identity"], "AUTHORITY_CHANGED")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise IntegrationError("AUTHORITY_OWNER_BUSY") from None
            verify_observation(value["record"]["repository"], authority)
            require(_load(repository) == value, "LOCATOR_CHANGED")
            marker = {"schema": "golem.intent-authority-revoked.v1", "plan": plan,
                      "plan_sha256": reviewed_plan_sha256}
            _publish(common_fd, TOMBSTONE, encoded(marker))
            return marker
        finally:
            os.close(fd)


def _publish(common_fd, destination, data):
    require(len(data) <= contract.LIMIT, "REGISTRATION_LIMIT")
    pending = PENDING + uuid.uuid4().hex
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600, dir_fd=common_fd)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
        os.fchmod(fd, 0o400)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.link(pending, destination, src_dir_fd=common_fd, dst_dir_fd=common_fd, follow_symlinks=False)
    os.fsync(common_fd)
    os.unlink(pending, dir_fd=common_fd)
    os.fsync(common_fd)


def registration_plan(root, authority, pins, *, git):
    repository = repository_identity(root, git=git)
    with _common_lock(repository):
        observed = authority_identity(authority, repository, pins)
        record = {"schema": "golem.intent-authority-registration.v1", "repository": repository,
                  "authority": observed, "producer": _producer()}
        contract._validate(record, REGISTRATION)
        require(len(encoded(record)) <= contract.LIMIT, "REGISTRATION_LIMIT")
        existing = _load(repository)
        require(existing is None or existing["record"] == record, "AUTHORITY_CONFLICT")
        plan = {"schema": "golem.intent-authority-plan.v1", "record": record,
                "before_sha256": None if existing is None else sha(encoded(existing))}
        return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def register(root, authority, pins, reviewed_plan_sha256, *, git, bridge, approve_local_owner=False):
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    contract._validate(reviewed_plan_sha256, contract.DIGEST)
    repository = repository_identity(root, git=git)
    with _common_lock(repository, exclusive=True) as common_fd:
        # Build the reviewed snapshot under the registration lock, without
        # reacquiring that lock through registration_plan().
        record = {"schema": "golem.intent-authority-registration.v1", "repository": repository,
                  "authority": authority_identity(authority, repository, pins), "producer": _producer()}
        contract._validate(record, REGISTRATION)
        existing = _load(repository)
        require(existing is None or existing["record"] == record, "AUTHORITY_CONFLICT")
        plan = {"schema": "golem.intent-authority-plan.v1", "record": record,
                "before_sha256": None if existing is None else sha(encoded(existing))}
        require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
        require(file_pin(bridge) in record["authority"]["pins"], "NATIVE_BRIDGE_PIN_REQUIRED")
        value = {"schema": "golem.intent-authority-locator.v1", "record": record,
                 "registration_sha256": sha(encoded(record))}
        data = encoded(value)
        require(len(data) <= contract.LIMIT, "REGISTRATION_LIMIT")
        verify_observation(repository, record["authority"])
        root_fd = os.open(record["authority"]["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(root_fd)
            require({"device": info.st_dev, "inode": info.st_ino} == record["authority"]["identity"], "AUTHORITY_CHANGED")
            result = subprocess.run([str(bridge), "--inspect-fd" if existing is not None else "--register-fd",
                                     str(root_fd), value["registration_sha256"]],
                                    input=encoded(record), pass_fds=(root_fd,), capture_output=True, timeout=15,
                                    env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}, check=False)
            require(result.returncode == 0, "NATIVE_REGISTRATION_BLOCKED")
            require(len(result.stdout) <= contract.LIMIT, "NATIVE_OUTPUT_LIMIT")
            observed = decode(result.stdout)
            require(isinstance(observed, dict) and
                    observed.get("schema") == "golem.intent-journal-inspection.v1" and
                    observed.get("execution_authorized") is False and observed.get("pending") is False and
                    observed.get("registration_sha256") == value["registration_sha256"], "NATIVE_CONTRACT")
        finally:
            os.close(root_fd)
        verify_observation(repository, record["authority"])
        if existing is not None:
            return existing
        _publish(common_fd, LOCATOR, data)
        return value


@contextmanager
def authorized_root(root, registration_sha256, *, git):
    """Hold shared locator lock through native owner-lock acquisition/use.

    Read/observation capability ONLY, not a D02 write approval or native guard.
    The expected digest comes from the host's approved registration binding.
    """
    contract._validate(registration_sha256, contract.DIGEST)
    repository = repository_identity(root, git=git)
    with _common_lock(repository):
        value = _load(repository)
        require(value is not None, "AUTHORITY_REGISTRATION_REQUIRED")
        require(value["registration_sha256"] == registration_sha256, "REGISTRATION_PIN_MISMATCH")
        record = value["record"]
        require(record["producer"] == _producer(), "PRODUCER_CHANGED")
        require(record["repository"]["git"] == repository["git"], "GIT_PIN_MISMATCH")
        verify_observation(record["repository"], record["authority"])
        # Also check the requesting linked worktree, not just the enrolled root.
        authority = authority_identity(Path(record["authority"]["path"]), repository,
                                       [Path(p["path"]) for p in record["authority"]["pins"]])
        require(authority == record["authority"], "AUTHORITY_IDENTITY_OR_PIN_CHANGED")
        fd = os.open(authority["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(fd)
            require({"device": info.st_dev, "inode": info.st_ino} == authority["identity"], "AUTHORITY_CHANGED")
            yield fd, record
            require(_load(repository) == value, "LOCATOR_CHANGED")
            verify_observation(record["repository"], authority)
            require(repository_identity(root, git=git) == repository, "REPOSITORY_IDENTITY_CHANGED")
        finally:
            os.close(fd)


def native_inspect(root, registration_sha256, *, git, bridge):
    """Use pinned native journal inspector with inherited fd, never a root path."""
    bridge = real_path(str(bridge))
    with authorized_root(root, registration_sha256, git=git) as (fd, record):
        require(file_pin(bridge) in record["authority"]["pins"], "NATIVE_BRIDGE_PIN_REQUIRED")
        result = subprocess.run([str(bridge), "--inspect-fd", str(fd), registration_sha256], pass_fds=(fd,),
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=15,
                                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}, check=False)
        require(result.returncode == 0, "NATIVE_INSPECTION_BLOCKED")
        require(len(result.stdout) <= contract.LIMIT, "NATIVE_OUTPUT_LIMIT")
        value = decode(result.stdout)
        require(isinstance(value, dict) and value.get("schema") == "golem.intent-journal-inspection.v1"
                and value.get("execution_authorized") is False and value.get("pending") is False
                and value.get("registration_sha256") == registration_sha256, "NATIVE_CONTRACT")
        return value


def _object_store_snapshot(root, registration_sha256, *, git, bridge):
    """Called under common-dir lock; never turns authorized_root into a writer."""
    contract._validate(registration_sha256, contract.DIGEST)
    repository = repository_identity(root, git=git)
    value = _load(repository)
    require(value is not None, "AUTHORITY_REGISTRATION_REQUIRED")
    require(value["registration_sha256"] == registration_sha256, "REGISTRATION_PIN_MISMATCH")
    record = value["record"]
    require(record["producer"] == _producer(), "PRODUCER_CHANGED")
    require(record["repository"]["git"] == repository["git"], "GIT_PIN_MISMATCH")
    verify_observation(record["repository"], record["authority"])
    observed = authority_identity(Path(record["authority"]["path"]), repository,
                                  [Path(p["path"]) for p in record["authority"]["pins"]])
    require(observed == record["authority"], "AUTHORITY_IDENTITY_OR_PIN_CHANGED")
    require(file_pin(bridge) in observed["pins"], "NATIVE_BRIDGE_PIN_REQUIRED")
    return {"registration": value, "requesting_repository": repository, "bridge": file_pin(bridge)}


def _object_store_plan(snapshot, operation, request, expected_sequence, expected_head, baseline, sources):
    for digest in (operation, request, expected_head):
        contract._validate(digest, contract.DIGEST)
    require(type(expected_sequence) is int and 0 <= expected_sequence < 2**64, "SEQUENCE_INVALID")
    require(type(baseline) is bytes and 0 < len(baseline) <= contract.LIMIT, "BASELINE_LIMIT")
    require(type(sources) is tuple and 0 < len(sources) <= 4096, "SOURCE_LIMIT")
    total = 0
    def item(data):
        return {"byte_length": len(data), "sha256": sha(data)}
    rows = []
    for source in sources:
        require(type(source) is tuple and len(source) == 2, "SOURCE_INPUT_INVALID")
        control, text = source
        require(type(control) is bytes and 0 < len(control) <= contract.LIMIT, "SOURCE_CONTROL_LIMIT")
        require(type(text) is bytes and 0 < len(text) <= 16 * 1024**2, "SOURCE_BODY_LIMIT")
        total += len(text)
        require(total <= 64 * 1024**2, "SOURCE_SET_LIMIT")
        rows.append({"control": item(control), "text": item(text)})
    plan = {"schema": "golem.intent-object-store-plan.v1", "snapshot": snapshot,
            "operation_id": operation, "request_digest": request, "expected_sequence": expected_sequence,
            "expected_head": expected_head, "baseline": item(baseline), "sources": rows,
            "lane": "intake", "execution_authorized": False}
    require(len(encoded(plan)) <= contract.LIMIT, "PLAN_LIMIT")
    return {"plan": plan, "plan_sha256": sha(encoded(plan))}


def object_store_plan(root, registration_sha256, operation, request, expected_sequence, expected_head,
                      baseline, sources, *, git, bridge):
    """Review-only exact input/pin binding, not semantic approval or a write."""
    bridge = real_path(str(bridge))
    repository = repository_identity(root, git=git)
    with _common_lock(repository):
        snapshot = _object_store_snapshot(root, registration_sha256, git=git, bridge=bridge)
        require(snapshot["requesting_repository"] == repository, "REPOSITORY_IDENTITY_CHANGED")
        return _object_store_plan(snapshot, operation, request, expected_sequence, expected_head, baseline, sources)


def store_objects(root, registration_sha256, operation, request, expected_sequence, expected_head,
                  baseline, sources, reviewed_plan_sha256, *, git, bridge, approve_local_owner=False):
    """Store an intake proposal only, with EX locator lock and per-phase host guard.

    A bridge interruption has an unknown commit outcome: never retry or clean up
    authority files here. The native inspector remains the source of truth.
    """
    require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
    contract._validate(reviewed_plan_sha256, contract.DIGEST)
    bridge = real_path(str(bridge))
    repository = repository_identity(root, git=git)
    with _common_lock(repository, exclusive=True), ExitStack() as stack:
        snapshot = _object_store_snapshot(root, registration_sha256, git=git, bridge=bridge)
        require(snapshot["requesting_repository"] == repository, "REPOSITORY_IDENTITY_CHANGED")
        plan = _object_store_plan(snapshot, operation, request, expected_sequence, expected_head, baseline, sources)
        require(plan["plan_sha256"] == reviewed_plan_sha256, "PLAN_STALE")
        authority = snapshot["registration"]["record"]["authority"]
        root_fd = os.open(authority["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        stack.callback(os.close, root_fd)
        def guard():
            require(_object_store_snapshot(root, registration_sha256, git=git, bridge=bridge) == snapshot, "PLAN_STALE")
            info = os.fstat(root_fd)
            require({"device": info.st_dev, "inode": info.st_ino} == authority["identity"], "AUTHORITY_CHANGED")
        guard()
        inputs = []
        for data in (baseline, *(part for source in sources for part in source)):
            file = stack.enter_context(tempfile.TemporaryFile())
            file.write(data)
            file.flush()
            inputs.append(file.fileno())
        child_read, parent_write = os.pipe()
        parent_read, child_write = os.pipe()
        stack.callback(os.close, parent_write)
        stack.callback(os.close, parent_read)
        output = stack.enter_context(tempfile.TemporaryFile())
        errors = stack.enter_context(tempfile.TemporaryFile())
        args = [str(bridge), "--store-objects-fd", str(root_fd), registration_sha256, operation, request,
                str(expected_sequence), expected_head, str(child_read), str(child_write), *map(str, inputs)]
        try:
            process = subprocess.Popen(args, pass_fds=(root_fd, child_read, child_write, *inputs),
                stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"})
        finally:
            os.close(child_read)
            os.close(child_write)
        try:
            deadline = time.monotonic() + 120
            requests = 0
            while True:
                remaining = deadline - time.monotonic()
                require(remaining > 0, "OBJECT_STORE_COMMIT_UNKNOWN")
                ready, _, _ = select.select([parent_read], [], [], remaining)
                require(bool(ready), "OBJECT_STORE_COMMIT_UNKNOWN")
                message = os.read(parent_read, 1)
                if not message:
                    break
                requests += 1
                require(message == b"G" and requests <= 4, "NATIVE_GUARD_PROTOCOL")
                guard()
                require(os.write(parent_write, b"A") == 1, "OBJECT_STORE_COMMIT_UNKNOWN")
            process.wait(timeout=max(0.01, deadline - time.monotonic()))
            require(process.returncode == 0, "OBJECT_STORE_BLOCKED_OR_COMMIT_UNKNOWN")
            guard()
            output.seek(0)
            data = output.read(contract.LIMIT + 1)
            require(len(data) <= contract.LIMIT, "NATIVE_OUTPUT_LIMIT")
            result = decode(data)
            require(isinstance(result, dict) and result.get("schema") == "golem.intent-object-store-result.v1"
                    and result.get("execution_authorized") is False
                    and result.get("registration_sha256") == registration_sha256, "NATIVE_CONTRACT")
            require(type(result.get("sequence")) is int and result["sequence"] > 0
                    and type(result.get("replayed")) is bool, "NATIVE_CONTRACT")
            contract._validate(result.get("event_digest"), contract.DIGEST)
            return {**result, "reviewed_plan_sha256": reviewed_plan_sha256}
        except (IntegrationError, OSError, subprocess.TimeoutExpired) as error:
            # Once spawned, even a failed final host check may follow a commit.
            # Preserve the precise cause, but never imply rollback/no effects.
            cause = error.code if isinstance(error, IntegrationError) else type(error).__name__
            raise IntegrationError("OBJECT_STORE_COMMIT_UNKNOWN:" + cause) from error
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
