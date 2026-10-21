# D3 Opt-In Startup and Resume Hooks

D3 adds local command-hook adapters for **Codex CLI 0.141.0** and **Claude Code
2.1.196**, reusing unchanged [D1 approval](integration-d1.md) and
[D2 disclosure/service](integration-d2.md) contracts. It does not install itself,
modify a user's client settings, or introduce a new native execution path.

**Client conversation resume is not Golem Work resume.** The hook never calls
native start, claim, resume, heartbeat, begin, reconcile, submit, publish or
finalize. Existing core state, owner/sequence/binding/protected-file guards,
CAS, journal, receipts and registered document revisions remain authoritative.

## Support Matrix

| Surface | Implemented and exercised | Not inferred |
| --- | --- | --- |
| Codex CLI 0.141.0 | Real app-server, normal untrusted/trusted hook state, startup/resume, profile-change failure forwarded into a loopback model request | Desktop UI activation, cloud orchestration, every later Codex version |
| Claude Code 2.1.196 | Real CLI, disableAllHooks respected, startup/resume, profile-change failure forwarded into a loopback model request | Claude Desktop/ChatGPT hooks, remote Hosted sessions, every later Claude version |
| clear/compact | Explicitly selectable, native adapter fixtures, four-source Codex 0.141.0 declaration | Physical client compaction/clear end-to-end certification |
| Unsupported/changed client | Refuse unknown profile/version or changed executable; explicit D2 MCP remains available | Automatic update, downgrade or guessed compatibility |
| Platform | POSIX local host; macOS local verification and separate macOS/Linux CI gate | Windows native runtime or network filesystems |

The actual-client fixtures use isolated HOME/CODEX_HOME/CLAUDE_CONFIG_DIR,
synthetic disposable native Works, no real credentials and a **loopback-only
synthetic provider**. They inspect the next outgoing request for the notice;
they do not contact a paid model or prove model understanding. Synthetic usage
numbers are not provider usage or billing evidence.

Current official documentation describes more capabilities than these pinned
versions. D3 does not emit Claude's newer onFailure, resume-cost, initial-message
or skill-reload fields, or Codex mcp_tool hook handlers. No trust/permission
bypass flag is generated. A version string is a compatibility declaration, not
publisher authentication; the owner also pins the exact executable bytes.

## Delivery Boundary

SessionStart additionalContext is a privileged context channel: Codex treats it
as extra developer context and Claude places it in a system reminder. D3 does
**not** copy arbitrary Work documents, judgment prose, CLI stderr, transcript
contents, owner tokens or embedded instructions into that channel.

The hook runs the existing complete D2 context validation privately and emits a
bounded **SCOPED_MCP_NOTICE** containing only:

- Explicit project/Work IDs and native sequence.
- Allowlisted native resume reason, next-operation label and boolean flags.
- Native projection digest and Work-record observation digest.
- Owner-selected MCP server name, `golem_context_get` and the exact D2 query args.
- READING_AID, no execution authority, no complete-context delivery, unknown
  provider budget and unobserved MCP connection/model consumption.

The host/agent can then explicitly retrieve the full context using D2's ordinary
MCP tool result channel. A reference is **not** complete execution input. This
hook does not silently invoke a model, launch an MCP server, assert that a server
is connected, or claim that the model fetched/understood the context. No generic
memory DB or conversation-history scanner is added.

Notice text is limited to **2,000 UTF-8 bytes**, including maximum-length scoped
IDs. It is never truncated. This keeps the factual notice small rather than
disabling a client's spill safeguards for a full document bundle. The installed
client fixtures verify actual notice forwarding; this byte cap is not a provider
token-count proof. Large original sources stay behind the existing D2 limits.

## Owner Setup

1. Retain a current D1 enrollment for the selected project, Work and client.
2. Retain a separately reviewed D2 transfer policy with `MODEL_SERVICE`
   destination and both `work_inspect` and `context_get` allowed. Native D1
   record/status/next permissions are all required. LOCAL_HOST alone is not
   upgraded to automatic model-visible disclosure.
3. Select one explicit Work/context query and one client. Do not infer a Work
   from cwd, recency, conversation text or a transcript file.
4. Build and review a D3 profile, generate its fragment, then explicitly merge
   that fragment into the intended client's settings. Preserve all existing
   settings and other hook entries. Do not combine multiple matching fragments
   accidentally: clients may run every matching hook.

The implementation is stdlib-only and needs Python 3.11+; it reuses D2's domain
service directly, without importing the optional MCP transport SDK.

```sh
python3 tools/integration_hook_contract.py schema
python3 tools/integration_hook_contract.py pin --input /canonical/native-client
python3 tools/integration_hook_contract.py pin --input /canonical/python3.11
```

