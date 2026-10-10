# Provider usage attributed to Work

The agent command runner accepts an optional `usage` binding on each command.
It supplies `GOLEM_USAGE_STREAM` to the child process, collects that usage-only
JSON-lines stream even after a failed command, and binds it to Work, attempt,
session, provider account, and request IDs. `view`, `measure`, and `report` expose
the resulting accounting. SDK calls require an instrumented adapter. Dedicated
Codex and Claude Code CLI calls also have built-in terminal-event adapters;
hosted chat account totals are not usage evidence.

Example command-plan entry (replace the executable and IDs before execution):

```json
{
  "id": "agent-call",
  "argv": ["/absolute/provider-adapter", "run"],
  "timeout": 60,
  "usage": {
    "provider": "openai.responses.v1",
    "account_id": "private-account-alias",
    "project_id": "project-1",
    "work_id": "work-1",
    "attempt_id": "attempt-1",
    "session_id": "session-1",
    "request_ids": ["request-1"]
  }
}
```

`request_ids` enumerates expected call identities, including separately identified
retries/fallbacks. The integration must bind the real response to these identities;
the caller must not reuse an ID across billable calls. Attribution is explicitly
caller-supplied and is not independent provider attestation. Account IDs are local
aliases, never credentials. A shared session's aggregate totals cannot be divided
among Works by this interface. Each command has one stream writer; concurrent
commands receive different private stream paths.

Provider adapters call `provider_usage.emit` after extracting usage from the SDK:

```python
import os
from provider_usage import emit

emit(os.environ["GOLEM_USAGE_STREAM"],
     provider="openai.responses.v1", request_id="request-1",
     model=response.model, usage=response.usage.model_dump(), final=True)
```

The helper validates the usage-only schema and fsyncs an append. A producer using
additional SDK usage fields must explicitly select this version's supported fields;
unknown fields fail closed rather than silently changing normalization. For Claude,
use the assembled final Message usage, or assembled cumulative usage snapshots:
merge `message_start` and `message_delta` in the SDK adapter before emitting. Raw
partial deltas or response content must not be passed as usage. Emit `final=False`
for an interrupted stream; retain the known partial amount with UNKNOWN coverage.

Supported contracts:

- `codex.exec.v1`: reads `codex exec --json` stdout, correlates `thread.started`
  with one `turn.completed`, and normalizes input/cache/output plus optional
  `reasoning_output_tokens`. No token price or invoice amount is inferred.
- `claude.code.v1`: reads `claude -p --output-format stream-json --verbose`
  stdout, correlates init/result session IDs, and normalizes terminal usage.
  When `modelUsage` is available, checked per-model counters replace the terminal
  counters for accounting, including auxiliary model calls; they are never added
  on top of terminal usage. The terminal counters remain separate in metadata.
  `total_cost_usd` is preserved separately in `cli_usage.estimated_cost`, using
  Decimal and explicit half-even nano rounding, never in actual `cost`.
  Multiple reported models are listed without claiming HTTP request-level attribution.
- `openai.responses.v1`: `input_tokens`, `output_tokens`, input cached tokens and
  optional cache-write tokens, output reasoning tokens, optional total tokens.
  Cache reads are subtracted from input; reasoning is subtracted from output.
- `anthropic.messages.v1`: input/output plus optional cache-read/cache-write input.
  Cache writes belong to input in the existing C cost convention. The original
  write count is also preserved. Separate reasoning is not reported in this
  contract and remains included in output; zero separate reasoning is not proof
  of no reasoning. Tool-call billing is not inferred from model content.

For CLI contracts, use the actual CLI executable in `argv` and select the matching
provider above. There is exactly one unique `request_ids` entry per dedicated CLI
invocation; it is a caller correlation ID, **not** a provider HTTP request ID.
The terminal counters cover that invocation, not every individual internal call.
The runner automatically derives a usage-only stream from the private captured
stdout. The immutable execution manifest binds original stdout/stderr; the outer
observation manifest separately binds derived usage after the process completes.
Both inventories must verify independently. Missing terminal usage stays UNKNOWN, and malformed usage retains the
real process exit code and raw evidence while failing collection. Fresh invocation
is required: resume/continue/fork options are rejected before launch because
conversation totals can include earlier executions. Repeated IDs within a plan
are rejected, including retries. A unique ID must also be used across new plans.

For a minimal live check, use an isolated committed repository, Codex read-only
sandbox and ephemeral mode, or Claude safe mode with `--tools ""` and
`--no-session-persistence`. Existing authentication is used by the CLI, not read
or copied by this collector. Provider calls require user authorization. Binary
hash, argv, exit code, source identity, stdout, stderr and normalized usage are
preserved in the private observation bundle. CLI model availability is checked
by the actual call; a failed model request is not silently replaced by the runner.

