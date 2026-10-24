"""MCPB adapter: fail-closed access with public, setup-only diagnostics."""
import asyncio
import os
from pathlib import Path
import sys

import integration_contract as c
import integration_mcp as mcp
from integration_service import Service
from integration_transfer import Transfer

GUIDANCE = {
    "MCPB_REVIEWED_POLICY_REQUIRED": "Set the reviewed policy file and its exact SHA-256 in extension settings.",
    "OWNER_TRANSFER_APPROVAL_REQUIRED": "Review the disclosure scope, then explicitly enable disclosure consent in extension settings.",
    "PRODUCER_CHANGED": "This policy belongs to different Golem module bytes. Select an owner-reviewed policy for this installed version; do not rewrite pins automatically.",
    "TRANSFER_POLICY_CHANGED": "The file no longer matches the reviewed SHA-256. Review the policy before changing the configured digest.",
    "REGISTRY_CHANGED": "The approval registry identity changed. Ask the owner to review the registry; do not recreate approvals.",
    "SETUP_VALIDATION_FAILED": "The configured policy or registry could not be validated. Inspect local configuration; no project access is enabled.",
}


def setup_notice(code):
    code = code if code in GUIDANCE else "SETUP_VALIDATION_FAILED"
    return {"schema": "golem.integration-setup.v1", "state": "SETUP_REQUIRED",
        "code": code, "message": GUIDANCE[code], "project_access_enabled": False,
        "execution_authorized": False, "automatic_retry_allowed": False,
        "approval_modified": False, "next_operation": "OWNER_REVIEW_SETTINGS_THEN_RESTART"}


def configured_service():
    """No policy read before consent; no native calls during setup validation."""
    policy = os.environ.get("GOLEM_TRANSFER_POLICY", "")
    digest = os.environ.get("GOLEM_REVIEWED_POLICY_SHA256", "")
    if not policy or len(digest) != 64 or any(v not in "0123456789abcdef" for v in digest):
        return None, setup_notice("MCPB_REVIEWED_POLICY_REQUIRED")
    if os.environ.get("GOLEM_APPROVE_DATA_TRANSFER", "").lower() != "true":
        return None, setup_notice("OWNER_TRANSFER_APPROVAL_REQUIRED")
    try:
        return Service(Transfer(Path(policy), digest, approve_data_transfer=True)), None
    except (c.IntegrationError, OSError, ValueError) as error:
        return None, setup_notice(getattr(error, "code", "SETUP_VALIDATION_FAILED"))


def setup_server(notice):
    # Apply the same SDK and public icon checks as the normal D2 server.
    mcp.server(None)
    from mcp.server import Server
    from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool, ToolAnnotations

    async def list_tools(ctx, params):
        return ListToolsResult(tools=[Tool(name="golem_setup_status",
            description="Golem setup required. Returns only public configuration guidance; cannot access projects or approve disclosure.",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                        idempotentHint=True, openWorldHint=False))])

    async def call_tool(ctx, params):
        valid = params.name == "golem_setup_status" and params.arguments in (None, {})
        value = notice if valid else {"state": "BLOCKED", "code": "UNSUPPORTED_SETUP_REQUEST",
                                     "execution_authorized": False}
        return CallToolResult(content=[TextContent(type="text", text=c.encoded(value).decode())],
                              isError=not valid)

    return Server("Golem (setup required)", version="0.1.4", icons=mcp.server_icons(),
        on_list_tools=list_tools, on_call_tool=call_tool,
        instructions="Golem project access is blocked. " + notice["message"] +
                     " Only setup status is available. The owner must review settings and restart; never infer approval.")


async def run_setup(notice):
    from mcp.server.stdio import stdio_server
    instance = setup_server(notice)
    incoming = mcp.BoundedInput()
    async with stdio_server(stdin=incoming) as (reader, writer):
        await instance.run(reader, writer, instance.create_initialization_options())
    if incoming.error is not None:
        raise incoming.error


def main():
    try:
        service, notice = configured_service()
        if notice is not None:
            sys.stderr.write(c.encoded(notice).decode() + "\n")
            asyncio.run(run_setup(notice))
        else:
            asyncio.run(mcp.run(service))
        return 0
    except (c.IntegrationError, OSError, ValueError) as error:
        sys.stderr.write(c.encoded(setup_notice(getattr(error, "code", "SETUP_VALIDATION_FAILED"))).decode() + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
