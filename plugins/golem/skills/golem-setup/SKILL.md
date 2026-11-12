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
   The adapter needs a POSIX host; Codex's connection relay needs Python 3.11+.
   Verify the declared interpreter; never silently substitute another executable.
   Run `status` first using the same
   `--client` value as the declaration: Codex defaults to `codex`, Claude Code
   uses `claude-code`, and the portable manifest uses `portable`. Their default
   states are respectively `~/.local/share/golem/codex-plugin`,
   `~/.local/share/golem/claude-code-plugin`, and
   `~/.local/share/golem/portable-plugin`. These are separate approvals; never
   copy/import another client's adapter record or silently share `--state`.
   The Desktop bundle selects `--client claude-desktop`; its explicit configured
   `--state` overrides the adapter's `~/.local/share/golem/claude-desktop-plugin`
   default and must contain a separately reviewed Desktop launcher record.
   Use `inspect-state --client CLIENT --state PATH` for the adapter's validated
   approval location and exact pins. Do not assume `STATE/approval.json` or
   duplicate the adapter's private storage layout in a maintenance controller.
   This read-only inspection neither starts a service nor configures a launcher.
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
4. Recheck `status` with the same client selector. Keep four observations separate:
   disk selection, the intended live connection, the host's current catalog, and
   definitions actually delivered in the intended chat. Owner's Codex connection
   panel accepts an external observation of that chat ID, turn ID, exact marker
   and actual tool names. Copy the opaque
   `golem-connection-v1:INSTANCE:CHILD_GENERATION:CATALOG_GENERATION:NONCE`
   marker from the first tool definition; never invent one or substitute a marker
   read from a local diagnostic. The marker is correlation data, not an approval,
   secret credential or authenticated chat identity. The panel checks it against
   one live relay and the current catalog. Absent, stale, ambiguous or mismatching
   observations leave delivery unverified and block choosing a transport by guess.
   A service owning a plan, or sharing the Desktop PID, is insufficient.
   A verified target's idle relay may refresh only that connection to the already
   reviewed/configured state. It cannot replace its own installed adapter code.
   Old adapters or a missing marker need a supported initial host reconnect;
   an unavailable official control socket is an explicit unsupported path, not
   permission to guess an IPC endpoint. A host-wide official reload requires its
   separate effect to be authorized. Preserve other chats and ongoing work.
   A new conversation alone, disk `config/batchWrite`, `tools/list_changed`, or a
   reload ACK is not proof of delivery. Observe definitions in the same chat's
   subsequent turn after renewal. Do not claim that an in-progress turn changed.
   For one known Codex relay ID, the installed adapter's `connection-status
   --client codex --state PATH --connection-instance ID` reads only that relay's
   status. It does not discover transports, reload a host or call a Work tool.
   `host_catalog` separates the current refresh generation's host list requests
   and forwarded responses from its last complete catalog digest. A forwarded
   response is not proof that the host cached it or exposed it to the model.
   If the host does not re-list, do not repeat the relay refresh: use the supported
   host reconnect/reload within the user's scope, then inspect definitions in a
   subsequent turn of the same chat. A reload queues loaded-thread refreshes;
   changing an in-progress turn's tool inventory is not guaranteed. A new
   app-server fixture is not verification of the existing Desktop process.
   Transport idle is not proof that native leases or external work have ended.
   Never retry uncertain refreshes, replay Work requests or kill an existing host.
5. After a connection change, verify actual definitions for the required tools
   before issuing short-lived execution preparations. Only then prepare the exact
   action under its existing policy and native freshness checks. Do not extend an
   old plan's TTL, reuse its instance in another service or renew it automatically
   while waiting for installation/reload. Connection readiness grants no action.
   Only if calls are separately authorized, call `golem_projects_list` and an
   explicitly granted Work; otherwise record calls as NOT_RUN. Report external
   definition observations, host catalog, configuration and actual calls
   separately. Native completion still requires its original checks. Stop on
   quota, stale pins, owner conflicts or unknown effects without retries or
   evidence deletion.

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
