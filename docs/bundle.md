# Case Study Bundles (29E)

[한국어](bundle.ko.md)

Export a single ResearchCase as a **private, derived, structurally redacted**
review bundle. No network publication, provider call, raw artifact copying,
acceptance grant, or source Work mutation occurs. This is a Golem format, not
a claim of BagIt or RO-Crate conformance.

## Export and Verify

```sh
golem research export WORK --case CASE_ID --output NEW_DIR --redact samples/research/redaction-minimal.json
golem research bundle-verify NEW_DIR
golem research bundle-verify NEW_DIR --expect-manifest MANIFEST_SHA256
```

Use the `manifest_sha256` returned by export as the optional pin, retaining it
through a separately trusted channel. The parent output directory must exist;
choose a private location outside version-controlled repositories and do not
commit generated bundles without a separate disclosure review.
The output directory must be new and outside the source Work. Existing paths,
symlink components and `..` components are rejected. The directory is mode 0700,
files 0600. Source paths must be privately controlled, without hostile same-user
concurrent mutations. Local export is denied by Work `DENY`/`ASK_ALWAYS` policies;
this API does not introduce a new approval bypass.

All projection and reference validation finishes before creating the destination.
Files use no-replace publication and fsync; `manifest.json` is published last.
An interrupted write can leave a private incomplete directory. Keep it private
and retry with a fresh destination. No automatic deletion or overwrite occurs.
If an I/O error happens after final publication, verify the directory before
deciding whether it completed. Source journal/CAS state is never modified.

## Fixed Contents

| File | Meaning |
| --- | --- |
| `research-case.json` | Local case alias, case type, withheld context/questions and evidence references |
| `attempt-decisions.jsonl` | Plans and decisions with stable local attempt aliases; controlled categories only |
| `outcome-adjudications.jsonl` | Enrollment and all historical outcome revisions, not current completion |
| `cohort-observations.jsonl` | Selected member's observations only; other members/roster not copied |
| `metrics.json` | Selected 29C counts, coverage, recovery and unavailable measurements; identifiers/time/history omitted |
| `evidence-inventory.json` | Deduplicated verified source objects, local aliases, explicit raw omission |
| `redaction-policy.md` | Applied suppression profile and linkability caveat |
| `narrative.md` | Generated reviewer instructions and scope, not an invented research interpretation |
| `manifest.json` | Format/version/profile, privacy status and payload digests/sizes |
| `checksums.sha256` | SHA-256 of the eight payload files and manifest; excludes itself |

Empty event streams are empty files, not evidence of PASS. Names and ordering are
fixed. No arbitrary input-derived filenames are used. `bundle-verify` rejects
missing/extra files, malformed manifests, symlinks and mismatched hashes/sizes.
It hashes exact UTF-8 bytes, without newline normalization.

## Redaction Contract

The policy has exactly three fields:

```json
{"schema_version":1,"profile":"MINIMAL","acknowledge_linkability":false}
```

- **MINIMAL** suppresses original Work/case/attempt/project/cohort IDs, authored
  prose, paths, questions, hypothesis, intervention, rationale, arbitrary counts,
  raw statuses, timestamps, source hashes and source sizes. Bundle-local aliases,
  operation/category values, historical outcome counts and selected metric groups
  remain. Prose is not searched with a fallible secret-pattern blacklist.
- **LINKABLE** has the same suppression except that inventory source SHA-256/size
  and manifest Work-head digest are retained. It requires
  `acknowledge_linkability: true`. [Example](../samples/research/redaction-linkable.json).
  Source hashes can enable guessing, correlation and re-identification.

Unknown fields, profiles, versions or inconsistent acknowledgement are rejected.
There is no raw-export override. Every export is `PRIVATE_REVIEW_REQUIRED`, with
`public_release_approved=false`, `acceptance_verified=false` and no independent
review claim. Source privacy labels never automatically authorize publication.
Even MINIMAL retains counts, categories and graph structure that may identify a
rare case. Local aliases are not differential privacy or proven anonymization.

## Evidence Inventory Scope

The scope is **selected case research records and their direct typed CAS references**.
Each inventoried source object is hash-verified once during export; missing or
corrupt evidence aborts it. Rows always say `RAW_OMITTED` and
`NO_TRANSITIVE_EXPANSION`. Projected records reference inventory aliases, preserving
local connectivity without copying original strings or content.

References include prior decisions/plans, QA receipts, adjudication policies,
observations and cohort definitions when directly referenced. Contents of those
objects are not recursively exported. Whole-Work documents, source code, logs,
unrelated cases, other cohort members and orphan CAS objects are not scanned or
copied. This is not a complete Work archive, an independently replayable Work,
or a proof that the withheld artifacts support the claimed conclusions.

Narrative hypotheses and contextual explanations are deliberately withheld in
v1. A reviewer may need separately authorized, manually reviewed contextual
material. Do not silently insert it into a checksum-verified generated bundle;
keep human interpretation distinct from engine observations.

## Integrity and Limits

`golem.case-study-bundle.v1` verifies file membership, lengths and checksums, not
the truth of results, redaction quality, identity, or origin of the source Work.
An attacker can replace content and recompute every checksum. A separately trusted
manifest pin detects that change; it is still not a signature or identity proof.
Verification always reports `authenticity_verified=false` and
`redaction_verified=false`. Review omitted evidence before drawing conclusions.

No export timestamp is invented. `REPLAY_PREFIX_NO_WALL_CLOCK` keeps output
deterministic for the same source state and policy. MINIMAL withholds the Work
head, so unrelated Work changes may leave its output unchanged. LINKABLE pins
the full replay head. The export does not probe current source files or re-run QA.

Limits: 4 KiB policy, existing 256 research events, 2,048 unique inventory objects,
4 MiB serialized in-memory bundle. Over-limit exports fail, never silently truncate.
CAS hashing is streamed; time depends on referenced evidence size. The existing
shared Work lock provides a coherent replay view, not protection from hostile
same-user filesystem rewriting.

C API in `golem/research.h`: `golem_research_redaction_validate`,
`golem_research_bundle`, `golem_research_bundle_verify`. Inputs are borrowed;
bundle reply is malloc-owned and released with `golem_execution_reply_free`.
Output remains unchanged on failure. The in-memory format is exactly
`{"schema_version":1,"files":{filename: UTF8-content-string, ...}}`.
No new journal schema or completion rule is introduced. 29F external exports
remain separate work.

## Research Basis

- [NIST SP 800-188 (2023), sections 4.3 and 4.3.2](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-188.pdf):
  direct identifiers, indirect identifiers and linkage risk require review;
  removing strings or hashing identifiers alone does not establish privacy.
- [RFC 8493, sections 2 and 3](https://www.rfc-editor.org/rfc/rfc8493.html):
  explicit inventories and checksums separate completeness from integrity.
  Golem borrows these principles but does not implement the BagIt layout.
- [Soiland-Reyes et al., Packaging research artefacts with RO-Crate](https://www.researchobject.org/2021-packaging-research-artefacts-with-ro-crate/manuscript.pdf):
  objects, context and provenance motivate explicit source/derived relationships
  and the disclosure of absent artifacts. This bundle is not JSON-LD RO-Crate.
- [Venkataramanan and Shriram, Data Privacy: Principles and Practice (2017), preview](https://api.pageplace.de/preview/DT0400.9781498721059_A28393879/preview-9781498721059_A28393879.pdf):
  reviewed the public preface, contents and introductory material only, not the
  full text. The privacy/utility trade-off motivates conservative withholding
  and explicit loss of contextual evidence rather than an anonymization claim.
