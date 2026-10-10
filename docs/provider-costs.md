# Provider Cost Adapters

Reviewed 2026-10-09. `tools/provider_costs.py` is a read-only adapter boundary,
not an invoice issuer, payment verifier or Work allocation engine. It complements
the request observations and signed delegated exports in
[usage-integrations.md](usage-integrations.md).

## Contracts

| Adapter | Endpoint scope | Exact normalization |
| --- | --- | --- |
| `openai.costs.v1` | Organization Costs API, grouped by project and line item | JSON decimal currency units |
| `anthropic.costs.v1` | Console organization Cost Report, grouped by workspace and description | Decimal string cents divided by 100 |

Aggregated API costs are not request-level charges. These adapters do not read
ChatGPT/Codex subscription bills, claude.ai Enterprise Analytics, cloud reseller
bills or payment status. Anthropic's documented Priority Tier reporting exclusion
also means this endpoint must not be assumed to cover every charge.

Account identity is an explicit caller alias, not a provider-verified account
binding. Query periods are UTC day-aligned, start-inclusive/end-exclusive, at most
366 days. The versioned query schema rejects unknown fields:

```json
{
  "schema": "golem.provider-cost-query.v1",
  "provider": "openai.costs.v1",
  "account_id": "organization-alias",
  "start_time": 172800,
  "end_time": 259200
}
```

Use a private regular file for this query and private evidence files; never put
credentials in the query, command line, Git or chat. `fetch` reads only the explicitly
selected environment variable (defaults: `OPENAI_ADMIN_KEY`, `ANTHROPIC_ADMIN_KEY`).
It does not search CLI authentication stores or the surrounding environment.
Organization-level administrator access is required for this implemented key path.

```sh
python3 tools/provider_costs.py fetch --query PRIVATE_QUERY \
  --credential-env GOLEM_BILLING_ADMIN_KEY --output NEW_CAPTURE
python3 tools/provider_costs.py ingest --query PRIVATE_QUERY \
  --page PRIVATE_PAGE_1 --page PRIVATE_PAGE_2 --output NEW_CAPTURE
python3 tools/provider_costs.py view --bundle NEW_CAPTURE
```

`ingest` preserves `FILE_UNAUTHENTICATED`; it never pretends a fixture or exported
file was fetched over authenticated HTTPS. Even a fetched capture's unsigned local
manifest is an integrity check, not independent attestation of its network origin.

## Storage and Failure Boundaries

The collector stores query, producer/source fingerprints, bounded raw pages,
request query/cursor, timestamp, provider request ID, payload SHA-256 and a derived
report. Credentials and HTTP error bodies are not recorded. Responses echoing the
configured secret are rejected before persistence. Publication uses exclusive
private files and a final inventory manifest; errors retain an `INCOMPLETE` record
and completed pages, without a successful manifest. No automatic retries occur.

Fixed HTTPS origins, certificate/hostname verification, disabled environment
proxies and rejected redirects prevent forwarding administrator credentials to an
unselected destination. Limits are 32 pages, 1 MiB per page, 32 MiB raw capture,
4,096 rows and 1 MiB derived output. Default request timeout is 10 seconds and
collection deadline is 120 seconds; each read checks the deadline, with the socket
timeout bounding a blocked read. Split larger queries explicitly. No global
transport or credential configuration is changed.

Exact `Decimal` arithmetic retains sub-nanocurrency fractions; API aggregates are
not rounded into the native uint64 ledger. Refunds, unsupported precision, duplicate
buckets, cursor loops, unknown fields and incomplete pagination fail closed.
Absent amounts, currencies, days or empty results do not become zero. The report
separates `api_amount_complete` from `api_window_complete`; `work_cost` is always
null and `provider_bill_authenticated` always false. Null means unknown, not free.

`load` hashes the bounded private files, replays raw pages and checks the derived
result and request/cursor binding. A rewritten aggregate cannot be accepted merely
because its manifest hash was also rewritten. An attacker controlling all local
files can still forge an unsigned capture; this is not a signature scheme.

## Reconciliation

After re-verifying a delegated signed export, the existing billing command can
also compare its total with the API capture:

```sh
python3 tools/billing_evidence.py reconcile --bundle USAGE_BUNDLE \
  --export PRIVATE_EXPORT --signature PRIVATE_SIGNATURE --public-key PRIVATE_KEY \
  --artifact PRIVATE_INVOICE --trust PRIVATE_TRUST_POLICY --output NEW_RESULT \
  --cost-api-bundle PRIVATE_API_CAPTURE --confirm-same-api-scope
```

Account alias, provider and exact period must agree. Without the explicit same-API-
scope assertion, complete day coverage, complete amounts and matching currency,
the comparison is `UNKNOWN_COVERAGE`. Otherwise it reports exact `MATCH` or
`DIFFERENCE`. The assertion remains caller-provided, not independently verified.
A difference is preserved; it does not override signed request charges.

Verified API files are copied into the reconciliation bundle, so relocating the
original capture does not break this evidence chain. Aggregate totals never allocate
cost to Works, fill unknown request costs or consume an unallocated remainder.
Request-level delegated billing and native owner/stage checks retain their separate
authority. Neither aggregate agreement nor an Ed25519 signature from a local
delegate authenticates a provider invoice or proves payment.

## Extension and Verification

Keep new providers in the adapter module: add an explicit versioned provider,
fixed endpoint/auth contract, unit normalization and schema/pagination fixtures.
Do not add provider network calls or credentials to the native ledger. Schema
changes require explicit parser/test updates rather than permissive field dropping.

`test_provider_costs.py` exercises exact units, bounded parsing/pagination, private
capture replay, tampering, unknown coverage, secret handling, TLS configuration,
redirect/error handling and mocked HTTPS transport. `test_usage_integrations.py`
also exercises real Ed25519 verification plus capture snapshots and separation of
request charges from aggregate comparisons. Fixtures and mocked transport are not
live administrator API access or genuine invoice verification.

## Research Basis

- [OpenAI Costs reference](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs): endpoint, daily buckets, dimensions and pagination.
- [Anthropic Cost Report reference](https://platform.claude.com/docs/en/api/beta/organization/cost_report/retrieve) and [Usage and Cost API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api): endpoint scope, cents, administrator access and coverage exclusions.
- [RFC 6750](https://www.rfc-editor.org/rfc/rfc6750.html): credential confidentiality and TLS inform the transport boundary; this is not an OAuth flow implementation.
- [Sigelman et al., Dapper (2010)](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/): correlation motivates retaining provider request IDs rather than guessing request attribution from totals.
- [Kleppmann, Designing Data-Intensive Applications (2017)](https://www.oreilly.com/library/view/designing-data-intensive/9781491903063/): immutable facts, derived views and idempotence inform capture/replay separation. Publisher contents were inspected, not the full textbook. These applications are engineering judgments, not experimentally demonstrated savings.
