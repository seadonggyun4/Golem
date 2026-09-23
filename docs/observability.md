# Derived Observability Export

[한국어](observability.ko.md) | [Research](research.md) | [Disclosure policy](bundle.md)

Golem exports a **read-only, case-scoped snapshot** as OTLP JSON logs or PROV-JSON.
CAS and the Work journal remain the source of truth. Neither output is an import
format, a completion decision, an authenticated execution trace, or permission to publish.
No Collector, endpoint, credentials, SDK or network transmission is configured.

[Runtime diagnostics](runtime-events.md) add a separate fixed-allowlist event-page
export in this derived layer. Those pages are not case-study bundles and do not
change this case-scoped redaction contract or become QA evidence.

## CLI

```sh
golem research observability WORK --case CASE_ID --format otlp --redact samples/research/redaction-minimal.json
golem research observability WORK --case CASE_ID --format prov --redact samples/research/redaction-minimal.json
```

Output is JSON on stdout; errors go to stderr with a nonzero exit status. All
validation and mapping finish before output begins. An output I/O error can still
leave partial bytes. Save only in a private location **outside the source Work**:

```sh
umask 077
set -C
golem research observability WORK --case CASE_ID --format otlp --redact POLICY.json > /private/export/new.otlp.json
```

Create the private parent beforehand. `set -C` prevents normal shell overwrite.
Shell redirection opens the destination before Golem runs: even failed commands
can leave an empty file. Golem cannot protect a path opened by your shell; do not
redirect to CAS/journal files or use a source path as the destination. Protect
captured stdout too. There is no automatic upload or background export.

## Contract

Mapping version: `golem.observability.v1`. Input is the existing 29E structural
projection, generated internally after strict Work replay and direct CAS digest
verification. There is no arbitrary JSON-to-telemetry passthrough or raw-file path.
Unknown formats, invalid policies, unknown cases and corrupt evidence fail closed.
The Work's export permission applies; `DENY` and `ASK_ALWAYS` are not bypassed.

| Concern | Behavior |
| --- | --- |
| MINIMAL | Original IDs, prose, paths, times and source hashes/sizes withheld |
| LINKABLE | Explicit acknowledgement required; original hashes can correlate private data |
| Authority | `DERIVED_ONLY`, always `PRIVATE_REVIEW_REQUIRED` |
| Time | No wall-clock, timestamps, durations or invented observation time |
| Identity | Manifest-content namespace; not a unique execution/person/Work identity |
| Limits | 29E case/event/inventory bounds; output at most 4 MiB; no transitive CAS expansion |
| Reproducibility | Same replay prefix, policy and engine version give identical bytes |
| Ownership | Borrowed inputs; malloc-owned reply; free with `golem_execution_reply_free` |

`golem_research_observability(store, case_id, policy, format, out, diagnostic)`
supports `GOLEM_RESEARCH_EXPORT_OTLP_LOGS` and `GOLEM_RESEARCH_EXPORT_PROV_JSON`.
Serialize calls on a Work handle. Output remains unchanged on failure. The API
does no filesystem writes. Bundle v1's ten-file format is unchanged.

## OTLP Mapping

The JSON shape is an `ExportLogsServiceRequest`:
`resourceLogs[] -> scopeLogs[] -> logRecords[]`. Nine snapshot logs contain the
eight redacted payload files and manifest. Each `body.stringValue` preserves the
corresponding redacted file bytes; `golem.payload.name` labels its format. JSONL
bodies remain JSONL strings, not an undocumented substitute for OTLP AnyValue.
Resource attributes carry mapping version, derived manifest SHA-256, privacy,
authority and time basis. These `golem.*` attributes are local conventions.

This is **snapshot telemetry, not one span/log per original execution**. Declared
PASS/FAIL remains inside the redacted payload; it is not promoted to a trusted span
status or log severity. Trace/span IDs and both timestamp fields are omitted.
Missing protobuf timestamps decode as zero (unknown), not the epoch of an event.
There is no live OTel observer here. A downstream Collector must apply its own
actual observation timestamp when it observes the data; it must not overwrite
historical time with that value. Backend ingestion and retention are deployment
concerns and have not been tested against a live Collector.

