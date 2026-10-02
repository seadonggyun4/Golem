# One-command bounded lifecycle

`tools/agent_lifecycle.py run` coordinates an explicitly reviewed
`prepare -> execute -> finalize` procedure in one invocation. Each phase contains
1..16 commands, at most 32 overall. Every command must exit successfully, retain
complete mechanical evidence and satisfy typed JSON-output checks before the next
command starts. Exit zero with `PENDING_APPROVAL` cannot satisfy required `READY`.

This is opt-in, not automatic adoption by every native CLI entry point. The
controller does not author documents, invent approvals or infer deployment
protocols. Work/session/execution/approval/completion APIs remain authoritative.

## Usage

```sh
python3 tools/agent_lifecycle.py validate lifecycle.json
python3 tools/agent_lifecycle.py run lifecycle.json --store "$PRIVATE_RUN_STORE" \
  --reviewed-plan "$REVIEWED_PLAN_SHA256"
python3 tools/agent_lifecycle.py inspect "$PRIVATE_RUN_STORE/$RUN_ID"
```

Validation prints a digest without executing commands. Review the exact plan
before supplying the digest. This pin is not authenticated human approval and
does not replace native execution-contract approval. The store must be private
and outside the source repository. Keep it outside the Work registry as well.

Plan shape (placeholders are intentionally non-runnable):

```json
{
  "schema": "golem.agent-lifecycle-plan.v1",
  "run_id": "check-001",
  "cwd": "/absolute/canonical/repository",
  "inputs": {"/absolute/immutable/request.json": "SHA256"},
  "phases": {
    "prepare": [{"id": "ready", "argv": ["/absolute/project-host", "prepare"],
      "timeout": 30, "executable_sha256": "SHA256",
      "expect": [{"path": ["state"], "equals": "READY"}]}],
    "execute": [{"id": "apply", "argv": ["/absolute/project-host", "execute"],
      "timeout": 300, "executable_sha256": "SHA256",
      "expect": [{"path": ["state"], "equals": "RECORDED"}]}],
    "finalize": [{"id": "close", "argv": ["/absolute/project-host", "finalize"],
      "timeout": 30, "executable_sha256": "SHA256",
      "expect": [{"path": ["state"], "equals": "CLOSED"}]}]
  }
}
```

No implicit shell, interpolation, dynamic executable selection or `eval` is used.
Explicit interpreters can still execute arbitrary code and must be reviewed.
Request/script files referenced by argv should be listed in `inputs`; dependencies
are not inferred. Declared hashes are checked before the first command and around
each dispatch. Native JSON commands should use `--output-mode full`.

Checks use object-key paths and exact scalar types: `true` does not equal `1`.
Unknown fields, empty phases/check lists and duplicate IDs fail closed. Timeouts
are 1..3600 seconds; plans are at most 256 KiB. Checks are not a semantic QA oracle.

`finalize` is successful-path work, not unconditional cleanup. Hosts must own
indispensable cleanup and native recovery. Approval wait stops the sequence;
the controller neither approves nor polls indefinitely. Dynamic native receipt
handoffs require a reviewed project host; this version does not substitute prior
stdout into later requests. This is not a general autonomous Work executor.

## State and Recovery

| State | Meaning |
| --- | --- |
| NOT_RUN / NOT_DISPATCHED | Not reached, or pre-dispatch validation failed |
| DISPATCH_UNCERTAIN | Dispatch intent recorded; completion not established |
| FAILED / BLOCKED | Process/evidence failed, or JSON checks did not match |
| CHECKS_PASSED | This command met declared checks, not semantic acceptance |
| FINISHED | All three phases met checks; not live native DONE |
| STOPPED | A failure was observed; later commands were not dispatched |
| RECONCILE_REQUIRED | No complete final manifest; inspect effects, do not replay |

Exclusive directory creation reserves a run ID within the private store. Parent
directories and dispatch records are fsynced before effects. Only the reservation
creator dispatches; concurrent callers read results or report uncertainty. Plan
and manifest publication is atomic for concurrent readers. Different recorded
intent under the same ID is rejected. Never remove reservations or change IDs/stores
as an automatic retry. Identity is scoped to this retained local store, not global.

Local records and external effects are not one atomic transaction. A crash after
an effect but before its receipt leaves uncertainty. SIGKILL can leave children
running. Reconcile processes, native receipts and actual effects before a new
operation. There is no automatic resume, retry, compensation, rollback or
exactly-once external-effects guarantee. Failures are preserved, not skipped.

Files are 0600 and directories 0700. Evidence contains plan, producer/module hashes,
source identity, dispatch/completion records, stdout/stderr and existing mechanical
execution records. Successful runs also capture final source identity; failed
commands retain their own post-command observation when capture completes.
The final inventory detects accidental corruption, not malicious same-user changes.
Missing final evidence never permits redispatch. Filesystem durability limitations
and executable TOCTOU remain; hashes are not a sandbox or hermetic build proof.

## Design and Research

The controller reuses process capture, source identity, private storage, strict JSON
and command validation. It adds sequencing, result gates and run reservations.
New project procedures are data under the same closed schema; more complex resume
or compensation requires a new reviewed contract, not hidden retries.

One `run` invocation coordinates all phases; underlying commands remain separate.
Review, plan authoring, reconciliation and evidence inspection are additional
interactions. Token, cost and production latency savings have not been measured.

Reviewed 2026-10-02; these are reading scopes, not whole-book claims:

- [Helland, Life beyond Distributed Transactions, CIDR 2007](https://www.cidrdb.org/cidr2007/papers/cidr07p15.pdf),
  sections 5-6: processed-message identity and explicit uncertainty inform retained
  run IDs and reconciliation. No distributed entity architecture is implemented.
- [Featonby, Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/),
  introduction, side effects, client identity and atomicity: parameter equality is
  not intent identity. Without atomic external effects, this runner refuses replay.
- [Lamport, Specifying Systems (2002)](https://lamport.azurewebsites.net/tla/book-21-07-04.pdf),
  section 7.3, pp. 76-78: retain intermediate transitions instead of treating a
  multi-command sequence as atomic. No TLA+ proof/model checking is claimed.
- [Beyer et al., Site Reliability Engineering (2016), chapter 7](https://sre.google/sre-book/automation-at-google/),
  consistency, platform and use-case sections: automate bounded known procedures
  and expose partially completed operations rather than assuming atomic rollout.

Applications to this local runner are engineering inferences. A scanned Sagas PDF
was located but not used as a text-verified basis; a Gray transaction-paper URL
failed retrieval. Automatic compensation was not inferred from either source.

Tests cover subprocess success/failure, blocked zero exits, timeout, malformed JSON,
typed checks, input drift, duplicate/conflicting IDs, concurrency, persistence
failures, actual controller SIGKILL, corrupt evidence and native document
registration. They do not certify production deployments or all Work lifecycles.
