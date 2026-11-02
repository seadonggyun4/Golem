# Gate review, security and conformance plan

## Gate A review

Reviewed baseline f2563f5 in the user-selected Golem checkout. Initial worktree clean;
fast-forwarded four existing origin commits without replacing user changes. Existing
installed client runtime/policies are separate immutable snapshots and remain unchanged.
Existing common JSON parser rejects duplicate keys/invalid UTF-8/NUL/trailing tokens;
reuse it and `golem_digest_bytes`. Pack v0 is intentionally narrower than future role,
Evidence and binding objects. No persisted format or reducer change is needed for M1.

Consistency review: structural validity is never grant/readiness/DONE; exact bytes are
not canonical semantic JSON; range declarations are not runtime compatibility; a pack
is not a proof pack/template/plugin; Truthound has no release capability in the observed
three-tool inventory; installed MCP remains unchanged. All future effects are labelled
planned. M1 may proceed without an owner-policy decision. Native mutation M4 requires
an explicit design gate first. No broad delegated approval is introduced.

## Milestones

| Stage | Files / public contract | Persistence / rollback / acceptance |
| --- | --- | --- |
| M0 | docs/workpacks; source audit and terminology | Documentation only. Gate A consistency reviewed; revert docs only |
| M1 | include/golem/workpack.h, src/workpack, samples/workpacks, tests/c, fuzz | Pure bounded byte validator, additive API; no migration. Valid/invalid fixtures, failure output invariance, installed C consumer and mutation smoke must pass. Revert additive code before any binding exists |
| M2 | src/cli/workpack.c + native file reader/inspect/compatibility API | Fixed bounded no-follow input, deterministic reports; no Work writes. Symlink/race/CLI/compatibility tests required. Not implemented |
| M3 | native static catalog/search | No central service. Deterministic ranking, ambiguity/duplicate/version tests; owner-selected catalog only. Not implemented |
| M4 | native binding/resolve, immutable reference and receipt schema | New persisted state; review compatibility with old readers, migration refusal, exact key/generation/owner/fence and policy intersection before coding. No automatic rollback or existing Work migration |
| M5 | role mapping and proposal parser | Separate typed claims/assessments; stale/cross-owner/self-approval/disagreement tests; preserve failed/unknown outputs. No model truth |
| M6 | Evidence manifest/export/verify | Explicit output publication and disclosure; truncation/corruption/missing object/unsigned origin/current-vs-historical tests; retain partial exports, no auto retry |
| M7 | reference adapters and local scenario | Mock/native/real Truthound tests reported separately; no automatic release, provider grants or project changes |

Non-goals at every milestone: scheduler, merge broker, hosted service, model/provider
configuration, billing, license change, repository split and client marketplace migration.
Risks: adding public API requires binding/version/export inventory review; coarse schema
names must not be mistaken for existing capability grants; schema validation cannot
predict availability. M1 has no path API, so filesystem safety is not implemented by it.

## Threat model and test matrix

| Threat / negative case | M1 disposition / later test gate |
| --- | --- |
| oversized/malformed/YAML/non-object/trailing data/deep JSON | reject bounded strict JSON; fixture and mutation smoke |
| duplicate/escaped duplicate keys, NUL, bad UTF-8 | shared parser rejection; regression cases |
| unknown schema/extensions/fields/executable/provider/path declaration | closed manifest, fail with static diagnostic |
| ambiguous Unicode ID, traversal IDs, empty/duplicate IDs, invalid version/latest | ASCII identity grammar, exact version parser, duplicate arrays reject |
| untrusted descriptions/instruction injection/hidden network | inert bounded data, no dispatch API; no semantic sanitization claim |
| pack substitution/digest mismatch/canonical ambiguity | exact-byte digest tested; M4 compares reviewed digest and immutable source |
| symlink escape/racy file/duplicate catalog ID | no filesystem API in M1; M2/M3 tests mandatory before support |
| capability escalation/prohibited effect/unavailable tool/owner denial | declarations only in M1; M4 intersection denial tests required |
| self-approval/forged identity/foreign owner/duplicate worker | no claims in M1; M4/M5 existing native ownership/SOD tests |
| stale parent/evidence/verifier, interrupted Work/unknown effects | M4/M5 reject, preserve uncertainty; never retry effects |
| downgrade/rollback/unsupported core/replay historical binding | M2 reports compatibility; M4 exact historical pin, no migration |
| malicious verifier/disagreement/reasoning leakage | M5 bounded proposal and provenance; raw reasoning never required |
| forged receipt/missing objects/truncation/projection tampering | M6 integrity tests; unsigned provenance never authenticated |
| Korean/English positive-negative discovery/ties | M3 deterministic corpus; no embedding APIs |

M1 tests must compare output unchanged on failure, stable same-byte digest and distinct
reformatted digest; sizes/counts at and above bounds; invalid semantic versions and
range reversal; required/unknown fields; meaningful text; non-ASCII identity; full
reference fixture. Fuzz target uses public API only and deterministic mutation smoke;
coverage-guided runs are separate evidence, not implied by smoke. An installed consumer
must link only the exported C header/library. Existing native regressions remain enabled.
M1's schema draft has extra semantic constraints beyond JSON Schema; native validator
is canonical, schema text is a discovery aid and cannot grant authority.

## Current execution record

Gate A documentation committed before implementation. M1 implementation/test outcomes
will be appended after running them. M2–M7 remain NOT_IMPLEMENTED, not merely NOT_RUN.
No unresolved policy choice blocks the pure validator. Before M4, decide binding event
schema/version compatibility, trusted role mapping, precise ceiling vocabulary and
independent identity evidence. No default owner policy is invented here.
