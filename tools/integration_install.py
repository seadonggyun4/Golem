"""Owner-only client configuration and empty-project bootstrap transactions."""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import sys
import uuid

import execution_record as records
import integration_backend as backend
import integration_config as config
import integration_contract as c
import integration_registry as r
import integration_transfer as transfer
import integration_reload_probe as runtime_adapter
import integration_update as updates

RUNTIME = c.obj({"python": c.PIN, "sdk_root": c.PATH, "sdk_identity": c.IDENTITY,
                 "files": {"type": ["object"], "minProperties": 1, "maxProperties": 256,
                           "propertyNames": c.PATH, "additionalProperties": c.DIGEST}})
TARGET = c.obj({"client": c.enum(*config.CLIENTS), "config": c.PATH, "server_name": c.ID,
                "runtime": RUNTIME, "transfer_policy": c.PIN})
STOPPED = {"const": "STOPPED_OWNER_ATTESTED"}
REFERENCE = c.obj({"installation_id": c.ID})
INSTALL = c.obj({"installation_id": c.ID, "clients_stopped": STOPPED, "targets": c.array(TARGET, 8)})
REMOVE = c.obj({"installation_id": c.ID, "clients_stopped": STOPPED})
BOOTSTRAP = c.obj({"bootstrap_id": c.ID, "project_id": c.ID, "root": c.PATH})
SPECS = {"install": INSTALL, "remove": REMOVE, "bootstrap": BOOTSTRAP}
MODULES = ("integration_install.py", "integration_config.py", "integration_launch.py", "integration_hook_contract.py")


def producer():
    root = Path(__file__).resolve().parent
    return {**updates.producer(), **{name: c.sha(r.regular(root / name)) for name in MODULES}}


def parent(path):
    c.require(path.is_absolute() and path.name not in ("", ".", "..") and
              str(path) == str(path.parent / path.name), "PATH")
    r.real_path(str(path.parent))
    info = path.parent.stat()
    c.require(info.st_uid == os.getuid() and not info.st_mode & 0o022, "CONFIG_PARENT_UNSAFE")
    return r.identity(path.parent)


