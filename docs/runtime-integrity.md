# Runtime Integrity and Recovery

## Guarantees

| Layer | Check | Limit |
| --- | --- | --- |
| WorkRun v1 journal | Frame version, CRC32, contiguous sequence, semantic replay | CRC is not authentication |
| Journal writer/replay | Ordered SHA-256 checkpoint, exact endpoint verification | Reopen requires a separately retained anchor to detect prior rewriting |
| Journal inspection | SHA-256 source digest and ordered frame chain | Trusted external head required to detect deliberate rewriting |
| Document event log | Previous-frame digest and content-addressed payload | Whole-store rollback requires an external anchor to detect |
| Evidence CAS | SHA-256 bytes and no-replace publication | Content identity does not prove truth or authorship |
| Completion | Historical evaluator dispatch and current live verification | Historical acceptance is not current acceptance |

The WorkRun wire format remains v1, including its historical `HWJR` magic.
Changing this identifier for branding would break existing records. No existing
bytes are rewritten. The derived chain is explicitly not a new journal format,
signature, MAC, or forward-secure log. It is now also used by writer recovery
and daemon admission, without changing the v1 bytes.

## Inspect and Anchor

```sh
golem journal inspect /absolute/path/journal.bin
golem journal inspect /absolute/path/journal.bin --expect-chain PREVIOUSLY_RETAINED_SHA256
golem replay /absolute/path/journal.bin --expect-chain PREVIOUSLY_RETAINED_SHA256
```

Inspection emits JSON, including `source_digest`, `chain_head`, `records`,
`valid_bytes`, `discarded_bytes` and `stream_status`. Counts use decimal strings
like the existing CLI's uint64 projections. A malformed stream still emits its
report but exits nonzero. I/O/argument failures do not emit a successful report.
The CLI bounds input to 64 MiB; the borrowed-byte C API has no file-size policy.

For each complete structurally valid encoded frame F:

```text
H0 = 32 zero bytes
Hi = SHA256(ASCII("golem.journal.chain.v1") || H(i-1) || SHA256(Fi))
```

There is no terminating NUL in the domain string. The frame includes its schema,
type, length, sequence, payload and CRC. Store the head outside the same mutable
trust boundary. An attacker who can replace both log and head can rewrite both.
An exact whole-frame truncation looks like an unfinished run without a retained
expected head. `--expect-chain` checks exact equality, not append-only extension.
Inspection checks framing, not valid Core transitions or business acceptance.

The writer computes its checkpoint on open and extends it only after a successful
append fsync. `golem_journal_checkpoint_get` returns that value without I/O.
File recovery always compares the streaming replay against this opened/durable
checkpoint before exposing a WorkRun. A same-length, CRC-correct rewrite during
the handle lifetime is rejected. This does not prevent hostile writers from
modifying the file during an append; advisory locking remains the writer contract.
An unanchored reopen observes the bytes currently present, not their provenance.

Streaming callers may copy a retained checkpoint with
`golem_replay_expect_checkpoint` before feeding bytes; finish checks head, count
and byte length. Unanchored legacy replay remains available explicitly for
compatibility. The daemon computes its expected checkpoint from the already
published intent transcript and compares the locked writer snapshot before
runtime recovery/dispatch. Intents and journal in the same compromised directory
are not independent authentication. No signing keys or trusted remote service
are implied by this change.

## Explicit Salvage

First stop all writers and retain the original privately. Obtain its
`source_digest` from inspection, then explicitly accept losing a torn final frame:

```sh
golem journal salvage /absolute/path/journal.bin /absolute/path/new-recovery \
  --expect-source SOURCE_SHA256 --accept-truncated-tail
```

The command only accepts a truncated final header/payload following at least one
complete frame. It rejects CRC corruption, version errors, gaps, an empty stream,
an intact stream and invalid transitions in the prefix. It verifies the prefix
through Core replay before creating a new directory. It never edits the source,
overwrites an existing destination, skips a corrupt interior record, runs an
agent, grants a lease, or infers that an interrupted external effect is safe to retry.

The new directory contains `journal.bin` (exact verified prefix), `salvage.json`
(source digest, chain head, retained/discarded byte counts). Files are published
with no-replace links and file/directory fsync through the existing CLI backend.
A final `salvage.commit` contains the SHA-256 of the exact receipt bytes and is
published only after both components succeed. Retain this digest separately:

