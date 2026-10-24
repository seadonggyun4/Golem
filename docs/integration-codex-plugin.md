# Codex Local MCP Plugin Setup

Golem can be installed as a local Codex plugin, with its own listing and icon.
The verified 0.1.3 package uses the supported compatibility manifest layout.
This is a local installation, not a public plugin-directory release, a Hosted
gateway or a self-contained engine distribution. Developer: **Donggyun Seo**.

## Prerequisites and Approval

1. Build the native engine and prepare the optional MCP runtime using the
   [runtime guide](runtime-reference.md#build-and-run) and
   [D1 installer](integration-install.md#plan-and-apply).
2. Follow [D1 enrollment](integration-d1.md) and [D2 disclosure](integration-d2.md)
   to review the exact projects, Works, native executable/producer pins and
   permitted tools. Codex/OpenAI disclosure must be explicitly approved; a
   Claude grant does not authorize a different destination.
3. Obtain the reviewed D1 launcher's exact `command` and `args` from the selected
   managed configuration. Keep its configuration, installation state, registry
   and policy available. The launcher still checks those original records.
4. Back up settings privately and obtain owner approval for the marketplace,
   plugin enablement and any manual-server transition. Do not overwrite other
   servers, trust settings or tool approval preferences.

The observed synthetic installation grants three Works and only
`golem_projects_list`, `golem_work_inspect`, `golem_history_read`,
`golem_context_get`, `golem_evidence_read` and `golem_completion_check`.
These limits belong in reviewed grants/policy, not just in descriptive metadata.
No hook, handoff recipient, automatic resume or native write is bundled.
The local process has the user's OS access; Golem policy is not an OS sandbox.

## Prepare a Private Marketplace

Create a new owner-controlled directory outside the source checkout and private
evidence stores. The reusable public generator accepts a private JSON file with
exactly `command` (absolute interpreter path) and `args` (string array), copied
from your reviewed launcher. It reads no client configuration or approval policy
automatically. Do not include credentials in launcher arguments.

```sh
python3 tools/integration_codex_plugin.py \
  --launcher /private/reviewed-launcher.json \
  --output /private/new-local-marketplace \
  --marketplace golem-local --server golem-local
```

Output must not exist. Identifier syntax, duplicate fields, extra fields, NUL
and `${...}` client expansion are rejected before publication. Only five files
are emitted: catalog, plugin manifest, MCP declaration, icon and license. Output
directories are private and files are mode 0600. A disk failure can leave partial
output; preserve it and choose a fresh path after review. No install or approval
is performed. Generated `.mcp.json` contains the explicitly supplied local paths,
so keep the generated package private; the public generator contains no host paths.
It does not authenticate your launcher or grant native authority. Existing D1
launch checks remain responsible for pins and authorization.

The historical synthetic example below uses `golem-synthetic`; when using the
generator defaults, substitute `golem-local` in installation commands. The
following layout and templates describe the same packaging contract:

```text
local-marketplace/
  .agents/plugins/marketplace.json
  plugins/golem/
    .codex-plugin/plugin.json
    .mcp.json
    assets/icon.png
    LICENSE
```

Copy the unmodified `assets/Golem-mcp.png` from this repository to
`plugins/golem/assets/icon.png`, and include `LICENSE`. Do not copy policies,
registry contents, credentials, config backups, Work data or raw traces.

`plugins/golem/.codex-plugin/plugin.json`:

```json
{
  "name": "golem",
  "version": "0.1.3",
  "description": "Owner-approved local Golem workflow context and evidence.",
  "author": {"name": "Donggyun Seo"},
  "license": "PolyForm-Noncommercial-1.0.0",
  "mcpServers": "./.mcp.json",
  "requires_local_executor": true,
  "interface": {
    "displayName": "Golem",
    "shortDescription": "Read approved workflow context and evidence",
    "developerName": "Donggyun Seo",
    "category": "Developer Tools",
    "composerIcon": "./assets/icon.png",
    "logo": "./assets/icon.png"
  }
}
```

`plugins/golem/.mcp.json` (replace both placeholders with the exact reviewed
launcher values before installing; this example is not a runnable launcher):

```json
{
  "mcpServers": {
    "golem-synthetic": {
      "type": "stdio",
      "command": "<reviewed interpreter absolute path>",
      "args": ["<exact reviewed launcher argument array, not this string>"]
    }
  }
}
```

Do not append `enabled=false` from a disabled manual table to this server
declaration. Preserve the reviewed command/arguments exactly, including literal
paths and launch digest; do not substitute a shell wrapper or regenerate consent.
This package references a local runtime and is not portable to another machine
without a separate installation and approval review.

`.agents/plugins/marketplace.json`:

```json
{
  "name": "golem-synthetic",
  "interface": {"displayName": "Golem Synthetic"},
  "plugins": [{
    "name": "golem",
    "source": {"source": "local", "path": "./plugins/golem"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "category": "Developer Tools"
  }]
}
```

The path is relative to the marketplace root, not `.agents/plugins`. These names
describe the tested synthetic installation; they do not grant synthetic scope
or authenticate an owner. Public plugin publication is a separate process.

## Install and Check

Use the CLI belonging to the intended desktop client, not an unrelated older
`codex` on PATH. The observed bundled CLI was `0.163.0-alpha.11.2`; check its
version/help before using these commands. Paths below are placeholders.

```sh
codex plugin marketplace add /absolute/path/to/local-marketplace --json
codex plugin add golem@golem-synthetic --json
codex plugin list --marketplace golem-synthetic --json
codex mcp list --json
```

The official documentation also provides installation through the desktop
Plugins UI. If the selected CLI lacks `plugin add`, use that supported UI rather
than editing plugin caches or inventing commands.

For an approved transition from manual `[mcp_servers.golem]`, preserve the table
and its command/args, setting only `enabled=false`. Keep the plugin server name
distinct (`golem-synthetic` here): in the tested client, a disabled manual server
named `golem` also disabled the same-named plugin server. Verify manual `golem`
is disabled and plugin `golem-synthetic` enabled before making calls. Do not
modify the original D1-managed target merely to rename this presentation layer.

Open the plugin listing and check the Golem artwork, developer **Donggyun Seo**
and installed version. Reopen the details page after metadata updates. If tool
exposure is stale, inspect the actual conversation's catalog; arrange a client
reload or a new conversation with owner approval, not automatic termination.

Start with `golem_projects_list`, then inspect only a granted Work. Verify the
six expected tools and rejected/unlisted scope separately from connection success.
Stop on approval, pin, snapshot or `AUDIT_QUOTA` errors; do not repair by widening
grants, rewriting evidence or repeatedly filling the registry. `AVAILABLE` is
delivery only. Completion checks can correctly return `RECONCILE_SESSION` and
`acceptance_verified=false`.

## Update and Removal

Change the source package, review it and reinstall using the supported client
path. `author.name` and `interface.developerName` must both be `Donggyun Seo`;
the owner-local generator was corrected as well as the installed manifest.
Metadata changes do not justify reapproving producer bytes. Runtime changes need
the separate [D5 review](integration-d5.md), not automatic pin refresh.

Remove only this plugin through the client UI or its supported `plugin remove`
command. Do not delete its registry, audit records or retained approvals. Do not
automatically re-enable the preserved manual server: that is another explicit
configuration decision. Uninstalling is not revocation of already delivered data.

The public generator was also exercised through reinstallation and eight actual
desktop calls using the same approved scope; see
[public generator verification](integration-codex-desktop.md#public-generator-reinstallation).

See [actual calls and UI verification](integration-codex-desktop.md#plugin-path-verification)
and [official plugin packaging](https://developers.openai.com/plugins/build/plugins).
The latter also describes a newer portable manifest; this record does not claim
that the tested compatibility package has been migrated to it.
