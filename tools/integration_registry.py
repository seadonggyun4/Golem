"""Owner-invoked, private, local-cooperative project approval registry.

No client configuration, project file or Work is created or modified. Registry
approval is not native execution permission or authenticated human provenance.
"""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import sys
import uuid

import integration_contract as contract
from integration_contract import IntegrationError, decode, encoded, require, sha, validate


def real_path(value):
    path = Path(value)
    require(path.is_absolute() and str(path) == value and ".." not in path.parts, "PATH")
    for part in (path, *path.parents):
        require(not part.is_symlink(), "SYMLINK")
    require(path.resolve(strict=True) == path, "PATH")
    return path


def identity(path):
    info = real_path(str(path)).stat()
    require(stat.S_ISDIR(info.st_mode), "DIRECTORY_REQUIRED")
    return {"device": info.st_dev, "inode": info.st_ino}


def regular(path, limit=contract.LIMIT, private=False):
    path = real_path(str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit, "UNSAFE_FILE")
        if private:
            require(info.st_uid == os.getuid() and info.st_mode & 0o077 == 0, "PRIVATE_MODE")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        after = os.fstat(fd)
        require(len(data) <= limit and (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "FILE_CHANGED")
        return data
    finally:
        os.close(fd)


def file_pin(path):
    return {"path": str(real_path(str(path))), "sha256": sha(regular(path, 134217728))}


def check_project(project):
    validate("project", project)
    root, runtime = real_path(project["root"]), real_path(project["runtime_root"])
    require(identity(root) == project["identity"] and identity(runtime) == project["runtime_identity"], "ROOT_CHANGED")
    require(runtime.is_relative_to(root) and runtime != root, "PROJECT_SCOPE")
    require(runtime == root / ".golem", "PROJECT_SCOPE")
    for pin in [project["cli"], *project["sdk_pins"]]:
        require(file_pin(Path(pin["path"])) == pin, "PIN_MISMATCH")
    require(os.access(project["cli"]["path"], os.X_OK), "CLI_NOT_EXECUTABLE")
    for work in project["works"]:
        path = real_path(work["path"])
        require(path != runtime and path.is_relative_to(runtime), "WORK_SCOPE")
        require(identity(path) == work["identity"], "WORK_CHANGED")
        require(sha(regular(path / "events/00000001.evt")) == work["genesis_sha256"], "WORK_LINEAGE_CHANGED")
    return project


def describe(project_id, root, cli, sdk_files, works):
    """Pin explicit existing paths; never scan projects or invoke an executable."""
    root = real_path(str(root))
    runtime = root / ".golem"
    value = {"schema": "golem.integration-project.v1", "project_id": project_id,
             "root": str(root), "identity": identity(root), "runtime_root": str(runtime),
             "runtime_identity": identity(runtime), "cli": file_pin(cli),
             "sdk_pins": [file_pin(p) for p in sdk_files],
             "works": [{"work_id": work_id, "path": str(real_path(str(path))),
                        "identity": identity(path),
                        "genesis_sha256": sha(regular(Path(path) / "events/00000001.evt"))}
                       for work_id, path in works]}
    return check_project(value)


def producer():
    root = Path(__file__).resolve().parent
    return {name: sha(regular(root / name)) for name in
            ("integration_contract.py", "integration_registry.py", "integration_backend.py",
             "execution_record.py", "verify_agent.py")}


class Registry:
    def __init__(self, root):
        self.root = real_path(str(root))
        self.root_identity = identity(self.root)
        self._private(self.root)

    @staticmethod
    def _private(path):
        info = path.stat()
        require(info.st_uid == os.getuid() and info.st_mode & 0o077 == 0, "PRIVATE_MODE")

    @classmethod
    def create(cls, root, *, approve_local_owner=False):
        require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
        path = Path(root)
        require(path.is_absolute() and not path.exists() and not path.is_symlink(), "REGISTRY_EXISTS_OR_PATH")
        real_path(str(path.parent))
        path.mkdir(mode=0o700)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return cls(path)

    @contextmanager
    def locked(self, exclusive=False):
        require(identity(self.root) == self.root_identity, "REGISTRY_CHANGED")
        self._private(self.root)
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            require({"device": os.fstat(fd).st_dev, "inode": os.fstat(fd).st_ino} == self.root_identity, "REGISTRY_CHANGED")
            try:
                fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            except BlockingIOError:
                raise IntegrationError("REGISTRY_BUSY") from None
            yield
        finally:
            os.close(fd)

    def _pointer(self, project_id):
        contract._validate(project_id, contract.ID)
        return self.root / (project_id + ".current")

    def _load(self, project_id):
        path = self._pointer(project_id)
        if not path.exists() and not path.is_symlink():
            return None, None
        pointer_bytes = regular(path, private=True)
        pointer = decode(pointer_bytes)
        require(isinstance(pointer, dict) and set(pointer) == {"generation", "sha256"}, "REGISTRY_CORRUPT")
        contract._validate(pointer["generation"], contract.INTEGER)
        contract._validate(pointer["sha256"], contract.DIGEST)
        data = regular(self.root / f"{project_id}.{pointer['generation']}.{pointer['sha256']}.json", private=True)
        require(sha(data) == pointer["sha256"], "REGISTRY_CORRUPT")
        record = decode(data)
        require(isinstance(record, dict) and set(record) == {
            "schema", "generation", "state", "enrollment", "reviewed_plan_sha256",
            "producer", "registry", "registry_identity"}, "REGISTRY_CORRUPT")
        require(record["schema"] == "golem.integration-registry-record.v1" and
                record["generation"] == pointer["generation"] and
                type(record["generation"]) is int and record["state"] in ("ACTIVE", "REVOKED"), "REGISTRY_CORRUPT")
        validate("enrollment", record["enrollment"])
        require(record["registry"] == str(self.root) and record["registry_identity"] == self.root_identity,
                "REGISTRY_CHANGED")
        require(isinstance(record["producer"], dict) and set(record["producer"]) == set(producer()), "REGISTRY_CORRUPT")
        for pin in record["producer"].values():
            contract._validate(pin, contract.DIGEST)
        contract._validate(record["reviewed_plan_sha256"], contract.DIGEST)
        require(record["enrollment"]["project"]["project_id"] == project_id, "REGISTRY_CORRUPT")
        return record, sha(pointer_bytes)

    def _scope(self, project):
        root = Path(project["root"])
        require(not self.root.is_relative_to(root) and not root.is_relative_to(self.root), "REGISTRY_SCOPE")

    def _plan(self, enrollment, action):
        validate("enrollment", enrollment)
        project = enrollment["project"]
        if action == "approve":
            check_project(project)
        self._scope(project)
        current, before = self._load(project["project_id"])
        require(current is None or current["generation"] < contract.INTEGER["maximum"], "GENERATION_LIMIT")
        require(action in ("approve", "revoke"), "OPERATION")
        if action == "revoke":
            require(current is not None and current["enrollment"] == enrollment, "REGISTRY_CONFLICT")
        plan = {"schema": "golem.integration-plan.v1", "action": action,
                "registry": str(self.root), "registry_identity": self.root_identity,
                "before_sha256": before, "generation": 1 if current is None else current["generation"] + 1,
                "enrollment": enrollment, "producer": producer()}
        require(len(encoded(plan)) <= contract.LIMIT, "PLAN_LIMIT")
        return plan

    def plan(self, enrollment, action="approve"):
        with self.locked():
            plan = self._plan(enrollment, action)
            return {"plan": plan, "plan_sha256": sha(encoded(plan)), "native_state_changed": False}

    def _publish(self, path, data, replace=False):
        temporary = self.root / ("pending-" + uuid.uuid4().hex)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(fd)
            if replace:
                if path.exists() or path.is_symlink():
                    regular(path, private=True)
                os.replace(temporary, path)
            else:
                os.link(temporary, path, follow_symlinks=False)
                temporary.unlink()
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            os.close(fd)
            if temporary.exists():
                temporary.unlink()

    def apply(self, enrollment, reviewed_plan_sha256, *, action="approve", approve_local_owner=False):
        require(approve_local_owner is True, "OWNER_APPROVAL_REQUIRED")
        with self.locked(exclusive=True):
            plan = self._plan(enrollment, action)
            require(sha(encoded(plan)) == reviewed_plan_sha256, "PLAN_STALE")
            record = {"schema": "golem.integration-registry-record.v1", "generation": plan["generation"],
                      "state": "ACTIVE" if action == "approve" else "REVOKED", "enrollment": enrollment,
                      "reviewed_plan_sha256": reviewed_plan_sha256, "producer": plan["producer"],
                      "registry": str(self.root), "registry_identity": self.root_identity}
            data = encoded(record)
            require(len(data) <= contract.LIMIT, "REGISTRY_RECORD_LIMIT")
            project_id = enrollment["project"]["project_id"]
            path = self.root / f"{project_id}.{record['generation']}.{sha(data)}.json"
            if path.exists():
                require(regular(path, private=True) == data, "REGISTRY_CONFLICT")
            else:
                self._publish(path, data)
            self._publish(self._pointer(project_id), encoded({"generation": record["generation"],
                                                            "sha256": sha(data)}), replace=True)
            return record

    def authorize(self, binding, work_id, operation):
        """Caller holds the shared registry lock through the bounded native read."""
        validate("binding", binding)
        record, _ = self._load(binding["project_id"])
        require(record is not None and record["state"] == "ACTIVE", "PROJECT_APPROVAL_REQUIRED")
        require(record["generation"] == binding["generation"], "GRANT_STALE")
        require(record["producer"] == producer(), "PRODUCER_CHANGED")
        project = record["enrollment"]["project"]
        grant = next((g for g in record["enrollment"]["grants"] if
                      g["principal_id"] == binding["principal_id"] and g["client_id"] == binding["client_id"]), None)
        require(grant is not None, "PRINCIPAL_SCOPE")
        require(work_id in grant["work_ids"] and operation in grant["operations"], "GRANT_SCOPE")
        self._scope(project)
        check_project(project)
        return project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("schema", "describe", "init", "plan", "apply", "revoke-plan", "revoke", "read"))
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--kind", choices=tuple(contract.CONTRACTS))
    parser.add_argument("--reviewed-plan")
    parser.add_argument("--approve-local-owner", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "schema":
            result = contract.schema(args.kind)
        elif args.operation == "describe":
            require(args.input is not None, "INPUT_REQUIRED")
            value = validate("description", decode(regular(args.input, private=True)))
            result = describe(value["project_id"], value["root"], Path(value["cli"]),
                              [Path(p) for p in value["sdk_files"]],
                              [(w["work_id"], Path(w["path"])) for w in value["works"]])
        elif args.operation == "init":
            require(args.registry is not None, "REGISTRY_REQUIRED")
            Registry.create(args.registry, approve_local_owner=args.approve_local_owner)
            result = {"state": "INITIALIZED", "native_state_changed": False}
        else:
            require(args.registry is not None and args.input is not None, "INPUT_REQUIRED")
            registry = Registry(args.registry)
            value = decode(regular(args.input, private=True))
            if args.operation == "read":
                from integration_backend import read
                result = read(registry, value)
            elif args.operation in ("plan", "revoke-plan"):
                result = registry.plan(value, "revoke" if args.operation == "revoke-plan" else "approve")
            else:
                result = registry.apply(value, args.reviewed_plan, action="revoke" if args.operation == "revoke" else "approve",
                                        approve_local_owner=args.approve_local_owner)
        sys.stdout.buffer.write(encoded(result))
    except (IntegrationError, OSError, ValueError) as error:
        code = error.code if isinstance(error, IntegrationError) else "IO_OR_CONTRACT_ERROR"
        sys.stdout.buffer.write(encoded({"state": "BLOCKED", "code": code,
            "next_operation": "REVIEW_OWNER_CONFIGURATION_OR_NATIVE_EVIDENCE", "automatic_retry_allowed": False,
            "evidence_path": getattr(error, "evidence_path", None)}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
