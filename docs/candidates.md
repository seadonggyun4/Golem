# Bounded isolated candidates

The version-1 [candidate host API](../include/golem/candidate.h) coordinates
already connected agents or approved local workers. It does not launch providers,
grant shell approval, apply patches, merge branches or authorize publication.
Existing single-Work execution remains unchanged. Parallelism is explicit opt-in.

## Integration

1. Register the repository, allocate independent child Works, and provision their
   [workspaces](workspaces.md) under repository-wide admission. Preserve the main
   tree's uncommitted changes. Supply dedicated canonical build/temp directories
   outside all candidate trees and Work stores.
2. Freeze a common task, base commit, gate fingerprint, environment and experiment
   protocol. Use `golem_candidate_gate_digest` on an issued execution-v4/v5 checkpoint
   before dispatch. It includes executable identity, protected oracle file bytes,
   gate configuration, inventory policy and log policy. The example manifest has
   placeholder digests, not executable authorization.
3. Open one exclusive parent Work coordinator and the repository-wide admission
   owner. Construct `golem_candidate_host` from trusted callbacks, never agent
   JSON. Call `create`, then `enroll` for every candidate.
4. `reserve` durably reserves the group budget before enqueueing a root admission
   ticket. The existing global scheduler grants it. `start` checks the current
   ticket and budget, records START_INTENT, then invokes the nonblocking callback
   once. The callback must publish the real Work/session/runtime binding through
   admission and reach RUNNING. Candidate tickets are background, non-nested
   tickets; local execution uses a shared bounded worker pool with matching
   CPU/memory and IO reservations. The coordinator itself must not hold a worker
   slot while waiting for these workers.
5. The current agent follows the child's normal Markdown/development/QA contract.
   The host supplies live leases, heartbeat/cancellation and reviewed command
   authorization. Workers may not bypass this through a separate shell path.
6. After observed termination, persist the termination proof in the parent CAS
   and issue `finish` with the child's QA receipt and actual usage. Only after
   settlement/release succeeds may the host acknowledge the worker-pool job.
7. `compare` collects fresh evidence, then renders a deterministic comparison.
   `select` records an explicitly authorized human choice. A separate target Work
   must run QA against the actual target source before `target-check` can pass.

Callbacks and borrowed handles must remain stable during a serialized call. The
host must not reenter parent APIs from callbacks. Close child writer handles
between calls when independent current-agent clients need them. Replies are
owned buffers released with `golem_execution_reply_free`; outputs are unchanged
on failure. JSON allocations are private to the module and json-c.

## Manifest and requests

[group.json](../samples/candidates/group.json) is a structural single-candidate
template. Every field is required. Keep `parallel_opt_in: false` and `workers: 1`
unless the operator expressly enables multiple candidates. V1 supports 1-8
candidates and one dispatch intent per candidate. A retry is a separately
budgeted candidate/group, not a hidden second attempt.

`cpu` uses admission CPU-millis units; `memory` uses bytes; `io` is logical slots;
`tokens` is total token reservation; `nano_cost` is integer billionths of the
declared three-letter currency. Limits and per-candidate reservations are positive
integers up to INT64_MAX. Worker/CPU/memory/IO caps bound concurrent reservations;
tokens and cost are cumulative across the group. Unknown usage retains its full
reservation. Reported overruns are retained, invalidate eligibility, and block
subsequent starts, including already granted tickets. Reservations do not enforce
physical CPU, memory or provider billing by themselves: the trusted executor must
apply its resource/provider limits. No overspend or speedup guarantee is made.

Requests accepted by `golem_candidate_call`:

| Operation | JSON fields after `operation` |
| --- | --- |
| `create` | `manifest` |
| `status`, `compare`, `cohort-record` | `group_id` |
| `enroll`, `reserve`, `select` | `group_id`, `candidate` |
| `start`, `cancel` | `group_id`, `candidate`, `token` |
| `finish` | `group_id`, `candidate`, `token`, `termination`, `qa`, `cancelled`, `tokens_known`, `cost_known`, `tokens`, `nano_cost` |
| `target-check` | `group_id`, `candidate`, `qa` |
| `diff-seal` | `group_id`, `candidate`, `redaction` |
| `diff`, `review-check` | `group_id`, `candidate` |
| `review` | `group_id`, `candidate`, `diff`, `qa`, `decision`, `reviewer` |

