# Codex Desktop Synthetic Verification

## Scope

On 2026-10-24 (Asia/Seoul), an owner-approved **new desktop conversation**
completed actual Golem MCP calls against three synthetic Works. The six permitted
tools were projects_list, work_inspect, history_read, context_get, evidence_read
and completion_check, each with the `golem_` prefix. No hook, native write,
automatic resume or handoff authority was added.

The desktop host used its bundled Codex CLI 0.163.0-alpha.11.2. Earlier isolated
CLI/model tests are separate evidence: a successful CLI or standalone SDK call
does not prove that an existing desktop conversation exposes the tools.

## Observed Results

The parent conversation inspected the new conversation's actual `mcpToolCall`
records, including server, tool, arguments, completion status and duration.
These were not subprocess/CLI substitutes for desktop calls.

| Tool | Calls | Observed duration (ms) |
| --- | ---: | --- |
| golem_projects_list | 1 | 107 |
| golem_work_inspect | 3, one per synthetic Work | 139, 103, 117 |
| golem_history_read | 1 | 92 |
| golem_context_get | 1 | 357 |
| golem_evidence_read | 1 | 170 |
| golem_completion_check | 1 | 191 |

All eight calls completed without errors or retries. The conversation reported
AVAILABLE deliveries with execution_authorized=false, native_state_changed=false
and ownership_transferred=false. Its entire turn took 38.882 seconds, including
model processing. This single bounded run is not a latency distribution, load
test, reliability guarantee or cost-saving measurement.

Interpretation remained bounded: AVAILABLE means delivery, not Work completion.
The completion check returned RECONCILE_SESSION with acceptance_verified=false
and completion_sequence=0; this does not establish a unique cause or the presence
of every required document. Evidence hash verification establishes byte integrity,
not truth. Capacity is an observation, not a reservation. The server's
model_consumption=NOT_OBSERVED assertion was not rewritten: the desktop trace and
final interpretation provide separate client-side evidence of model use.

## Existing Versus New Conversation

The existing conversation had no exposed Golem tools even though shared settings
contained the approved enabled launcher. Read-only desktop logs showed Golem
initialization success. Process start times also showed that the running app and
app-server predated registration, despite an attempted reopen.

With the same shared configuration and policy, the new desktop conversation
exposed all six tools and completed the eight calls above. This isolates the
observed symptom to existing-conversation exposure/refresh rather than a general
registration or server-startup failure. The precise internal client cause remains
unproven; do not claim all existing conversations reload on restart or that every
client version behaves this way.

When diagnosing this boundary, distinguish configuration, initialization, tool
exposure and actual calls. Inspect the exact client's logs and tool catalog.
With owner approval, test a new conversation before changing permissions or pins.
Do not automatically terminate running clients, weaken approval checks, set every
server as required, or treat a CLI success as desktop verification.

## Plugin Path Verification

Later on 2026-10-24, the same scoped launcher was packaged as local plugin
`golem@golem-synthetic` version 0.1.3. This was distinct from the manual MCP
registration above, which alone did not produce an installed plugin listing.
The owner approved adding the local marketplace, enabling the plugin and
preserving the manual `golem` table with `enabled=false`.

The initial same-name plugin server was also disabled by the manual setting.
With separate owner approval, only the plugin server name changed to
`golem-synthetic`. Resolved settings then showed manual `golem` disabled and
plugin `golem-synthetic` enabled. Launcher command/arguments and the reviewed
policy were unchanged; all unrelated parsed Codex settings matched the backup.
No automatic hook or broader permission was added.

The existing synthetic verification conversation refreshed its tool catalog and
exposed all six tools under `mcp__golem_synthetic`, attributed to the Golem plugin.
It completed these actual desktop MCP calls, not CLI/SDK substitutes:

| Tool | Calls | Observed caller elapsed time (ms) |
| --- | ---: | --- |
| golem_projects_list | 1 | 293 |
| golem_work_inspect | 3 | 137, 121, 125 |
| golem_history_read | 1 | 369 |
| golem_context_get | 1 | 1267 |
| golem_evidence_read | 1 | 650 |
| golem_completion_check | 1 | 264 |

All eight returned AVAILABLE without errors or retries, with
execution_authorized=false, native_state_changed=false and
ownership_transferred=false. Context remained READING_AID with
execution_ready=false; completion remained RECONCILE_SESSION with
acceptance_verified=false. One sample per operation is not a performance
benchmark or a comparison proving that plugins are faster/slower than manual MCP.

Owner-provided screenshots separately confirmed the installed listing and icon.
After correcting both `author.name` and `interface.developerName`, another
screenshot confirmed **Donggyun Seo** in the actual client UI. The private
generator and source/installed manifests were updated, not just this document.
The owner-approved screenshot is published in the README; it contains no private
policy, local path, credential or Work evidence. The public installation recipe
is in [Codex local plugin setup](integration-codex-plugin.md). The machine-specific
generator/package and its approval records are not public repository artifacts.

The synthetic project's 84 file hashes were unchanged. Existing policies,
Claude's connection and all unrelated settings were preserved; native Works
and TRAP were not modified. Normal private audit appends are expected.
This existing-chat refresh succeeded in this run; it does not erase the earlier
exposure failure or promise universal hot reload.

## Public Generator Reinstallation

