# Common Work record protocol

## Scope and authority

Work status is already derived by replay, not an independently writable status
file. Assessment input, ordered journal events, and rendered reports have
different identities and responsibilities. Consolidation must not replace those
identities with a second mutable summary or silently rewrite historical evidence.

`src/document/record.c` now owns the common native write protocol. The existing
unified Work record read view remains a projection. This change consolidates
write and read implementation; it does not physically deduplicate all assessment fields,
merge every product journal, compact historical records, or change public APIs.

## Write contract

1. The caller validates domain rules, idempotency, authority, and input schema
   under the existing store lock. It allocates its response at the existing point.
2. `dw_record_prepare` checks writable/poisoned state and the caller's JSON budget,
   then persists the original JSON-C compact representation in CAS. Preparation
   alone is not a committed event. Unreferenced prepared evidence can remain.
   Budget checking and persistence now use the same single serialization, so a
   custom JSON-C serializer cannot produce a different second representation.
3. The common publisher verifies that the referenced CAS object exists and has
   the expected digest. For runtime/admission links, the read-only lease guard
   runs after this verification, immediately before publication.
4. `dw_publish` retains the existing immutable, no-replace, fsync-based publication
   protocol. The common writer emits the historical document/agent 80-byte frame
   or the existing raw/hexadecimal digest reference, without changing identities.
5. Only successful publication updates the output digest. The caller retains
   responsibility for adopting the event in its domain-specific in-memory state.

Missing/corrupt prepared evidence and uncertain publication poison the handle:
reopen and replay rather than blindly appending again. A final authority guard
denial publishes nothing and does not poison the store. An error after physical
publication is not a rollback assertion. Existing identical publication retries
remain idempotent; conflicting bytes are rejected. Hashes provide integrity,
not authentication against an attacker able to rewrite all stored evidence.

## Migrated paths

| Family | Common writing boundary |
| --- | --- |
| Work creation and document submission | JSON preparation and document event |
| Agent assessment/session transitions | Bounded preparation and agent event |
| Approval, research, role, completion, reentry | Preparation and document event |
| Runtime profile and runtime/admission links | Preparation and document event; final lease guard for links |
| Workspace and candidate records | Preparation and hexadecimal CAS reference |
| Execution receipts, results, change findings | Raw CAS reference |
| Candidate cancellation notice | Raw CAS reference |

Policy enrollment, dispatch/start intent, workspace ownership markers, requested
proof/report exports, and Markdown projections intentionally retain their own
publication calls. They are not interchangeable CAS event references. Runtime
and admission subsystem journals are not merged into the Work journal. Domain
validation, replay, state adoption, and required completion evidence remain at
their existing owners; no persistent projection cache or new dependency is added.

## Maintenance and verification

### Common reading boundary

`src/document/record_read.c` owns contiguous stream discovery and frame/CAS
validation for document replay, agent replay, history (including incremental
history), and the unified Work-record projection. `dw_record_scan` enforces
canonical eight-digit filenames, caller-specific sequence limits and the caller's
empty-stream policy. It ignores unfinished `.pending-*` publications without
deleting them. `readdir` and `closedir` errors retain syscall diagnostics.

`dw_record_read` checks the existing 80-byte domain/sequence/previous-digest
frame against the writer's codec, computes its identity, and reads verified CAS
JSON. It never repairs or publishes data. Its output digests and JSON ownership
change together only on success. Read-only handles work; read errors do not
poison the handle or adopt partial domain state. Domain reducers, lease checks,
authorization and lock ownership remain with the existing callers.

An existing frame containing the wrong sequence is consistently
`CORRUPT_JOURNAL`; the history projector previously called this `MISSING_RECORD`.
Directory gaps remain `MISSING_RECORD`, missing files/CAS retain their existing
read errors, and oversized/nonregular files retain the low-level I/O failure.
Public signatures, successful JSON results, journal bytes and CAS identities
are unchanged. No key sorting, semantic JSON deduplication, persistent cache,
cross-Work deduplication or disk migration is introduced. Prefix validation is
still performed even for pages after the first page.

### Regression guardrails

`work_record_inventory.py` inventories remaining low-level publication calls
and checks known event writers use common preparation. It also checks the three
stream readers use the common reader and keeps magic strings in one codec owner.
New writers must use this
boundary or document and test a distinct publication contract. This source-level
tripwire is not a proof against arbitrary macros or indirect calls.

`work_record_writer` exercises 14 isolated scenarios: single serialization with
an exact budget boundary, document/agent frame
compatibility, raw/hex references, read-only rejection, budget rejection, missing
CAS evidence, final guard order/denial, invalid names, corrupt CAS evidence,
failure before/after publication, and conflicting publication. It also verifies
idempotent preparation/publication and unchanged output on failure. Broader
API/CLI tests cover replay and the migrated domain paths. Fault injection is
test-local; no production environment-variable bypass is added.

`work_record_reader` exercises 13 isolated scenarios covering both domains,
bad magic/sequence/previous digest, truncation, missing/corrupt CAS, stream gaps,
noncanonical names, sequence budgets, symlinks and nonregular files. It also
checks empty-stream policy, ignored pending files, unchanged failure outputs,
read-only use and shared payload identity with distinct domain frames.

These checks do not establish power-loss correctness on every filesystem or
Linux compatibility. No token, latency, or storage-saving claim follows merely
from writer consolidation.

## Research basis

The following primary sources informed the design. Reading was scoped to the
sections identified below, not the entirety of each book or paper. The mapping
to Golem is an engineering inference, not a claim to implement their algorithms.

| Source and inspected scope | Design implication |
| --- | --- |
| Quinlan and Dorward, [Venti: a new approach to archival storage](https://www.usenix.org/legacy/events/fast02/quinlan/quinlan.pdf), FAST 2002, abstract and section 3 | Reuse the existing content-addressed payload identity and verify reads; do not equate a shared payload with one event. No new hash algorithm or storage backend is adopted. |
| Abiteboul, Hull, Vianu, *Foundations of Databases* (1995), [chapter 11](https://webdam.di.ens.fr/Alice/pdfs/Chapter-11.pdf), introduction and lossless decomposition discussion | Remove implementation redundancy without losing information or conflating independently meaningful facts. |
| Abiteboul et al., [Incremental Maintenance for Materialized Views over Semistructured Data](https://www.vldb.org/conf/1998/p038.pdf), VLDB 1998, abstract/introduction and section 3.1 | Distinguish authoritative records from derived views and preserve update ordering. No materialized-view cache is introduced here. |
| Pillai et al., [All File Systems Are Not Created Equal](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-pillai.pdf), OSDI 2014, introduction and section 2.2 | Preserve persistence ordering and ambiguous-error handling; mocked failures do not replace a filesystem crash matrix. |
| Fowler, [Event Sourcing](https://www.martinfowler.com/eaaDev/EventSourcing.html), application state storage and event handling | Keep replay-derived state separate from durable event authority; centralize mechanism without centralizing domain decisions. |
| W3C, [PROV-DM](https://www.w3.org/TR/prov-dm/), entity/activity/derivation and bundles | Preserve source identities and provenance distinctions rather than flattening all records into one summary. |

The 2026-10-03 extension rechecked the database textbook's section 11.2
(lossless decomposition), Venti section 3, Pillai section 2.2, and PROV-DM
sections 5.1.1-5.1.4. These motivate information preservation, verified shared
payloads and separate event identities; they do not establish a formal
normalization proof, PROV conformance or crash safety for Golem.