See [pinned candidate diff and review](candidate-diff.md) for source-retention
approval, immutable projection, completeness limits, and live review gates.

The token contains `ticket`, `epoch`, `instance` (32 hex characters) and `boot`
(SHA-256). Obtain it from the current admission owner. `termination` is a parent
CAS digest, but its existence alone is not proof that a worker stopped: `check`
must attest this. `qa` is the child-issued QA receipt, or an empty string when
missing. Unknown cost/token amounts must be zero with their known flag false;
zero is then not treated as free execution. Empty or foreign candidate IDs fail.
Group IDs must be unique within the admission namespace (`cf-<group>-<candidate>`).
Conflicting operation identities fail closed rather than reusing a ticket.

Read-only/structural CLI commands remain available:

```sh
golem candidate validate samples/candidates/group.json
golem candidate gates CHILD_WORK CHECKPOINT_SHA256
golem candidate status PARENT_WORK GROUP_ID
```

The [current-agent CLI host](candidate-host.md) additionally provides approved
lifecycle calls, persistent admission, cancellation polling and operator-attested
settlement. It supplies the host implementation; callers no longer need to write
C callbacks for this cooperative local mode. There is no `--approve-everything`
option. Installed projects do not become parallel-agent hosts merely by upgrading.

## Comparison and selection

V1 compares execution-v4/v5, single-repository QA at the pinned base HEAD. Candidate
working-tree edits are allowed; a new HEAD requires a new group. Protected oracle
files must be present in the checkpoint. Only candidate-root prefixes in argv are
normalized for comparison, not arbitrary strings or runtime differences.

Execution v5 keeps inventory in bounded CAS objects. Comparison and target-check
read each object's digest-verified bytes from its own Work store; missing or corrupt
objects cannot produce an eligible candidate. The comparison oracle and scoped
patch digest remain storage-format-independent: equivalent v4/v5 inputs compare
identically, without rewriting historical receipts. The 1,024 included-path bound
still applies; this is not unbounded repository support.

All candidates must be terminated, have fresh PASS/FAIL QA, the same gate and
environment digests, and complete within-budget usage for a comparable result.
Finished candidates may remain in READY/ACTIVE or be SEALED/RETAINED; inspection
does not reactivate them. Removed or replaced workspaces cannot be compared.
Missing/stale/error QA, cancellation, a changed base, changed environment or
unknown cost produces INCOMPARABLE and an empty winner. Comparable zero passes
gives NO_ELIGIBLE, one gives SOLE_PASS, multiple gives TIE. No confidence score,
test count, model name or cheapest price breaks ties. Actual QA, document
freshness and inventory policy are checked again at selection time.

Selection is not acceptance, patch application or merge authorization. The
`$target` host binding must refer to a distinct Work with a matching environment.
Target QA must be fresh and match the same base and oracle. Both issued QA
receipts are revalidated against their current sources. Their policy-scoped
HEAD/index/worktree inventories must match exactly, excluding physical checkout
identity. A successful result includes `selected_patch_verified: true`, both QA
receipt digests and `scoped_patch_identity`. Different edits, stale receipts and
different index state are rejected, even when both test suites pass.

This is exact scoped content equivalence, not automatic patch application or a
general merge/applicability test. Policy-excluded paths are outside this proof;
unrelated included target edits are rejected. The proof is valid at inspection
time, not a lock against subsequent edits. Completion and publication still
require their own policy, fresh source verification and approval. The result
continues to set `merge_authorized` and `push_authorized` to false.

## Recovery and evidence

### Current-agent connector

`golem_candidate_current_host` builds a borrowed C host from trusted, immutable
candidate bindings and mandatory `authorize`/`request_cancel` callbacks. Pass the
returned host to `golem_candidate_call`; do not dispatch its callbacks from agent
JSON. The connector resolves only configured candidates and an optional target.
It checks Work/session/runtime identity before begin, then uses
`golem_admission_publish_work` to check the live RUNNING claim and fresh inputs
and publish the durable Work binding. Duplicate starts are rejected. Reopening
an uncertain running ticket requires reconciliation, never automatic redispatch.

