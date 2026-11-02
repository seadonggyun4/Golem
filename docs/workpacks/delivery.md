# CLI/API, discovery and distribution boundary

## Commands (M2–M7 native commands implemented with limits)

| Command | Input → output | Effects, gates and errors |
| --- | --- | --- |
| `golem pack validate PACK` | bounded file → structural report/digest | M2 read only; native validator; no Work lock |
| `golem pack inspect PACK` | bounded file → inert metadata | M2 read only; escape untrusted text |
| `golem pack compatibility PACK` | manifest + fixed core version → declared compatibility | M2 no runtime readiness/authority |
| `golem pack list --catalog INDEX` | explicit catalog → bounded ordered entries | M3 read only, no recursive host scan |
| `golem pack search QUERY --catalog INDEX` | catalog + ≤256-byte query → scored refs | M3 no provider/embedding/network |
| `golem pack resolve WORK REQUEST` | exact references/current role → proposed intersection | M4 read-only native Work lock as required; no implicit binding |
| `golem pack bind WORK REQUEST --approve-binding DIGEST` | owner-reviewed reference + expected generation/key → binding receipt | M4 mutation; Work lock/CAS/native gate; exact idempotency |
| `golem pack explain WORK` | immutable binding + live state → blockers | M4 read only; historical vs live explicit |
| `golem pack proposal-validate FILE` | bounded proposal → exact digest | M5 pure structural validation; no authenticated identity |
| `golem pack assess WORK FILE [FILE...]` | 1..8 claims + current binding → separate native role evaluation | M5 read-only Work; no approval/assessment publication |
| `golem pack reference-observe CAPTURE --expect-source SHA --expect-config SHA --expect-pack SHA` | pinned Truthound capture → typed untrusted observation | M7 no tool execution, Work write or release verdict |
| `golem receipt manifest WORK REQUEST PARENT [--format json\|markdown]` | exact current refs → inventory/approval digest | M6 read-only review; no export |
| `golem receipt export WORK REQUEST PARENT --approve-export DIGEST [--format json\|markdown]` | reviewed inventory → private package | M6 separate exact disclosure gate; no Work writes |
| `golem receipt verify DIRECTORY --expect-manifest DIGEST` | bounded package → anchored integrity | M6 unsigned origin; no current completion verdict |

M2 uses the existing CLI exit taxonomy described below. Later commands must separately
review their status mapping without changing existing command semantics. Input is
64 KiB for manifests; M3 catalog 256 entries/1 MiB; M6 bounds are in
[receipts.md](receipts.md).
Reads are repeatable but not automatically retried on failure; mutation retries must
use native exact-request lookup and preserve uncertainty. Reads do not require new
Work audit; MCP delivery appends its existing scoped read audit. M1 has no
CLI audit or file access. Work changes need existing durable native records.

M2 adds bounded snapshot reading, metadata inspection and declared-version comparison.
M3 adds local catalog discovery. All fourteen CLI operations now have [common MCP
routes](mcp.md); dedicated Python/TypeScript Work Pack SDK bindings remain unimplemented.
CLI remains a thin public C API façade, never a Python reducer.
API version must be advertised separately from catalog schema and native core version.
New API symbols must not imply complete language binding parity.

## Local catalog design (M3)

Explicit owner-selected static JSON index contains pack ID/version, schema, digest,
relative local manifest reference, status, intent terms, aliases, category, capability
names and negative intent. No install implies review. Read through M2 no-follow root;
reject every duplicate ID/version, including identical duplicates. Validate every referenced manifest,
never trust index metadata over exact bytes. At most 256 entries, 1–16 aliases/intent/negative-intent terms per
field, 1–32 native capability names, 256 bytes per text term. No mutable latest authority or hidden network requirements.

