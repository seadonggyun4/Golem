"""Pinned installed D2 launcher. Config presence never grants project authority."""
import argparse
from pathlib import Path
import sys

import integration_contract as c
import integration_config as config
import integration_registry as r
import integration_install as install
import integration_reload_probe as runtime_adapter


def check(path, digest):
    data = r.regular(path, private=True)
    c.require(c.sha(data) == digest, "LAUNCH_PIN_CHANGED")
    value = c.decode(data)
    c.require(value["schema"] == "golem.integration-launch.v1" and value["producer"] == install.producer(), "PRODUCER_CHANGED")
    manager = install.Installer(Path(value["state"]))
    c.require(manager.registry.root_identity == value["state_identity"], "INSTALL_STATE_CHANGED")
    with manager.registry.locked():
        directory, plan = manager.stored(value["installation_id"])
        c.require(path == directory / f"launch-{value['index']}.json" and
                  not (directory / "remove-plan.json").exists() and not (directory / "removed.json").exists(), "INSTALL_REMOVED_OR_PARTIAL")
        target = plan["request"]["targets"][value["index"]]
        c.require(value["target"] == target and str(Path(sys.executable).resolve()) == target["runtime"]["python"]["path"],
                  "INSTALL_INTERPRETER_CHANGED")
        runtime_adapter.validate_runtime(target["runtime"])
        _, entry = manager.launch(plan["request"], value["index"])
        config.managed(target["client"], r.regular(Path(target["config"])), target["server_name"], entry)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch", type=Path, required=True)
    parser.add_argument("--reviewed-launch-sha256", required=True)
    args = parser.parse_args()
    try:
        target = check(args.launch, args.reviewed_launch_sha256)
        from integration_mcp import main as serve
        pin = target["transfer_policy"]
        sys.argv = [sys.argv[0], "--policy", pin["path"], "--reviewed-policy-sha256", pin["sha256"], "--approve-data-transfer"]
        return serve()
    except (c.IntegrationError, OSError, ValueError, KeyError, TypeError) as error:
        sys.stderr.write(c.encoded({"state": "INSTALL_LAUNCH_BLOCKED", "code": getattr(error, "code", "IO_OR_CONTRACT_ERROR")}).decode())
        return 1


if __name__ == "__main__":
    sys.exit(main())
