# Revision-scoped status

Each evidence row exposes the [common verification dimensions](evidence-verification.md).
Domain PASS, parser validity, captured execution and hash integrity remain separate.

`tools/revision_status.py` projects E2E, local QA, remote CI, native completion and
deployment into one view. It does not create CI/deployment systems, change native
acceptance, run tests, finalize Work, recover reports, or deploy. It reuses the
existing recorder, source identity and bundle checks.

## Read-only entry

```sh
python3 tools/revision_status.py INDEX.json --cwd REPOSITORY
```

The index selects evidence explicitly; it is not authority or an execution plan:

```json
{
  "schema": "golem.revision-status-index.v1",
  "binding": {"project_id": "project", "work_id": "work"},
  "repository": "owner/repository",
  "entries": [
    {"id": "check", "channel": "local_qa", "adapter": "command.v1",
     "bundle": "/private/evidence/observation", "revision": "COPY_RECORD_SHA256",
     "step": "check", "scope": "focused-regression"}
  ]
}
```

Use intact `agent_io` bundles and their `record.json` SHA-256. Entries are checked
individually; corrupt evidence does not erase valid results in other channels.
Limits: 128 entries and existing bounded JSON inputs. The target must be a Git root
whose HTTPS/SSH GitHub origin matches the index repository. Enterprise/other
providers require reviewed adapters, not identity bypasses.

The target includes commit, tracked/untracked source tree hash and dirty state.
Local evidence needs unchanged before/after source matching that target. Missing
source is UNBOUND; source mutation is not current evidence. Remote commit matching
covers only a clean local source. A dirty tree is COMMIT_ONLY_DIRTY_SOURCE even if
HEAD matches. Non-atomic snapshots exclude ignored dependencies, like the existing
recorder; this is not hermetic build verification. Source is checked before and
after projection; detected changes block acceptance.

## Adapters

| Adapter | Channels | Result |
| --- | --- | --- |
| command.v1 | e2e/local_qa | OBSERVED_EXIT_OK, never semantic test PASS |
| junit.v1 | e2e/local_qa | UTF-8 JUnit stdout, actual nonempty cases and consistent counters; errors/failures FAIL, skips PARTIAL |
| github-run.v1 | remote_ci | Captured REST run with exact repository, workflow ID, SHA, run ID/attempt and URL |
| github-deployment.v1 | deployment | Captured deployment/status pair with exact SHA, environment, deployment/status IDs and API URLs |
| native-completion.v1 | completion | Captured native response, bound Work/selection; historical DONE requires revalidation |

GitHub run `scope` is the decimal workflow ID, not its mutable name. Deployment
`scope` is the exact environment; stdout has `deployment` and `status` keys holding
provider responses. Fetching remains in explicitly approved read-only commands or
provider adapters; this reader never executes instructions from logs or indexes.
JUnit scope is the declared index label, not an authenticated acceptance plan;
`scope_basis` states that distinction. DTDs/entities, empty reports and contradictory
counters cannot manufacture PASS. Coverage sufficiency stays with existing policy.

Each result retains source_relation, freshness, scope and authenticity flags.
Conflicting current-source results yield CONFLICT, never a convenient PASS.
Stale results stay visible but do not enter current-source aggregation. No implicit
rerun ordering is assumed. The index does not enumerate every required check;
channel PASS covers only the selected evidence, not all project workflows/tests.

Remote PASS means a recorded result for the matching revision, not latest remote
state or currently serving software. `remote_latest_verified=false`, unsigned
`authenticity_verified=false`, and deployment `serving_currently_verified=false`
remain explicit. Pending, cancelled, neutral, inactive, missing and invalid are
not PASS. Hash checking is not producer authentication.

## Fresh native completion

```sh
python3 tools/revision_status.py INDEX.json --cwd REPOSITORY \
  --cli GOLEM_BINARY --work WORK_DIRECTORY --selection SELECTION_ID \
  --output NEW_PRIVATE_OBSERVATION
```

All four optional arguments must be supplied together. This runs only existing
`work record`, `session next` and `completion resume` queries via `observe_plan`.
It does not start providers, regenerate reports, finalize, or dispatch host effects.
The private recorder retains requests, raw outputs, diagnostics and source hashes.

Only successful, source-pinned live native DONE with valid receipt/evidence-root
digests sets `native_acceptance_verified=true`. Stored DONE never sets it. The live
query controls the completion summary while historical results stay visible.
Source changes between query and projection block acceptance. Native document
generation/source guards remain authoritative. This describes the query instant,
not a guarantee against later Work mutation or proof of independent review.

`overall_completion=NOT_INFERRED`: native completion, remote CI and deployment are
distinct. None grants execution/deployment authority. CLI exit=0 means a valid
projection, not project completion; failures/missing checks remain in JSON.
No narrative report is generated or independently editable status stored.

## Explicit Remote Refresh

For restartable continuous collection and automatic policy discovery, see
[Continuous Revision Status Collection](status-collector.md). The bounded
resource-ID refresh below remains available independently.

`tools/remote_status.py` connects the common projection to bounded, read-only
GitHub REST requests. It is not a background collector. It requires the same index,
an explicit resource query file, and a **new private output directory outside the
repository**:

```sh
python3 tools/remote_status.py INDEX.json QUERIES.json --cwd REPOSITORY \
  --output NEW_PRIVATE_CAPTURE --timeout 60
```