Initial lexical ranking: ASCII casefold, split whitespace; Unicode display text uses
exact UTF-8 matching until normalization rules are specified. Positive score is number
of distinct query terms matching intent/alias/category/capability tokens; any matching
negative-intent phrase excludes an entry. Sort score descending then ASCII ID, numeric
version, digest; return all top ties as AMBIGUOUS, zero matches as NO_MATCH. No automatic
selection or bind, especially for Korean tokenization ambiguities. Fixtures must cover
Korean/English positive/negative queries, ties, duplicate index entries and stale digest.
No vector database or remote search. This is Golem runtime discovery, not external GEO.

## Machine-readable source contract for styxis-plugin

M1–M7 maintain a source metadata record with schema/API versions, fourteen public native entrypoints,
the fourteen CLI routes, five common MCP tools, reference inventory and security boundary.
Only exact M4 bind mutates Work; M6 separately exports private files. Source metadata
is not proof that a particular installed client exposes or may call those tools. Build/release automation
must attach the actual source commit/archive digest separately; never put a self-referential
commit hash in the source record or use mutable latest. A branch name is not provenance.
Packaged files need independent artifact inventory and compatibility checks.

Golem supplies contracts, local runtime requirements, capability ceiling and reference
inventory. `styxis-plugin` supplies Claude/Codex manifests, launchers, marketplace copy,
agent task phrases, installation instructions, distribution tests and public discovery.
Existing `plugins/golem` and integration packaging modules stay in place during M1.
Migration plan: inventory existing identities/pins → define release metadata → verify
byte-equivalent packages in styxis-plugin → owner-reviewed client update → separately
review retirement of redundant packaging. No destructive moves, public Alpha catalog
registration or installation updates in this task. `styxis-io` content is untouched.


## M2 implemented behavior

```sh
golem pack validate samples/workpacks/dataset-release-gate.json
golem pack inspect samples/workpacks/dataset-release-gate.json
golem pack compatibility samples/workpacks/dataset-release-gate.json
golem pack compatibility samples/workpacks/dataset-release-gate.json --core-version 0.1.0
```

The default comparison version is the compiled `GOLEM_VERSION_STRING`, never a remote
or mutable latest version. This compares the numeric inclusive declared interval only;
it does not check tools, ABI support, role mappings, policy or current Work readiness.
M2 uses existing CLI conventions: **0 success, 1 native/read/output failure or declared
incompatibility, 2 usage error**. Existing commands retain their exit semantics. Incompatibility emits a successful
comparison report with `declared_compatible:false` on stdout and the existing
`golem.cli-error.v1` UNSUPPORTED_VERSION diagnostic on stderr, then exits 1.
Malformed input emits no success report. Errors never authorize retries.

