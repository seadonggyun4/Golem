# Feature and result boundaries

When the owner supplies a feature artifact, its `tools/integration_distribution.py catalog`
lists source ceilings and contracts without reading Work or creating approval.
A launcher-only plugin may not include that artifact. Use actual tool discovery
and the table below; do not search the host for packages or infer a profile.

| Profile | Source ceiling | Required authority |
| --- | --- | --- |
| read | D2 context/evidence/native observations | Existing D1 + D2; external files require explicit resource policy |
| prepare | read plus M2 drafts/input review and M5 review proposals | Same read authority; draft never dispatches |
| task | D2/M2 plus existing D4/M3 task actions | Exact current D4 owner action; QA approval remains separate |
| quality | D2/M2 plus existing QA/evidence/research/accounting actions | Exact D4 action; helper effects require separate M4 contract |
| parallel | D2/M2 plus bounded native candidate/workspace/inventory actions | Exact D4 action; candidate host and termination attestation require separate M5 contract |

Actual discovery may expose fewer tools. A profile never enrolls projects, changes
policies, enables helper/host effects or grants credentials/network/export rights.

`golem_work_inspect` takes project_id, work_id and view (status/next/record).
Keep opaque plan_id/plan_sha256 and original action_id/request_id from returned
preparations. Do not invent an ID or hash to turn unavailable/stale evidence into
an accepted action. `golem_workspace_read` returns an original D4 historical result;
current workspace RESUME is an exact owner action, not a read-permission upgrade.

Candidate compare/review/target checks use owner-pinned queries. Selection never
authorizes merge. M5 DAG/merge proposals have NOT_EVALUATED readiness and grant no
resource reservation. Scheduler, typed-edge evidence acceptance, receiver resource
broker, merge queue, integration workspace/fresh QA, target ref CAS broker and
merge publication receipt are NOT_IMPLEMENTED. Do not suggest tools for these.

If setup is actually requested, use the separate Golem Setup skill. Existing
connections and approvals remain in force; ordinary Work failure is not permission
to reinstall, reconnect, rewrite pins, reload or change configuration.