Paths above are placeholders. `pin` streams an executable of at most 512 MiB,
checks canonical path/regular-file identity and metadata stability, and rejects
symlinks and multi-link files. Installed native client binaries can exceed D1's
128 MiB data-file limit; D3 does **not** raise that D1 limit. Resolve a launcher
symlink explicitly before selecting a pin. Node/shell wrappers with unpinned
interpreter/dependency resolution are not certified by the native-client tests.

Some Claude installations hardlink their binary. Do not remove links, rewrite
the installed file or relax the pin check. An owner can separately stage/review
a single-link immutable client snapshot and use that pinned binary. The actual
Claude fixture does this only inside its disposable test directory; it never
changes the installed binary. Interpreter pins also require a canonical
single-link executable, matching the interpreter that runs the hook.

Profile draft (all paths, IDs and digest placeholders must be replaced):

```json
{
  "schema": "golem.integration-hook-profile.v1",
  "client": "codex-cli",
  "client_version": "0.141.0",
  "client_pin": {"path": "/private/reviewed-codex", "sha256": "REPLACE"},
  "python_pin": {"path": "/private/reviewed-python", "sha256": "REPLACE"},
  "transfer_policy": {"path": "/private/d2-transfer.json", "sha256": "REPLACE"},
  "context": {
    "project_id": "project", "work_id": "work", "selection_id": "selection",
    "source_snapshot": "REPLACE", "target_kind": "planning", "recipe": "current-v1"
  },
  "sources": ["startup", "resume"],
  "mcp_server": "golem",
  "delivery": "SCOPED_MCP_NOTICE",
  "producer": {}
}
```

For Claude use `client: claude-code`, `client_version: 2.1.196` and its reviewed
native binary. Use the existing exact D2 context request: D3 does not pick a
new selection/source/target automatically when an old query becomes stale.
The original policy bytes/hash, generation and scope remain subject to D1/D2.

```sh
python3 tools/integration_hook_contract.py plan --input /private/hook-draft.json
```

This fills the ten D1/D2/D3 producer hashes, validates the closed profile and
probes only the selected binary's `--version`. That probe uses the existing
recorder with a five-second/8-KiB bound, an isolated HOME and minimal environment,
never the real client home or a project cwd. Its private `read-hook-probe-*`
record and stdout/stderr remain under the approved registry, including failures;
it does not enable hooks or modify client configuration. Retain the plan output
as a private 0600 single-link profile outside the enrolled project, review its
exact bytes and compute its file SHA-256.

```sh
python3 tools/integration_hook_contract.py check \
  --profile /private/reviewed-hook.json --reviewed-profile-sha256 REVIEWED_SHA256 \
  --approve-hooks
python3 tools/integration_hook_contract.py fragment \
  --profile /private/reviewed-hook.json --reviewed-profile-sha256 REVIEWED_SHA256 \
  --approve-hooks
```

`check` reports CONFIGURATION_CHECKED and client_activation NOT_OBSERVED, not
native QA, connected MCP or active client installation. The fragment uses
absolute, POSIX-shell-quoted interpreter/script/profile paths, the exact reviewed
profile hash, a source matcher and a synchronous command with a 240-second host
timeout. It contains no arbitrary model-supplied argv or administrative tool.

For Codex, merge the `hooks` fragment into the chosen hooks.json next to its
active config layer. Review and trust the exact handler through the client's
normal `/hooks` workflow; project-local config also needs project trust. Do not
auto-seed trust from this integration or use a bypass flag. Global/managed policy
may disable hooks and remains authoritative. The fixture's temporary trust state
is a test-only owner approval of the generated command/hash, not a production
trust installer or a test of the interactive trust UI.

For Claude Code, merge into the deliberately selected settings JSON or pass a
reviewed file through `--settings`. Do not overwrite unrelated keys/hooks, flip
disableAllHooks or managed restrictions, write CLAUDE_ENV_FILE or request a model
turn through hook output. Existing project/profile setup remains separate.

## Runtime and Failure Contract

`tools/integration_hooks.py` accepts only its owner-reviewed profile arguments
and one bounded SessionStart JSON event on stdin. `session_id` is a bounded host
label whose hash is recorded for correlation, not native owner authentication.
The script never opens transcript_path. Extra host metadata is bounded and
ignored; it cannot replace profile identity, project, Work, source or authority.

The event cwd must exactly equal the registered canonical project root. A
subdirectory, nested repository, alias or different project is not automatically
enrolled or selected. Unsupported source/event, stale policy/generation,
changed executable/interpreter/module, missing/corrupt evidence and unsafe roots
produce an explicit advisory BLOCKED notice.

Runtime order:

1. Verify private profile/exact hash, producer/interpreter/client pins and D2
   disclosure. Reauthorize D1 record/status/next for the fixed Work.
2. Validate event source/cwd/session metadata; do not accept event-supplied grants.
3. Use D2 work_inspect status/next and require matching sequence. Preserve only
   the allowlisted preflight facts for the notice.
