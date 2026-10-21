# D6 Remote Gateway

D6 is an **opt-in, owner-launched TLS MCP resource server on one authoritative
host**, not an OAuth authorization server, transparent provider proxy, remote
filesystem writer or general agent daemon. It reuses D1 project/grant identity,
D2 scoped disclosure/context/handoff, D4 typed actions/receipts and D5 admission,
participation and uncertainty. D3 hooks remain local opt-in readers. Native core,
store formats and protected-file checks are unchanged.

## Independent Security Gates

| Gate | Authority |
| --- | --- |
| TLS endpoint and canonical Host/Origin | Reviewed gateway resource URL and certificate/key pins |
| Remote principal | Reviewed issuer/key set; verified access-token subject and OAuth client ID |
| Local project/Work permissions | Existing D1 binding, generation, identity/genesis and live grants |
| Remote disclosure | Separate D2 MODEL_SERVICE policy, data class and exact destination ID |
| Allowed remote tools | Delegate's explicit tool allowlist and token scopes |
| Native change / QA | Separate owner remote-mutation opt-in plus original D4 policy/action and native approval |
| Maintenance / uncertainty | Existing D5 fences and D4 durable intent; no remote clear/reconcile/admin tool |

An authenticated remote identity is mapped to an owner-approved local binding;
it does not turn LOCAL_COOPERATIVE into authenticated native approval or certify
the identity of a historical author/reviewer. ClientInfo, model text, headers,
paths, Work content and claimed recipients cannot select a different delegate.
Different remote subject/client pairs cannot share one local principal/client
identity. Resource-server authorization is not permission to approve QA.

## Token Profile and External Authorization Server

The owner selects an external authorization server and preregistered client.
D6 publishes the SDK's RFC 9728 protected-resource metadata and bearer challenge.
The external AS/client own authorization-code + PKCE, user authentication,
registration, refresh and consent UI. D6 neither implements these flows nor
claims that a particular Hosted product has completed them. There is no automatic
issuer discovery, dynamic registration or remote key fetch in the gateway.

Supported profile is deliberately narrow: RFC 9068-style signed access tokens,
`typ: at+jwt`, `alg: RS256`, an explicit known `kid`, 2048-8192-bit RSA keys, one
exact string issuer/audience, and required `sub`, `client_id`, `iat`, `nbf`, `exp`,
`jti`, `scope`. Integer dates and a maximum 30-300-second issued lifetime are
required; the owner chooses the maximum in policy. The audience is the canonical
HTTPS `/mcp` URL, not a provider API or an interchangeable list of resources.
`golem.read` is mandatory; native actions additionally require `golem.write`.
Unknown signing keys, HMAC/none, ID-token typing, duplicate JSON keys, remote key
URLs/critical header extensions, unapproved subject/client pairs and unsupported
confirmation-key profiles are rejected. No ID token or provider credential is
accepted as a substitute. Bearer tokens are never forwarded to native commands
or downstream services.

JWKS is a private pinned owner file containing only `keys` with public RSA
`kty/kid/alg/use/n/e` fields. Other vendor formats require explicit review and a
future adapter; there is no permissive fallback. Key rotation requires a new
reviewed policy and restart. Scope grants cannot expand the explicit local
tool/project/Work/disclosure intersection. Short-lived bearer tokens remain
replayable if stolen during their validity: D6 does not claim DPoP, mTLS client
binding, token theft immunity or authentication independent of the reviewed AS.

## Policy and Launch

```sh
python3 tools/integration_gateway_contract.py schema
python3 tools/integration_gateway_contract.py schema --kind revocations
python3 tools/integration_gateway_contract.py plan --input /private/gateway-input.json
```

The closed `golem.integration-gateway.v1` policy contains `issuer`, `resource`,
`jwks`, `tls_cert`, `tls_key`, `revocation_file`, exact allowed `origins`, bounded
`max_token_seconds`, `requests_per_minute`, `max_inflight`, `delegates` and producer
hashes. A delegate contains `delegate_id`, `subject`, `oauth_client_id`,
`destination_id`, pinned D2 `transfer_policy`, optional pinned D4 `mutation_policy`
and `tools`. A local-only disclosure policy is insufficient. D4's transfer pin
must exactly match the delegate's D2 policy. Existing D1/D2/D3/D4/D5 files are not
rewritten or silently refreshed by D6.

