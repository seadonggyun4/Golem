# Automatic hosted usage delivery

`tools/usage_pipeline.py` connects the existing provider adapters to an explicitly
owned native WorkRun. Collection, durable delivery and native application remain
distinct states. It is not an account-wide conversation interceptor or billing
service. Original provider usage and verified billing remain separate evidence.

## Ownership and configuration

Create an existing private inbox (0700), a private hosted binding described in
[usage integrations](usage-integrations.md), and a private route file (0600):

```json
{
  "schema": "golem.usage-route.v1",
  "run_id": "run-id",
  "sequence": 1,
  "currency": "USD",
  "tool_calls": {},
  "inbox": "/absolute/private/run-inbox",
  "require_billed": false
}
```

One pipeline binds one account/project/Work/attempt/session to one native stage
sequence. Both binding and route are immutable once initialized. Never infer a
Work from cwd, the latest session or an account-level aggregate. Use one inbox per
native run and one authoritative usage observation route per provider invocation.
Request IDs in native reports are namespaced by the complete attribution identity.

`tool_calls` optionally maps provider request/turn IDs to observed integer counts.
Without a count, token partial sums still reach native storage, but the native v1
aggregate's `usage_known` remains false; placeholder zero is **not known zero**.
These partial reports use `golem.native-cost-report.v2`. Only the explicit v2
JSON/inbox import accepts observed nonzero usage with completeness false; native
v1 decoding and typed report inputs still require zero unknown usage. Aggregated
partial values never satisfy enabled usage budgets. Unknown money must still be
zero with `cost_known: false`. Older native binaries cannot import this v2 path;
upgrade the owner, preserve the failed inbox and do not rewrite sealed evidence.
`tool_usage_complete` exposes this limitation separately from token completeness.
Use `require_billed: true` if native settlement must wait for verified charges.
Otherwise cost remains unknown, even after usage settlement. An append-only
settled ledger cannot later be repriced; billing-waiting workflows must select
that policy before collection, not replace a published report afterward.

```sh
python3 tools/usage_pipeline.py init --directory NEW_PRIVATE_PIPELINE \
  --binding PRIVATE_BINDING --route PRIVATE_ROUTE
python3 tools/usage_pipeline.py pump --directory PRIVATE_PIPELINE
python3 tools/usage_pipeline.py listen --directory PRIVATE_PIPELINE \
  --token-file PRIVATE_TOKEN --duration 60
python3 tools/usage_pipeline.py close --directory PRIVATE_PIPELINE
python3 tools/usage_pipeline.py sync --directory PRIVATE_PIPELINE
```

`pump` consumes a live JSONL notification stream forwarded by the owning Codex
app-server client, not a manually assembled report. Its EOF declares the selected
scope closed. Forward only the bound, serialized turns with the correct cumulative
baseline; failed/interrupted or unobserved turns remain incomplete. The current
Codex desktop conversation is not intercepted; its owner must provide this stream.

### Owned Codex connection

`tools/codex_hosted.py` removes manual notification forwarding for a fresh,
explicitly owned Codex app-server stdio thread. Supply a private attribution JSON
containing `account_id`, `project_id`, `work_id`, `attempt_id`, the route above,
and a JSON array of 1-32 prompt strings on stdin:

```sh
python3 tools/codex_hosted.py --directory NEW_PRIVATE_DIRECTORY \
  --attribution PRIVATE_ATTRIBUTION --route PRIVATE_ROUTE --cwd PROJECT_ROOT \
  --timeout 300 < PRIVATE_PROMPTS_JSON
```

It automatically binds returned thread/turn IDs, captures usage notifications,
preserves the cumulative baseline between serialized turns, and publishes a
separate immutable inbox sequence per turn. Reserve those native stage sequences
before launching; this adapter does not create/advance native stages. Tool counts
remain unknown unless independently supplied. Thread ownership and fresh zero
baseline are required; it never guesses usage for resumed or unrelated threads.
The optional `--model` is an explicit override, not an automatic fallback.