```sh
golem journal verify-salvage /absolute/path/new-recovery --expect-receipt RECEIPT_SHA256
```

Verification requires all components, the expected receipt digest, a matching
prefix chain/count/length and valid Core replay. It does not run an agent or
grant execution authority. Old exports without a marker do not pass this new
verification command; they remain inspectable. An interrupted export may leave
an incomplete directory; retain it and use another destination. Never synthesize
a missing marker to make a partial export pass. The receipt is not a signature.
Verification checks the exported snapshot, not a concurrently modified original.
The source digest pins the bytes inspected by this invocation. A concurrent writer
after the read can still advance the original: quiescence remains an operator duty.
Do not substitute the recovered file into a live daemon automatically.
This command supports WorkRun binary journals, not document event directories.

## Completion Evolution

Schema-1 completions already bind `assessment.policy.predicate` into the evidence
root and policy digest. Replay now selects its evaluator from that stored field:
`golem.completion.development.v1` dispatches to `co_evaluate_v1` in
`completion/predicate_v1.c`; an unknown
predicate/schema returns `UNSUPPORTED_VERSION` rather than treating it as corrupt.
A missing identifier remains malformed. Today's completion issuance/live check
uses the current evaluator separately from historical replay.

Adding acceptance semantics requires a new predicate, a dispatcher branch and
old/new compatibility fixtures. Preserve v1 assessment and report bytes. Shared
dependency changes can still affect historical behavior: version dispatch is an
explicit compatibility boundary, not an automatic guarantee that arbitrary future
refactoring is safe. Existing recovery/idempotency integration tests must continue
to open schema-1 records and compare report bytes without rerunning QA.

The historical Markdown renderer is now `renderer_v1.c`. Dispatch uses the
record schema and recorded predicate; changes to future presentation must use a
new version rather than editing this renderer. Replay's byte-for-byte report
check remains enabled, so an unrelated CAS object cannot replace a report.

`completion_historical_store` loads a synthetic store produced by commit
`5184979`, not the code under test, and checks its original report digest without
restoring or executing its source project. This exercises the shared workflow,
reentry and session dependencies as well as evaluator/renderer dispatch.
Those helpers are not blindly duplicated into a second runtime. Their historical
behavior is a compatibility contract: semantic changes need a versioned path and
must continue to pass this fixed fixture. The fixture covers a development+QA
completion with sessions, not every possible historical assessment.

## Process and Memory Ownership

`EPIPE`/`ECONNRESET` while sending stdin means the child declined remaining input.
The supervisor closes the input endpoint, drains output and reaps normally;
unsent input still yields `INCOMPLETE_WORK`, including a zero exit code. Other
send errors remain `IO`. A child that closes stdin and hangs still times out.
Signal/exit details remain available for failure classification.
Pipe draining after reap also honors the original timeout: transient `EAGAIN`
is not EOF or an I/O failure. A retained pipe or unresolved group-cleanup denial
still prevents success; the reaped process-group ID is never signalled again.

Document-store allocators now cover workflow/context scratch and CAS JSON reads
as well as owner/graph storage. Scratch never escapes into public replies.
Public reply buffers, standalone I/O buffers and `open_memstream` use the C heap;
release them with their documented API, not a store allocator. json-c, MD4C and
OpenSSL own their allocations. A custom allocator is not a process-wide quota.

The seven workflow subsystems use the checked-in `.clang-format`. Internal
prefixes identify ownership: `dw` document work, `wf` workflow, `ex` execution,
`as` agent session, `co` completion, `re` reentry, `ds` discovery. They are not
public ABI. Completion authorization and record construction are separate helpers;
predicate dispatch is in `completion/evaluator.c`.
Agent-session replay's duplicate-key scratch also uses the store allocator.
The historical-store test injects failure at each store allocation in session
replay and checks that all temporary allocations are released on each failure.

## Python Prototype

The root Python package is historical, not the C runtime. Its console script is
now **`golem-prototype`**, never `golem`. Existing installations must be upgraded
in their own virtual environment to replace old entrypoint metadata; editing this
repository cannot remove an already-installed script from another environment.
Use Conan/CMake for the C CLI and `bindings/python` for native bindings.

An old installed launcher can be audited and explicitly quarantined:

```sh
python3 tools/retire_legacy_cli.py /absolute/venv/bin/golem
python3 tools/retire_legacy_cli.py /absolute/venv/bin/golem --apply-sha256 AUDITED_SHA256
```

The tool accepts only recognized Python entrypoint ASTs, rejects native binaries,
symlinks and custom wrappers, and never executes the selected file. Apply verifies
the digest and inode, publishes a no-overwrite backup before unlinking the old
name, and retains that backup. Stop concurrent installers first; this is not a
defense against an attacker controlling the parent directory. Interrupted backup
publication requires inspection, not an automatic overwrite. It does not uninstall
the Python distribution or install the C CLI; use the Conan installer afterwards.

## Failure Tests and Limits

- `journal_checkpoint`: byte-chunked anchored replay, endpoint/head mismatch,
  writer/inspector equality, and CRC-correct same-size modification during recovery.
- `journal_syscall_faults`: short writes, EINTR, partial EIO and fsync failure;
  no acknowledged checkpoint or second append after an uncertain commit.
- `recovery_publication_faults`: write, file/directory fsync and link failures;
  no completion marker after a failed component.
- `journal_inspect_cli`: missing export components, rewritten receipt, exact
  source preservation, chain verification and semantic replay.
- Existing daemon crash tests still kill the process during dispatch/recovery and
  require idempotent prefix repair without duplicate execution.
- CLI submission retries only pre-publication queue-lock contention with the
  same run identity, for at most 100 attempts separated by 10 ms. I/O and uncertain
  commit failures are never retried. Reader contention and persistent BUSY have
  integration tests verifying that no duplicate/partial job is published.

These tests model process/syscall failures. They do not reproduce SSD controller
failure, storage that lies about flushes, or every filesystem's power-loss ordering.
Do not label them a physical power-loss certification.

## Research and Design Rationale

- [Arpaci-Dusseau and Arpaci-Dusseau, OSTEP, Crash Consistency: FSCK and Journaling](https://pages.cs.wisc.edu/~remzi/OSTEP/file-journaling.pdf):
  distinguishes structural consistency from fully recovered user data. A valid
  journal prefix does not establish that an interrupted task finished or had no effects.
- [Pillai et al., All File Systems Are Not Created Equal, OSDI 2014](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-pillai.pdf):
  application update protocols depend on filesystem persistence guarantees.
  Golem retains explicit synchronization; neither unit tests nor fsync calls alone
  prove behavior under every storage device failure.
- [Schneier and Kelsey, Secure Audit Logs to Support Computer Forensics (1999)](https://www.schneier.com/academic/archives/1999/05/secure_audit_logs_to.html):
  distinguishes an untrusted logging machine from trusted verification. Golem
  uses an unkeyed commitment, not the paper's cryptographic forward-security scheme.
- [Mohan et al., Bounded Black-Box Crash Testing, OSDI 2018](https://www.usenix.org/conference/osdi18/presentation/mohan):
  motivates small deterministic failure cases. Byte-cut and syscall-fault tests
  here are narrower than filesystem power-loss testing and do not prove durability.
- [SQLite recovery documentation](https://www.sqlite.org/recovery.html):
  recovered data requires revalidation. Golem exports a separate verified prefix
  and makes lost bytes explicit instead of silently repairing evidence in place.
- [SQLite atomic commit](https://www.sqlite.org/atomiccommit.html):
  motivates preserving file/directory synchronization and distinguishing atomic
  visibility from durability; this is not an implementation of SQLite transactions.
- [Fowler, Event Sourcing](https://www.martinfowler.com/eaaDev/EventSourcing.html):
  replay and external effects must be separated. Historical evaluation does not
  rerun agents/tests; current freshness checks remain separate.
- [Kleppmann and Riccomini, Designing Data-Intensive Applications, Chapter 5](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch05.html):
  the publicly available encoding/evolution excerpt motivates explicit durable
  schema compatibility. Only the accessible excerpt was reviewed, not the full book.
- [Feathers, Working Effectively with Legacy Code](https://www.informit.com/store/working-effectively-with-legacy-code-9780132931779):
  the publisher's description and contents motivate regression tests before changes
  and isolated dependency tests. The complete book was not available for review.
- [Linux send(2)](https://man7.org/linux/man-pages/man2/send.2.html):
  documents closed/reset peer errors, distinct from a successful input delivery.

These sources inform engineering choices; they do not certify this implementation.