Review the canonical plan output, source and dependencies, exact destination,
allowed Works/tools, AS client configuration and TLS deployment. Save a private
0600 policy outside project roots and approve its digest separately. This is
owner administration, not a model-facing setup operation. Example paths below
are placeholders, not changes to an installed product:

```sh
python3 -m pip install -r tools/requirements-gateway.txt
python3 tools/integration_gateway.py --policy /private/gateway.json \
  --reviewed-policy-sha256 REVIEWED_SHA256 --approve-remote-gateway
```

Native changes are disabled unless a pinned D4 policy is included **and** the
owner supplies `--approve-remote-mutations`. This flag does not create actions,
approve native QA or execute anything at startup. D4 action IDs still fix exact
native bytes, session/owner/binding, sequence/source and any local decision.
No remote shell, arbitrary executable/path, owner approval, maintenance switch,
quarantine clearance, token issuance, migration or automatic Work resume tool is
exposed. TLS certificate and unencrypted private key must be pinned private
owner files; startup checks matching public keys and validity dates. Clients
must independently verify the endpoint's trusted chain and hostname. Test keys
are generated only in disposable fixtures and are never production trust roots.

Default listener is `127.0.0.1`. `--listen-host` is an explicit owner deployment
choice; nothing changes firewalls, DNS, public tunnels, client configuration or
global startup. The supported executable terminates TLS itself with proxy-header
trust disabled. HTTP reverse-proxy termination/header trust is **not supported**;
use a separately reviewed deployment or TLS passthrough. Do not expose the ASGI
object through a host that fabricates trusted HTTPS scope. Internet deployment
requires real certificates, network exposure review, AS/client setup and an
approved external smoke test beyond local TLS verification.

## HTTP and Disclosure Boundaries

The SDK supplies JSON-RPC and Streamable HTTP; D6 does not hand-roll MCP framing.
The gateway is stateless, with no session ID, resumable event store or shared
principal credential. Modern discovery and the 2025-11-25 handshake profile are
tested separately. Older HTTP+SSE and arbitrary protocol/client versions are not
claimed. GET may be refused with 405; it does not open an unsolicited SSE feed.

Every request passes exact Host and present-Origin checks, including metadata.
Wildcard origins, duplicate headers, cookies, query credentials, forwarded/
original proxy headers, content encoding, copied session IDs and Last-Event-ID
are rejected. Origin absence permits non-browser clients but never bypasses
authentication. No permissive CORS, redirects or implicit destination fetch is
added. Issuer/audience and local policy checks happen again inside tool handling
and before releasing buffered output. Revoked/expired authorization cannot release
a late successful response. D2 budgets, complete-input and freshness requirements
remain authoritative; no required context is truncated or treated as consumed
by the model merely because it was delivered.
Direct browser JavaScript preflight for the authenticated MCP endpoint is not a
supported client profile; no unauthenticated OPTIONS access is added. Hosted
server-to-server HTTP clients do not require that browser-specific permission.

Limits are per single gateway process: 16 KiB headers, 8 KiB bearer token,
256 KiB body/single strict JSON object, 5-second body deadline, 8 MiB buffered
response, at most eight active requests with no waiting queue, 240 total requests
per rolling minute and at most 120 per delegate (owner-configurable). Rejection
precedes backend admission; authentication attempts also consume the total rate
budget. SDK execution has a 900-second async deadline in addition to existing
bounded native subprocess limits. Cancellation/deadline is not proof that a
native effect stopped; existing D4 evidence remains authoritative. This is not
distributed rate limiting or protection from every network/OS-level denial of
service. The CLI also bounds Uvicorn connection admission and keepalive.

Default telemetry has no raw tokens, prompts, native document bodies, subject or
OAuth client identifiers. Private `remote-*` records retain only the delegate ID,
hashed token ID/arguments, tool, policy hash and result hash/local evidence ID.
D1/D2/D4 keep their original private evidence. Whole approved Work content may
itself contain secrets: disclosure consent is not automated redaction, a data-loss
prevention system or proof of safe cloud transmission. Do not enable debug/access
logging or external middleware that records bearer headers or bodies.

## Revocation, Update and Uncertainty

