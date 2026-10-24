# D1 Client Installation and Approved Bootstrap

This owner-only POSIX control plane extends [D1](integration-d1.md), not native
Work authority. `integration_install.py` reuses D1 private records, identities,
locks, strict values and audit bounds; D2 disclosure/grants; D3 executable pins;
and D5's pinned interpreter/SDK command builder. Existing D1-D6 producer contracts
and native formats are unchanged. No real product/client is configured by tests.

## MCP Server Icon

D2 stdio, D4 stdio and D6 gateway advertise the same public server icon through
the SDK's `icons` metadata: `assets/Golem-mcp.png`, a 256x256 PNG embedded as a
`data:image/png;base64,...` URI. No external image fetch, private filesystem path,
project information or credentials are included. Tool results do not repeat it.
The asset must accompany the source installation. Its SHA-256 is pinned in the
existing producer-hashed `integration_mcp.py`; missing or changed bytes block
server construction. Existing producer-pin updates still require the established
explicit review procedure, not automatic policy reapproval.

The owner-supplied original remains unchanged. The registration copy uses the
owner-requested expanded-background artwork, resized to 256x256. Artwork fills
the square without the original white surround or pre-rendered rounded frame;
the client can apply its own mask. Bright clouds in the artwork are intentional.
Client-added padding and whether a client displays server icons remain client
behavior, not a server guarantee. This does not publish a registry listing or
modify any installed client settings.

