#ifndef GOLEM_ADAPTER_PROTOCOL_H
#define GOLEM_ADAPTER_PROTOCOL_H

#include "golem/core.h"
#include "golem/policy.h"
#include "golem/cost.h"
#include "golem/evidence.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_ADAPTER_VERSION 1
#define GOLEM_ADAPTER_ID_CAPACITY 96
#define GOLEM_ADAPTER_JSON_MAX 16384
#define GOLEM_ADAPTER_MSGPACK_MAX 4096
#define GOLEM_ADAPTER_ALL_STAGES ((1u << GOLEM_STAGE_COUNT) - 1u)
typedef struct golem_adapter golem_adapter;
typedef struct golem_adapter_capability {
    uint32_t version;
    char adapter_id[GOLEM_ADAPTER_ID_CAPACITY];
    uint32_t stages;
    golem_effect effect;
    bool simulation;
} golem_adapter_capability;
typedef struct golem_adapter_request {
    uint32_t version;
    char request_id[GOLEM_ADAPTER_ID_CAPACITY];
    char run_id[GOLEM_ADAPTER_ID_CAPACITY];
    char adapter_id[GOLEM_ADAPTER_ID_CAPACITY];
    golem_stage stage;
    uint64_t sequence;
    uint32_t attempt;
    golem_receipt context;
    bool has_predecessor;
    golem_digest predecessor;
} golem_adapter_request;
typedef struct golem_adapter_result {
    golem_adapter_request request; /* Exact request binding, copied by value. */
    golem_stage_status outcome;
    golem_failure failure;
    bool simulation;
    golem_receipt evidence;
    golem_cost_amount usage;
} golem_adapter_result;
typedef enum golem_adapter_message {
    GOLEM_ADAPTER_CAPABILITY = 1, GOLEM_ADAPTER_RUN_STAGE, GOLEM_ADAPTER_STAGE_RESULT
} golem_adapter_message;
typedef struct golem_adapter_envelope {
    golem_adapter_message type;
    union {
        golem_adapter_capability capability;
        golem_adapter_request request;
        golem_adapter_result result;
    } data;
} golem_adapter_envelope;
/* Trusted in-process implementation callbacks, not a sandbox or dynamic loader.
 * probe must be side-effect free. Both callbacks borrow context for the call;
 * the context must outlive adapter free. Do not reenter/mutate the WorkRun from
 * callbacks. A callback failure may still have caused external effects. */
typedef struct golem_adapter_ops {
    golem_status (*probe)(void *context, golem_adapter_capability *out, golem_diagnostic *diagnostic);
    golem_status (*run_stage)(void *context, const golem_adapter_request *request,
        golem_evidence_store *store, golem_adapter_result *out, golem_diagnostic *diagnostic);
} golem_adapter_ops;

/* Inputs borrowed for call, value outputs independent copies; no aliasing.
 * Errors preserve outputs except diagnostic and required on BUFFER_TOO_SMALL.
 * IDs use 1..95 ASCII letters/digits/underscore/dot/colon/hyphen. No commands,
 * credentials or raw prompts in envelopes: context is a CAS receipt.
 * Native structs are NOT wire formats. Caller serializes adapter/run access. */
golem_status golem_adapter_create(const golem_adapter_ops *ops, void *context,
    const golem_allocator *allocator, golem_adapter **out);
/* Copies ops/allocator, BORROWS context. Free releases only adapter; NULL no-op. */
void golem_adapter_free(golem_adapter *adapter);
golem_status golem_adapter_probe(const golem_adapter *adapter,
    golem_adapter_capability *out, golem_diagnostic *diagnostic);
/* RUNNING attempt only, after normal/optimized admission. Copies IDs and receipt;
 * no CAS verification yet. NULL predecessor means none (zero digest in output). */
golem_status golem_adapter_request_init(const golem_work_run *run, const char *adapter_id,
    const char *request_id, const golem_receipt *context, const golem_digest *predecessor,
    golem_adapter_request *out);
