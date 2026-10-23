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

Version 0.1.2 adds a setup-only MCP mode for missing consent, missing policy,
changed policy digest or changed producer pins. Initialization remains available,
but the only tool is `golem_setup_status`; it returns fixed public guidance and
`project_access_enabled: false`. It never returns configured paths, policy
contents, registry identifiers or Work data. Without consent it does not read
the policy. No project tool, enrollment or approval-writing capability is
available in this mode. It cannot transition to normal access within a running
process: the owner must review settings and restart the extension.

`OWNER_TRANSFER_APPROVAL_REQUIRED` means disclosure consent is off;
`PRODUCER_CHANGED` means the policy pins different module bytes;
`TRANSFER_POLICY_CHANGED` means the file differs from its reviewed digest.
Do not fix these by automatically regenerating pins or enabling consent.
Other validation failures receive generic public setup guidance, not raw
exception details. Dependency, transport and asset-integrity failures can still
prevent startup; this is not a claim that every failure becomes a connected UI.
Claude controls its own connection banner; the detailed cause is available to
the model through the setup tool and in structured local stderr.

The 0.1.2 packaging adapter does not change D2 producer modules, so the explicitly
reviewed 0.1.1 policy remains compatible when its native pins and grants still
validate. Existing settings and approvals are never migrated automatically.

Version 0.1.1 uses expanded-background artwork, without an embedded white
surround. Claude still controls the outer icon container and its padding.
Updates do not silently refresh existing producer approvals: changed module
hashes require a separately reviewed disclosure policy.

Successful responses retain `state: AVAILABLE` for compatibility and add
`state_scope: DELIVERY_ONLY` and `work_completion_inferred: false`. This means
data is available, not that the Work is complete. Only the native completion
result is authoritative for the queried selection; delivery never grants
execution or ownership.

For context candidates, an exact, bounded native snapshot-mismatch observation
is surfaced as `SOURCE_SNAPSHOT_MISMATCH`, with no automatic retry. The native
status remains `GOLEM_ERR_STALE_RESULT`. Other stale errors, malformed or
incomplete diagnostics and recording failures remain `NATIVE_FAILURE`.
Free-form stderr and private paths stay in local evidence, not model output.

The 0.1.1 update was exercised in Claude Desktop 3.6556.2 on macOS using an
owner-approved synthetic-only policy. Two prompts made three native read calls:
status, completion and an intentionally mismatched context snapshot. Claude
reported the delivery-only scope, refused to infer completion and relayed
`SOURCE_SNAPSHOT_MISMATCH` with automatic retry disabled. This is a bounded
client observation, not a guarantee about every model response. The expanded
artwork was visible after installation; Claude's outer dark padding remained.
The test connection and disclosure consent were disabled afterwards, with the
previous configuration values restored. Existing producer approvals were not
rewritten for the update.

Installation is separate from Golem authorization. The owner must supply an
existing private D2 disclosure policy, its explicitly reviewed SHA-256, and
affirmative disclosure consent (default false). Normal access uses the unchanged
D2 Transfer, Service and MCP transport. Registry grants, producer pins, native read guards
and output limits remain enforced. No auto-enrollment, bootstrap, Work resume,
mutation, issuer approval or policy regeneration is provided.

The packaged producer bytes match the selected source revision, not necessarily
the previously installed release. Runtime updates still require review; this is not the D1
installer's runtime-pin transaction and does not claim its launch receipt.
Claude's local-extension warning concerns broad OS process access: a Golem grant
restriction is not an OS sandbox. Obtain explicit consent before installation.

## Audit Capacity and Interpretation (0.1.3)

Version 0.1.3 changes producer modules and requires separately reviewed pins;
existing policies are not rewritten. For an approved project, `projects_list`
also returns `golem.integration-audit-capacity.v1`: bounded metadata inventory,
limits, remaining read directories/entries/bytes and explicit blocking reasons.
The aggregate covers the shared registry, not a particular Work. It exposes no
file names or contents and is omitted when no projects are approved. The listing
does not consume a read directory and remains available at audit saturation.

The unchanged limits are 256 read directories, 16384 entries and 128 MiB logical
file bytes. Inventory errors, unsafe links/types and incomplete scans fail
closed; unknown remaining capacity is null, never zero or unlimited. A complete
observation does not reserve capacity, verify physical free space or guarantee
admission. Byte and entry limits are rechecked at each native read; future output
sizes are not reserved by this preflight.

Before compound queries create their first read record, the service checks read
directory headroom: context/handoff need five slots, evidence/completion three,
status/history one. These conservative costs include before/after observations;
early failure can consume fewer slots. Per-read checks remain in place. Stop on
`AUDIT_QUOTA`; do not automatically retry, delete evidence, raise limits or create
a replacement registry. Retention, rotation and durable archival policies remain
undecided and are not implemented by this release.

`AVAILABLE` still describes delivery only, including when the nested capacity
report is `BLOCKED`. Native `RECONCILE_SESSION` is not proof that all required
documents exist or that there is a unique cause. `EVIDENCE_NOT_REFERENCED` means
no supported committed reference was established, not that storage lacks the
object. A null `local_evidence_id` is not proof that no audit record was written.
Errors do not determine the Work's outcome. These explicit fields and MCP
instructions guide interpretation without changing native completion authority.

On 2026-10-23, owner-approved 0.1.3 installation in Claude Desktop 3.6556.2
was checked with three sequential synthetic-only calls: capacity listing,
completion and intentional unreferenced evidence denial. Claude distinguished
observed capacity from reservation, reconcile action from document completeness,
and missing reference/identifier from absent bytes/audit records. Client log
request/response intervals were 114/750/107 ms respectively (one sample each,
excluding model inference and human approval waits; not a performance guarantee).
The synthetic project's 84 files, prior approval records/policies and manual
client configuration remained unchanged. The approved connection and disclosure
consent stayed enabled. This is bounded macOS client verification, not proof that
all model answers avoid overgeneralization. Saturation, unsafe inventory and
compound-call headroom rejection are covered by local regression fixtures, not
by filling the active client registry again.

## Verification and Rollback

Tests check deterministic contents, producer-byte preservation, false/missing
consent blocking project access, digest syntax, and extracted-bundle modern/legacy stdio
connections with an empty approval registry. No actual Work is needed for icon
testing. The generated manifest was separately checked against the official
[0.4 JSON Schema](https://github.com/modelcontextprotocol/mcpb/blob/main/schemas/mcpb-manifest-v0.4.schema.json).

Version 0.1.2 was installed in Claude Desktop 3.6556.2 on 2026-10-23 with
explicit owner approval. A real `projects_list` call returned only the approved
synthetic project and its three synthetic Works, with six read-only native
tools and no execution authority. Consent and the connection were left enabled
at the owner's request; per-call client approval remains required. The synthetic
project's 84 files and the existing manual client configuration were unchanged.
Missing-consent, stale-producer and changed-policy setup responses were verified
with extracted-package modern and legacy MCP stdio tests; these are protocol
checks, not claims about every Claude error banner or other client versions.

For client verification, use a disposable empty registry and no project grants.
Inspect preview, installed extension details and connector details separately;
record where artwork is actually shown. Do not mark UI verification successful
from a protocol response alone. Remove only the test extension through Claude's
extension UI after verification, and compare the existing manual configuration
with its pre-test hash. Do not edit unrelated connector settings or preferences.
