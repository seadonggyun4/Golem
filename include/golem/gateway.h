#ifndef GOLEM_GATEWAY_H
#define GOLEM_GATEWAY_H
#include "golem/adapter_protocol.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_GATEWAY_VERSION 1
typedef enum golem_envelope_encoding {
    GOLEM_ENCODING_JSON = 1, GOLEM_ENCODING_MSGPACK = 2
} golem_envelope_encoding;
typedef enum golem_signature_scheme {
    GOLEM_SIGNATURE_NONE = 0,
    GOLEM_SIGNATURE_ED25519_RESERVED = 1 /* NOT implemented or accepted. */
} golem_signature_scheme;
typedef enum golem_gateway_trust {
    GOLEM_GATEWAY_REQUIRE_SIGNATURE = 0, /* Fail closed when zero-initialized. */
    GOLEM_GATEWAY_ALLOW_UNSIGNED_LOCAL = 1
} golem_gateway_trust;
/* In-memory gateway preparation contract, NOT a serialized frame or trust token.
 * Payload/signature are borrowed; the caller keeps storage alive and immutable.
 * payload_digest hashes EXACT payload bytes, not canonicalized values. It is
 * integrity metadata, not authentication, and does not authenticate this header.
 * Signature fields are reserved, must be empty/NONE in this implementation.
 * No verified flag can be supplied by a peer. Future signed framing needs a
 * domain-separated transcript binding version, encoding, identity and freshness. */
typedef struct golem_gateway_envelope {
    uint32_t version;
    golem_envelope_encoding encoding;
    golem_bytes payload;
    golem_digest payload_digest;
    golem_signature_scheme signature_scheme;
    char key_id[GOLEM_ADAPTER_ID_CAPACITY];
    golem_bytes signature;
} golem_gateway_envelope;
/* Validates one adapter payload and returns an UNSIGNED wrapper borrowing bytes.
 * No input ownership transfer. Value output unchanged on error; diagnostic may
 * change. JSON may allocate internally; MessagePack decoding does not. */
golem_status golem_gateway_envelope_prepare(golem_envelope_encoding encoding,
    golem_bytes payload, golem_gateway_envelope *out, golem_diagnostic *diagnostic);
/* Explicit opt-in to unsigned local decoding: ALLOW_UNSIGNED_LOCAL.
 * REQUIRE_SIGNATURE ALWAYS returns POLICY_DENIED until a trusted verifier exists.
 * Any signature/key/algorithm claim is rejected, even in unsigned mode.
 * Verifies payload digest and schema, then returns an independent value copy.
 * Never authorizes/dispatches work or verifies CAS references/provenance. No
 * enrollment, replay defense, key trust, socket gateway or signing is implied. */
golem_status golem_gateway_envelope_decode(const golem_gateway_envelope *envelope,
    golem_gateway_trust trust, golem_adapter_envelope *out, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