The public generator introduced in `620659d` was subsequently exercised against
the same approved synthetic installation on 2026-10-24. An explicit private JSON
containing only the previously reviewed command and argument array was supplied
to `tools/integration_codex_plugin.py`. A fresh output used the existing
marketplace/server identifiers; the previous package was backed up privately.
The generated catalog and package were placed at the already registered local
source and reinstalled with the desktop client's bundled `plugin add` command.
No new marketplace, policy, grant, hook or manual-server setting was required.

The installed plugin files matched the public generator's output byte for byte.
The launcher values and parsed Codex configuration were unchanged. Both clients'
reviewed policy hashes and all 84 synthetic project file hashes still matched
their retained baselines. Package generation and installation did not alter
the native engine or its producer pins. Private launch inputs, backups and
generated host-specific packages remain outside the public repository.

The approved desktop conversation again exposed `mcp__golem_synthetic` and
completed the following actual calls, with zero errors or retries:

| Tool | Calls | Caller elapsed time (ms) |
| --- | ---: | --- |
| golem_projects_list | 1 | 384 |
| golem_work_inspect | 3 | 160, 205, 252 |
| golem_history_read | 1 | 114 |
| golem_context_get | 1 | 436 |
| golem_evidence_read | 1 | 234 |
| golem_completion_check | 1 | 243 |

All responses were AVAILABLE with execution_authorized=false,
native_state_changed=false and ownership_transferred=false. Completion still
returned RECONCILE_SESSION, acceptance_verified=false and completion_sequence=0.
Context remained READING_AID with execution_ready=false. The entire conversation
turn took 32.657 seconds, including model processing; these single samples are
not a latency distribution or a performance comparison.

This confirms public generation, installed-file identity and actual desktop
calls within the approved scope. It does not independently establish a new
server process after reinstallation or universal client hot reload. No new UI
screenshot was taken in this run; earlier icon/developer display observations
remain separately scoped. Existing Claude connection, evidence, TRAP and real
Works were preserved. Expected private integration audit appends are distinct
from native Work mutation.

## GitHub Marketplace and Setup Skill

On 2026-10-24, the owner approved transition to the repository-backed `golem`
marketplace. Package `golem@golem` 0.2.0 was installed from GitHub, with developer
Donggyun Seo, website https://github.com/seadonggyun4/Golem and the
`golem-setup` skill registered as the initial setup skill. Tracked installed
package bytes matched the reviewed source. The existing exact synthetic launcher
was connected through the owner-private adapter record; native producer/runtime
pins and both model-service policies were retained. The old local
`golem@golem-synthetic` installation was preserved but disabled, and manual
`golem` remained disabled. The new server is `golem-local`.

The first setup observation failed with SETUP_VALIDATION_FAILED and exit code 1:
status opened the owner lock with writable access, which the agent's read-only
sandbox rejected. No native query was performed in that attempt. The adapter
was corrected to use a read-only descriptor and shared lock for status/serve;
configure keeps exclusive writable locking. A regression simulates a host that
rejects writable lock opens. The corrected package source is `3393070`.
The existing private approval was neither rewritten nor regenerated.

The actual desktop conversation discovered and applied `golem:golem-setup`.
Its subsequent installed-script status returned CONFIGURED, exit code 0, in
847 ms. It then used the plugin's `mcp__golem_local` tools for these calls:

| Tool | Calls | Caller elapsed time (ms) |
| --- | ---: | --- |
| golem_projects_list | 1 | 357 |
| golem_work_inspect | 3 | 239, 203, 263 |
| golem_history_read | 1 | 186 |
| golem_context_get | 1 | 1120 |
| golem_evidence_read | 1 | 1383 |
| golem_completion_check | 1 | 986 |

All eight calls returned AVAILABLE with zero errors/retries and
execution_authorized=false, native_state_changed=false,
ownership_transferred=false. Native completion remained RECONCILE_SESSION with
acceptance_verified=false and completion_sequence=0. Context remained READING_AID,
execution_ready=false. This bounded observation verifies skill discovery, setup
diagnosis and actual calls; these timings are not a performance distribution.
The earlier setup failure remains a separate observation.

Semantic config comparison allowed only the new Git marketplace/plugin and the
old plugin's disablement. Other settings, both reviewed policies and all 84
synthetic file hashes were unchanged. Existing evidence and Claude connection
were preserved, with normal private read-audit appends. TRAP and real Works were
not modified. No new screenshot was taken: the installed website/skill/icon
metadata was checked, while actual UI rendering remains the earlier separately
recorded observation. The GitHub catalog is a distribution source, not an
OpenAI-reviewed public directory listing. Private connection records and source
launcher arguments are excluded from this document and the repository.

## Preservation and Limits

For the initial manual-server run, final checks compared Codex settings, the exact Golem launcher and
policy, Claude's active policy/manual configuration, and synthetic file hashes
and modes against retained baselines. No additional configuration changes were
needed for the new conversation. Private audit records were appended normally;
read-only native operations do not imply zero audit writes. Existing evidence
was not deleted or rotated. TRAP and real Works were not accessed or modified.

This verifies only the approved synthetic scope on the observed macOS client.
It does not certify production Works, product acceptance, Hosted gateway activation,
all providers, negative cases in this desktop run, or existing-chat hot reload.
Private policies, approvals, raw traces, personal paths, hashes and conversation
identifiers are deliberately excluded from this public record.

See [D2 contracts](integration-d2.md), [owner installation](integration-install.md),
[Claude MCPB verification](integration-mcpb.md) and the
[official Codex MCP configuration](https://developers.openai.com/codex/mcp).
