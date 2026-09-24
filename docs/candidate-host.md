# Current-Agent Candidate CLI Host

The installed C CLI now supplies the current-agent host implementation. No C
callbacks, provider subprocesses or SDK credentials are required. Existing
`candidate validate/gates/status` and the embedding API remain available.

This is a **local cooperating-client** protocol, not remote authentication or
physical containment. A person/process with the same user and filesystem access
can invoke the same commands. Approval hashes bind reviewed content; they are not
secret credentials or proof of a human identity. Never auto-approve agent output.

## Prepare And Serve

1. Create the parent and independent child Works with existing Work/document
   commands. Register runtime profiles and follow the session workflow, including
   submission of earlier managed Markdown. Each candidate start requires a live
   RUNNING claim and its real `runtime_binding`, not a placeholder digest.
2. Review [host.json](../samples/candidates/host.json). Supply canonical absolute
   paths, dedicated build/temp directories, one repository-wide admission root,
   and the enrolled session/runtime/environment identities. Limits are logical
   reservations. Existing admission ledgers retain their recorded limits; config
   does not silently resize them. Work stores cannot alias parent/other roots.
3. Use an existing private control directory (0700, current user, no symlink
   components). Keep the socket path short enough for the OS Unix socket limit.
   The endpoint is created with 0600 and same-UID peers are checked on macOS/Linux.
4. Review the configuration before running:

```sh
golem candidate host-validate host.json
# After reviewing the exact configuration, use the returned digest:
golem candidate serve host.json /private/control/candidate.sock --approve-config CONFIG_SHA256
```

Serve runs in the foreground; supervise it with your terminal/process manager.
It holds the parent Work and repository admission owner locks until shutdown.
Only child Works needed by an operation are opened; an unrelated configured
candidate need not be available. Handles are released after every call, so existing
session/execution CLI commands can operate between calls. Busy stores fail rather than waiting
while holding an agent's lock. Do not open a second coordinator for that namespace.

Use `workspace-create` below if the child worktree has not been provisioned.
Its configured `tree` must match the existing workspace layout
`worktree_root/<work_id>/<candidate>`. Freeze a v4 or v5 execution checkpoint and its
`candidate gates CHILD_WORK CHECKPOINT_SHA256` before creating the group manifest.
Use v5 explicitly for larger inventories. Historical v4 receipts are not upgraded;
comparison and target-check support both formats and validate external CAS evidence.

## Request Approval And Lifecycle

Each operation is a JSON request file. Inspect it, then obtain its digest:

```sh
golem candidate request-digest request.json
golem candidate call /private/control/candidate.sock request.json --approve-request REQUEST_SHA256
```

Digests use json-c compact JSON, preserving parsed member order, like execution
approval. No mutation is automatically approved. Changing fields changes the
digest. Hashes supplied inside the request are not approval flags. The local CLI
transports flags in a separate control envelope, checked again by the host.

