# Hosted usage, billing evidence and native accounting

This extends the [command usage collector](provider-usage.md) without scanning
account histories, copying authentication, recording prompts, or changing global
agent settings. Three boundaries have separate schemas and tests: usage-only
provider events, authenticated delegated accounting evidence, and a trusted native
ledger import. None grants Work execution or completion authority.

## Hosted event collection

`tools/hosted_usage.py` supports `codex.app-server.v1` JSON-RPC notifications and
`claude.otel.v1` OTLP/JSON logs. An explicit private binding assigns one session to
one account/project/Work/attempt. Shared sessions require enumerated turn or prompt
IDs; whole-session collection requires `session_owned: true` for Claude. Account
names are local aliases, not credentials or provider identity attestations.

Codex binding example:

```json
{
  "schema": "golem.hosted-usage-binding.v1",
  "provider": "codex.app-server.v1",
  "account_id": "account-alias", "project_id": "project", "work_id": "work",
  "attempt_id": "attempt", "session_id": "thread-id", "turn_ids": ["turn-id"],
  "baseline": {"inputTokens": 0, "cachedInputTokens": 0,
               "outputTokens": 0, "reasoningOutputTokens": 0}
}
```

The caller must obtain the cumulative baseline before the bound turn starts.
Zero is valid only for a known fresh thread, not an unknown resumed conversation.
`turn/started`, `thread/tokenUsage/updated` and `turn/completed` drive the collector.
It subtracts the baseline from cumulative `total`, never sums snapshots or uses
context-window `last` as invoice usage. Counter resets, unbound or overlapping
turns and attribution conflicts fail closed. Failed turns retain partial usage.
An unobserved previous turn blocks the next turn until its usage boundary is
known; its missing tokens are never silently attributed to that next turn.

Claude replaces `turn_ids`/`baseline` with `prompt_ids` and `session_owned`.
`api_request` events use provider request IDs, session/prompt IDs, model and token
counts. Bodies, user identities, prompts and client price estimates are discarded.
Numeric and decimal-string OTLP integers are accepted; bools/floats are not.

```sh
python3 tools/hosted_usage.py ingest --binding PRIVATE_BINDING --source PRIVATE_EVENTS --output NEW_BUNDLE
python3 tools/hosted_usage.py listen --binding PRIVATE_BINDING --seconds 60 --output NEW_BUNDLE
```

The listener requires a caller-generated `GOLEM_USAGE_INGEST_TOKEN` of at least
32 ASCII characters. It binds only loopback, authenticates before reading bounded
bodies, and accepts strict Content-Length or chunked framing (including older
Claude versions). Configure only the intended child process:

```text
CLAUDE_CODE_ENABLE_TELEMETRY=1
OTEL_LOGS_EXPORTER=otlp
OTEL_METRICS_EXPORTER=none
OTEL_TRACES_EXPORTER=none
OTEL_EXPORTER_OTLP_PROTOCOL=http/json
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=<returned complete endpoint URL>
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer <private token>
```

`agent_io.py usage-total` accepts command and hosted bundles together and validates
their inventories before request union. Manifests identify the collector modules.
Use one authoritative observation route per invocation: CLI invocation totals and
OTel request events covering that same invocation have different identities and
must not be added together. Automatic cross-granularity deduplication is not claimed.
Each accepted batch is durably published before acknowledgment. Sealed checkpoints
use unique attempt names; failed partial evidence is not overwritten on retry.
Transient publication OS errors return HTTP 503 without advancing collector state.
Schema/identity conflicts return 400 and authorization failures return 403.
Sealed checkpoints remain independently readable after interruption; the legacy
collector alone does not resume. The [automatic delivery pipeline](usage-pipeline.md)
adds durable parser reconstruction, owned-process collection and native finish-time
import without changing this legacy interface. An absent exporter, dropped batch or missing bound identity is
not zero usage. `usage_complete` covers observed/declared requests, **not** proof
that every provider event was delivered. No current desktop conversation is
intercepted: its owning client must explicitly forward these supported events.

## Billing authentication and reconciliation

`tools/billing_evidence.py` verifies a caller-pinned delegated billing authority's
Ed25519 signature over exact export bytes, verifies the invoice artifact digest,
and checks account/provider, period, unique request IDs and checked integer totals.
The verification receipt also binds the parsed payload to reject accidental
mutation between verification and reconciliation.
OpenSSL execution and key algorithm checks are recorded. RFC 8410 Ed25519 key
encoding is enforced; a 64-byte signature alone is insufficient. Keys and evidence
must be bounded private regular files. Never place credentials in a binding.

`golem.billing-export.v1` contains issuer/provider/account/currency, invoice ID,
period_start/end, artifact_sha256, total_nano, unallocated_nano and request entries
with request_id/nano_cost/timestamp. Its signed total must equal entries plus the
unallocated remainder. `golem.billing-trust.v1` pins issuer/provider/account and
the exact public-key SHA-256. Negative charges/refunds need a future signed schema;
they are rejected rather than reinterpreted as unsigned charges.

```sh
python3 tools/billing_evidence.py reconcile --bundle USAGE_BUNDLE \
  --export PRIVATE_EXPORT --signature PRIVATE_SIGNATURE --public-key PRIVATE_KEY \
  --artifact PRIVATE_INVOICE --trust PRIVATE_TRUST_POLICY --output NEW_RESULT
```