4. Use D2 context_get, retaining its complete-source/freshness/digest checks.
   Require the sequence still matches the initial preflight. Never retry on drift.
5. Recheck profile and transfer bytes; prepare bounded notice and private audit.
   Emit the client-compatible hookSpecificOutput JSON.

Audit files live only under new private `read-hook-*` directories in the D1
registry, separately from native evidence. They record profile/event hashes,
prepared output and OUTPUT_PREPARED with host delivery NOT_OBSERVED. Successful
stdout emission does not prove that a client accepted output. Candidate/raw native
logs remain in D2's private spool; raw host transcripts are not collected.
Existing D1 audit admission limits still apply and may block frequent hooks. No
automatic pruning or deletion of evidence, pending output or failed records occurs.

Each native child retains D1's 15-second limit and minimal environment; a hook can
perform several reads (up to eleven native invocations in the normal path).
Client cancellation/timeout can discard output and must not be treated as a
successful delivery. Native reads cannot be converted into a write to fix it.

Failure returns a well-formed additionalContext notice plus systemMessage with
an error code/recovery label. Exit **0 means advisory output was formed**, not
that context, execution or product QA passed. Owner `check/plan` failures exit
nonzero. Hook failure is not a global permission gate: clients can continue a
conversation when a hook is disabled, untrusted, absent, timed out or broken.
The unchanged native core still decides whether later operations are valid.

| Condition | Advisory recovery, never automatic |
| --- | --- |
| Profile/policy/client/SDK pin changed | Review new bytes and owner approvals, then client reload/trust as needed |
| Unsupported client version or unavailable hook | Use explicit D2 MCP, review a separately tested adapter profile |
| Wrong cwd, source not opted in | Start at approved root or review explicit source selection |
| Native source/selection/sequence changed | Read current native state and review the exact D2 context request |
| Live other owner or unknown RUNNING effects | Native preflight, WAIT/recovery investigation; no takeover/reexecution |
| Boot/clock/expired lease | Original native next-operation label; no implicit resume/reconcile |
| DONE | Native DONE information remains DONE, no cleanup resume |
| Corrupt state, policy denial or audit capacity | Preserve evidence and inspect locally; no repair, fallback PASS or retry |

Removing the selected handler opts out. Changing/deleting the private profile or
revoking D1/D2 blocks future reads; already emitted host context cannot be recalled.
Do not delete native CAS/journal/receipts when disabling this adapter. Updates
require new reviewed pins/profile/fragment, not an automatic Work migration.

## Verification

- `tools/test_integration_hooks.py`: closed schema, private/pinned input,
  destination consent, no event-based authority, maximum notice size, failure
  diagnostics, preflight, no document injection and no retry.
- `tools/verify_hook_schema.py`: optional independent Draft 2020-12 validator;
  no client/native execution.
- CTest `integration_startup_hooks`: real native disposable Work, four source
  events, stale context, revocation, live foreign owner, corrupt CAS, concurrency
  and full Work file bytes/modes/addition/deletion checks.
- `tests/c/integration_d3_hooks.py CLI SOURCE --codex-client BINARY --claude-client
  BINARY`: actual pinned clients with isolated homes and local synthetic requests;
  untrusted/disabled behavior, startup, resume and profile-change failure.
  CI installs exact official client versions into a temporary prefix, not globally.

These are distinct evidence levels. Direct hook invocation does not certify an
actual host event; model-request capture does not certify UI rendering, model
understanding, a real Hosted provider, physical reboot or all client releases.
No existing product Work, TRAP install, migration, VM or UACTT is used.

Source/support review: [D3 references](integration-layer-references.md#d3-client-hook-support-review).

### Local Review Record

2026-10-21, macOS, disposable stores and isolated client homes:

| Gate | Observed result |
| --- | --- |
| Full Python regression, including execution-boundary coverage | 535/535 PASS |
| D3 focused profile/domain tests, included above | 14/14 PASS |
| Native D3 plus both real pinned CLI lifecycle fixtures, ASan/UBSan binary | 7/7 PASS |
| Related D1/D3/session/binding/execution/completion/context CTests | 8/8 PASS |
| Independent D3 JSON Schema assertions | 40/40 PASS |

An initial regression correctly rejected an unrecorded version subprocess. The
probe was routed through the existing recorder with bounded output and retained
evidence; no bypass allowlist was added. The installed Claude hardlink remained
unchanged, and its fixture used only a temporary single-link snapshot.

Native gates ran on the host because the managed sandbox cannot exercise all
boot-identity paths. CI independently runs native and actual-client fixtures on
macOS/Linux; final per-revision results are recorded in GitHub Actions, not
inferred from this local record. No real client setting/trust, real provider
session, TRAP installation or existing Work was modified.
