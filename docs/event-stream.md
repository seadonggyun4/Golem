# Read-only Event Stream

The optional `golem-events` process serves **derived admission diagnostics**, not
execution commands, approval endpoints or completion evidence. It does not create
a Work, take a lease, acquire a writer lock or modify the admission journal.

## Build and Run

Install libevent development headers (`libevent-dev` on Debian/Ubuntu, `libevent`
with Homebrew). The default library and CLI build do not depend on libevent.

```sh
cmake -S . -B build/events -G Ninja -DCMAKE_BUILD_TYPE=Release -DGOLEM_BUILD_EVENT_BRIDGE=ON
cmake --build build/events
umask 077
openssl rand -hex 32 > /private/path/golem-observer.token
build/events/golem-events /absolute/existing/admission /private/path/golem-observer.token 8087
```

The directory is an existing **admission journal directory**, the same source
used by `golem events DIR --jsonl`, not an arbitrary Work directory. Port `0`
chooses an available port and prints the loopback URL. A private token file must
be a regular, nonsymlink file owned by the current user, with no group/other
permissions, containing 64 lowercase hexadecimal characters and an optional LF.
Do not commit the token or copy it into agent prompts, query parameters or logs.

Only `GET /events` is supported. The client supplies:

- `Host: 127.0.0.1:PORT`, matching the printed address exactly.
- `Authorization: Bearer TOKEN`, loaded from the private file by a trusted client.
- Optional `Last-Event-ID: CURSOR` from the last complete event it accepted.

All browser `Origin` headers are rejected; no CORS is enabled. Native browser
EventSource does not expose arbitrary authorization headers. This bridge targets
trusted CLI/host clients, not direct cross-origin browser access. There is no UI,
remote bind flag, TLS termination, Unix socket transport or proxy trust mode.
Do not expose this plaintext loopback service through a public proxy.

Token deletion, permission change or content rotation closes active streams at
the next poll and makes the service unavailable. Restart with the new token.
Loopback plus a token is not protection against malicious same-UID processes able
to read that file or inspect the process. A separate OS principal is needed for
that threat model.

## Frames and Reconnects

The response uses `text/event-stream`, `Cache-Control: no-store`, and fixed
allowlisted event data. No prompts, paths, source text, stdout, credentials,
agent names or approval tokens are exported. Hashes and numeric IDs are still
linkable information and are not claimed to be anonymous.

```text
id: 1:STREAM_DIGEST:SEQUENCE:ANCHOR_DIGEST
event: queued
data: {"version":1,"origin":1,"subject":"3","epoch":"1","status_known":false,"status":0,"elapsed_known":false,"elapsed_ns":"0"}

```

The existing versioned cursor is reused without format changes. Stream digest
identifies the durable journal; epoch is an event field, not a new cursor UUID.
Unsigned 64-bit values in SSE data are decimal strings to avoid JavaScript
precision loss. SSE names and JSON are generated from fixed enums/numeric fields,
so untrusted strings cannot inject `id`, `event` or newlines. Each frame ends in
a blank line. Heartbeat comments every five seconds do not advance the cursor.

At connection start, an unnumbered `source` frame explicitly reports
`transient_worker_gap: true`. Worker-pool observations are in-memory only and
cannot be recovered through this journal bridge. Reconnection does not invent
those missing events or treat gaps as Work completion.

Clients retain the cursor only after a complete frame and reconnect with
`Last-Event-ID`. Delivery can duplicate around disconnects; deduplicate by the
entire cursor. Do not compare sequence values from different streams.

| Response | Meaning |
| --- | --- |
| 400 | Malformed cursor, unsupported path/query/method or body |
| 401 / 403 | Missing/invalid read token, Host or Origin violation |
| 409 | Cross-stream, forged-anchor or future cursor |
| 410 | Cursor outside retained window; explicit gap acknowledgement required |
| 503 | Subscriber limit, source unavailable or revoked credential |

The retained view has 256 records. Without a cursor the caller explicitly starts
at the oldest retained record. On 410, reconcile with the authoritative journal
and only then deliberately restart without a cursor. Do not silently drop a
saved cursor. During an active stream, source faults or retention loss emit a
best-effort unnumbered `gap` and end the stream. On a stalled socket even a gap
cannot be guaranteed to arrive; EOF is not success. Reconnect from the last
**client-received** cursor, not a server enqueue position.

## Resource and Ownership Contract

- Maximum 32 active subscriptions; further subscribers receive 503.
- Each connection has at most 64 KiB queued userspace output including framing
  reserve. Four consecutive failed enqueue attempts close a slow subscriber.
  No producer or writer waits on an observer.
- Each poll refreshes one shared view, then copies at most 64 events per client.
  Refresh interval is 250 ms; each subscriber maintains its own cursor.
- Header limit is 4 KiB, request bodies are disallowed and HTTP I/O timeout is
  ten seconds. The standalone process caps its soft FD limit at 128, including
  unauthenticated connections. Kernel socket buffers are additional bounded
  OS resources; the userspace limit is not a whole-process RSS claim.
- Full-prefix journal verification is O(journal length) per refresh. It runs in
  the separate observation process. This is not an incremental index or a hard
  latency guarantee on slow disks. Source errors fail closed rather than serving
  stale snapshots as fresh.

The reusable C reader is `golem/event_reader.h`: open pins a read-only directory,
refresh verifies a new prefix against the previous checkpoint, read copies a
bounded in-memory page and close frees the handle. Use one caller at a time.
The supplied allocator is copied. No caller buffers are retained. On failed
refresh reads fail until a successful refresh; journal truncation/replacement is
rejected. The SSE encoder uses caller-owned buffers and supports a sizing call.

## Tests and References

```sh
ctest --test-dir build/events --output-on-failure -R 'event_reader|event_bridge|runtime_events|mutation_document'
```

The HTTP tests exercise real loopback sockets, reconnect and restart, source
immutability, cursor gaps, auth rejection, subscriber admission, connection churn,
heartbeat and credential revocation. They do not prove production traffic capacity.
`.github/workflows/observation.yml` enables the optional target under sanitizers
on Linux and macOS; a local macOS run is not a remote Linux CI pass.

- [WHATWG SSE](https://html.spec.whatwg.org/multipage/server-sent-events.html):
  frame termination, comment heartbeats and Last-Event-ID behavior.
- [libevent HTTP server manual](https://libevent.org/libevent-book/Ref10_http_server.html):
  use its HTTP parser and streaming responses rather than a custom parser.
- [Welsh, Culler, Brewer, SEDA, SOSP 2001](https://people.eecs.berkeley.edu/~prabal/teaching/resources/eecs582/welsh01seda.pdf):
  explicit queues and overload control motivate bounded observation, without
  adopting SEDA's entire adaptive runtime or claiming its benchmark results.
- [Anderson, Security Engineering, third edition, chapter 6](https://www.cl.cam.ac.uk/archive/rja14/Papers/SEv3-ch06.pdf):
  distinguish read authorization from OS protection boundaries.
- [Kleppmann, Designing Data-Intensive Applications, chapter 11](https://www.oreilly.com/library/view/designing-data-intensive-applications/9781491903063/ch11.html):
  publisher chapter preview identifies logs, streams and fault tolerance as
  relevant background. The preview is not treated as access to the full chapter.