`golem.integration-remote-revocations.v1` is a private owner file with `epoch`,
`disabled`, `not_before`, `revoked_jtis` and `revoked_delegates`. Replace it
atomically under the same owner-private parent, with a strictly increasing epoch.
An unchanged epoch must retain identical bytes; regressions fail closed. Missing,
linked, corrupt or unsafe files block access. The epoch high-water mark is
process-local; after restart the owner must preserve the current revocation
file. This is not persistent anti-rollback attestation against a malicious local
administrator. `not_before` invalidates tokens issued earlier; `disabled` denies
all remote admission. Process-relative wall/monotonic regression also blocks auth.

Revocation stops subsequent admission and disclosure, **not an already admitted
native effect**. In-flight effects remain subject to original D4/C live policy
and approval guards. Do not claim instantaneous remote cancellation, retract a
delivered body, or rewrite a native result. A failed/disconnected response is
DELIVERY_UNCONFIRMED to its receiver; a preserved D4 result may be historical and
complete, or COMMIT_UNKNOWN if original native evidence was lost. Inspect the
original request/receipt without automatically retrying or substituting a new ID.
Known historical results are not current DONE; COMMIT_UNKNOWN remains uncertain.

Gateways with D4 authority hold D5 managed participation for their lifetime and
per-dispatch D4 writer descriptors. Stop all such gateways before D5 switch.
Freeze rejects new D4 work; no server PID is killed or force-taken. Resolve
uncertainty only through [D5's separate owner procedure](integration-d5.md), which
is intentionally unavailable remotely. Policy/producer/generation drift requires
new owner review. Restart/reload does not silently grant old policies a new D1
generation. Read-only gateways retain D2's read semantics and no native writes.

## Verification and Research

Install the optional dependencies, then run:

```sh
python3 tools/verify_gateway_schema.py
python3 -m unittest discover -s tools -p 'test_integration_gateway.py'
python3 tests/c/integration_d6_gateway.py build/asan/golem . \
  /usr/bin/cc build/asan/golem-integration-host
```

The native host must be built with `GOLEM_BUILD_INTEGRATION_HOST=ON`; it remains
optional/default-off for ordinary native consumers. D6 does not add HTTP/crypto
dependencies to the C library or dependency-free D1/D2 users. CI installs the
optional gateway requirements explicitly and runs actual TLS/native tests with
ASan/UBSan on macOS/Linux. Tests generate issuer keys, certificates and native
Works in private temporary directories. They include two clients/protocols,
scoped context/handoff, TLS trust refusal, HTTP challenges and hostile headers,
live revocation, native replay, D5 maintenance, lost committed native replies,
TLS request cancellation after a QA effect and pending-versus-approved QA.

These are real loopback TLS/MCP/native tests, **not an actual Hosted client or
external AS deployment**. Production ingress, real ChatGPT/Claude/Codex Hosted
activation, Windows, network filesystems, physical power loss and arbitrary
past engines are NOT_VERIFIED unless separately recorded. Native Works, TRAP,
CAS/journals/receipts and registered document revisions are not modified by
installation of this source implementation.

The [D6 research review](integration-layer-references.md#d6-remote-security-review)
maps MCP authorization/transports/security guidance, RFC 8725/9068/9700, PyJWT,
and existing least-privilege/complete-mediation literature to these decisions.
It is a bounded security design review, not a penetration-test certification or
proof of all Hosted interoperability.

Local macOS checks, 2026-10-21; remote CI remains a per-commit result:

| Gate | Observed result |
| --- | --- |
| Full Python regression with gateway dependencies | 593/593 PASS |
| D6 security unit cases, included above | 16/16 PASS |
| Independent D6 schema assertions | 55/55 PASS |
| Real loopback TLS/MCP/native D6, ASan/UBSan | 7/7 PASS |
| Real loopback TLS/MCP/native D6, Release | 7/7 PASS |
| Existing D1/D3/D4/D5 native CTest entries | 4/4 PASS |

The full local Python run uses a canonical Python 3.11 executable with the pinned
SDK import root: existing shell-script fixtures cannot execute a shebang whose
interpreter path contains spaces. Running directly through the SSD venv produced
five fixture ENOENT errors; those are not hidden or counted as a product PASS.
Fixtures were not altered to bypass any native guard. Physical power loss,
external ingress/AS and actual Hosted activation remain unverified.
