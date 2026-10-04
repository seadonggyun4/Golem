# CLI failure diagnostics

The CLI appends one `golem.cli-error.v1` JSON record to stderr when command
dispatch returns nonzero. Existing human messages and domain error records stay
intact. Consumers must select JSON lines by schema, not parse all stderr as one
JSON document. Successful stdout protocols and existing exit codes are unchanged,
except that an otherwise silent stdout flush failure now returns 1.

## Contract

- `code`: stable native enum name, `CLI_USAGE`, or `CLI_FAILED` when native status
  is unavailable. All current nonzero public statuses have centralized mappings.
- `status_code`: native numeric status or null; distinct from process `exit_code`.
- `command`: allowlisted command family, `unknown`, or `cli` before dispatch.
- `phase`: recorded boundary, not a claim about the ultimate root cause.
- `message`: human summary; do not branch on this text.
- `errno`: captured OS error where instrumented, otherwise null. Never infer it
  from a later cleanup operation or from a diagnostic message string.
- `system_errors`, `system_errors_omitted`, `system_errors_role`: bounded native
  observations, explicitly distinct from inferred causes. See
  [scoped system errors](system-errors.md) for C API, fields and coverage.
- Optional `diagnostic`, `diagnostic_truncated`, and `offset`: original typed
  diagnostic, when available. Original stderr remains the detailed evidence.
- `category` and `next_action`: conservative recovery guidance, not authorization.
- `retry_effect: false`, `execution_authorized: false`, and
  `effects: "NOT_INFERRED_FROM_EXIT_STATUS"`: failure does not prove that no
  mutation occurred. Inspect state and reconcile before repeating effects.

Allocation/serialization failure produces a smaller `CLI_DIAGNOSTIC_UNAVAILABLE`
record containing schema, code, exit_code, retry_effect, execution_authorized.
Consumers must tolerate this reduced shape and unknown future codes/fields.

The context is private to the single CLI invocation, not a thread-safe library
last-error API. Register new native statuses in `src/cli/error.c`; the catalog
test checks public enum coverage. Call `cli_error_note` at terminal failure
boundaries and `cli_error_errno` immediately after a failing OS operation.
Do not note recoverable warnings. A same-status terminal emitter retains the
earlier failure context; reset the context before starting an independent command.

## Boundaries and compatibility

This is additive unification, not removal of session/host/Work error schemas.
Programs expecting exactly one stderr JSON object must migrate to schema-based
line selection. Successful cache fallback remains a warning, not a failure.
QA FAIL and BLOCKED domain results with successful transport are not converted
into CLI failures. No automatic retry, policy bypass, or state repair is added.

Normal return paths share the envelope. Signals, crashes, forced termination,
and unwritable stderr cannot guarantee delivery. Detailed errno instrumentation
now also covers shared evidence, document, journal and daemon storage, boot
identity, host transport, process supervision and parent-side resource-control
boundaries, not every library syscall. Cleanup observations do not replace the
terminal status, and child exit codes do not identify an unobserved child syscall.
See the [coverage and ownership contracts](system-errors.md). Unknown
information is left unknown. Existing diagnostic text is not
a new redaction boundary; treat raw logs according to their existing sensitivity.

## Research and design decisions

These are selected sections read for design, not claims of exhaustive book
review or proof that published failure statistics apply to Golem.

| Primary reference | Applied decision | Limit |
| --- | --- | --- |
| [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html), sections 3.1, 3.2, 5 | Stable machine identity separate from human detail; extensible fields; avoid reflecting arbitrary argv | CLI JSON is not an HTTP Problem Details implementation |
| [Yuan et al., OSDI 2014](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-yuan.pdf), sections 4.1-4.2 | Exercise explicit error handlers, including failure of diagnostic construction | Tests do not establish absence of all faults |
| [Beyer et al., Site Reliability Engineering, Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/) (2016) | Preserve observations; separate evidence from causal diagnosis; recovery guidance without unsupported certainty | No claim of root-cause identification from an exit code |
| [Lamport, Specifying Systems](https://lamport.azurewebsites.net/tla/book-02-02-27.pdf), section 7.3 (Addison-Wesley, 2002) | Distinguish command completion, effect completion, and reporting failure instead of treating them as one atomic event | Design reasoning only; no new formal model or proof |

## Verification

`cli_error_contract` exercises native status coverage, unknown status, allocation
failure fallback, context reset, JSON escaping, usage boundaries, request open
failure, stdout failure, and successful silence. Existing CLI integration suites
remain necessary to check domain behavior. Host-only clock/socket tests must be
reported separately from restricted-environment diagnostic checks.