The embedding host remains responsible for exact-request approval, authentic
termination/billing, cancellation delivery and source quiescence. No default-allow
callback is supplied. All handles, strings and options are borrowed for the host
lifetime; serialize calls and do not mutate bindings during a call. This connects
an existing agent; it does not spawn a provider or supply physical resource limits.
Logical reservation must not be represented as OS CPU/memory containment.
For host-owned Linux commands, [resource execution](resource-execution.md) offers
an explicit cgroup-v2 backend. It is not implicitly attached to current agents
and does not replace candidate approval, lease, QA or settlement gates.

The installed CLI implements the cooperative host variant described above. Its
explicit operator termination attestation is labeled as such; it does not claim
independent observation of a provider or forcibly stop an external GUI agent.

The parent stores `candidate-groups/<group>/0001` through `0128`, referencing
versioned CAS events with sequence and predecessor digest. Existing no-replace
CAS/fsync publication is reused. Replay rejects malformed transitions, gaps,
changed event bytes and missing referenced parent evidence. Unpublished temporary
files confer no authority. Parent Work locking serializes calls; a poisoned
writer must be reopened. This ledger does not alter document completion state.

START_INTENT without RUNNING is uncertain, never a retry invitation. Restart
changes admission epochs; stale tokens cannot continue execution. An operator
must reconcile nonexecution/termination using the current admission token and
the same recorded usage before finishing. CANCEL_REQUESTED retains reservations;
requesting cancellation is not observed termination. SETTLING records usage
before releasing global admission; retries cannot rewrite it. No group cleanup,
suffix deletion, forced worktree removal or evidence deletion occurs here.

The ledger is not signed and cannot detect removal of an entire unanchored suffix.
Trusted, quiescent local roots and callbacks are required. Directory identity and
ancestry checks prevent registered aliases, not malicious same-user filesystem
races. Git metadata/configuration is shared across worktrees; ports, databases,
compiler caches and network effects need separate host isolation or serialization.

## Research export

The optional `cohort` references an already registered 29D FULL_USE case. Protocol,
task and evaluation digests must match. Protocol CAS JSON must exactly contain:

```json
{"schema_version":1,"unit":"TASK_BEST_OF_N","candidate_count":2,
 "limits":{"workers":2,"cpu":2000,"memory":8192,"io":2,"tokens":100,"nano_cost":100},
 "currency":"USD"}
```

For one candidate use `TASK_SINGLE_CANDIDATE`. Limits and currency must equal the
manifest. `cohort-record` stores all candidate rows, failures, cancellations and
costs as evidence, and adds one task-level observation, not N successful tasks.
An incomparable completed group records NOT_DONE. It never creates or rewrites
the comparison roster. Retry after a cross-ledger publication interruption is
idempotent only if the evidence is unchanged; changed evidence fails closed.

Reports expose task, candidate and dispatch-intent denominators separately.
BEST_OF_N is not a measured single-run success rate or a causal-effect estimate.
Wall-clock and physical CPU totals are explicitly unavailable in this version;
the implementation makes no performance-gain claim.

## Design sources and validation scope

- Chen et al., [Evaluating Large Language Models Trained on Code](https://arxiv.org/abs/2107.03374),
  section 2.1: task-level success from multiple samples motivates separate
  denominators; adaptive heterogeneous candidate groups are not assumed to meet
  that paper's sampling assumptions.
- Cawley and Talbot, [JMLR 2010](https://www.jmlr.org/papers/v11/cawley10a.html):
  selection bias motivates separating candidate choice from target verification.
  Running the same gates on the target is not independent statistical validation.
- Arpaci-Dusseau and Arpaci-Dusseau, [OSTEP: Common Concurrency Problems](https://pages.cs.wisc.edu/~remzi/OSTEP/threads-bugs.pdf):
  hold-and-wait motivates root-only admission and a nonblocking coordinator.
- [Ray logical resources](https://docs.ray.io/en/latest/ray-core/scheduling/resources.html)
  and [nested tasks](https://docs.ray.io/en/latest/ray-core/tasks/nested-tasks.html):
  reservation differs from OS enforcement; Golem prohibits nested candidate
  tickets instead of copying Ray's dynamic resource-yield mechanism.
- [Git worktree](https://git-scm.com/docs/git-worktree): per-worktree files do not
  imply separate shared configuration or refs.

Tests use a deliberately trusted fixture host, fixed local worker commands and
real Golem QA receipts. They do not establish paid Codex/Claude integration,
untrusted-code containment, multi-host scheduling or production billing accuracy.
