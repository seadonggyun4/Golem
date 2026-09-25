# Pinned Candidate Diff and Review

Candidate diffs are immutable, versioned **derived evidence**, not patches to
apply and not permission to merge or push. The existing candidate host supports
the operations below through `golem_candidate_call` and `golem candidate call`.
No new agent process or shell is started.

## Capture

After a candidate is FINISHED with an issued, current v4/v5 QA receipt:

```json
{"operation":"diff-seal","group_id":"group","candidate":"a","redaction":"source"}
```

The trusted host must authorize this exact request, including source retention,
hold exclusive workspace authority and quiesce writers through capture. `source`
persists source bytes in private CAS; it is not an automatic secret scrubber.
Use `redaction:"metadata"` to omit file names and source content from the returned
projection. Metadata views cannot receive PASS reviews. Hashed paths are not
anonymization and underlying private CAS must remain access controlled.

Resolution is only through a registered candidate, its workspace receipt and
filesystem identity, settled QA, and QA checkpoint. Requests accept no arbitrary
path, Git revision, URL, command, or executable. QA and input-document freshness
are checked before and after capture. The parent CAS preserves the exact before
and after inventories, QA receipt and projection before the group journal points
at them. Other QA dependencies are not recursively exported.

The `full-file-hex-v1` renderer emits changed files with:

- Exact before/after head, index and worktree identities, modes and sizes.
- Byte-exact before/after worktree content as hexadecimal strings, including
  binary files and symlink targets. Null means absent or unavailable; an empty
  string means an actual zero-byte file. Inspect `content_complete` to distinguish.
- ADD, DELETE or MODIFY. Renames are deliberately represented as DELETE + ADD;
  there is no fuzzy rename inference or line-hunk renderer in v1.

Historical preimages come only from the pinned blob OID, verified against the
inventory SHA-256 and size. Missing dirty/untracked preimages are not replaced
with HEAD content. Current files are opened component-by-component without
following symlinks; symlinks are read, never traversed. Git only performs a fixed
`cat-file blob <validated-oid>` call, without filters/textconv/diff drivers. Git
hooks, network effects and ambient Git environment are disabled by the existing
workspace supervisor boundary. This is not a sandbox against malicious
same-user writers; the trusted host must enforce quiescence.

Bounds: 64 displayed changed paths, less than 16 KiB per file content capture,
32 KiB aggregate raw content, and 192 KiB row JSON. Inventory coverage remains
the existing policy-scoped 1,024 paths. Extra rows set `truncated`; missing or
oversize content and uncovered staged content set `complete:false` and per-row
`content_complete:false`. No incomplete view can authorize full review. Narrow
the candidate scope or use a future renderer for larger reviews; do not suppress
the limit. All limits are implementation-versioned, not caller-controlled.

## Read

```sh
golem candidate diff /absolute/parent-work group a
```

Returns JSON with `observation:"HISTORICAL_NOT_LIVE"`. This works even when the
registered candidate tree has been moved or removed. It does not prove that
present files match. All content is hex/JSON escaped; clients must not render it
as trusted HTML, executable Markdown, shell input or an applicable patch.

Local reads use Work filesystem read authority, just like `candidate status`.
Hosts may call `{"operation":"diff","group_id":"group","candidate":"a"}`;
when a host is supplied its authorization callback is mandatory. The production
Unix-socket host uses exact-request approval. No HTTP endpoint is added.

## Review and Freshness

Use the digest returned by `diff-seal`:

```json
{"operation":"review","group_id":"group","candidate":"a","diff":"<sha256>","qa":"","decision":"PASS","reviewer":"reviewer-session"}
```

`decision` is PASS or FAIL. `reviewer` is an audit label, **not authentication**;
the trusted host must verify reviewer authority. Receipts are append-only and
the latest decision governs. They bind the exact diff, candidate QA, checkpoint,
input manifest, inventories, group manifest and enrollment through digests.
Hashes establish identity/integrity, not authorship or reviewer independence.

```json
{"operation":"review-check","group_id":"group","candidate":"a"}
```

Rechecks live candidate QA/document freshness and latest PASS identity. Changing
code or input documents makes the live review unusable; changing the projection
digest requires a matching review. Historical reads remain available.

Once a candidate has a sealed diff, compare/select require its fresh PASS review.
Old groups without a diff retain their existing contract; hosts that require
reviews universally must require `diff-seal` before selection. This is not an
implicit migration of old groups or a global Work-completion predicate.

After selection, review the target separately by submitting the same operation
with `qa` set to the target's exact issued QA digest. The target must resolve
through the host, pass QA, and match the selected policy-scoped patch identity.
`target-check` then requires that target-bound review as well as live freshness.
A different QA receipt or changed target requires re-review. Review never grants
merge/push authority, and no patch is applied. A selected group cannot reseal;
changed candidates require a new group/attempt under the existing lifecycle.

## Design References

- [Git cat-file](https://git-scm.com/docs/git-cat-file) distinguishes raw blob
  access from filter/textconv operations. The renderer uses only raw access.
- [Git diff](https://git-scm.com/docs/git-diff) documents external drivers and
  text conversion; no such extension executes in this renderer.
- Bacchelli and Bird, [Expectations, Outcomes, and Challenges of Modern Code
  Review, ICSE 2013](https://sback.it/publications/icse2013.pdf): reviewers need
  change context; review is not a substitute for actual QA. This motivates
  preserving QA and input identities alongside content, not claiming correctness.
- Anderson, [Security Engineering, third edition, chapter 6](https://www.cl.cam.ac.uk/archive/rja14/Papers/SEv3-ch06.pdf):
  access-control mechanisms and capabilities motivate a trusted authorization
  boundary rather than treating caller labels as authority.
- [W3C PROV-DM](https://www.w3.org/TR/prov-dm/) distinguishes derivation and
  responsibility. Projection identity is separate from original execution evidence.
- [SLSA v1.1 attestation model](https://slsa.dev/spec/v1.1/attestation-model)
  motivates binding claims to immutable subjects. Golem does not claim SLSA
  compliance or introduce cryptographic signing through this feature.

These are engineering applications of the references, not empirical evidence of
Golem performance or reviewer accuracy. The integration tests exercise real local
QA commands; live provider effectiveness remains a separate deployment study.
