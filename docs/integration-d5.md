# D5 Updates, Reload and Quarantine Recovery

D5 is an **owner-only local maintenance API**, not an MCP tool, auto-updater,
daemon or new native recovery authority. It reuses D1 approval generations,
D2 disclosure and read-only MCP, D3 executable pins, D4 durable intents and the
existing execution recorder. Native core formats and reducers are unchanged.
Agents still decide what work to do; Golem checks which transitions are valid.

## Support Boundary

The implemented update unit stages owner-pinned ENGINE, SDK, INTEGRATION, MCP and
INSTRUCTIONS files together. Exactly one executable ENGINE is required. The
automatic switch changes **only D1 CLI/SDK enrollment pins** through D1's existing
reviewed approval transaction. Integration/MCP/instruction files are staged and
hashed, not automatically installed into Python environments or client settings.
The owner must separately review runtime installation/configuration and reload
each client. This is not an end-to-end client installer or signed distribution.

The separate [D1 owner installer](integration-install.md) can apply/remove reviewed
MCP settings for its supported profiles. It does not change this D5 transaction
into automatic runtime installation, hook trust or actual client reload observation.

Supported local mechanisms require POSIX private files, no-follow opens, fsync
and flock on macOS/Linux. Windows, network filesystems, actual Desktop/Hosted
reload, physical power loss and arbitrary historical engine compatibility are
NOT_VERIFIED. Existing D1/D2/D3 client support limits remain in force. No TRAP,
real Work, migration, VM or UACTT is used by this implementation's tests.

## State and Admission

Lifecycle records live in the private D1 registry, outside native Works:
`d5-state-<sha256>.json` plus `.d5-<project_id>.current`. Records form a verified,
bounded hash chain; only the pointer is atomically replaced. Missing history,
corruption, exhausted quotas or unexpected phase changes fail closed.

| Phase | Allowed next action |
| --- | --- |
| No lifecycle / OPEN | Owner plans and approves freeze |
| FROZEN | Stage, verify, investigate/clear quarantine, switch, or explicit thaw |
| SWITCH_INTENT | Explicit repair observes the D1 commit boundary; no retry |
| RELOAD_REQUIRED | Read-only reload probes, ready, or reviewed no-effect restore |

Freeze precedes staging conservatively and blocks **new D4 admission**, not
arbitrary direct CLI/C calls. A D4 server holds its own kernel participation
descriptor for its lifetime. In-flight writers hold separate descriptors through
final evidence publication. Switch requires all current D1 principal/client
acknowledgements and every relevant descriptor to be unheld. No PID probing,
killing, forced ownership transfer or lock-file deletion occurs. An admitted
long-running action may finish after freeze; maintenance must wait for it.
The owner must also stop independent direct callers and external processes.

Current bounds: 32 staged files, 128 MiB staged source bytes, 128 retained client
participants and 128 D4 intents; 256 lifecycle records. A full selected Work
inventory permits 16,384 entries, 128 MiB/file and 256 MiB total. Existing registry
quota and 256-KiB structured-envelope bounds also apply. Required data is never
truncated. There is no automatic evidence garbage collection, history reset or
orphan-record deletion. Exhaustion or incomplete participant metadata requires
owner investigation; a new registry must not be used to escape quarantine.

## Owner CLI Procedure

Inputs and plans must be private regular owner files, canonical absolute paths,
no links; plans bind producer hashes, registry identity, approval generation,
lifecycle head, artifact pins and relevant full Work inventories. Apply rechecks
the exact plan and requires its SHA-256 plus the separate owner approval flag.
Do not treat model-supplied IDs or a matching hash as owner authorization.

```sh
python3 tools/integration_update.py schema --operation freeze
python3 tools/integration_update.py plan --registry /private/registry \
  --operation freeze --input /private/freeze.json
python3 tools/integration_update.py apply --registry /private/registry \
  --input /private/reviewed-plan.json --reviewed-plan-sha256 REVIEWED_SHA256 \
  --approve-maintenance
python3 tools/integration_update.py inspect --registry /private/registry --project-id PROJECT
```

The same plan/apply interface handles each subsequent operation. Use the emitted
closed schema for its precise input; paths above are placeholders, not an install
recipe for a real Work. Persist the returned canonical JSON plan without editing
and review it before apply. Applied plans are additionally retained immutably in
the registry; stage and verification return pinned evidence references.

