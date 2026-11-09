---
name: golem-setup
description: Connect or diagnose an explicitly approved local Golem launcher for Codex or Claude Code. Use for Golem installation and connection setup, not ordinary Work execution.
---

# Golem Setup

For an explicit setup/maintenance request, first inspect the intended client's
resolved MCP command and installed working directory. Installation grants no
project access. Reuse the user's existing authorization and preserve unrelated
settings, approvals, evidence and clients.

The numbered adapter steps below apply only when that declaration actually runs
this package's `scripts/launcher.py`. A private launcher-only package runs its
explicitly reviewed command directly and may include no adapter script, tools
directory or feature inventory. For that layout, preserve the resolved launcher
and its existing owner/runtime/policy pins; use actual tool discovery to diagnose
its scope. Do not run a missing adapter, configure the default adapter state, or
search the host for a replacement. Use the original owner installation/maintenance
contract only when this request authorizes a concrete connection change, then
verify reload and calls separately.

1. Inspect this plugin's resolved MCP declaration with the intended client's
   supported configuration tools (`codex mcp list --json` for Codex). Resolve the
   exact installed script; Claude Code expands `${CLAUDE_PLUGIN_ROOT}` and does
   not depend on the project working directory. Do not print unrelated settings.
   The adapter needs Python 3 and a POSIX host. Run `status` first using the same
   `--client` value as the declaration: Codex defaults to `codex`, Claude Code
   uses `claude-code`, and the portable manifest uses `portable`. Their default
   states are respectively `~/.local/share/golem/codex-plugin`,
   `~/.local/share/golem/claude-code-plugin`, and
   `~/.local/share/golem/portable-plugin`. These are separate approvals; never
   copy/import another client's adapter record or silently share `--state`.
   The Desktop bundle selects `--client claude-desktop`; its explicit configured
   `--state` overrides the adapter's `~/.local/share/golem/claude-desktop-plugin`
   default and must contain a separately reviewed Desktop launcher record.
2. If unconfigured, locate the launcher explicitly selected by the owner. Export
   only its exact absolute `command` and string `args` into a new owner-private
   JSON file (0600). Do not copy a whole config, credentials or approval registry.
   Review the launcher's purpose, its existing project/Work/tool/disclosure
   scope and SHA-256. Do not infer approval from finding a file or calculating a
   hash. Obtain owner authorization if the current request does not cover this
   connection; do not ask again for the same authorized scope.
3. Create only the chosen state path's missing parent directories with private
   permissions when needed; preserve existing directory modes. Invoke the
   installed adapter with `configure --client CLIENT --launcher FILE
   --reviewed-launcher-sha256 DIGEST --approve-launcher`. This records a reviewed
   local command, not project grants. The existing launcher still enforces its
   native/runtime/producer/policy pins. Never rewrite those pins to fix startup.
4. Recheck `status` with the same client selector. Arrange a supported MCP reload
   or new conversation if authorized; preserve ongoing client sessions. Inspect
   actual tool exposure. Only if calls are authorized, call `golem_projects_list`
   and an explicitly granted Work; otherwise record calls as NOT_RUN. Confirm the
   returned tool scope rather than inferring it from the package.
5. Report configuration, tool exposure and calls separately. `AVAILABLE` means
   delivery. Native completion may still require reconciliation. Context delivery
   grants no execution, takeover or automatic resume. Stop on quota, stale pins,
   owner conflicts or unknown effects without retries or evidence deletion.

`EXISTING_APPROVAL_DIFFERS` refuses rebinding. `PARTIAL_PUBLICATION` preserves an
interrupted adapter record and blocks launch. Do not delete/replace these records
or construct recovery layers. Diagnose and report for explicit maintenance.
Raw paths, policy contents and arguments stay private. The adapter is a
same-user local process, not an OS sandbox or an authenticated approval issuer.

The public installation entry is
https://github.com/seadonggyun4/styxis-plugin#install.
Use only a published, pinned Golem entry; an unpublished candidate is not an
installed release. Product setup details remain at
https://github.com/seadonggyun4/Golem/blob/main/docs/integration-codex-plugin.md.
Claude Desktop uses a separately reviewed MCPB, not the Claude Code manifest;
neither manifest imports a Desktop policy or turns on a Work action.

When a feature artifact is explicitly supplied for packaging or maintenance,
inspect that selected artifact's
`tools/integration_distribution.py catalog` and its feature-package.json. Profile
selection is a tool ceiling, not a grant. The profile artifacts require an external
owner-pinned Python/SDK/native runtime; they are not signed self-contained releases.
Missing runtime/signature/host qualification is not installation success.

Use package-local `tools/integration_owner_maintenance.py schema|plan|inspect` for
the existing installation or D5 maintenance contracts. Its apply path requires
the exact reviewed original plan digest and explicit owner authorization; no
repair or automatic rollback is exposed. A reload ACK alone is insufficient:
D5 ready retains its existing required runtime probe, Work inventories and owner
checks. Do not run probes, stop clients, apply plans or reload when the active
request permits only code/fixtures. Preserve partial/unknown results for review.

For ordinary Work requests, use the separate Golem Work skill and currently
exposed tools. Do not start setup, reinstall, reconnect or change owner policies
merely because a Work operation fails or a packaged feature is unavailable.