```json
{"schema":"golem.remote-status-query.v1","queries":[
  {"id":"ci","channel":"remote_ci","scope":"20","resource_id":10},
  {"id":"production","channel":"deployment","scope":"production","resource_id":30}
]}
```

CI `resource_id` is a run ID and `scope` its numeric workflow ID; deployment
`resource_id` is a deployment ID and `scope` its environment. IDs must be selected
by the caller: this does **not** discover all required checks or the environment's
currently serving deployment. At most 16 resources, one GET per CI run and two
per deployment, are queried serially. Timeout is bounded to 300 seconds; individual
socket operations are capped at 20 seconds. The monotonic deadline is checked
between reads/requests; a blocking socket operation can overrun it by that cap.
No retry, polling, webhook registration, test dispatch, deployment or finalization
occurs. An optional `GH_TOKEN` is read from the environment, never from arguments
or an evidence file. Public resources may be queried without a token.

The fixed GitHub HTTPS origin uses certificate verification; redirects and proxies
are deliberately refused to avoid sending credentials to a changed identity.
Repository renames require explicit index/origin revalidation. Bodies are limited
to 2 MiB; duplicate JSON keys, non-JSON content, compression, and credential echoes
are refused. HTTP errors retain a controlled status-code diagnostic, not their
potentially sensitive response bodies. Rate limits stop the request; the tool
never retries through them or substitutes a cached PASS.

For CI, the GET refreshes the selected run's current attempt, with exact run,
repository, workflow and commit checks. It supersedes only historical evidence
for that same run. Different runs retain conflicts. For deployment, all statuses
returned by a complete single page (up to 100) are validated; any pagination link
blocks the query rather than claiming completeness. The unique latest `created_at`
selects the result without assuming list or numeric-ID ordering. Tied timestamps,
duplicate IDs, absent statuses, mismatched environment/identity, or truncated
responses block the query. This is conservative, not a guarantee of a globally
atomic remote snapshot; status changes after a GET remain possible.

`channels.*.scopes` exposes the selected workflow/environment/suite results
separately. A failed remote request makes the channel `REMOTE_QUERY_FAILED`, even
when historical PASS exists. Source changes from query start through projection
produce `SOURCE_CHANGED` and invalidate the live row; dirty trees
remain outside remote commit coverage. Each successful row's
`remote_latest_verified=true` is limited by
`latest_scope=SELECTED_RESOURCE_AT_REQUEST_TIME` and its observation timestamps.
The top-level `remote_latest_verified=false` remains: not every remote check or
deployment was discovered. Native completion authority is never inferred from a
remote result. The native live query and remote refresh remain separate explicit
entry points, sharing the same projection.

Captures retain valid provider response bytes, their hashes, generated endpoint
paths, queries, source pins, common verification dimensions, result JSON and a
SHA-256 manifest in a private directory. Hashes and TLS observation are not a
signed attestation or independent review. The saved `result.json` is a historical
record of that invocation, not a reusable live-status cache. The normal reader
does not import saved remote rows as fresh evidence. No claim of current serving
health, billing authority or comprehensive project completion is made.

## Research Basis

Reviewed material and engineering applications, not measured Golem benefits:

- [SLSA v1.2 Build: Verifying artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts),
  subject, canonical source and builder trust checks: compare exact identities and
  distinguish integrity from authenticity. No SLSA level/attestation claim.
- Shahin, Babar and Zhu, *Continuous Integration, Delivery and Deployment: A
  Systematic Review on Approaches, Tools, Challenges and Practices* (IEEE Access,
  2017), [paper](https://arxiv.org/pdf/1703.07019), foundations (Section II.A)
  and reported review results: expose pipeline
  stages distinctly, without conflating test success and deployment.
- Winters, Manshreck and Wright (eds.), *Software Engineering at Google* (2020),
  [chapter 23](https://abseil.io/resources/swe-book/html/ch23.html), CI concepts and
  result visibility: source-specific observations, separate from executing builds.
  Public chapter sections were consulted, not the entire book.
- GitHub official [workflow-run API](https://docs.github.com/en/rest/actions/workflow-runs),
  [deployment status API](https://docs.github.com/en/rest/deployments/statuses) and
  [deployment SHA identity](https://docs.github.com/en/rest/deployments/deployments):
  preserve provider states, IDs, attempts, environment and revision.
- GitHub [REST best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api),
  consulted 2026-10-10: serial requests, bounded failure handling and explicit
  resource selection. GitHub recommends webhooks over polling; this implementation
  deliberately provides only an on-demand refresh. Conditional-request caching
  would be appropriate for a future explicitly requested collector, not a reason
  to treat stored data as live. Its recommendation to follow redirects is narrowed
  here by credential/identity policy: redirects fail closed instead.

Tests use real subprocess bundles plus an actual native completion fixture:
DONE, historical DONE revalidation, and source-change refusal. Remote adapters
use provider-shaped fixtures; live CI, deployment health and provider signatures
are not verified by those tests.
Remote-refresh tests additionally exercise GET transport policy, HTTP/rate errors,
body and page bounds, current-attempt supersession, preserved conflicts, deployment
ordering ambiguity, dirty/source-changing revisions and failure without cached
PASS fallback. Fixtures do not establish actual GitHub access or deployed health.
