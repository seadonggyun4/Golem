# Work Pack through common MCP

All 14 existing Work Pack CLI operations have common MCP routes. The separate
exact-action contract was explicitly selected from the [review proposal](mcp-design.md)
(SHA-256 `9ec6ba68ccd10cda5e40bade7037709337a69afc1d1a87cc4230d8149c013053`).
This is source/fixture delivery, not installation in Codex or Claude. Existing
client packages and TopSolar policies remain unchanged.

Ask the agent naturally to inspect a Pack, find a matching Pack, or check evidence.
The agent builds tool arguments; a prompt does not grant filesystem or action rights.

| Common tool | Operations | Required scope |
|---|---|---|
| `golem_workpack_read` | validate, inspect, compatibility, resolve, explain, proposal_validate, assess, reference_observe | Existing D1 Work record access + explicit D2 tool selection |
| `golem_workpack_resource_read` | list, search, receipt_verify | D1/D2 + separately owner-pinned resource files and tool selection |
| `golem_workpack_bind` | pack bind | D4 exact request + separate native binding digest |
| `golem_workpack_receipt_manifest` | receipt manifest | D4 exact request + private output parent/identity/format |
| `golem_workpack_receipt_export` | receipt export | D4 exact manifest inputs + separate native export digest |

For ordinary reads supply `project_id`, `work_id`, `operation` and the relevant
exact JSON string. `compatibility` also takes `core_version`; `reference_observe`
takes independent source/config/Pack SHA-256 values. `assess` accepts 1–8 proposal
strings. The agent cannot supply a host input path. Native parsers and current
Work contracts decide validity; this Python layer only constructs fixed commands.

For catalog/search, the resource contains the index plus every Pack file it names.
Select its `resource_id` and basename `index_name`; search additionally takes `query`.
For receipt verification, the resource contains the sealed package at its logical
root and the caller supplies `manifest_sha256`. Missing or mismatched files fail.
No directory enumeration, implicit file grant, URL fetch or external Truthound call
is added. Existing resource limits (64 files, 1 MiB/file, 8 MiB total) may be narrower
than native receipt limits; oversized native packages are not supported by this
MCP snapshot route. Input envelopes remain bounded to 256 KiB and native limits
also apply. Results must fit the existing D2 disclosure and audit budgets.

Work reads compare the native record before/after; drift blocks delivery.
Resources are rehashed after the native call. Failures retain audit evidence and
are never retried automatically. A successful delivery is not authenticated origin,
semantic truth, execution permission, release readiness, QA PASS or completion.

The common schemas and package closure are shared by Codex and Claude. The
installed source/producer pins must be explicitly reviewed before upgrading;
source implementation and protocol fixtures are not Desktop E2E evidence.

For the three D4 tools the caller supplies only `project_id`, `work_id`,
`action_id` and `request_id`. The pinned action envelope uses the existing
`golem.integration-native-action.v1` form: `native_json` contains `request_json`
(exact native JSON text), plus `approval_digest` for bind/export. Manifest/export
also contain `output_parent`, `output_identity` (`device`, `inode`) and `format`
(`json` or `markdown`). Body/context/count are empty and the execution `approval`
field must be null: a QA approval receipt cannot authorize binding/export.
The parent must be canonical, owner-private, outside project/runtime/registry
and policy/action paths. Core rechecks its own locks, current generation,
selection, digest, parent identity and immutable publication rules.

`action_prepare` can assemble an unapproved draft and report missing fields;
it does not issue an approval or inspect an output parent. Native semantic
validation is deferred to the corresponding native resolve/manifest/action.
After owner review, `approved_action_prepare` and `action_confirm` reuse the
existing exact D4 path. A native failure after dispatch remains COMMIT_UNKNOWN;
repeat request IDs return the recorded result without another native dispatch.
Partial publication is preserved, never repaired, overwritten or retried.

The `task` profile exposes the three new D4 tool families only when the current
owner policy selects them. `read` exposes only the two read tools. No profile
selection grants authority. Existing external-role binding, semantic release
predicates, independent identity and scheduler/merge limitations remain unchanged.

Verification commands (disposable fixtures only):

```sh
python -m unittest discover -s tools -p 'test_integration_*.py'
python -m unittest discover -s tools -p 'test_capability_*.py'
python tests/c/workpack_mcp.py BUILT_GOLEM SOURCE_ROOT
python tests/c/workpack_mcp_actions.py BUILT_GOLEM SOURCE_ROOT BINDING_FAULT_HELPER
python tools/capability_refresh.py --root SOURCE_ROOT
```

The native fixtures cover all 14 CLI operations through the common service,
including private bind/export and resource snapshot verification. Current/legacy
stdio tool-list/call checks exercise read delivery; they are not Desktop UI E2E.
Reference observation uses MOCK responses and never calls Truthound. Prior M7 real
Truthound captures remain historical evidence, not a new external execution.
Boundary tests cover absent scope, foreign resource IDs, input/byte limits,
Work drift, output identity/mode/scope, separate digests and uncertain dispatch.
Actual client installation, model-driven action E2E and TopSolar execution: NOT_RUN.
