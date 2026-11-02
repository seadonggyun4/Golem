# M4 binding design gate — selected 2026-11-02

Status: OWNER_SELECTED for implementation and isolated fixtures. Original proposal
SHA-256: `81be10a3fb1f468c51a52a278cf9de2a4488733341c94da30a21854133e2e665`.
This is not permission to apply a binding to an existing production Work.
Implemented subset and its limits are documented in [binding](binding.md). Baseline: 865be0a on
workpack-contract-m1. Existing client packages, TopSolar and immutable records stay untouched.

## Findings from existing native contracts

- `include/golem/approval.h`, `src/policy/approval_scope.c`: durable native approval
  describes/consumes execution prepare/finish/run scope. A pack binding is not one of
  those operations. Reusing an execution receipt for binding would change authority.
- `include/golem/role_contract.h`, `src/workflow/role_store.c`: role enrollment uses an
  exact reviewed contract digest supplied by a trusted local caller. This is local
  attestation, not authentication of a human or an independent principal. DENY and
  ASK_ALWAYS still block mutation. Role enrollment is immutable and grants no execution.
- `include/golem/document.h`, `src/document/{storage,registry}.c`: a store handle owns
  the native shared/exclusive lifetime lock. Generation checks, hash-chained events,
  CAS verification, poisoned writers and exact-key replay already exist.
- `src/document/internal.h`: `dw_record_prepare` / `dw_event_write` are the shared
  publication mechanism; callers retain domain validation and allocation-free adoption.
- Current role rules cannot authenticate independent principals. Symbolic external
  tool names in a manifest are not native runtime grants or availability evidence.
- The milestone gate in development-plan.md explicitly leaves binding persistence,
  trusted mapping, ceiling vocabulary and identity evidence undecided before M4.

## Proposed choice: immutable native binding with separate exact approval

1. Add resolve/bind/explain native APIs and thin local CLI façades. No MCP exposure,
   installation changes, service, scheduler or new policy file applied to any client.
2. Introduce a closed, versioned `workpack-binding` event in the existing Work event
   chain. Retain the exact manifest bytes in native CAS and bind their digest, ID,
   version and selection to the reviewed mapping. One immutable binding per Work;
   other selections cannot bypass it. No replace/unbind/migrate/automatic rollback.
3. Old Works without binding remain unchanged. An older reader encountering the new
   event must fail closed, rather than silently ignoring it. Fixture tests must use
   the baseline reader to verify this before treating format compatibility as passed.
4. Bind requires a **separate, domain-separated exact binding digest** supplied by a
   trusted local caller (`--approve-binding`). It covers the native-computed Work,
   selection, manifest, existing policy/role references and binding request scope.
   Execution receipts, role approval digests and M2 drafts cannot substitute for it.
   This follows the existing local role-attestation model; it is not a new durable
   approval issuer, authenticated owner identity or grant to an agent to self-approve.
5. Preserve DENY/ASK_ALWAYS, exclusive lock, expected generation and exact key/content
   replay. Validate the current selection/input closure and any required native
   owner/fence before publication. If that identity/fence cannot be established by
   existing contracts, reject; do not infer it from caller-provided strings.
6. Reuse only explicitly supported existing native role/operation semantics. Mapping
   must match an already enrolled reviewed native role contract, not silently enroll
   or replace it. Map capabilities to a finite native operation/effect vocabulary;
   derive effects from native code, never from an agent's `available:true` or effect
   assertions. Unknown/custom/external mappings and unavailable operations block.
   Required independent identity remains blocked until a real native identity contract
   can prove it. The Truthound reference pack is not automatically bindable in M4.
7. Bind records requirements and references, **not execution permissions**. Every later
   operation retains its own native/D4/host/network/export/credential approvals.
   Existing completion predicates are neither replaced nor weakened. Unsupported pack
   completion or role requirements block rather than being accepted as inert obligations.
8. Resolve is read-only and produces exact references, proposed intersection and
   blockers. It cannot approve, enroll roles, create CAS objects or bind. Explain
   distinguishes historical binding receipt from current applicability and native
   completion. Generation is a write CAS precondition, not a fabricated claim that
   historical binding proves current readiness after subsequent Work changes.
9. Preallocate replies and validate before publishing through the existing record/CAS
   writer. On I/O uncertainty preserve the native poisoned/COMMIT_UNKNOWN outcome.
   No automatic write retry or alternate key; read-only historical lookup must not
   redispatch or renew approval. No second ledger or sidecar authority.

## Implementation and verification boundary

The choice authorizes implementing/testing this new contract only. Existing TopSolar,
client policy bytes, approval keys/pins, Work, evidence and COMMIT_UNKNOWN records are
not test subjects and receive no binding. Fixtures create disposable synthetic Works
and synthetic exact local approval inputs. No production approval is issued.

Before claiming completion, check closed schema/size limits; exact pack substitution;
duplicate/conflicting keys; current selection and policy/role drift; unsupported or
prohibited effects; missing mappings; DENY/ASK_ALWAYS; missing/foreign identity/fence;
read-only versus writable store; competing lock; stale generation; unchanged failed
outputs; reopen/replay; CAS tampering; old-reader rejection; interrupted publication
and uncertain outcome without redispatch; historical versus live explain. Run existing
native/static regression and installed C consumer tests. No client E2E is implied.

The detailed wire field names and limits will be documented with the implemented
native validator after this authority/persistence choice. If implementation discovers
that any promised check lacks a reusable native contract, retain that case as BLOCKED
and report the limitation; do not invent a bypass to pass fixtures.

Alternative: implement resolve/explain only and explicitly leave bind NOT_IMPLEMENTED
until a different durable owner authorization/identity protocol is separately designed.
That alternative would not complete the user's full M4 request.