def snapshot(path):
    parent(path)
    if not path.exists() and not path.is_symlink():
        return None
    data = r.regular(path)
    info = path.stat()
    c.require(info.st_uid == os.getuid() and not info.st_mode & 0o7133, "CONFIG_FILE_UNSAFE")
    return {"sha256": c.sha(data), "device": info.st_dev, "inode": info.st_ino,
            "mode": stat.S_IMODE(info.st_mode), "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns}


@contextmanager
def directory_lock(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise c.IntegrationError("CONFIG_BUSY") from None
        yield
    finally:
        os.close(fd)


def retain(path, data):
    if path.exists() or path.is_symlink():
        c.require(r.regular(path, private=True) == data, "INSTALL_RECORD_CONFLICT")
    else:
        records.save(path, data)


def mkdir(path):
    path.mkdir(mode=0o700)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish_config(path, before, data):
    """Cooperating installers serialize; last-moment drift is never overwritten."""
    c.require(snapshot(path) == before, "CONFIG_DRIFT")
    temporary = path.parent / (".golem-config-" + uuid.uuid4().hex)
    try:
        records.save(temporary, data)
        os.chmod(temporary, before["mode"] if before else 0o600)
        fd = os.open(temporary, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        c.require(snapshot(path) == before, "CONFIG_DRIFT")
        if before is None:
            # Link publishes without replacing a competing newly created file.
            os.link(temporary, path, follow_symlinks=False)
            temporary.unlink()
        else:
            os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary.exists():
            temporary.unlink()


class Installer:
    def __init__(self, state):
        self.registry = r.Registry(state)
        self.root = self.registry.root

    def directory(self, identifier, *, bootstrap=False):
        c._validate(identifier, c.ID)
        return self.root / (("bootstrap-" if bootstrap else "installation-") + identifier)

    def stored(self, identifier):
        directory = self.directory(identifier)
        value = c.decode(r.regular(directory / "plan.json", private=True))
        c.require(value["operation"] == "install" and value["request"]["installation_id"] == identifier and
                  value["state"] == str(self.root) and value["state_identity"] == self.registry.root_identity,
                  "INSTALL_RECORD_CONFLICT")
        c.require(c.decode(r.regular(directory / "committed.json", private=True))["plan_sha256"] ==
                  c.sha(c.encoded(value)), "INSTALL_RECORD_CONFLICT")
        return directory, value

    @staticmethod
    def original(directory, plan, index):
        data = r.regular(directory / f"before-{index}.bin", private=True)
        previous = plan["facts"]["targets"][index]["before"]
        item = plan["request"]["targets"][index]
        expected = previous["sha256"] if previous else c.sha(b"" if item["client"] == "codex-config" else b"{}\n")
        c.require(c.sha(data) == expected, "INSTALL_BACKUP_CORRUPT")
        return data

    def launch(self, draft, index):
        item = draft["targets"][index]
        runtime_adapter.validate_runtime(item["runtime"])
        policy = transfer.Transfer(Path(item["transfer_policy"]["path"]), item["transfer_policy"]["sha256"],
                                   approve_data_transfer=True)
        c.require(not self.root.is_relative_to(policy.registry.root) and
                  not policy.registry.root.is_relative_to(self.root), "INSTALL_STATE_SCOPE")
        c.require(not Path(item["config"]).is_relative_to(policy.registry.root), "CONFIG_NATIVE_SCOPE")
        c.require(policy.value["destination"] in ("LOCAL_HOST", "MODEL_SERVICE"), "TRANSFER_POLICY_SCOPE")
        with policy.registry.locked():
            for scope in policy.current()["scopes"]:
                for work_id in scope["work_ids"]:
                    project = policy.registry.authorize(scope["binding"], work_id, "record")
                    root = Path(project["root"])
                    c.require(not self.root.is_relative_to(root) and not root.is_relative_to(self.root), "INSTALL_STATE_SCOPE")
                    c.require(not Path(item["config"]).is_relative_to(Path(project["runtime_root"])), "CONFIG_NATIVE_SCOPE")
        value = {"schema": "golem.integration-launch.v1", "state": str(self.root),
                 "state_identity": self.registry.root_identity, "installation_id": draft["installation_id"],
                 "index": index, "target": item, "producer": producer()}
        path = self.directory(draft["installation_id"]) / f"launch-{index}.json"
        command = runtime_adapter.command(Path(__file__).resolve().with_name("integration_launch.py"),
            ["--launch", str(path), "--reviewed-launch-sha256", c.sha(c.encoded(value))], item["runtime"])
        c.require(all("${" not in part for part in command), "CLIENT_ENV_EXPANSION_FORBIDDEN")
        entry = {"command": command[0], "args": command[1:]}
        return value, entry

    def target(self, item, entry, *, remove=False, created_container=False, original=None):
        path = Path(item["config"])
        c.require(not {".golem", ".git"}.intersection(path.parts), "CONFIG_NATIVE_SCOPE")
        c.require(path.name == config.FILENAMES[item["client"]], "CLIENT_CONFIG_PATH")
        c.require(not path.is_relative_to(self.root) and not self.root.is_relative_to(path), "INSTALL_STATE_SCOPE")
        identity = parent(path)
        before = snapshot(path)
        data = r.regular(path) if before else (b"" if item["client"] == "codex-config" else b"{}\n")
        after, created = config.edit(item["client"], data, item["server_name"], entry,
                                     remove=remove, created_container=created_container)
        # Exact unchanged installations restore original bytes, including whitespace.
        if remove and original is not None:
            original_after = config.edit(item["client"], original, item["server_name"], entry)[0]
            if data == original_after:
                after = original
        c.require(snapshot(path) == before and parent(path) == identity, "CONFIG_DRIFT")
        return {"path": str(path), "parent": identity, "before": before, "after_sha256": c.sha(after),
                "created_container": created, "entry": entry,
                "managed_change": {"before": entry if remove else None, "after": None if remove else entry}}, data, after

    def facts(self, operation, request):
        c.require(operation in SPECS, "INSTALL_OPERATION")
        c.bounded(request)
        c._validate(request, SPECS[operation])
        c.require(len(c.encoded(request)) <= c.LIMIT, "JSON_SIZE")
        if operation == "bootstrap":
            root = r.real_path(request["root"])
            c.require(not {".golem", ".git"}.intersection(root.parts), "BOOTSTRAP_NATIVE_SCOPE")
            c.require(root.is_dir() and root.stat().st_uid == os.getuid() and not root.stat().st_mode & 0o022, "PROJECT_ROOT")
            c.require(not root.is_relative_to(self.root) and not self.root.is_relative_to(root), "INSTALL_STATE_SCOPE")
            path = root / ".golem"
            c.require(not path.exists() and not path.is_symlink(), "BOOTSTRAP_EXISTS_USE_D1_ENROLLMENT")
            c.require(not self.directory(request["bootstrap_id"], bootstrap=True).exists(), "BOOTSTRAP_ID_USED")
            return {"root_identity": r.identity(root), "manifest": {
                "schema": "golem.integration-bootstrap.v1", "project_id": request["project_id"],
                "bootstrap_id": request["bootstrap_id"], "grants_created": False, "work_created": False}}
        identifier = request["installation_id"]
        if operation == "remove":
            directory, old = self.stored(identifier)
            c.require(not (directory / "removed.json").exists() and not (directory / "remove-plan.json").exists(), "REMOVE_ALREADY_STARTED")
            result = []
            for index, item in enumerate(old["request"]["targets"]):
                original = self.original(directory, old, index)
                launch = c.decode(r.regular(directory / f"launch-{index}.json", private=True))
                c.require(launch["target"] == item, "INSTALL_RECORD_CONFLICT")
                target, _, _ = self.target(item, old["facts"]["targets"][index]["entry"], remove=True,
                    created_container=old["facts"]["targets"][index]["created_container"], original=original)
                result.append(target)
            return {"install_plan_sha256": c.sha(c.encoded(old)), "targets": result}
        c.require(not self.directory(identifier).exists(), "INSTALL_ID_USED")
        c.require(len({item["config"] for item in request["targets"]}) == len(request["targets"]), "DUPLICATE_CONFIG_TARGET")
        result = []
        for index, item in enumerate(request["targets"]):
            _, entry = self.launch(request, index)
            target, _, _ = self.target(item, entry)
            result.append(target)
        return {"targets": result}

    def plan(self, operation, request):
        with self.registry.locked():
            value = {"schema": "golem.integration-install-plan.v1", "operation": operation, "request": request,
                     "state": str(self.root), "state_identity": self.registry.root_identity,
                     "producer": producer(), "facts": self.facts(operation, request)}
            c.require(len(c.encoded(value)) <= c.LIMIT, "JSON_SIZE")
            return value

    def apply(self, plan, digest, *, approve_installation=False, repair=False):
        c.require(approve_installation is True, "OWNER_INSTALL_APPROVAL_REQUIRED")
        c.bounded(plan)
        c.require(isinstance(plan, dict) and set(plan) == {"schema", "operation", "request", "state", "state_identity", "producer", "facts"}, "SCHEMA")
        c.require(c.sha(c.encoded(plan)) == digest, "PLAN_DIGEST")
        c.require(plan["schema"] == "golem.integration-install-plan.v1" and plan["state"] == str(self.root) and
                  plan["state_identity"] == self.registry.root_identity and plan["producer"] == producer(), "INSTALL_PLAN_STALE")
        operation, request = plan["operation"], plan["request"]
        c.require(operation in SPECS, "INSTALL_OPERATION")
        c._validate(request, SPECS[operation])
        with self.registry.locked(exclusive=True):
            backend._quota(self.root)
            counts = {"install": len(list(self.root.glob("installation-*"))),
                      "bootstrap": len(list(self.root.glob("bootstrap-*")))}
            c.require(all(count <= 128 for count in counts.values()), "INSTALL_QUOTA")
            if not repair and operation in counts:
                c.require(counts[operation] < 128, "INSTALL_QUOTA")
            if operation == "bootstrap":
                return self.bootstrap(plan, repair=repair)
            directory = self.directory(request["installation_id"])
            plan_name = "plan.json" if operation == "install" else "remove-plan.json"
            if repair:
                c.require(r.regular(directory / plan_name, private=True) == c.encoded(plan), "REPAIR_ORIGINAL_PLAN_REQUIRED")
                c.require(not (directory / ("committed.json" if operation == "install" else "removed.json")).exists(), "INSTALL_ALREADY_COMPLETED")
            else:
                c.require(plan["facts"] == self.facts(operation, request), "INSTALL_PLAN_STALE")
                if operation == "install":
                    mkdir(directory)
                retain(directory / plan_name, c.encoded(plan))
            old = plan if operation == "install" else c.decode(r.regular(directory / "plan.json", private=True))
            targets = old["request"]["targets"]
            # Check and back up every target before changing the first file.
            prepared = []
            for index, item in enumerate(targets):
                planned = plan["facts"]["targets"][index]
                path = Path(item["config"])
                c.require(parent(path) == planned["parent"], "CONFIG_PARENT_CHANGED")
                if operation == "install":
                    launch, entry = self.launch(old["request"], index)
                    retain(directory / f"launch-{index}.json", c.encoded(launch))
                else:
                    entry = old["facts"]["targets"][index]["entry"]
                c.require(planned["entry"] == entry, "INSTALL_PLAN_STALE")
                before_path = directory / f"{'before' if operation == 'install' else 'remove-before'}-{index}.bin"
                current = snapshot(path)
                if not before_path.exists():
                    c.require(current == planned["before"], "CONFIG_DRIFT")
                    retain(before_path, r.regular(path) if current else (b"" if item["client"] == "codex-config" else b"{}\n"))
                before = r.regular(before_path, private=True)
                c.require(c.sha(before) == (planned["before"]["sha256"] if planned["before"] else
                    c.sha(b"" if item["client"] == "codex-config" else b"{}\n")), "INSTALL_BACKUP_CORRUPT")
                after = config.edit(item["client"], before, item["server_name"], entry,
                    remove=operation == "remove", created_container=old["facts"]["targets"][index]["created_container"])[0]
                if operation == "remove":
                    original = self.original(directory, old, index)
                    if before == config.edit(item["client"], original, item["server_name"], entry)[0]:
                        after = original
                c.require(c.sha(after) == planned["after_sha256"], "INSTALL_PLAN_STALE")
                mode = planned["before"]["mode"] if planned["before"] else 0o600
                already = current is not None and current["sha256"] == c.sha(after) and current["mode"] == mode
                c.require(current == planned["before"] or repair and already, "CONFIG_DRIFT")
                prepared.append((path, planned, after, already))
            for index, (path, planned, after, already) in enumerate(prepared):
                with directory_lock(path.parent):
                    c.require(parent(path) == planned["parent"], "CONFIG_PARENT_CHANGED")
                    current = snapshot(path)
                    if not (repair and already):
                        publish_config(path, planned["before"], after)
                    else:
                        mode = planned["before"]["mode"] if planned["before"] else 0o600
                        c.require(current and current["sha256"] == c.sha(after) and current["mode"] == mode, "CONFIG_DRIFT")
                    retain(directory / f"{'applied' if operation == 'install' else 'removed'}-{index}.json",
                           c.encoded({"after_sha256": c.sha(after), "path": str(path)}))
            name = "committed.json" if operation == "install" else "removed.json"
            retain(directory / name, c.encoded({"plan_sha256": digest, "state": "RELOAD_REQUIRED" if operation == "install" else "REMOVED"}))
            return {"state": "RELOAD_REQUIRED" if operation == "install" else "REMOVED", "installation_id": request["installation_id"],
                    "client_activation": "NOT_OBSERVED", "grant_revoked": False, "native_state_changed": False}

    def inspect(self, identifier):
        with self.registry.locked():
            directory = self.directory(identifier)
            plan = c.decode(r.regular(directory / "plan.json", private=True))
            state = "PARTIAL"
            if (directory / "removed.json").exists():
                state = "REMOVED"
            elif (directory / "remove-plan.json").exists():
                state = "PARTIAL_REMOVAL"
            elif (directory / "committed.json").exists():
                self.stored(identifier)
                state = "RELOAD_REQUIRED"
            return {"state": state, "installation_id": identifier, "plan_sha256": c.sha(c.encoded(plan)),
                    "client_activation": "NOT_OBSERVED", "native_state_changed": False}

    def bootstrap(self, plan, *, repair=False):
        request, facts = plan["request"], plan["facts"]
        root = r.real_path(request["root"])
        c.require(r.identity(root) == facts["root_identity"], "PROJECT_ROOT_CHANGED")
        c.require(root.stat().st_uid == os.getuid() and not root.stat().st_mode & 0o022, "PROJECT_ROOT")
        directory = self.directory(request["bootstrap_id"], bootstrap=True)
        runtime = root / ".golem"
        with directory_lock(root):
            if not repair:
                c.require(facts == self.facts("bootstrap", request), "INSTALL_PLAN_STALE")
                mkdir(directory)
                retain(directory / "plan.json", c.encoded(plan))
                mkdir(runtime)
                retain(directory / "created.json", c.encoded({"identity": r.identity(runtime)}))
            else:
                c.require(r.regular(directory / "plan.json", private=True) == c.encoded(plan), "REPAIR_ORIGINAL_PLAN_REQUIRED")
                c.require(not (directory / "committed.json").exists(), "INSTALL_ALREADY_COMPLETED")
                created = c.decode(r.regular(directory / "created.json", private=True))
                c.require(r.identity(runtime) == created["identity"], "BOOTSTRAP_IDENTITY_CHANGED")
            c.require(set(p.name for p in runtime.iterdir()) <= {"integration"}, "BOOTSTRAP_CONTENT_DRIFT")
            child = runtime / "integration"
            if not child.exists() and not child.is_symlink():
                mkdir(child)
            r.real_path(str(child))
            c.require(child.is_dir() and set(p.name for p in child.iterdir()) <= {"manifest.json"}, "BOOTSTRAP_CONTENT_DRIFT")
            retain(child / "manifest.json", c.encoded(facts["manifest"]))
            # No Work, capsule, SDK, grant or native event is created.
            for path in (child, runtime, root):
                fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            retain(directory / "committed.json", c.encoded({"plan_sha256": c.sha(c.encoded(plan)), "state": "BOOTSTRAPPED"}))
            return {"state": "BOOTSTRAPPED", "runtime_identity": r.identity(runtime), "grants_created": False,
                    "work_created": False, "next_operation": "EXPLICIT_NATIVE_WORK_CREATION_THEN_D1_ENROLLMENT"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "schema", "runtime", "plan", "apply", "repair", "inspect"))
    parser.add_argument("--state", type=Path)
    parser.add_argument("--operation", choices=tuple(SPECS))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--reviewed-plan-sha256")
    parser.add_argument("--approve-installation", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "runtime":
            result = runtime_adapter.runtime()
        elif args.command == "schema":
            c.require(args.operation is not None, "OPERATION_REQUIRED")
            result = {"$schema": "https://json-schema.org/draft/2020-12/schema", **SPECS[args.operation]}
        else:
            c.require(args.state is not None, "STATE_REQUIRED")
            if args.command == "init":
                r.Registry.create(args.state, approve_local_owner=args.approve_installation)
                result = {"state": "OWNER_INSTALL_STATE_CREATED"}
            else:
                c.require(args.input is not None, "INPUT_REQUIRED")
                manager = Installer(args.state)
                value = c.decode(r.regular(args.input, private=True))
                if args.command == "inspect":
                    c._validate(value, REFERENCE)
                    result = manager.inspect(value["installation_id"])
                else:
                    result = manager.plan(args.operation, value) if args.command == "plan" else manager.apply(value,
                        args.reviewed_plan_sha256, approve_installation=args.approve_installation, repair=args.command == "repair")
        sys.stdout.buffer.write(c.encoded(result))
        return 0
    except (c.IntegrationError, OSError, ValueError, KeyError, TypeError) as error:
        sys.stderr.write(c.encoded({"state": "BLOCKED_OR_PARTIAL", "code": getattr(error, "code", "IO_OR_CONTRACT_ERROR"),
            "automatic_retry_allowed": False, "next_operation": "PRESERVE_FILES_REVIEW_ORIGINAL_PLAN_AND_USE_EXPLICIT_REPAIR"}).decode())
        return 1


if __name__ == "__main__":
    sys.exit(main())
