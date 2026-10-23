# Claude Desktop MCPB Packaging

## Registration Surfaces

| Surface | Golem icon source | Observed scope |
| --- | --- | --- |
| Manual local `mcpServers` | MCP `serverInfo.icons` | Claude Desktop 3.6556.2 connected successfully but displayed its generic connector symbol |
| Desktop extension `.mcpb` | Package `manifest.json` `icon` | The same client displayed the Golem artwork in preview and installed connector list/details, without the original white surround |
| Hosted connector directory | Separate catalog registration | Not implemented or verified by this package |

The official [Claude local MCP guide](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
documents Settings > Extensions > Advanced settings > Install Extension. Private
MCPB installation does not require public directory publication. The
[MCPB manifest specification](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)
defines the package-relative `icon` field separately from protocol metadata.
The client adds dark padding around the preview image; the asset cannot control
this outer layout. A preview alone is not proof of installed connector rendering.

On 2026-10-23, an owner-approved temporary installation on macOS completed with
an empty registry and no project grants. Claude Desktop 3.6556.2 reported the
extension connected and displayed its artwork in connector details. No tools
were available, as expected. The test extension and its configuration were then
removed through the UI; the extension list returned to empty. The original
manual client configuration remained byte-identical. No real Work was accessed.
This verifies this client's MCPB display path, not Codex or Hosted directories,
and does not promise that artwork fills Claude's outer decorative frame.

## Build Without Installation

```sh
python3 tools/integration_mcpb.py --output /private/tmp/golem.mcpb
```

The builder refuses an existing output. It emits a deterministic ZIP from an
explicit public-file allowlist: unchanged D2 producer modules, a small entry
adapter, the hash-checked edge-to-edge PNG, manifest, dependency declaration and
the existing license. No policy, registry, Work, evidence or credential is copied.
It neither changes client settings nor invokes a package manager.

Manifest 0.4 uses the official
[UV runtime example](https://github.com/modelcontextprotocol/mcpb/tree/main/examples/hello-world-uv).
The host may download Python dependencies; direct MCP versions match
`tools/requirements-mcp.txt`. Transitive dependencies are not fully locked by
this first packaging path. Do not claim an offline or hermetic runtime. POSIX
support is declared; Windows is excluded because the existing registry uses
`fcntl`. Actual client UI testing is macOS only, not Linux certification.

## Approval Boundary

Installation is separate from Golem authorization. The owner must supply an
existing private D2 disclosure policy, its explicitly reviewed SHA-256, and
affirmative disclosure consent (default false). The entry adapter delegates to
the unchanged D2 entry point. Registry grants, producer pins, native read guards
and output limits remain enforced. No auto-enrollment, bootstrap, Work resume,
mutation, issuer approval or policy regeneration is provided.

The packaged producer bytes are unchanged, so existing policy module hashes
remain comparable. Runtime updates still require review; this is not the D1
installer's runtime-pin transaction and does not claim its launch receipt.
Claude's local-extension warning concerns broad OS process access: a Golem grant
restriction is not an OS sandbox. Obtain explicit consent before installation.

## Verification and Rollback

Tests check deterministic contents, producer-byte preservation, false/missing
consent rejection, digest syntax, and extracted-bundle modern/legacy stdio
connections with an empty approval registry. No actual Work is needed for icon
testing. The generated manifest was separately checked against the official
[0.4 JSON Schema](https://github.com/modelcontextprotocol/mcpb/blob/main/schemas/mcpb-manifest-v0.4.schema.json).

For client verification, use a disposable empty registry and no project grants.
Inspect preview, installed extension details and connector details separately;
record where artwork is actually shown. Do not mark UI verification successful
from a protocol response alone. Remove only the test extension through Claude's
extension UI after verification, and compare the existing manual configuration
with its pre-test hash. Do not edit unrelated connector settings or preferences.