The connection is bounded by framing, total bytes, message count and wall time.
The shared private-process recording boundary owns source/executable identity,
redacted metadata and child-group cleanup. Only normalized usage events are
durably stored; prompts, responses, auth messages and stderr are not persisted.
Requests for approval/authentication refresh are refused, not auto-approved.
The owning client uses read-only sandbox/never-approve settings. An interactive
client requiring richer capabilities must retain its existing owner-forwarded
adapter rather than grant this accounting client execution authority.

This covers owned fresh stdio sessions, existing owner-forwarded Codex streams,
and authenticated Claude exports/owned launches. It does **not** connect arbitrary
ChatGPT/Codex desktop, browser, Cowork or inaccessible cloud conversations. Those
surfaces need provider-supported exports and an authorized owner binding; account
aggregates cannot establish Work attribution. "All Hosted paths" is not a
supported coverage claim.

`listen` uses authenticated, bounded loopback OTLP/JSON ingestion. Duration expiry
does **not** close the session: its owner must close after exporter flush. For an
owned Claude Code child, the launcher combines collection, waiting and closing:

```sh
python3 tools/usage_pipeline.py run-claude --directory PRIVATE_PIPELINE \
  --timeout 300 --flush 2 -- claude --session-id BOUND_SESSION_UUID -p 'task'
```

Use a whole-session Claude binding (`session_owned: true`, empty `prompt_ids`) and
the exact session ID. The launcher sets telemetry only in that child's environment,
disables content-bearing signals, uses a random bearer token, reaps timed-out
process groups and never changes global configuration. Managed provider settings
still win; missing/redirected exports remain unknown rather than being bypassed.
Flush grace reduces late exports but is not proof of lossless provider delivery.
Only usage metadata is persisted. Child stdout/stderr remain inherited, not copied
into usage records. Child timeout or export errors retain an open recoverable scope.
The shared `execution_record.run_private` boundary retains executable/source
identity, start/end and exit reason without argv, environment or stream capture.

## Native owner integration

The native owner enables its ordinary cost ledger, then opts in **before begin**:

```c
golem_work_run_cost_enable(run, &options);
golem_work_run_cost_inbox_enable(run, private_inbox, require_billed);
```

Check both return codes. `golem_work_run_finish` imports the stage's sealed snapshot
before changing execution state, then settles the ledger. Missing, unsealed,
identity-conflicting, malformed, over-capacity or required-but-unbilled snapshots
cannot advance the stage. Existing callers without an inbox keep their behavior;
the deterministic `local.noop` CLI simulation is intentionally not rerouted.
Cancellation attempts sealed import but never waits on accounting. Inspect
`golem_work_run_cost_inbox_status`; late delivery can be imported with
`golem_work_run_cost_inbox_sync`, then settled explicitly after cancellation.
Accounting never satisfies completion requirements or grants execution authority.

## Billing arrival and retries

`sync` or bounded `deliver` accepts all five `--billing-export`,
`--billing-signature`, `--billing-public-key`, `--billing-artifact`, `--billing-trust`
paths. `deliver --duration 120` waits for collection close and local billing evidence
arrival, then re-verifies the delegated Ed25519 export and publishes automatically.
No receipt JSON alone grants trust. Only exact account/provider/request joins are
allocated. Aggregated usage/cost API buckets, estimates and unmatched invoice rows
are never allocated proportionally to Works. The delegated signer is not a claim
that the provider signed the invoice. API access and authentic accounting exports
must be supplied by an authorized adapter/operator.
Verified billing source bytes and pinned policy are retained in the private queue;
restart re-verifies these artifacts before replaying a billed snapshot. At most
32 supplied billing evidence sets are retained per pipeline; repeated automatic
re-verification uses temporary verification output, not unbounded history.

