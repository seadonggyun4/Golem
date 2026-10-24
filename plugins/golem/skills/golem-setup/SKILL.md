---
name: golem-setup
description: Connect or diagnose an explicitly approved local Golem launcher for the Codex plugin. Use for Golem installation and connection setup, not ordinary Work execution.
---

# Golem Setup

Use the installed plugin's `scripts/launcher.py` to connect an existing reviewed
launcher. Installation grants no project access. Reuse the user's existing
authorization and preserve unrelated settings, approvals, evidence and clients.

1. Inspect this plugin's resolved MCP configuration with the intended client's
   `codex mcp list --json`. Use its exact `PLUGIN_ROOT` and `PLUGIN_DATA` values;
   do not guess a data directory or print unrelated settings. The adapter needs
   Python 3 and a POSIX host. Run its `status --state DATA` first.
2. If unconfigured, locate the launcher explicitly selected by the owner. Export
   only its exact absolute `command` and string `args` into a new owner-private
   JSON file (0600). Do not copy a whole config, credentials or approval registry.
   Review the launcher's purpose, its existing project/Work/tool/disclosure
   scope and SHA-256. Do not infer approval from finding a file or calculating a
   hash. Obtain owner authorization if the current request does not cover this
   connection; do not ask again for the same authorized scope.
3. Invoke the installed adapter with `configure --state DATA --launcher FILE
   --reviewed-launcher-sha256 DIGEST --approve-launcher`. This records a reviewed
   local command, not project grants. The existing launcher still enforces its
   native/runtime/producer/policy pins. Never rewrite those pins to fix startup.
4. Recheck `status`. Arrange a supported MCP reload or new conversation if needed;
   preserve ongoing client sessions. Inspect actual tool exposure and call
   `golem_projects_list`, then one explicitly granted Work. Confirm the actual
   returned tool scope; do not assume the package itself restricts it to six tools.
5. Report configuration, tool exposure and calls separately. `AVAILABLE` means
   delivery. Native completion may still require reconciliation. Context delivery
   grants no execution, takeover or automatic resume. Stop on quota, stale pins,
   owner conflicts or unknown effects without retries or evidence deletion.

`EXISTING_APPROVAL_DIFFERS` refuses rebinding. `PARTIAL_PUBLICATION` preserves an
interrupted adapter record and blocks launch. Do not delete/replace these records
or construct recovery layers. Diagnose and report for explicit maintenance.
Raw paths, policy contents and arguments stay private. The adapter is a
same-user local process, not an OS sandbox or an authenticated approval issuer.

For current installation details see
https://github.com/seadonggyun4/Golem/blob/main/docs/integration-codex-plugin.md.