Counts remain historical snapshot data, not synthetic OTel counters with fabricated
temporality/start times. The manifest digest links this mapping to the 29E manifest,
not to a newly committed CAS object. The checksum file is not included as a log.

## PROV Mapping

PROV-DM concepts are serialized with **PROV-JSON (W3C Member Submission)**, not
represented as a W3C Recommendation serialization or PROV-O/JSON-LD.

| Entity/activity | Meaning |
| --- | --- |
| `g:eNNNN` | Scoped alias for inventoried original CAS evidence; bytes omitted |
| `g:redact` | Structural projection and direct-source verification transformation |
| `g:bundle` | Redacted intermediate, with manifest text and derived manifest digest |
| `g:map` | Deterministic mapping transformation |
| `g:projection` | Derived projection description, never original evidence |

`used` connects transformations to their inputs. `wasGeneratedBy` connects only
new derived entities to those transformations. `wasDerivedFrom` points from the
projection to the bundle and from the bundle to inventoried sources. These are
coarse transformation dependencies, not field-level causal explanations or proof
that a recorded observation is true. References inside original documents are not
automatically promoted to PROV causal relations. There are no claimed agents,
signatures, start/end times, inferred actor identities or original-source generation
events. The graph covers direct inventory only, not a complete Work provenance DAG.

The `g` prefix expands to `urn:golem:derived:<manifest-sha256>:`. Identical redacted
content can deliberately share this namespace; do not use it to count independent
cases. MINIMAL cannot identify a unique original Work or journal prefix. LINKABLE's
manifest includes the original Work head, but that digest is neither a signature
nor an external trusted freshness anchor. No private content is dereferenced.

## Verification And Limits

The integration suite checks byte-equivalent redacted payloads, relation endpoints
and direction, deterministic replay, source immutability, privacy, invalid inputs
and corrupt evidence. An optional independent consumer test uses
`opentelemetry-proto` and `prov` in a separate test environment:

```sh
python tests/c/observability_conformance.py build/dev/golem . build/dev/tests/c
```

Those packages are test-only, not C/CLI runtime dependencies. Versions are pinned
in `tests/c/requirements-observability.txt`; install
them into a separate virtual environment, not the application's environment.
Consumer parse and roundtrip checks do not establish full PROV constraint validation, clinical or
scientific validity, anonymity, authenticity, Collector interoperability or live
production integration. Rare categories can re-identify a case. Review privately
before sharing. Exported claims never update research adjudication or completion.

## References And Design Rationale

- [OTel logs data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/): preserve missing time and distinguish source time from observation time.
- [OTLP specification](https://opentelemetry.io/docs/specs/otlp/): protobuf JSON envelope; actual payload uses string AnyValues without inventing numeric wire fields.
- [Official logs protobuf](https://github.com/open-telemetry/opentelemetry-proto/blob/main/opentelemetry/proto/logs/v1/logs.proto): optional trace context and unknown timestamp semantics.
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) and [PROV-JSON](https://www.w3.org/submissions/prov-json/): distinguish entities, transformations, usage and derivation.
- [Buneman, Khanna and Tan, 2001, Why and Where](https://www.pure.ed.ac.uk/ws/files/16509989/Why_and_Where_A_Characterization_of_Data_Provenance.pdf): source location and contribution are different questions. We implement coarse derivation, not their query-provenance algebra or causal inference.
- [Moreau and Groth, 2013, Provenance: An Introduction to PROV](https://www.provbook.org/): modeling, validation and provenance management are distinct concerns. The publicly available author overview/chapter descriptions were reviewed; this is not a claim to have reviewed the full book.

Specifications and public research material reviewed on 2026-09-23. This mapping
is versioned independently of upstream specifications so later signal mappings
can be added without changing authoritative journals or the 29E contract.
