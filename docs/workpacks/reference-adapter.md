# M7: Truthound observation adapter and local scenario

The native `golem_workpack_reference_observe` API and thin CLI validate a bounded
capture of **Truthound 3.3.1 Local's three legacy tools**. They do not call a provider,
read a dataset, issue approvals, create a Work or authenticate captured execution.
Mock, native-document integration and actual external calls are separate evidence.

```text
explicitly approved synthetic files → actual Truthound local MCP (or labelled mock)
  → retained check/profile/scan responses + source/config/Pack pins
  → native reference-observe: untrusted typed observation
  → separately bound native-observation-review document Work
  → native document role evaluation → exact private export → offline integrity verify

No arrow grants release authority, authenticates an external identity or establishes DONE.
```

## Native adapter

```sh
golem pack reference-observe CAPTURE.json --expect-source SOURCE_SHA256 --expect-config CONFIG_SHA256 --expect-pack PACK_SHA256
```

All three independently selected expected hashes are required. The CLI uses the
existing bounded native CLI reader and parser and prints full JSON (0 success,
1 native error, 2 usage). It has no automatic output-store publication. Explicit
existing command recording retains its original behavior. C API output stays
unchanged on error and successful replies use `golem_execution_reply_free`.

The capture is ≤256 KiB, strict UTF-8 JSON with exactly these fields:

| Field | Contract |
| --- | --- |
| `schema` | `golem.workpack.truthound-capture.v0` |
| `mode` | `MOCK` or `CAPTURED_EXTERNAL`; a declaration, never proof of a real call |
| `pack_json` | Exact manifest string ≤64 KiB; native Pack validator; ID `io.styxis.golem.dataset-release-gate`, version `0.1.0`; compare independent exact hash |
| `source` | `{digest,size}`; digest equals expected source pin, size 1..100 MiB; caller attestation, not an adapter dataset read |
| `config_json` | Exact config JSON string ≤4096 bytes; compare independent exact hash |
| `results` | Exactly three ordered `{tool,response_json}` entries: check_file, profile_file, scan_pii; each response string ≤64 KiB |

Config has exactly `schema:golem.workpack.truthound-config.v0`,
`producer_version:3.3.1`, `producer_digest` (operator's retained toolchain inventory
hash), `max_file_bytes:104857600`, `max_items:100`, `max_response_bytes:65536`,
`timeout_seconds:30`. These match the inspected Local adapter defaults. Unknown
versions/settings fail closed; there is no generic provider or command selection.
A producer digest inside a caller-supplied capture does not authenticate that producer.
Total capture/output limits can reject a capture whose individually bounded strings
expand when JSON-escaped; no truncation or partial success is used.

Each response must have exactly schema_version=1, operation=check/profile/scan,
boolean ok/truncated, data, error. Failed calls retain `{code}` and null data.
Successful data uses the inspected native Local projection:

- Check: row_count, column_count, nullable boolean success, issue_count,
  execution_issue_count, checks of name/success/issue_count.
- Profile: row_count, column_count, columns of name/dtype/null_pct/unique_pct.
  Percentages remain bounded native display strings or null; no new statistics engine.
- Scan: row_count, finding_count, count_semantics fixed to
  `estimated_from_first_1000_non_null_values`, findings of column/pii_type/count/confidence.
  Confidence is nullable numeric 0..100. Counts are estimates, not observed unique people.

Counts preserve null, otherwise require nonnegative integers. Arrays are ≤100;
column names ≤256 bytes, other display text has fixed smaller bounds. Unknown keys,
raw samples, duplicate checks/columns, malformed/duplicate JSON keys, wrong operations,
wrong pins and incompatible schema/settings fail. Known row/column counts must agree
across successful responses; untruncated profile/finding counts must match their arrays. Names/text remain untrusted JSON
data and cannot dispatch tools or instructions. The adapter is not a secrets sanitizer.

The output `golem.workpack.reference-observation.v0` retains each parsed response,
its exact original response digest, source/Pack/config pins and declared mode. Quality
is `TOOL_FAILED`, `UNKNOWN`, `DECLARED_CHECKS_FAILED` or `DECLARED_CHECKS_SATISFIED`.
The last two require exactly the null/duplicate checks, nonempty row/column counts,
known consistent issue/success fields, zero execution issues and untruncated checks.
Missing checks, contradictory fields, truncation, empty data and unknowns cannot pass.
Profile/scan transport completeness is separate from check quality; a clean check
cannot establish PII absence. `complete_untruncated_delivery` says nothing about
semantic sufficiency. Source/config equality compares attestations, not a signed
binding to the actual dataset processed by a legacy tool.

Every report states `source_binding:UNAUTHENTICATED_CAPTURE_ATTESTATION`,
`identity_verified:false`, `authorized:false`, `completion_verified:false`,
`release_readiness:NOT_EVALUATED`. Relabelling MOCK as CAPTURED_EXTERNAL never changes
those fields. Independent retained transport evidence is needed to report a real run.

## Supported native bridge

The existing external release Pack remains **not bindable** by M4. No new role,
owner/fence identity, execution permission or semantic release predicate is introduced.
The scenario tests this rejection, then uses the distinct reference
[`io.styxis.golem.native-observation-review`](../../samples/workpacks/native-observation-review.json)
with the existing doc-only role, document.read/role.evaluate ceiling and
native-documents-v1 mapping. The v0 schema's fixed READY_FOR_RELEASE literal remains
a declaration even in that document Pack; native binding does not evaluate it.

The adapter observation is quoted in a valid native planning document. Existing
native input manifests, parent closure, parser, immutable publication, exact binding
approval and role evaluation are reused. A structural SATISFIED result does not make
external findings true or a dataset releasable. M5 keeps semantic proposals untrusted.
M6 exports the selected native document closure after its own exact export approval;
external observation JSON is document content, **not a new independently authenticated
M6 object type**. Its body hash binds those quoted bytes. Verify remains unsigned
integrity only. Original source datasets are not automatically exported or imported.

## Validation layers

| Layer | What is run | What it cannot establish |
| --- | --- | --- |
| Mock fixture | Labelled synthetic envelopes, pin/schema/size failures, truncation, unknowns, contradictory checks, inert injection strings | Truthound execution |
| Native local scenario | Real compiled Golem; unsupported release binding rejection; distinct document binding, observation submission, M5 evaluation, M6 export/verify | External execution, release or current completion |
| Actual Truthound | Owner-approved installed 3.3.1 stdio server, two exact synthetic CSVs × three tools; before/after file hashes and raw protocol results retained | Desktop UI E2E, signature of processed input, PII absence or production dataset coverage |
| Retained actual-result scenario | The six saved responses enter the same native adapter; issue-result observation follows the native document bridge | Re-execution of Truthound or a new execution receipt |

`tests/c/workpack_reference.py` defaults only to explicit fixture/native modes in
CTest; it never launches Truthound. Its optional `real` mode requires
`GOLEM_WORKPACK_REAL_CAPTURE_DIR` with already authorized retained capture-clean.json
and capture-issues.json. It must not relabel mock data as actual tool evidence.
For a new live run, review exact files/digests, installed server/config, call count,
time/effects and isolated permission scope before executing any external tools.
No existing global consent or client connection is inferred or changed.

General external-role binding, independent principal verification, authoritative
READY_FOR_RELEASE, automatic publication, new MCP delivery and production deployment
remain NOT_IMPLEMENTED/outside this limited M7 contract. See
[the execution record](development-plan.md) for exact results and NOT_RUN scopes.