Only exact account/provider/request matches receive billing amounts. Duplicate
usage counts once; conflicts stop reconciliation. Aggregated costs and unmatched
requests remain unallocated. Original observations are immutable; results are
derived separately. CLI estimates never become actual billing evidence.

`PINNED_DELEGATED_BILLING_AUTHORITY` means the chosen local authority signed an
export. It is **not** a provider-issued signature, verified payment or independent
invoice attestation; `provider_bill_authenticated` remains false. The policy's
trustworthiness and the exporter's access to genuine billing data are external
requirements. No live administrator API credentials or genuine provider invoice
were available for verification. [Provider cost adapters](provider-costs.md) now
collect bounded OpenAI/Anthropic API aggregates and compare an explicitly matching
scope against a re-verified delegated export. They do not assign Work charges or
authenticate provider invoices. Unit fixtures prove cryptographic
behavior, not actual charges. Internal reconciliation functions take trusted
verified objects; a receipt JSON file alone is not authentication.

## Native WorkRun ledger bridge

`native-export` selects a final observed request, an explicit Work, run ID, stage
sequence, currency and **known tool-call count**. No count is invented from tokens.
Pass the billing arguments above to reverify a billed export; otherwise cost is
unknown, not free. Output uses canonical decimal strings to preserve uint64 values.

```sh
python3 tools/billing_evidence.py native-export --bundle USAGE_BUNDLE \
  --work-id WORK --request-id REQUEST --run-id RUN --sequence 1 \
  --currency USD --tool-calls 0 --output NEW_NATIVE_REPORT
```

The trusted owner passes that `golem.native-cost-report.v1` JSON to
`golem_work_run_cost_report_json`. The decoder bounds input, rejects duplicate or
unknown fields, verifies run identity and validates all counters. The existing
ledger enforces ownership, begun stage, currency, duplicates and settlement rules.
It never maps a document Work to an arbitrary WorkRun or opens/finishes/settles one.
Native input is trusted accounting data, not a C cryptographic verifier.

The ledger is append-only: do not import an unpriced final request expecting to
replace it later with billing under the same identity. Defer final publication
when later billing is required; conflicting final reports remain errors.

## Research Basis

Reviewed 2026-10-09; these are design applications, not measured cost savings.

- [Codex app-server](https://learn.chatgpt.com/docs/app-server) and its
  [token notification schema](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/schema/json/v2/ThreadTokenUsageUpdatedNotification.json)
  define lifecycle and cumulative counter boundaries.
- [Claude monitoring](https://code.claude.com/docs/en/monitoring-usage) defines
  request correlation, cache buckets, OTel transport and client cost estimates.
- [OpenAI organization costs](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs)
  are aggregated; request-level Work billing cannot be inferred from those buckets.
- [RFC 9421](https://www.rfc-editor.org/rfc/rfc9421.html) motivates explicit covered
  bytes and trust boundaries. This custom detached export is not an RFC 9421 implementation.
- [RFC 9530](https://www.rfc-editor.org/rfc/rfc9530.html) distinguishes digest
  integrity from authenticity; [RFC 8410](https://www.rfc-editor.org/rfc/rfc8410.html)
  defines the accepted Ed25519 public-key encoding.
- [Sigelman et al., Dapper (2010)](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/)
  informs request correlation rather than ambiguous account-total attribution.
- [Kleppmann, Designing Data-Intensive Applications (2017)](https://www.oreilly.com/library/view/designing-data-intensive/9781491903063/)
  informs immutable observations, derived reconciliation and idempotence. Publisher
  contents were inspected, not the full textbook.

## Verification

Authorized local probes on 2026-10-09 collected actual Claude OTel request events
and Codex app-server token notifications from isolated fresh sessions. The initial
Claude probes retained UNKNOWN usage after incompatible HTTP/OTLP representations;
the corrected collector accepted installed Claude 2.1.196's chunked JSON and numeric
integers. Final Claude observation: two request IDs, 6,708 uncached input tokens and
62 output tokens. Final Codex observation: 13,095 uncached input, 2,432 cache reads
and five output tokens. All actual cost fields remained null. Private raw evidence
is not committed. These probes are not interception of this desktop conversation,
actual invoice reconciliation, Linux validation, remote CI, or cost-savings proof.
The actual Codex report was also exported into a native `cost-run` test owner:
importing it twice counted once, and terminal-stage settlement preserved its token
buckets and unknown cost. This verifies the bridge, not production WorkRun mapping.
CTest separates `provider_usage_integrations` as `host-required`; the real HTTP
receiver test is not part of the restricted-environment diagnostic profile.
Earlier local Python regression: 230 tests passed with source identity unchanged
during capture and execution inventory PASS. The final focused CTest selection
(hosted/billing integration plus ten cost cases) passed 11/11. These tests include
15 hosted/billing unit cases; counts are not additive because suites overlap.
The broader dev CTest run passed its 372-test starting inventory. The new separate
host integration registration was checked in the final focused selection. This
is not a claim of one immutable-source 373-test run; remote CI and Linux were not run.

The subsequent provider cost adapter extension passed 247 Python tests and a
12-test focused CTest selection (both provider integration groups plus ten native
cost cases). Source identity was unchanged within each recorded execution. API
transport tests use mocked HTTPS responses; billing tests use synthetic signed
exports, not genuine provider invoices. The broad CTest result above remains a
historical run, not a new full-suite result for the extended source.