Each envelope has schema `golem.provider-usage.v1`, request_id, model, usage,
final (boolean), and billing (null or an object). Billing accepts an integer
`nano_cost`, a three-letter `currency`, and `evidence_sha256`. It represents the
adapter's reported request-level billed amount. The digest links a separately
retained billing artifact; this module does not authenticate or fetch the invoice.
Do not copy secrets or an entire invoice into the usage stream. Estimated token
prices cannot be supplied as actual billing. No live price table or currency
conversion is embedded in the collector.

```sh
python3 tools/agent_io.py run --plan PLAN.json --cwd REPOSITORY --output NEW_BUNDLE
python3 tools/agent_io.py measure NEW_BUNDLE
python3 tools/agent_io.py usage-total BUNDLE_A BUNDLE_B
```

The total command verifies bundle inventories and unions request identities
before computing per-Work totals. It rejects conflicting final reports and Work,
attempt, session, model, or account reassignment. Repeated identical reports count
once. Stream snapshots replace earlier cumulative values; they are not summed.
Currencies remain separate. Counters use checked uint64 arithmetic compatible
with the C ledger's token buckets and nano-currency amounts.

`usage_complete` and `cost_complete` describe only declared requests. Missing,
failed, interrupted, or stopped requests never establish free execution. An
unreported request preserves UNKNOWN coverage, known partial token sums remain
visible, and reported zero billing is distinguishable from missing billing.
Legacy records keep null usage. A request outside the binding, malformed stream,
private-file violation, or conflicting usage stops the runner and preserves its
raw capture for diagnosis. Usage collection itself grants no execution authority.

Native document Work and legacy WorkRun are different owners. The explicit
[hosted/billing/native integration](usage-integrations.md) adds event collection,
delegated signed-export reconciliation and a native report input without changing
ledger settlement semantics. It requires an explicit run/stage mapping and known
tool count; it does not pretend that a document Work is a C WorkRun. These results
do not enforce a provider account budget or automatically intercept the surrounding
desktop conversation.

## Research and design basis

Reviewed 2026-10-09. The following design choices are engineering applications of
the references, not evidence that this implementation improves costs:

- [OpenAI Responses reference](https://developers.openai.com/api/reference/resources/responses/methods/create):
  provider usage totals and cache/reasoning details motivate disjoint buckets.
- [Claude streaming](https://platform.claude.com/docs/en/build-with-claude/streaming):
  cumulative message-delta usage motivates snapshot replacement and explicit finality.
- [Codex non-interactive execution](https://learn.chatgpt.com/docs/non-interactive-mode):
  documented JSONL lifecycle and terminal usage drive the Codex CLI adapter.
- [Claude programmatic execution](https://code.claude.com/docs/en/headless):
  terminal usage, resumed conversation totals and client-side cost estimates drive
  the fresh-invocation boundary and billing/estimate separation.
- [OpenTelemetry GenAI spans](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md):
  distinguish input, output and cache counts; this local schema is not an OTel exporter.
- [Sigelman et al., Dapper (2010)](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/):
  request correlation motivates explicit request/session/attempt attribution.
- [Kleppmann, Designing Data-Intensive Applications (2017), chapters 11 and 12](https://www.oreilly.com/library/view/designing-data-intensive/9781491903063/):
  immutable observations, derived views and duplicate handling motivate union totals.
  Publisher contents were inspected; no claim of reviewing the entire textbook.
- [Stopford, Designing Event-Driven Systems (2018), chapter 7](https://www.oreilly.com/library/view/designing-event-driven-systems/9781492038252/ch07.html):
  idempotence and event-derived state inform conflict rejection and materialized totals.

Unit tests use synthetic provider events and real subprocess capture. Separate
authorized live probes on 2026-10-09 collected Codex CLI usage with `gpt-5.5`
and Claude Code terminal usage successfully. Codex calls using the default
`gpt-5.4` and configured `gpt-6.1-sol` were rejected by the account; their failure
records were retained rather than called successful. Claude's bracketed model
suffix and sub-nano cost representation were discovered by these live probes.
Actual multi-model output also showed that terminal usage can omit auxiliary
model counters; the model aggregate is therefore authoritative when provided.
Private raw probe evidence is not published in this repository. These observations
do not authenticate invoices, measure this surrounding desktop conversation,
or demonstrate cost savings. New provider versions extend adapters and tests;
they do not reinterpret historical records.

Final verification: 215 Python tool tests passed, and both final live probes
passed the original execution and derived observation inventory checks. Claude
also performed a bounded code review; findings were triaged against the actual
error boundary and documented event contracts. These are local macOS results,
not Linux, native C regression, remote CI or invoice verification results.
