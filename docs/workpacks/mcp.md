# Work Pack through common MCP

All 14 existing Work Pack CLI operations have common MCP routes. The separate
exact-action contract was explicitly selected from the [review proposal](mcp-design.md)
(SHA-256 `9ec6ba68ccd10cda5e40bade7037709337a69afc1d1a87cc4230d8149c013053`).
Implementation, installed bytes, tool exposure and actual model calls are separate
verification levels. Both client packages contain the common implementation; current
policy selection can still exclude these tools. See [verification status](#verification-status).

Ask the agent naturally to inspect a Pack, find a matching Pack, or check evidence.
The agent builds tool arguments; a prompt does not grant filesystem or action rights.

## Use in Codex or Claude

Use the project’s existing development chat with its reviewed Golem connection.
No special prompt syntax or separate Golem chat is required. Local CLI commands
are an alternative; opening a directory alone does not grant MCP access.

1. Confirm the intended launcher and the current chat’s actual tools. A server’s
   `ready` state is not proof that it loaded a newly installed launcher. Follow the
   [Codex reload guide](../integration-codex-plugin.md#업데이트정리) for client-specific checks.
2. Ask, for example: “Find a Work Pack for this job and inspect its requirements.”
   The catalog and every referenced Pack must be in an explicit resource contract.
   For a known Pack, request validate/inspect and compatibility with the selected version.
3. Request resolve for the exact Work and mapping; inspect blockers. Have the owner
   select the separate binding digest and exact D4 action before calling bind.
   Read explain afterward; a recorded binding is not permission to execute work.
4. Develop and test with the client’s separately authorized tools. Use proposal_validate
   and assess to compare claims with current native document obligations.
5. Have the owner select an exact manifest action, review its inventory/destination,
   then select the corresponding export digest/action. Verify the resulting package
   against its exact manifest through an explicitly allowed resource or native CLI.

Missing tools or scope must be resolved through review; do not rewrite policy pins,
substitute execution/QA approvals, or retry uncertain actions. A successful export
or integrity check does not finalize the Work.

## Tool and permission mapping

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

## Verification status

Snapshot: **2026-11-02**, common runtime source **f522de6**; subsequent **0339013**
changes only the Codex startup metadata generator, its packaging assertion, guide
and static review fingerprints. This is a bounded validation snapshot, not an
assertion that every Core feature is available or tested in every client.

| Level | Confirmed result | Remaining boundary |
| --- | --- | --- |
| Native/common MCP | All 14 CLI operations mapped to five tools; static, fixture and regression checks pass | Native semantics and existing authority remain mandatory |
| Installed-runtime fixtures | Both packaged runtimes: three concurrent connections, one reconnect and nine isolated reads per client passed; automatic Owner windows: zero | Local protocol checks, not model-driven Desktop E2E for every operation |
| Codex Desktop | Actual projects_list → work_inspect → bind → explain passed once each on a synthetic Work | Manifest/export/verify NOT_RUN: Desktop kept the earlier bind launcher and old tool catalog after the package metadata changed |
| Claude Desktop | Actual bind, manifest and export passed on a separate synthetic Work; native read-only verify reported VERIFIED | Verification establishes anchored integrity, not authenticated origin, semantic truth or current completion |
| Production Work | Existing TopSolar data, policies, approvals and evidence preserved | No production binding/export, QA or completion executed in this campaign |
| CI at 0339013 | Python regression and macOS/Ubuntu MCP contract jobs passed; CI Ready passed | Conditional jobs outside the changed scope were skipped; CI is not Desktop E2E |

The installation snapshot is **Codex 0.2.7**, one enabled identity, and **Claude
prepare 0.1.19**, one restored TopSolar identity. Codex’s disk metadata selects the
isolated export launcher while the running Desktop still uses the earlier bind
launcher: **effective TopSolar restoration is pending**, not complete. Claude’s
TopSolar connection is restored. Package version alone does not identify effective
launcher, policy or permission scope. Neither production connection should be
assumed to expose all Work Pack tools automatically.

Public source/CI evidence: [common source contract](../../samples/workpacks/source-contract.json),
[native/MCP fixture](../../tests/c/workpack_mcp.py),
[exact-action fixture](../../tests/c/workpack_mcp_actions.py),
[CI 0339013](https://github.com/seadonggyun4/Golem/actions/runs/41445243903).
Owner-private client traces and file inventories are retained in the workspace’s
`workpack-client-sync-20261102`, `workpack-client-e2e-20261102` and
`workpack-codex-discovery-20261102` records, referenced by `.golem-plugin-installations.json`.
They are not embedded in public docs or represented by CI results. Milestone-only
NOT_RUN/NOT_IMPLEMENTED statements in [development history](development-plan.md)
remain evidence of those earlier stages.

## Remaining work

- **Unverified:** load and confirm the export launcher in the owning Codex Desktop,
  perform the unused exact manifest/export actions only within a valid reviewed
  window, verify the result, and confirm effective TopSolar restoration. Preserve
  the successful bind and all uncertain results; do not reexecute bind or QA.
- **Unverified:** model-driven Desktop coverage of the other read/catalog/proposal/
  reference operations on both clients. Existing protocol fixtures do not cover
  this interaction layer. Arbitrary real projects and production exports are not certified.
- **Unimplemented:** general external/custom/session role bindings, independent
  principal proof, authoritative READY_FOR_RELEASE, general external typed evidence
  acceptance/QA receipt aggregation, dedicated Python/TypeScript Work Pack SDK APIs,
  automatic release and scheduler/merge broker.
- **Outside this validation:** production data/export, external network/credential
  grants and public marketplace migration. None is authorized by a Pack or by this guide.
