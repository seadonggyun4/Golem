# Consolidated Work records

`golem work record WORK REQUEST.json` reads the existing registry, session status,
and both document/agent event streams under one existing Work-store lock. It is a
derived read model, not a new writable database, approval, or completion receipt.
The default `agent_io.py observe` captures this instead of a separate status query.
Its following next/completion queries remain independent observations.

## One capture, multiple views

```json
{
  "schema_version": 1,
  "work_id": "example-work",
  "byte_budget": 33554432,
  "document_head": "",
  "agent_head": ""
}
```

Use `--output-mode full` before `work` for machine consumers. Native compact
output still supports verified original retrieval as described in
[CLI output](cli-output.md). The byte budget bounds complete serialized JSON
(maximum 32 MiB), not the allocation footprint. Insufficient space fails without
partial output or silently truncated history.

Both expected heads may be empty for a new capture. To require the same committed
prefix, supply BOTH heads from a prior record. A change to either stream rejects
the request. Matching heads do not pin elapsed time: lease validity can change
without an event. Offline views are historical captures, not live permission.
The lock covers cooperating local writers, not arbitrary filesystem tampering,
source repositories, remote hosts or global time.

The `golem.work-record.v1` payload contains:

| Section | Source and contract |
| --- | --- |
| `work_specification` | Verified original requirements and policy |
| `assessments` | One object per SHA-256 of JSON-C compact assessment bytes |
| `documents` | Every revision, original manifest/body/event digests, freshness and metadata with `assessment_ref` instead of embedded assessment |
| `status` | Existing session status, including state, live-lease observation and recent event details |
| `journal` | Existing history projection of ALL document and agent events, retaining payload/frame digests and stream/sequence ordering |

Reconstruct original metadata by copying `documents[i].metadata` and restoring
`assessment` from `assessments[assessment_ref]`, when present. Identity is native
serialization identity, not semantic equivalence or RFC 8785 canonical JSON:
different member orders can remain distinct. References are derived content IDs,
not new CAS receipts. Changed judgments and superseded revisions remain separate.
No prose interpretation creates QA PASS or changes original manifest identities.
Reconstruction preserves JSON field values, not original whitespace, key position
or exact metadata CAS bytes. Retrieve those bytes from the original registry/CAS;
do not recompute a registration identity from the normalized view.

History contains references and selected fields, not all raw payloads; original
CAS remains their source. Status's recent event details remain for compatibility
even where they overlap history fields. Identical text with different provenance
is not merged into one judgment. Markdown bodies are referenced by digest, not
copied into every view.

```sh
python3 tools/agent_io.py observe --cwd /path/to/repository \
  --cli /path/to/golem --work /private/path/work --work-id example-work \
  --selection selection --task code --output /private/path/new-observation
python3 tools/agent_io.py record-view /private/path/new-observation --section assessments
python3 tools/agent_io.py record-view /private/path/new-observation --section status
python3 tools/agent_io.py record-view /private/path/new-observation --section journal
python3 tools/agent_io.py report /private/path/new-observation
```

Section views and on-demand reports read the SAME captured stdout, verify the
observation manifest, and expose the same raw-record SHA-256 and stream heads.
They neither query the engine again nor maintain separate assessment/status/journal
files. Report source fields are JSON-escaped in indented code, not interpreted as
Markdown instructions. The execution recorder retains commands, executable/source
identity, exit status and stderr. Hash integrity does not authenticate authors.
Existing view/delta/raw/measure commands remain available.

## Compatibility and failures

- Existing assessment inputs, metadata schemas, CAS and journals are NOT rewritten
  or deleted. Physical duplicate bytes in legacy metadata remain; consolidation
  covers the reading/reporting boundary and the native
  [common write protocol](work-record-writing.md), not storage compaction.
  Replay and history projection also share its frame/CAS validation mechanism;
  domain-specific reduction and authorization remain separate.
- Discovery report, document inspect, session status and work history retain
  their contracts. Required native completion reports and QA gates remain required.
- Old observation bundles still support old views/report. `record-view` rejects a
  legacy bundle without a successful consolidated step instead of fabricating data.
- Missing/corrupt source prefixes or CAS, unknown request fields, wrong Work IDs,
  stale heads and insufficient budgets fail without emitting a partial record.
- Boot-identity clock failure remains a failed observation with its diagnostic,
  not an empty successful status. Offline rendering needs no clock or live Work.
- A later next/completion failure leaves the successful Work capture inspectable,
  but the enclosing observation still reports failure.

This does not replace every handwritten report, deduplicate different Works, or
change which inputs an agent must author. New schemas must preserve reconstruction
and authority boundaries. No background worker, second event store, database or
runtime dependency was added. Whole-history capture is bounded; large Works may
need the existing paged `work history` API instead. Performance is not measured.
Its [schema 2](incremental-history.md) also supports append-tolerant incremental
polling without replacing the consolidated record's snapshot contract.

## Research rationale

Sources inspected on 2026-10-02. The following are design inferences, not Golem
performance evidence, formal normalization proofs or conformance claims.

| Primary source and inspected scope | Decision and limitation |
| --- | --- |
| Abiteboul, Hull, Vianu, *Foundations of Databases* (1995), [chapter 11 introduction and section 11.2 decomposition/lossless join](https://webdam.di.ens.fr/Alice/pdfs/Chapter-11.pdf), [chapter 10.2 view dependencies](https://webdam.di.ens.fr/Alice/pdfs/Chapter-10.pdf) | Remove duplicate representation with reconstructible links and retained provenance. This JSON design is not claimed to be a formally normalized relational schema. Only relevant sections, not the whole book, were inspected. |
| Abiteboul et al., *Incremental Maintenance for Materialized Views over Semistructured Data*, VLDB 1998, [abstract, introduction, update discussion and section 4 cost model](https://www.vldb.org/conf/1998/p038.pdf) | Views must remain consistent with inputs. Rebuild bounded verified streams under one lock; defer persistent incremental caches until profiling justifies invalidation complexity. Lorel/OEM algorithms and measured benefits are not transferred to Golem. |
| Fowler, [Event Sourcing](https://www.martinfowler.com/eaaDev/EventSourcing.html), How It Works, Application State Storage, External Updates/Queries | Preserve source logs; rebuilding derived representations must not repeat external effects. Architectural guidance, not a consensus or exactly-once proof. |
| W3C, [PROV-DM](https://www.w3.org/TR/prov-dm/), sections 2.1, 2.2.2-2.2.3 | Separate authored assessments, observations and derived bundles; retain entity and collection identity. Hashes establish neither truth nor authentication. |
| Kleppmann, *Designing Data-Intensive Applications* (2017), [public publisher contents](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/titlepage01.html) | Bibliographic orientation for derived data/state-stream separation only. Paid chapter text was not read and supplies no implementation-specific claim. |

Tests compare status/history with existing APIs, reconstruct metadata, distinguish
assessments/revisions, reject stale heads/corruption/overflow, and verify no Work
mutation on success or injected clock failure. Tool tests cover same-source views,
deterministic reports, legacy rejection and tampering. These test structural
correctness, not provider token savings, semantic comprehension or model cost.
