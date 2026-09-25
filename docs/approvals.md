# Scoped HITL Approvals

Golem's approval ledger binds a trusted host decision to one concrete execution
request. It is independent of QA PASS, role assessment and completion. Approval
never proves that the command was successful.

## Trust Boundary

The public C API is in `golem/approval.h`. An embedding host supplies
`golem_approval_host.decide` and `recheck`. The host authenticates its operator,
retains the decision keyed by action digest, and checks issuer authorization,
policy epoch and revocation. Neither callback may wait for human input or reenter
the store. Collect the decision outside the Work lock, then open the store briefly
to record it. Do not give an agent a host that approves every callback.

The CLI can describe, request, inspect and expire approvals. It deliberately has
no authority to approve, deny or revoke: those mutations require the trusted host
API. The test helper supplies a synthetic host and is not installed.

Receipts are hash-linked local audit records, not signed capabilities. Same-UID
malicious processes with access to the host/store are outside this boundary.
There is no remote authentication service, signature/key custody system or shell
sandbox in this API. A host unable to authenticate a decision must return an
error, never manufacture an issuer from agent-provided JSON.

## Integration

1. Build the existing `prepare`, `finish` or `run` execution JSON.
2. Call `golem_approval_describe`, or
   `golem approval describe WORK_DIR EXECUTION.json`.
3. Copy the returned `action` unchanged into a request and register it through
   `golem_approval_call` or `golem approval call WORK_DIR REQUEST.json`:

   ```json
   {"schema_version":1,"operation":"request","key":"approval-request-1",
    "action":"REPLACE_WITH_THE_ACTION_OBJECT","ttl_ms":60000}
   ```

4. Close the Work while awaiting the external human decision. Save the returned
   `receipt_digest` as the request receipt, not an access token.
5. The authenticated host records its decision using `golem_approval_call`:

   ```json
   {"schema_version":1,"operation":"approve","key":"decision-1",
    "request_receipt":"REQUEST_RECEIPT_DIGEST","reason":"operator-reviewed"}
   ```

6. Execute through `golem_execution_call_receipted`, passing that request receipt,
   the same host and the existing typed contract/shell approval. Inputs and host
   callbacks are borrowed for the call; the successful reply is caller-owned and
   released with `golem_execution_reply_free`. Output is unchanged on failure.

The code does not weaken document-registration or session policies.
`ASK_ALWAYS` is satisfied for this execution operation only; it does not grant a
blanket Work/session permission. `DENY` remains absolute. Existing shell approval
is still required. Once a Work registers an approval request, its execution
operations must use receipts; the legacy API cannot bypass enrollment. Existing
AUTO_LOCAL Works without approval enrollment keep their previous behavior.

## Scope and Freshness

The v1 action includes Work identity, operation, request digest, Work policy,
execution contract (including argv, environment and cwd), document inputs, source
snapshot, executable bytes, runtime profile, role enrollment, binding identity and
session epoch/attempt/session token. The runner verifies scope again before each
gate and checks expiry and live host authority through supervisor heartbeats.
An active command may be cancelled when authority is lost; effects already made
are not rolled back. Snapshot coverage is exactly the contract's snapshot plan,
not every file on the computer. This is not an atomic OS-level TOCTOU defense.

Digests use the existing bounded JSON serialization, not RFC 8785/JCS. Preserve
the generated action and execution request member order; semantically equivalent
reordered input may require a new approval. Unknown fields and versions fail
closed. Candidate-host operations are not silently granted authority by this
execution API; they retain their separate contracts.

## Lifecycle and Recovery

`PENDING -> APPROVED -> CONSUMED -> RECORDED` is the successful path.
Pending requests can be denied; pending/approved requests can be revoked or
explicitly expired. Timeout never approves. TTL starts when requested, is capped
at one hour, uses monotonic time plus boot identity, and is never renewed by an
idempotent retry. Read-only status reports observed expiration without writing an
event; use `expire` to persist it and release a pending slot.

Every mutation has an idempotency key. Reusing a key with different content fails.
The bounded ledger holds 256 events and at most 32 pending/approved requests.
Consumption reserves capacity for a result event. Exhaustion fails closed; records
are not silently evicted. Store locking serializes concurrent consumers.

Consumption is durable before dispatch. A consumed receipt is never dispatched
again. A crash or execution error after consumption leaves `CONSUMED` with
`dispatch: UNCERTAIN`, including when it is unclear whether dispatch occurred.
Do not issue a replacement approval merely because a response was lost: first
reconcile actual effects and the execution attempt's evidence externally.

```json
{"schema_version":1,"operation":"recover","request_receipt":"REQUEST_RECEIPT_DIGEST"}
```

For `RECORDED`, recover returns the stored response without dispatch. For
`CONSUMED`, it reports uncertainty and does not infer success from orphan CAS
objects. It does not automatically repair a crash between execution-result
publication and the approval result event. This guarantees non-reuse of this
receipt, not exactly-once external effects or rollback. Replay checks historical
transitions without applying today's clock to yesterday's approval.

## Design References

- [RFC 9396, OAuth Rich Authorization Requests](https://www.rfc-editor.org/rfc/rfc9396.html):
  structured action scope and substitution protection; Golem does not implement OAuth.
- [Birgisson et al., Macaroons, NDSS 2014](https://theory.stanford.edu/~ataly/Papers/macaroons.pdf):
  contextual restrictions motivate scope and expiry checks; this implementation
  does not implement macaroon cryptography or delegation.
- [Anderson, Security Engineering, third edition, chapter 6](https://www.cl.cam.ac.uk/archive/rja14/Papers/SEv3-ch06.pdf):
  separate authority and enforcement boundaries; a local C callback is not an
  OS security boundary against an agent running with the same privileges.
