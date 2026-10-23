"""Build an explicit, public-file-only D2 desktop extension; never install it."""
import argparse
import io
import json
from pathlib import Path
import zipfile

import integration_mcp as branding
import integration_transfer as transfer
from integration_registry import regular


def manifest():
    return {
        "manifest_version": "0.4", "name": "golem", "display_name": "Golem",
        "version": "0.1.1",
        "description": "Owner-approved, read-only Golem workflow context and evidence.",
        "author": {"name": "Golem contributors"},
        "repository": {"type": "git", "url": "https://github.com/seadonggyun4/Golem"},
        "icon": "assets/Golem-mcp.png", "license": "PolyForm-Noncommercial-1.0.0",
        "server": {"type": "uv", "entry_point": "tools/integration_mcpb_entry.py",
            "mcp_config": {"command": "uv", "args": ["run", "--directory", "${__dirname}",
                "tools/integration_mcpb_entry.py"], "env": {
                "GOLEM_TRANSFER_POLICY": "${user_config.policy}",
                "GOLEM_REVIEWED_POLICY_SHA256": "${user_config.policy_sha256}",
                "GOLEM_APPROVE_DATA_TRANSFER": "${user_config.approve_data_transfer}"}}},
        "compatibility": {"platforms": ["darwin", "linux"], "runtimes": {"python": ">=3.11"}},
        "tools_generated": True,
        "user_config": {
            "policy": {"type": "file", "title": "Reviewed disclosure policy",
                "description": "Existing owner-private D2 policy. No project is auto-enrolled.", "required": True},
            "policy_sha256": {"type": "string", "title": "Reviewed policy SHA-256",
                "description": "Exact digest of the policy you reviewed, not an automatically computed approval.",
                "required": True},
            "approve_data_transfer": {"type": "boolean", "title": "Approve this policy's disclosure to Claude",
                "description": "Explicit disclosure consent only; does not grant native execution authority.",
                "default": False, "required": True}}}


def build():
    root = Path(__file__).resolve().parents[1]
    dependencies = regular(root / "tools/requirements-mcp.txt").decode().splitlines()
    payloads = {
        "manifest.json": json.dumps(manifest(), indent=2).encode() + b"\n",
        "pyproject.toml": ("[project]\nname = \"golem-desktop\"\nversion = \"0.1.1\"\n"
            "requires-python = \">=3.11\"\ndependencies = " + json.dumps(dependencies) + "\n").encode(),
        "assets/Golem-mcp.png": branding.icon_bytes(),
        "LICENSE": regular(root / "LICENSE"),
    }
    # An explicit allowlist excludes policies, registries, Works and credentials.
    for name in (*transfer.PRODUCER_NAMES, "integration_mcpb_entry.py"):
        payloads["tools/" + name] = regular(root / "tools" / name)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payloads.items()):
            entry = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = build()
    with args.output.open("xb") as stream:
        stream.write(data)
    print(json.dumps({"bundle": str(args.output), "bytes": len(data)}))


if __name__ == "__main__":
    main()
