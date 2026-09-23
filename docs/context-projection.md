# Context projection

Golem produces a derived reading aid, not a replacement for original Markdown,
approval receipts, QA evidence or completion gates. No additional agent is launched.
Public C API: `golem/context.h`. CLI commands are opt-in; agent resume does not
automatically consume these projections.

## Request

All fields are required. Replace the snapshot with an independently observed,
current source digest and use an existing registered stage selection.

```json
{
  "schema_version": 1,
  "renderer_version": 1,
  "recipe": "extractive-v1",
  "selection_id": "selection",
  "target_kind": "development-plan",
  "source_snapshot": "<64 lowercase hexadecimal characters>",
  "byte_budget": 2097152,
  "excerpt_bytes": 1024,
  "token_budget": 0,
  "tokenizer_id": "none",
  "agent_note": ""
}
```

```sh
golem context render WORK_STORE request.json
golem context markdown WORK_STORE request.json
golem context publish WORK_STORE request.json
golem context read WORK_STORE PROJECTION_DIGEST CURRENT_SOURCE_DIGEST
```

`render` returns a JSON bundle containing Markdown, source inventory and mandatory
facts. `markdown` prints its Markdown view. `publish` writes immutable CAS bytes and
returns a digest receipt; it does not create a document revision or advance the Work
journal. Retain the receipt and request independently. The same canonical request,
Work state and live workflow observations produce the same bytes. A changed note,
source, Work head or live next action can produce a different digest.

## Preservation and authority

- Full Work specification, acceptance criteria, document metadata/history, parent
  references, reentry/completion/research records and next action remain structured.
- Input closure originals are verified using the existing workflow integrity gate.
  Each excerpt carries a manifest digest, body digest and exact byte accounting.
- Lines containing registered requirement IDs or case-sensitive status/policy
  markers (`FAIL`, `PASS`, `SKIPPED`, `NOT_DONE`, `DENY`, `ASK_ALWAYS`,
  `ASK_ON_EXTERNAL_EFFECT`, `AUTO_LOCAL`) are preserved even outside the prefix.
- Source text and optional agent notes are indented as quoted data. This is not an
  LLM prompt-injection security proof. Notes never modify machine facts or authority.
- Arbitrary prose meaning is not extracted or guaranteed. Unmarked requirements
  must be read in the original. Historical records retain their historical meaning;
  a quoted PASS does not establish current completion.

The omission inventory describes the range absent from each prefix, which may
overlap separately preserved passages. JSON is the complete inventory surface.
The Markdown view includes the mandatory facts and exact source links.

## Budgets, freshness and fallback

The byte budget covers the complete serialized JSON, including duplicated Markdown
facts and metadata, not just excerpt bytes. Maximum bundle size is 2 MiB. Insufficient
space for mandatory facts fails without emitting a partial result. The output cap
is not a strict allocator quota. Large historical Works may exceed it.

The C API accepts a trusted deterministic tokenizer callback pinned by an ID. It
counts the complete JSON, not an approximate bytes-to-token conversion. The CLI
has no model tokenizer and rejects nonzero token budgets. Request ownership,
short-buffer and callback contracts are documented in the public header.

`read` verifies CAS and rebuilds against current originals, facts and Work head,
then compares the complete bytes. It does not trust an artifact's source snapshot
as proof of freshness. Callers must independently supply the current snapshot.
Unrelated Work events can conservatively invalidate a projection.

If the projection is missing or its recipe is unsupported, explicitly render
`original-v1` from an independently retained valid request. That recipe includes
all input bodies and still enforces budgets and integrity. Missing or corrupt
originals block; they never justify a fallback to unverified summary text.

## Validation and limits

The integration suite checks deterministic CAS identity, request key order,
start/middle/end fact retention, source revision invalidation, untrusted notes,
original fallback, corrupted originals, budget rejection and C buffer/tokenizer
contracts. The request validator is also part of the document fuzz harness.
These are structural regression tests, not evidence of agent comprehension,
semantic summarization quality, lower latency or reduced token cost.

Research rationale: [Lost in the Middle](https://arxiv.org/abs/2307.03172) motivates
position-sensitive fixtures; [PROV-DM](https://www.w3.org/TR/prov-dm/#component2)
informs derived-source separation; [Build Systems a la Carte](https://simon.peytonjones.org/assets/pdfs/build-systems-original.pdf)
informs dependency invalidation. [Introduction to Information Retrieval, evaluation](https://www-nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-text-classification-1.html)
informs separating fact retention from semantic quality and computational cost.