Success stdout is full bounded JSON `golem.workpack.report.v0`, including `operation`,
`exact_digest`, original byte `size`, `structurally_valid:true`, `authorized:false`,
`bound:false`, `work_done:false`. Inspect adds the full validated `manifest` as JSON
data (reserialized, not the digest's original byte representation). Compatibility adds
`core_version`, `declared_compatible`, `runtime_availability:"NOT_EVALUATED"`.
Output order is deterministic for identical bytes and inputs. No timestamp/path is
included. Descriptions are inert JSON strings, never terminal instructions or commands.
Output is bounded by twice the 64KiB input plus 1KiB envelope. Stdout failure may leave
partial output; nonzero status forbids interpreting it as a successful report.

Paths are explicit local CLI input authority, not an MCP grant. Relative paths start
at cwd; absolute paths start at `/`. Paths are <=4095 bytes; native component traversal
rejects `..` and symlinks, including parents. Regular single-link files only; no FIFO,
socket, directory, stdin, URLs, recursive scan or auxiliary file loading. Advisory
shared nonblocking lock plus two bounded reads, nanosecond mtime/ctime, inode/device,
size/mode/link count and final pathname reopen are compared. Observed drift fails;
there is no retry. Atime may change. This is a checked snapshot, not a guarantee that
a hostile same-user writer can never change or restore a file between observations.
The caller must keep cwd/input memory stable. There is no lock on or access to Work.

No automatic output-cache publication: these commands write directly to stdout even
with global compact/output-store options. Existing explicitly configured top-level
`GOLEM_RECORD_ROOT` recording still applies and may write command records; M2 neither
turns it on nor bypasses it. No policy changes, approvals, Work writes, subprocesses
or network are introduced by the native pack handlers. MCP delivery adds only its
existing scoped transport/recording; installation and policy selection are separate.

## M3 implemented catalog and search

```sh
golem pack list --catalog /reviewed/catalog.json
golem pack search '데이터 검증' --catalog /reviewed/catalog.json
```

`golem_workpack_catalog` is the common native implementation. CLI does no independent
parsing or ranking. The closed index is `{ "schema":"golem.workpack.catalog.v0",
"entries":[...] }`. Each entry has exactly these eleven fields:

| Fields | Contract |
| --- | --- |
| `id`, `version`, `schema`, `status`, `intent`, `negative_intent`, `capabilities` | Must equal the referenced validated manifest values (array order included) |
| `digest` | 64 lowercase hexadecimal SHA-256 characters over exact manifest bytes |
| `manifest` | Nonempty relative path <=1024 bytes, resolved relative to index directory |
| `aliases` | 1–16 distinct nonempty text strings, each <=256 bytes |
| `category` | Nonempty text <=256 bytes |

No extra keys, duplicate JSON keys, embedded NUL, invalid UTF-8 or duplicate ID/version
pairs are accepted. Empty catalogs are valid. Paths cannot contain absolute references,
URLs, backslashes, `.`/`..` or empty components. The M2 native no-follow/regular-file/
single-link/lock/drift checks apply to both index and manifests. Every entry is validated
before matching, even when the query would exclude it. Stale digests or copied metadata
fail the entire operation with no success stdout. Aliases/category are index-owned
search hints; they are not authenticated pack claims or approval.

The index is checked again after loading all references. This is bounded snapshot
observation, **not a cross-file atomic transaction**: manifests are validated at their
individual read times. A subsequent use must revalidate exact bytes. There is no scan,
watcher, persistent cache, network, embedding, subprocess, auto-install or binding.

Queries are strict UTF-8, 1–256 bytes, nonblank; ASCII whitespace is collapsed and ASCII
letters lowercased. Other Unicode is matched exactly without normalization, stemming
or language segmentation. Distinct query tokens score once across intent, aliases,
category and capability tokens. Negative phrases match contiguous normalized tokens
and exclude the entry. Substrings inside a token do not match. Search includes all
positive non-excluded results, sorted by score descending, ID byte order, numeric version
ascending, then digest. All highest-score ties remain visible as `AMBIGUOUS`; `MATCH`
means one highest-scoring candidate, never automatic selection or compatibility.

JSON `golem.workpack.discovery.v0` contains `entries` (ID/version/digest/relative
manifest/status/score), `result` (`LISTED`, `MATCH`, `AMBIGUOUS`, `NO_MATCH`),
`authorized:false`, `bound:false`, `runtime_availability:"NOT_EVALUATED"`.
Zero matches and ambiguity are successful observations (exit 0). Native errors exit 1;
usage errors exit 2. Full JSON goes to stdout without automatic output-cache writes.
The existing explicit command-recording option is preserved. No current Work is read.

Native output capacity is capped by the 2 MiB report bound. `required` includes NUL and
changes only on success/BUFFER_TOO_SMALL; output bytes remain unchanged on errors.
A NULL/zero output size query still reads files; its next call is a fresh observation.
CLI allocates the bounded output once and performs one catalog operation. M4 binding is limited to [native document contracts](binding.md).
See [common MCP delivery](mcp.md) for the read and exact-action routes, client
verification and current installation limits.

M4 resolve/bind/explain use the [separate exact binding contract](binding.md). Unsupported
external/development/identity mappings block; binding is not execution or semantic release approval.

M5 proposal-validate/assess use the [bounded untrusted proposal contract](proposals.md).

M6 manifest/export/verify use the [bounded private evidence package contract](receipts.md).

M7 uses the [Truthound observation adapter and native document bridge](reference-adapter.md).