1. **Freeze:** `project_id`, a unique `freeze_id`. Native state is untouched.
2. **Stage:** new private `destination` outside project and registry; `artifacts`
   have `name`, `role`, `source: {path, sha256}` and `mode: READ|EXECUTE`.
   Existing sources/destinations are not overwritten. A partial copy can only be
   completed with `stage-repair` referencing the exact original approved plan;
   conflicting bytes, modes, extra files or producer drift block repair.
3. **Verify:** staged `bundle` pin and target D1 `enrollment`. Grants, identities,
   native roots, runtime selection and Work genesis must remain identical; only
   CLI/SDK pins may change. Original and staged engines run doctor and original
   read-only record/status/next. Full inventories before/after must match and
   native heads/sequences must agree. Active owners or recovery-needed states
   block maintenance; no Work is resumed as a probe.
4. **Switch:** issued `verification` pin and `stopped` entries for **every** grant:
   `{principal_id, client_id, state: STOPPED_OWNER_ATTESTED}`. These are owner
   statements, supplemented by managed descriptor checks, not proof about every
   external process. No unresolved D4 request may remain. Drift requires a new
   review. D5 first publishes SWITCH_INTENT, then invokes the existing D1 approval
   transaction, then publishes RELOAD_REQUIRED. These are separate transactions,
   not an asserted multi-file atomic commit.
5. **Reload:** install/review the selected runtime explicitly, regenerate policies
   against the new D1 generation and producer, and reload clients through their
   supported mechanisms. An old D4 policy cannot silently gain the new generation.
   D4 cannot start while fenced. D2 read-only probes remain available.
6. **Ready:** actual recorded SDK probes plus every client's owner reload
   acknowledgement are mandatory. Run each probe in its reviewed MCP 2.3.0 /
   mcp-types 2.3.0 Python environment:

```sh
python3 tools/integration_reload_probe.py --policy /private/new-d2-policy.json \
  --reviewed-policy-sha256 POLICY_SHA256 --project-id PROJECT \
  --mode auto --output /private/new-probe --approve-reload-probe
```

Use `legacy` only for the reviewed legacy protocol profile. The probe invokes
actual SDK stdio tools/list and status/next for all grant Works, retains full
responses in its execution record, checks generation/policy/runtime/source pins
and proves no native inventory change. `ready.reloads` contains each
`principal_id`, `client_id`, `state: RELOADED_OWNER_ATTESTED`, and returned `probe`
pin. Ready verifies the recorder, exact worker argv, runtime pins, current policy,
scope and inventory. A fabricated JSON success or acknowledgement alone is not
accepted. Success is **SDK_READ_OBSERVED_OWNER_RELOAD_REPORTED**, not observed
Desktop activation. The interpreter/direct SDK files are pinned; this is not a
hermetic dependency environment or remote attestation. D4 may be restarted with
a newly reviewed policy only after OPEN.

## Interrupted Update and Restore

`repair-switch` requires fresh plan/approval and all stopped acknowledgements.
If D1 still matches the recorded before-pointer, it returns to FROZEN; if the
exact target enrollment and reviewed D1 plan committed, it moves forward to
RELOAD_REQUIRED. Any other state blocks. It never repeats D1 writes, infers
success from a process exit, or rolls back a Work.

`restore` is permitted only during RELOAD_REQUIRED, with no native inventory
change since switch, stopped participants, compatible retained old artifacts and
a pinned `golem.integration-restore-review.v1` owner review. The review binds
project/freeze/current enrollment digest, declares
`effects: NONE_SINCE_SWITCH_OWNER_ATTESTED`, and provides pinned inspection
evidence plus a reason ID. Native byte identity cannot establish absence of
external effects. If effects are unknown or occurred, preserve everything and
investigate; this restore path is not applicable. The old enrollment is approved
as a **new D1 generation**, never by rewinding a pointer. It still requires new
reload policies/probes and ready. Historical bindings remain stale.

`thaw` is an explicit no-switch abort from FROZEN, with all stopped acknowledgements,
no unresolved requests and original read-only native idle/safety checks. An
active owner or reconciliation requirement must be handled through the original
explicit native procedure, never bypassed just to complete maintenance.

## COMMIT_UNKNOWN Clearance

