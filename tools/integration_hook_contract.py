"""D3 owner-reviewed local command-hook profiles and configuration fragments."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import stat
import subprocess
import sys
import tempfile

import execution_record as records
import integration_backend as backend
import integration_contract as c
import integration_registry as r
import integration_service as service
import integration_transfer as transfer

VERSIONS = {"codex-cli": "0.141.0", "claude-code": "2.1.196"}
SOURCES = ("startup", "resume", "clear", "compact")
MODULES = ("integration_hook_contract.py", "integration_hooks.py")
PROFILE = c.obj({"schema": {"const": "golem.integration-hook-profile.v1"},
    "client": c.enum(*VERSIONS), "client_version": c.enum(*VERSIONS.values()), "client_pin": c.PIN,
    "python_pin": c.PIN, "transfer_policy": c.PIN,
    "context": service.SCHEMAS["context_get"], "sources": c.array(c.enum(*SOURCES), 4),
    "mcp_server": c.ID, "delivery": {"const": "SCOPED_MCP_NOTICE"},
    "producer": c.obj({name: c.DIGEST for name in (*transfer.PRODUCER_NAMES, *MODULES)})})


def producer():
    root = Path(__file__).resolve().parent
    return {**transfer.producer(), **{name: c.sha(r.regular(root / name)) for name in MODULES}}


def executable_pin(path):
    """Client binaries exceed D1's data-file limit; hash a bounded stream."""
    path = r.real_path(str(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        c.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                  before.st_size <= 536870912 and before.st_mode & 0o111, "CLIENT_EXECUTABLE")
        digest, size = hashlib.sha256(), 0
        while True:
            data = os.read(fd, 1048576)
            if not data:
                break
            size += len(data)
            c.require(size <= 536870912, "CLIENT_EXECUTABLE")
            digest.update(data)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode")
        c.require(all(getattr(before, key) == getattr(after, key) for key in fields) and
                  size == before.st_size, "CLIENT_CHANGED")
        return {"path": str(path), "sha256": digest.hexdigest()}
    finally:
        os.close(fd)


def validate(value):
    c.bounded(value)
    c.require(len(c.encoded(value)) <= c.LIMIT, "JSON_SIZE")
    c._validate(value, PROFILE)
    c.require(value["client_version"] == VERSIONS[value["client"]], "CLIENT_PROFILE_UNSUPPORTED")
    c.require(value["producer"] == producer(), "PRODUCER_CHANGED")
    return value


class Profile:
    def __init__(self, path, reviewed_sha256, *, approve_hooks=False):
        c.require(approve_hooks is True, "OWNER_HOOK_APPROVAL_REQUIRED")
        c._validate(reviewed_sha256, c.DIGEST)
        self.path, self.digest = r.real_path(str(path)), reviewed_sha256
        self.value = self.current()
        self.transfer = transfer.Transfer(Path(self.value["transfer_policy"]["path"]),
            self.value["transfer_policy"]["sha256"], approve_data_transfer=True)
        c.require(self.transfer.value["destination"] == "MODEL_SERVICE", "MODEL_DISCLOSURE_REQUIRED")
        args = self.value["context"]
        scope = self.transfer.scope(args["project_id"], args["work_id"], "context_get")
        self.transfer.scope(args["project_id"], args["work_id"], "work_inspect")
        self.service = service.Service(self.transfer)
        with self.transfer.registry.locked():
            for operation in ("record", "status", "next"):
                project = self.service._authorize(scope, args["work_id"], operation)
            c.require(not self.path.is_relative_to(Path(project["root"])), "HOOK_PROFILE_SCOPE")
            self.project_root = project["root"]

    def current(self):
        data = r.regular(self.path, private=True)
        c.require(c.sha(data) == self.digest, "HOOK_PROFILE_CHANGED")
        value = validate(c.decode(data))
        for name in ("client_pin", "python_pin"):
            pin = value[name]
            c.require(executable_pin(Path(pin["path"])) == pin, "CLIENT_OR_INTERPRETER_CHANGED")
        c.require(value["python_pin"]["path"] == str(Path(sys.executable).resolve()), "HOOK_INTERPRETER")
        return value


def fragment(profile):
    value = profile.current()
    command = shlex.join([value["python_pin"]["path"], str(Path(__file__).with_name("integration_hooks.py")),
        "--profile", str(profile.path), "--reviewed-profile-sha256", profile.digest, "--approve-hooks"])
    return {"hooks": {"SessionStart": [{"matcher": "^(" + "|".join(value["sources"]) + ")$",
        "hooks": [{"type": "command", "command": command, "timeout": 240}]}]}}


def plan(value):
    c.require(isinstance(value, dict), "SCHEMA")
    value = {**value, "producer": producer()}
    validate(value)
    pin = value["client_pin"]
    c.require(executable_pin(Path(pin["path"])) == pin, "CLIENT_CHANGED")
    disclosure = transfer.Transfer(Path(value["transfer_policy"]["path"]), value["transfer_policy"]["sha256"],
                                   approve_data_transfer=True)
    scope = disclosure.scope(value["context"]["project_id"], value["context"]["work_id"], "context_get")
    with disclosure.registry.locked():
        service.Service(disclosure)._authorize(scope, value["context"]["work_id"], "record")
        backend._quota(disclosure.registry.root)
        output = Path(tempfile.mkdtemp(prefix="read-hook-probe-", dir=disclosure.registry.root))
        # Client caches may create symlinks. Keep disposable caches outside the
        # strict audit inventory; retain only recorder-owned evidence in it.
        with tempfile.TemporaryDirectory(prefix="golem-client-version-") as home:
            scratch = str(Path(home).resolve(strict=True))
            result = records.capture([pin["path"], "--version"], output, 5, cwd=scratch, observe_source=False, limit=8192,
                env={**backend.ENVIRONMENT, "HOME": scratch, "CODEX_HOME": scratch,
                     "CLAUDE_CONFIG_DIR": scratch, "DISABLE_AUTOUPDATER": "1"})
    expected = ("codex-cli " + value["client_version"] if value["client"] == "codex-cli" else
                value["client_version"] + " (Claude Code)")
    c.require(result["returncode"] == 0 and result["reason"] == "EXIT" and result["recording"] == "RECORDED" and
              r.regular(output / "stdout.log", 8192, private=True).decode("utf-8").strip() == expected,
              "CLIENT_VERSION_MISMATCH")
    c.require(executable_pin(Path(pin["path"])) == pin, "CLIENT_CHANGED")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("schema", "pin", "plan", "fragment", "check"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--reviewed-profile-sha256")
    parser.add_argument("--approve-hooks", action="store_true")
    args = parser.parse_args()
    try:
        if args.operation == "schema":
            result = {"$schema": "https://json-schema.org/draft/2020-12/schema", **PROFILE}
        elif args.operation == "pin":
            c.require(args.input is not None, "INPUT_REQUIRED")
            result = executable_pin(args.input)
        elif args.operation == "plan":
            c.require(args.input is not None, "INPUT_REQUIRED")
            result = plan(c.decode(r.regular(args.input, private=True)))
        else:
            c.require(args.profile is not None, "INPUT_REQUIRED")
            profile = Profile(args.profile, args.reviewed_profile_sha256, approve_hooks=args.approve_hooks)
            result = fragment(profile) if args.operation == "fragment" else {
                "schema": "golem.integration-hook-check.v1", "state": "CONFIGURATION_CHECKED",
                "client_activation": "NOT_OBSERVED", "native_state_changed": False}
        sys.stdout.buffer.write(c.encoded(result))
        return 0
    except (c.IntegrationError, OSError, ValueError, subprocess.SubprocessError) as error:
        sys.stderr.write(c.encoded(service.blocked(error)).decode())
        return 1


if __name__ == "__main__":
    sys.exit(main())