The [official SDK icon documentation](https://py.sdk.modelcontextprotocol.io/servers/media/)
describes icon metadata and data URIs. Regression tests inspect all three server
initialization records and exercise icon delivery through actual stdio and TLS
clients, separately from any product UI rendering claim.

## Supported Settings

For Claude's extension UI branding, see [MCPB packaging](integration-mcpb.md).
For Codex's installed plugin listing, see [local plugin setup](integration-codex-plugin.md).
That package references the existing reviewed launcher; it does not replace D1
enrollment or the managed configuration/launch checks described here.
Manual `mcpServers` configuration and MCP protocol `serverInfo.icons` are not the
same registration surface as the desktop extension manifest's `icon`.

| Profile | Explicit selected target | Managed part |
| --- | --- | --- |
| `codex-config` | `config.toml`, user or trusted-project layer | One `mcp_servers.NAME` table |
| `claude-code-project` | Project `.mcp.json` | One `mcpServers.NAME` entry |
| `claude-desktop` | `claude_desktop_config.json` | One `mcpServers.NAME` entry |

The owner supplies each canonical path and existing parent; no HOME scanning,
default client selection, shared global credential or implicit project discovery
occurs. Configuration outside `.golem` is an explicit approved file change, not
a bypass of any existing source/protected-file policy. Targets inside native
`.golem` or installer state are forbidden. Existing parent directories must be
owner-owned and not group/world writable. Files must be owner-owned, single-link,
regular, non-executable, non-special and not group/world writable. Existing 0600
or 0644 modes are preserved; a new file is 0600. Backups are always 0600 under
0700 state. Review any pre-existing readability of secrets separately.

JSON edits use the standard decoder for member/value spans, after strict duplicate
key/UTF-8/depth validation. Only the selected member and necessary separator are
inserted/removed; unrelated values, formatting and hooks are not reserialized.
TOML uses Python `tomllib` for semantics and appends one exact marked table, leaving
all original bytes/comments intact. Unsupported/conflicting TOML layouts, JSONC,
duplicate names, invalid JSON, symlinks or ambiguous/edited managed entries block
instead of normalizing or taking over existing configuration. Semantic comparison
checks that every non-managed value is unchanged. Uninstall of an otherwise
unchanged installation restores the original bytes exactly.

This is a bounded implementation of the integration design's installer, **not**
every client's config schema: Claude user-local `.claude.json`, hook installation,
hook trust UI, settings precedence overrides and Windows ACLs are not added.
Existing hooks remain untouched; D3's separately reviewed fragment/trust workflow
is still explicit. Actual Desktop/Hosted activation is not inferred from a file.

## Plan and Apply

Use a new owner-private installation-state directory **outside projects and the
D1 registry**. Installer records must not be mixed into native evidence. All
example paths are placeholders, not instructions to modify an installed product.
Stop the selected clients and cooperating config writers before applying. The
required `clients_stopped: STOPPED_OWNER_ATTESTED` is an owner statement, not
independent process verification or permission to kill a process.

```sh
python3 tools/integration_install.py init --state /private/install-state \
  --approve-installation
python3 tools/integration_install.py schema --operation install
python3 tools/integration_install.py runtime
```

Run `runtime` in the reviewed optional MCP environment. It returns the original
D5 interpreter pin, canonical SDK root/identity and direct SDK file pins for
`mcp==2.3.0` / `mcp-types==2.3.0`. This is not a hermetic lock or publisher
authentication of transitive packages. Preserve/review the returned object as
each target's `runtime`. The generated launcher uses D5's `-I -B` bootstrap,
explicit reviewed import roots and no `PYTHONPATH` lookup. It rechecks runtime,
producer, D1/D2 policy, current grants and managed config before serving D2.
No arbitrary argv/environment/native mutation is supplied by a model.
Generated arguments containing `${` are rejected so client environment expansion
cannot silently change the owner-reviewed literal paths or launch command.

An install request has exactly `installation_id`, `clients_stopped`, `targets`.
Each target has `client`, `config`, `server_name`, `runtime`, `transfer_policy`.
The latter is the existing D2 `{path, sha256}` policy pin, not a new grant. Up to
eight distinct target paths are accepted. Each uses its own reviewed client
policy; a config/client label does not authenticate a host. The installer never
changes grants or upgrades LOCAL_HOST consent to MODEL_SERVICE.

```sh
python3 tools/integration_install.py plan --state /private/install-state \
  --operation install --input /private/install-request.json
python3 tools/integration_install.py apply --state /private/install-state \
  --input /private/reviewed-plan.json --reviewed-plan-sha256 PLAN_SHA256 \
  --approve-installation
```

Retain the canonical plan privately and review it before apply. It binds complete
requests, producer/runtime/policy pins, state/parent identities, original file
hash/mode/inode/timestamps, managed before/after entry and resulting file hash.
It does not print the full unrelated config or secrets as a diff. Raw original
bytes are backed up privately before the first config change. Plans/schema commands
do not install, invoke a client, access conversations or run native commands.

Apply holds the installer-state lock and takes nonblocking config-parent locks.
It revalidates every target and backs up all targets before the first write.
Files publish individually with fsync and atomic replacement; new-file publication
does not overwrite an intervening file. These are cooperative local locks, **not
a filesystem compare-and-swap against an uncooperative editor**. Stop writers;
there remains a final check/rename window against same-user code ignoring locks.
Concurrent managed installers/stale plans fail without retry.

The immutable launch inputs precede config writes; `committed.json` is published
last. Before commit or after removal begins, the generated launcher refuses to
start. Success is **RELOAD_REQUIRED / client_activation NOT_OBSERVED**, not a
connected host, understood context, native QA or semantic completion.

## Removal and Partial Apply

A removal request contains `installation_id` and the same stopped-client
attestation. `plan --operation remove` and `apply` require fresh exact approval.
Only the still-matching managed entry is removed. Later unrelated user edits or
other servers survive. Changed managed bytes block removal for owner review.
Backups, receipts, `.golem`, native evidence, grants and unrelated hooks remain.
Newly created config files are left as empty valid scaffolds, not deleted.
Removal disables future installed launches but does **not** revoke an existing
D2 process's grants or recall delivered context. Stop/reload the host and use
the separate D1 revoke procedure when access itself should be withdrawn.

```sh
python3 tools/integration_install.py inspect --state /private/install-state \
  --input /private/install-reference.json
python3 tools/integration_install.py repair --state /private/install-state \
  --input /private/original-reviewed-plan.json --reviewed-plan-sha256 PLAN_SHA256 \
  --approve-installation
```

The inspect input is exactly `{"installation_id":"owner-selected-id"}`. A crash,
disk error or busy parent may leave PARTIAL/PARTIAL_REMOVAL, not a rolled-back or
successful install. Preserve everything. Repair requires the exact retained
original plan, a fresh explicit owner approval, unchanged producer/pins and
original before bytes or exact intended after bytes/mode. Already published
matching files are observed, not rewritten. Drift, damaged backups or changed
parents block; no automatic backup restore, new-ID takeover or evidence deletion
is performed. Already completed IDs cannot be reused. Changed managed entries
require owner investigation, not forced removal. Record capacity is bounded by
128 installations, 128 bootstraps and existing D1 audit admission limits. No GC.

`inspect` reports the retained publication phase, not a fresh client activation
or full config audit. Runtime and settings are rechecked at launch/removal.

## Approved Project Bootstrap

Bootstrap input has exactly `bootstrap_id`, `project_id`, `root`. The root must
already exist, be canonical/owner-owned, not group/world writable and not overlap
installation state or lie inside `.golem`/`.git`.
`plan --operation bootstrap` and `apply` reuse exact-plan/owner approval.
**Existing `.golem` always blocks bootstrap**, even if empty. Use existing D1
describe/enrollment for an existing project; do not replace/move its directory.

The only generated content is a private new `.golem/integration/manifest.json`
declaring the selected IDs and `grants_created: false`, `work_created: false`.
No capsule, Work, source file, SDK, engine, selection, grant, event or journal is
generated. In particular `golem init` is not called: that command creates a
capsule template and is not a project-integration authority. This manifest is a
non-secret scaffold reference, not readiness or a native discovery/approval API.
Review `.gitignore` before later creating private material; bootstrap does not
rewrite ignore rules, AGENTS.md or any existing source/config file.

An explicitly approved partial bootstrap repair requires the retained created
directory identity and exact allowed scaffold; unexpected files are preserved
and blocked. A crash before the created-identity receipt is retained cannot be
automatically attributed or repaired. No cleanup/removal of `.golem` is offered.
After bootstrap, new Work creation and D1 enrollment remain separate original
procedures. No existing Work is resumed, migrated or adopted automatically.

## Verification and Basis

Unit tests cover lossless edits, owner/pin/schema refusal, stale bytes/metadata/
parents, managed drift, other servers, missing files, private backups, crash
boundaries, partial removal, explicit repair, lock contention, racing file creation
and non-overwriting bootstrap. `verify_install_schema.py` independently validates
the closed request schemas. `tests/c/integration_d1_install.py` tests installed
launchers over real modern/legacy SDK stdio and disposable native status/next,
full Work bytes/modes preservation and removal. Optional pinned Codex/Claude
CLI fixtures actually parse installed scoped configs in isolated homes; this is
not a real Hosted provider, Desktop UI or model-understanding test. CI executes
the gate separately on macOS/Linux under ASan/UBSan. Native core is unchanged.

Format/support basis reviewed 2026-10-22:
- [Official Codex MCP configuration](https://developers.openai.com/codex/mcp):
  TOML stdio command/args; project trust remains separate.
- [Claude Code MCP scopes](https://code.claude.com/docs/en/mcp): project JSON and
  scope/approval distinctions; no silent user-local settings rewrite.
- [Official MCP SDK host setup](https://py.sdk.modelcontextprotocol.io/get-started/real-host/):
  Desktop JSON launcher and separate restart/discovery verification.
- Existing [D5 update/recovery research](integration-layer-references.md#d5-update-and-recovery-review):
  immutable inputs, interruption boundaries and complete mediation. These are
  design guidance, not a distributed transaction or TUF compliance claim.

Windows, network filesystems, physical power-loss recovery, every client version,
real Hosted activation and installer-driven hook trust remain unverified
or unsupported as stated above. Tests never touch TRAP or real Work evidence.

Separate owner-approved [Codex desktop verification](integration-codex-desktop.md)
on 2026-10-24 exercised six read tools with three synthetic Works in a new
conversation. Shared configuration and startup success did not establish tool
exposure in the existing conversation. This result does not certify automatic
installation, existing-chat hot reload or every desktop client version.