Clearance is not native reconciliation or evidence repair. Keep the original
intent, action/request bytes, stdout/stderr, result and native receipts intact.
Stop participants and external effect producers; freeze and investigate using
original native read-only APIs and surviving external evidence. If native
reconciliation is necessary, an authorized owner performs the **existing native
procedure explicitly**, then returns to D5. No such action is automatic here.

```sh
python3 tools/integration_recovery.py schema
python3 tools/integration_recovery.py plan --registry /private/registry \
  --input /private/recovery-request.json
python3 tools/integration_recovery.py apply --registry /private/registry \
  --input /private/reviewed-recovery-plan.json \
  --reviewed-plan-sha256 REVIEWED_SHA256 --approve-recovery
```

The request binds project, Work, current D1 binding, original `mutation-<digest>`
evidence ID, all stopped acknowledgements and a pinned owner review. Review schema
`golem.integration-effect-review.v1` requires `processes: STOPPED_OWNER_ATTESTED`,
`disposition: NO_EFFECTS_CONFIRMED|EFFECTS_RECONCILED`, reason ID and pinned evidence.
These statements are not independently authenticated facts.

Plan/apply recheck original request digest, Work identity/genesis, D1 generation,
native idle/read safety, all preserved D4 evidence and owner evidence. Execution
requests additionally query original native approval recover: PENDING/APPROVED
or unreadable state blocks clearance. Consumed historical UNCERTAIN is not turned
into success. Missing original inputs or corrupt native state remain blocked.
Native state does not by itself prove that an external command had no effects.

The retained recovery plan and new `d5-resolution.json` + hash reference certify
only the owner's reviewed release of the integration dispatch quarantine.
Partial certificate publication may be explicitly completed only with identical
approved bytes; conflicts are preserved and blocked. Admission revalidates the
retained plan and original audit inventory. **Original COMMIT_UNKNOWN remains
COMMIT_UNKNOWN on exact replay.** The original logical session key, document
revision or execution attempt/checkpoint/contract is retired across replacement
request/action IDs. The certificate authorizes no execution, owner transfer,
QA PASS, completion or retry. Only a genuinely distinct subsequently approved
action can be admitted after explicit thaw/ready and fresh native checks.

## Tests and Design Basis

Unit tests cover closed owner requests, stale plans, all-client acknowledgement,
held participant/writer descriptors, partial staging, before/after D1 commit
crashes, restore effects review, damaged lifecycle history, forged reload
reports, stale owner evidence, cross-Work recovery, partial certificates and
post-clearance original evidence corruption. Independent JSON Schema checks
validate positive and negative inputs. Native synthetic tests cover lost committed
claim, explicit native cleanup, lost QA reply without rerun, still-dispatchable
approval refusal, direct new-event restore refusal, and actual two-client
modern/legacy SDK reload with full Work inventory preservation.

CTest `integration_update_recovery` is enabled with
`GOLEM_BUILD_INTEGRATION_HOST=ON`; `--mcp` adds the optional SDK gate. CI runs that
gate with ASan/UBSan on macOS/Linux. Per-revision CI results, local execution
results and actual Desktop/Hosted activation are distinct claims.

Design inferences reuse fail-safe defaults/complete mediation from
[Saltzer and Schroeder (1975)](https://web.mit.edu/Saltzer/www/publications/protection/Basic.html),
transaction interruption/flush caveats from [SQLite atomic commit](https://www.sqlite.org/atomiccommit.html),
and update-set consistency/authenticity distinctions from [TUF metadata](https://theupdateframework.io/docs/metadata/).
See the [research review](integration-layer-references.md#d5-update-and-recovery-review)
for academic/book review scope and limitations. These references are design
guidance, not a proof of exactly-once external effects or TUF compliance.

Local macOS checks on 2026-10-21 (remote CI is tracked per commit separately):

| Gate | Observed result |
| --- | --- |
| Full Python regression on host | 577/577 PASS; sandbox run had four existing loopback permission errors |
| D5 unit cases, included above | 22/22 PASS |
| Independent D5 schema assertions | 56/56 PASS |
| D5 actual native + modern/legacy MCP, ASan/UBSan | 8/8 PASS |
| D5 actual native + modern/legacy MCP, Release | 8/8 PASS |
| Existing D4 actual native + MCP | 15/15 PASS |
| Existing D2 actual read-only native + MCP | 6/6 PASS |
| D1/D3/D4/D5 native CTest entries | 4/4 PASS; SDK cases are separate |