The host supports all [candidate requests](candidates.md#manifest-and-requests),
except raw `finish`: use the typed `settle` operation below. `create`, `enroll`,
`reserve`, `start`, `cancel`, `compare`, `select`, `target-check` and `cohort-record`
require exact request approval. In particular, selection requires operator choice.

| Host operation | Exact additional request fields | Approval |
| --- | --- | --- |
| `workspace-create` | `candidate`, `base_commit` | Request digest |
| `grant` | None; grants the next eligible repository admission ticket | Request digest |
| `ticket` | `operation_id`, e.g. `cf-group-a` | Read-only |
| `poll` | `group_id`, `candidate`, `session` | Read-only |
| `status` | `group_id` | Read-only |
| `settle` | `group_id`, `candidate`, `token`, `qa`, `cancelled`, `tokens_known`, `cost_known`, `tokens`, `nano_cost` | Request digest + termination attestation |
| `shutdown` | None | Request digest |

Example requests, each in its own file:

```json
{"operation":"workspace-create","candidate":"a","base_commit":"<commit>"}
```
```json
{"operation":"create","manifest":{"<fields>":"see samples/candidates/group.json"}}
```
```json
{"operation":"enroll","group_id":"group","candidate":"a"}
```
```json
{"operation":"reserve","group_id":"group","candidate":"a"}
```
```json
{"operation":"grant"}
```

`grant`/`ticket` return `ticket`, `epoch`, `instance`, `boot`, plus `state` and
`operation_id`. Copy **only the four token fields** into start/cancel/settle's
`token`. Verify `operation_id` identifies the intended candidate. Grant is a
global scheduler action, not permission to start a different candidate.

Start durably connects the already active agent via the production Work publisher.
It does not execute the agent or create a second conversation. The agent continues
its ordinary document/development/QA workflow in the assigned tree. Gate/shell
approval, fresh inputs, session heartbeat and completion rules still apply.

## Cooperative Cancellation And Settlement

Before effects and between commands, the agent calls:

```json
{"operation":"poll","group_id":"group","candidate":"a","session":"current-agent"}
```

No approval flag is needed for poll. It checks current admission state, pinned
Work/session/initial binding, live claim, fresh inputs and runtime generation.
Later claims in the **same session, selection and generation** may continue;
an unrelated refreshed profile cannot silently replace the initial environment.
Between claims `may_continue` is false: obtain the next normal claim before more
effects. Poll does not renew leases or replace stage/execution authorization.

Approved `cancel` persists CANCEL_REQUESTED, updates admission, and publishes a
CAS-backed notice under `CHILD_WORK/candidate-notifications/<group_id>`. Repeated
delivery is idempotent. Poll reads the authoritative cancellation state even if
notice publication was interrupted. Successful cancel means **durably queued**,
not proven delivery to a GUI, forced process termination or released reservation.
The response marks delivery as `COOPERATIVE_POLL`. An agent must poll and obey it.

After stopping effects, the agent must submit/reconcile its active Work claim.
Expiry alone does not count as termination. The operator then reviews the exact
settlement, including QA receipt and actual or explicitly unknown usage:

```sh
golem candidate request-digest settle.json
golem candidate call /private/control/candidate.sock settle.json \
  --approve-request REQUEST_SHA256 --attest-termination REQUEST_SHA256
```

The second flag attests stopped/nonexecuted effects and the reviewed settlement.
It is **not** independent provider billing or OS process-exit evidence. The host
rejects a remaining active/recovery claim even with both flags. It creates a typed
parent CAS receipt with `trust: operator_attested`, binding the host configuration
and exact settlement request, then calls the existing finish/settle/release path.
Unknown token/cost flags require zero amounts but retain their reservation; zero
is not treated as known free usage. A raw `finish` cannot bypass this boundary.

Repeat an identical settlement only after inspecting status. Changed amounts,
proof identity or stale token are rejected by the original ledger. An interrupted
operation can leave unreferenced CAS objects; those do not authorize settlement.

## Recovery And Bounds

- Each call is serialized and bounded to a 256 KiB request. Framing is a 4-byte
  big-endian length plus JSON, capped at 512 KiB including envelopes. Receive/send
  deadlines and an eight-connection backlog bound stalled clients. The host is
  not a concurrent, hard-real-time cancellation service; comparison can perform I/O.
- A disconnected client may have committed. No automatic call retries occur.
  Inspect status/ticket; never blindly retry start after START_INTENT.
- Shutdown/SIGTERM does not release uncertain reservations or kill agents. After
  restart, admission advances epoch and requires reconciliation. Old start/finish
  tokens cannot continue; obtain the current ticket and attest settlement only
  after inspection. A retry is a newly budgeted group/candidate, not redispatch.
- Existing socket paths are never overwritten/unlinked at startup. After SIGKILL,
  use a new endpoint or have the operator remove the confirmed stale socket.
  Normal shutdown removes only the endpoint inode created by that server.
- Configuration is immutable for a server lifetime. Changes/revocation require
  explicit shutdown/restart and a newly reviewed config digest. A changed config
  does not rewrite recorded candidate enrollments or initial admission bindings.
- Parent/child ledgers, CAS and ownership checks remain authoritative. IPC has no
  TCP endpoint, credential storage, provider spawn, default shell or patch application.
  Physical CPU/memory containment and billing accuracy are not claimed.
- An optional `target` is `{work, tree, environment}` for a distinct target Work.
  Add it through an approved restart if necessary. Target-check still requires
  fresh target QA and scoped patch equivalence, and never grants merge/push.

For cooperating CLI/GUI agents, adapt the
[entry-point fragment](../samples/candidates/AGENTS.fragment.md).

## Research Basis

These are engineering adaptations, not claims that Golem implements distributed
consensus or inherits the papers' measured reliability/performance.

- [Burrows, Chubby, OSDI 2006, lock sequencers](https://static.usenix.org/events/osdi06/tech/full_papers/burrows/burrows_html/):
  accepting-side generation checks motivate persistent admission ownership and
  rejection of stale epochs after restart. A local flock is not a replicated lock service.
- [Featonby, Making retries safe with idempotent APIs](https://d1.awsstatic.com/builderslibrary/pdfs/making-retries-safe-with-idempotent-apis-malcolm-featonby.pdf):
  uncertain responses and changed intent motivate exact request approvals, durable
  start intent, immutable settlement and no blind start retry.
- [Arpaci-Dusseau and Arpaci-Dusseau, OSTEP, Common Concurrency Problems](https://pages.cs.wisc.edu/~remzi/OSTEP/threads-bugs.pdf):
  explicit state ordering and bounded ownership motivate one admission owner and
  releasing child Work handles between agent calls, rather than waiting on held locks.
- [Linux unix(7)](https://man7.org/linux/man-pages/man7/unix.7.html):
  pathname socket permissions and peer credentials inform the local transport.
  Same-UID malicious clients are outside this cooperative trust boundary.