/* Pure structural/identity validation; does not authenticate producer or verify CAS. */
golem_status golem_adapter_result_validate(const golem_adapter_request *request,
    const golem_adapter_result *result);
/* Checks RUNNING identity, probe/stage/effect, input CAS and predecessor before
 * calling run_stage. Capability effects cannot exceed the admitted effect.
 * Optimized starts additionally bind adapter_id to the selected route ID and
 * bind context/predecessor digests to the admitted optimization context. Hosts
 * register route-specific adapter handles with that ID (portable ASCII above).
 * One invocation per StageRun; after callback entry the dispatch slot is consumed
 * even on callback/result/evidence error, because effects may already have occurred.
 * Preflight errors do not consume it.
 * Lease-bound runtime runs also check ownership before/after callbacks and
 * before returning results. Stale ownership preserves out; effects/CAS writes
 * may remain and require reconciliation, never automatic redispatch.
 * Does not finish Core, settle costs, approve acceptance or launch a subprocess.
 * Returned evidence is CAS verified.
 * Replayed RUNNING attempts cannot dispatch: reconcile instead. Dispatch markers
 * are in-memory only; journal v1 does not provide exactly-once execution. */
golem_status golem_adapter_dispatch(golem_adapter *adapter, golem_work_run *run,
    const golem_adapter_request *request, golem_evidence_store *store,
    golem_adapter_result *out, golem_diagnostic *diagnostic);

/* JSON v1: one flat object, all field VALUES are strings. uint64 values use
 * canonical decimal strings (no leading zeros), avoiding JSON number precision
 * loss. Unknown/duplicate/missing keys, embedded NUL, invalid UTF-8, nested values,
 * trailing documents and oversized input are rejected. Whitespace/key order are
 * accepted. Encode required includes NUL; decode bytes exclude trailing NUL.
 * Codec uses bounded-depth json-c allocations, not the owner allocator. */
golem_status golem_adapter_envelope_encode(const golem_adapter_envelope *envelope,
    char *buffer, size_t capacity, size_t *required, golem_diagnostic *diagnostic);
golem_status golem_adapter_envelope_decode(golem_bytes bytes,
    golem_adapter_envelope *out, golem_diagnostic *diagnostic);

/* MessagePack v1 compact profile: flat map with stable unsigned integer keys,
 * unsigned integer values, native booleans, ASCII ID strings, and bin digests.
 * Same value schema/validation as JSON. No heap allocation or recursion.
 * Encode uses ascending keys/minimal widths; required is BYTES, without NUL.
 * Decode accepts map/key order and wider unsigned/length encodings, but rejects
 * duplicate/unknown/missing keys, signed numbers, nested values, trailing bytes,
 * type coercion and input above MSGPACK_MAX. Native structs are never serialized.
 * Caller owns all buffers; short buffer changes only required, other errors
 * preserve outputs. Decoder returns independent copies, not borrowed views. */
golem_status golem_adapter_msgpack_encode(const golem_adapter_envelope *envelope,
    void *buffer, size_t capacity, size_t *required, golem_diagnostic *diagnostic);
golem_status golem_adapter_msgpack_decode(golem_bytes bytes,
    golem_adapter_envelope *out, golem_diagnostic *diagnostic);

golem_status golem_adapter_noop_create(const golem_allocator *allocator, golem_adapter **out);
/* Leaf worker for standalone JSON transport, NOT an authorization API. Verifies
 * input CAS, writes deterministic simulation evidence, returns known-zero usage.
 * Always simulation=true; never finishes a WorkRun or attests task acceptance.
 * CAS effects may remain after failure. Runtime callers use dispatch above. */
golem_status golem_adapter_noop_run_stage(const golem_adapter_request *request,
    golem_evidence_store *store, golem_adapter_result *out, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif

#endif