Successful ingestion acknowledges durable local state, not ledger application.
`native_delivery: PUBLISHED` means a snapshot exists; `native_application:
OWNER_NOT_OBSERVED` deliberately does not assert the native process consumed it.
The native ledger is the authority for applied amounts. Pending delivery returns
CLI code 2; malformed collection/delivery returns 1. Initialization returns 0 on
successful creation even though collection is open. Preserve the directory and
retry `sync` after correcting permissions or supplying evidence. Schema/signature
errors stop; the local delivery waiter has at most 64 attempts and a 1-hour deadline.

## Persistence and limits

Normalized usage-only events are atomically replaced under a nonblocking process
lock, file and parent fsync precede acknowledgment, and restart reconstructs the
same parser state. Config fingerprints reject accidental reassignment, not a
malicious same-user writer. Exact event retries are idempotent even after close;
new late events fail visibly. Atomic native snapshots are write-once per sequence;
conflicting independent producers fail rather than overwrite.

Both source/destination directories must be private and symlink-free. Native code
retains the inbox directory descriptor and opens snapshots with no-follow flags.
JSON/state is limited to 1 MiB, normalized input to 4096 events, and native batches
to 256 reports (also subject to the configured ledger capacity). Reconstruction
cost is linear in the bounded event window; split large workloads by stage/attempt
rather than silently evicting evidence. Retain pipeline, billing evidence and inbox
for reconstruction. The native ledger and its deduplication state remain in-memory;
this is retry-safe delivery, **not distributed exactly-once recovery**. A crash
after partial native import can retain a prefix; replay deduplicates each request
in the same owner, while a recovered owner must reconstruct from retained snapshots.
This local POSIX adapter does not claim Windows support or arbitrary cloud egress.

## Design references

Consulted on 2026-10-10; these motivate design choices, not empirical performance
claims or evidence that real provider billing was tested:

- [Codex app-server reference](https://developers.openai.com/codex/app-server):
  owner-forwarded notifications and cumulative usage boundaries; no desktop scraping.
- [Claude Code monitoring reference](https://code.claude.com/docs/en/monitoring-usage):
  OTLP transport, explicit content gates, managed settings and estimated client costs.
- Psarakis et al., [Transactional Cloud Applications Go with the (Data)Flow,
  CIDR 2025, section 2.1](https://www.vldb.org/cidrdb/papers/2025/p25-psarakis.pdf):
  persist delivery identity before sending and distinguish durable receiver effects
  from transport retry. This implementation explicitly does not provide the paper's
  durable receiver transaction guarantee.
- Beyer et al. (eds.), [Site Reliability Engineering, chapter 21, Deciding to
  Retry](https://sre.google/sre-book/handling-overload/), O'Reilly, 2016:
  bounded retries and a single retrying layer rather than retry amplification.
- [Existing billing trust contract](usage-integrations.md): delegated verification,
  request-level attribution and no promotion of estimates to actual charges.

Regression coverage includes replay, failed durable writes, deferred delivery,
scope conflicts, private path checks, signed billing and tampering, child lifecycle,
authenticated HTTP, and real C finish/cancel import. Synthetic provider/billing
fixtures are explicitly not genuine charges or proof of universal hosted coverage.

## Live Connection Results, 2026-10-10

A real owned Claude Code invocation exported two provider requests through the
authenticated loopback receiver. The aggregate was 3556 input and 17 output tokens;
the native owner automatically imported both reports on stage finish and settled
them idempotently. Cost remained unknown and native usage completeness stayed false
because tool counts were not observed. This is real usage delivery, not authenticated
billing, independent token measurement or a product completion verdict. The first
attempt exposed the v1 partial-usage incompatibility; its failure evidence was
retained, and the corrected v2 path was tested with a separate invocation/inbox.

The installed Codex app-server completed its handshake and emitted failed-turn
notifications, but the provider rejected the configured model. An explicit,
user-approved `gpt-5.4` override was also rejected as unsupported, despite its
presence in `model/list`. No fallback model was silently chosen, and no usage or
ledger success was claimed for those calls. Synthetic stdio regressions cover the
successful owned Codex protocol, correlation, multiple turns and native import;
real Codex successful usage collection remains **NOT VERIFIED** in this account.
