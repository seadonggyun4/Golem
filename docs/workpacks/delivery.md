# CLI/API, discovery and distribution boundary

## Command plan (all CLI commands below are NOT IMPLEMENTED in M1)

| Command | Input → output | Effects, gates and errors |
| --- | --- | --- |
| `golem pack validate PACK` | bounded file → structural report/digest | M2 read only; native validator; no Work lock |
| `golem pack inspect PACK` | bounded file → inert metadata | M2 read only; escape untrusted text |
| `golem pack compatibility PACK` | manifest + fixed core version → declared compatibility | M2 no runtime readiness/authority |
| `golem pack list` | explicit catalog → bounded ordered entries | M3 read only, no recursive host scan |
| `golem pack search QUERY` | catalog + ≤256-byte query → scored refs | M3 no provider/embedding/network |
| `golem pack resolve WORK PACK` | exact references/current role → proposed intersection | M4 read-only native Work lock as required; no implicit binding |
| `golem pack bind WORK PACK` | owner-reviewed reference + expected generation/key → binding receipt | M4 mutation; Work lock/CAS/native gate; exact idempotency |
| `golem pack explain WORK` | immutable binding + live state → blockers | M4 read only; historical vs live explicit |
| `golem receipt export WORK --format json` | reviewed native refs → manifest | M6 explicit output write/disclosure gate |
| `golem receipt export WORK --format markdown` | same native refs → projection | M6 derived write, never receipt authority |
| `golem receipt verify PATH` | bounded inventory → integrity result | M6 read only, no implicit downloads |

Proposed common CLI exit codes: 0 structural/read success (never grants), 2 invalid
input/schema, 3 incompatible/unsupported, 4 denied/stale/missing requirement,
5 I/O/uncertain publication. Exact mapping to existing CLI errors must be reviewed
before M2; do not change existing command exit semantics. Input is 64 KiB for manifests;
M3 catalog proposed 256 entries/1 MiB; M6 bounds in roles-and-evidence.md.
Reads are repeatable but not automatically retried on failure; mutation retries must
use native exact-request lookup and preserve uncertainty. Reads do not require new
Work audit; future integration may append its existing scoped read audit. M1 has no
CLI audit or file access. Work changes need existing durable native records.

Only the additive native validator is in M1. Python/TypeScript bindings and MCP exposure
are NOT implemented. CLI will remain a thin public C API façade, never a Python reducer.
API version must be advertised separately from catalog schema and native core version.
New API symbols must not imply complete language binding parity.

## Local catalog design (M3)

Explicit owner-selected static JSON index contains pack ID/version, schema, digest,
relative local manifest reference, status, intent terms, aliases, category, capability
names and negative intent. No install implies review. Read through M2 no-follow root;
reject duplicate ID/version with differing digest. Validate every referenced manifest,
never trust index metadata over exact bytes. At most 256 entries, 16 aliases/terms per
field, 256 bytes per term. No mutable latest authority or hidden network requirements.

Initial lexical ranking: ASCII casefold, split whitespace; Unicode display text uses
exact UTF-8 matching until normalization rules are specified. Positive score is number
of distinct query terms matching intent/alias/category/capability tokens; any matching
negative-intent phrase excludes an entry. Sort score descending then ASCII ID, numeric
version, digest; return all top ties as AMBIGUOUS, zero matches as NO_MATCH. No automatic
selection or bind, especially for Korean tokenization ambiguities. Fixtures must cover
Korean/English positive/negative queries, ties, duplicate index entries and stale digest.
No vector database or remote search. This is Golem runtime discovery, not external GEO.

## Machine-readable source contract for styxis-plugin

M1 adds a source metadata record with schema/API versions, public native entrypoint,
no CLI/MCP claims, reference inventory and security boundary. Build/release automation
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
