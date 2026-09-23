#ifndef GOLEM_ADAPTER_DESCRIPTOR_H
#define GOLEM_ADAPTER_DESCRIPTOR_H
#include "golem/adapter_protocol.h"
#include "golem/supervisor.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_DESCRIPTOR_VERSION 1u
#define GOLEM_DESCRIPTOR_MAX_BYTES 16384u
#define GOLEM_DESCRIPTOR_MAX_TOOLS 64u
#define GOLEM_HARNESS_RESUME 1u
#define GOLEM_HARNESS_CANCEL 2u
#define GOLEM_HARNESS_STREAM 4u
#define GOLEM_HARNESS_ALL_FEATURES 7u
#define GOLEM_INPUT_JSON 1u
#define GOLEM_INPUT_MSGPACK 2u
#define GOLEM_INPUT_MARKDOWN 4u
#define GOLEM_INPUT_CONTEXT_REF 8u
#define GOLEM_INPUT_ALL 15u
typedef enum golem_harness_truth {
    GOLEM_HARNESS_UNKNOWN = 0,
    GOLEM_HARNESS_NO = 1,
    GOLEM_HARNESS_YES = 2
} golem_harness_truth;
typedef enum golem_harness_sandbox {
    GOLEM_SANDBOX_UNKNOWN = 0,
    GOLEM_SANDBOX_NONE = 1,
    GOLEM_SANDBOX_PROCESS = 2,
    GOLEM_SANDBOX_OS = 3,
    GOLEM_SANDBOX_CONTAINER = 4,
    GOLEM_SANDBOX_VM = 5
} golem_harness_sandbox;
typedef struct golem_harness_tool {
    char id[GOLEM_ADAPTER_ID_CAPACITY];
    golem_digest digest;
} golem_harness_tool;
/* Independent caller-owned values, not wire layouts. Zero initializes UNKNOWN.
 * Strings are bounded ASCII IDs (empty permitted only for unknown version/session).
 * tools are sorted by ID on encode/decode; duplicate IDs rejected. A tool digest
 * identifies its contract, not permission to invoke it. No pointers are retained. */
typedef struct golem_adapter_descriptor {
    uint32_t version;
    char adapter_id[GOLEM_ADAPTER_ID_CAPACITY];
    char adapter_version[GOLEM_ADAPTER_ID_CAPACITY];
    char session_id[GOLEM_ADAPTER_ID_CAPACITY];
    bool current_agent;
    uint32_t protocol_version, stages;
    uint32_t features_known, features_supported;
    uint32_t inputs_known, inputs_supported;
    golem_harness_truth simulation, hidden_prompt_known;
    golem_harness_sandbox sandbox;
    golem_effect effect;
    size_t tool_count;
    golem_harness_tool tools[GOLEM_DESCRIPTOR_MAX_TOOLS];
} golem_adapter_descriptor;

/* All inputs borrowed for synchronous call; outputs independent and unchanged on
 * failure (except diagnostic/required on short buffer). No input/output aliasing.
 * JSON uses strict keys, bounded integer masks, strings, tools; native structs are
 * never serialized. Encode excludes NUL, canonical fixed key order. json-c owns
 * temporary parser allocations. Queries never open a session, acquire a lease,
 * authenticate an agent, run a command or grant execution permission. */
golem_status golem_adapter_descriptor_validate(const golem_adapter_descriptor *descriptor);
golem_status golem_adapter_descriptor_decode(golem_bytes bytes, golem_adapter_descriptor *out);
golem_status golem_adapter_descriptor_encode(const golem_adapter_descriptor *descriptor,
                                             void *buffer, size_t capacity, size_t *required);
golem_status golem_adapter_descriptor_digest(const golem_adapter_descriptor *descriptor,
                                             golem_digest *out);
golem_status golem_adapter_descriptor_from_v1(const golem_adapter_capability *capability,
                                              golem_adapter_descriptor *out);
/* Refuses lossy conversion: v1 cannot represent unknown simulation or extra facts. */
golem_status golem_adapter_descriptor_to_v1(const golem_adapter_descriptor *descriptor,
                                            golem_adapter_capability *out);
/* Existing session description only. Empty session/version means unknown. */
golem_status golem_adapter_descriptor_current(const char *adapter_id, const char *session_id,
                                              golem_adapter_descriptor *out);

typedef struct golem_harness_requirements {
    size_t size;
    uint32_t version, stages, features, inputs;
    golem_harness_sandbox sandbox;  /* UNKNOWN = no sandbox requirement; exact match otherwise. */
    golem_harness_truth simulation; /* UNKNOWN = either; unknown claim never meets YES/NO. */
    golem_effect effect;
    size_t tool_count;
    golem_harness_tool tools[GOLEM_DESCRIPTOR_MAX_TOOLS];
} golem_harness_requirements;
/* Pure compatibility, not authorization. Required masks must be in BOTH claimed
 * and trusted host-observed support sets. Unknown is never true. Contradictory
 * positive claims are not promoted. Sandbox kinds are not a security ranking. */
golem_status golem_harness_compatible(const golem_adapter_descriptor *claimed,
                                      const golem_adapter_descriptor *observed,
                                      const golem_harness_requirements *required);

typedef struct golem_harness_observation {
    golem_adapter_descriptor descriptor;
    golem_digest profile_digest, binding_digest, evidence_digest, clock_domain;
    uint64_t epoch, observed_ns, expires_ns;
} golem_harness_observation;
/* Read-only receipt projection of trusted host facts. Caller may explicitly put
 * encoded bytes into CAS; encoding does not authenticate their truth. evidence_digest
 * references the independently collected host measurement, NOT this projection.
 * No decoder restores live authority from persisted observations. */
golem_status golem_harness_observation_encode(const golem_harness_observation *observation,
                                              void *buffer, size_t capacity, size_t *required);
typedef struct golem_harness_guard {
    size_t size;
    uint32_t version;
    const golem_adapter_descriptor *claimed;
    const golem_harness_requirements *required;
    golem_digest descriptor_digest, profile_digest, binding_digest, clock_domain;
    uint64_t epoch;
    /* Trusted host, NOT adapter/self-report callback. Recheck revocation/policy
     * and collect fresh observation on every call. Must return promptly; no
     * reentry/mutation of run/adapter/guard. All pointers borrowed for dispatch. */
    golem_status (*observe)(void *context, golem_harness_observation *out);
    /* Monotonic clock in clock_domain (host boot/instance identity, never a
     * reusable wall-clock label). Old domains must not survive host restart. */
    golem_status (*now)(void *context, uint64_t *out_ns);
    void *context;
} golem_harness_guard;
/* Opt-in hardened dispatch. Rechecks host observation just before callback and
 * after it, in addition to existing lease/policy/CAS gates. Observation evidence
 * must be present and hash-valid in store. No capability can
 * widen admitted effect. Post-dispatch failure preserves out but effects can
 * remain; never redispatch automatically. Legacy dispatch remains unenrolled. */
golem_status golem_adapter_dispatch_checked(golem_adapter *adapter, golem_work_run *run,
                                            const golem_adapter_request *request,
                                            golem_evidence_store *store,
                                            const golem_harness_guard *guard,
                                            golem_adapter_result *out,
                                            golem_diagnostic *diagnostic);

typedef struct golem_harness_probe_options {
    size_t size;
    uint32_t version;
    bool allow_process; /* default false; explicit trusted executable enrollment */
    const char *executable, *cwd;
    golem_digest expected_executable;
    uint64_t timeout_ns; /* 1 ns .. 30 s */
} golem_harness_probe_options;
typedef struct golem_harness_probe_result {
    golem_status status;
    golem_digest executable_digest, descriptor_digest, stdout_digest, stderr_digest;
    uint64_t duration_ns;
    golem_supervisor_result process;
    golem_adapter_descriptor claimed;
} golem_harness_probe_result;
/* Explicit metadata subprocess: argv=[executable,"--golem-describe"], empty stdin,
 * child env exactly LANG=C,LC_ALL=C, no inherited credentials or PATH; no shell.
 * Hash executable before/after, bounded supervisor output, timeout and group reap.
 * Trusted, quiescent executable required: pathname hashing is NOT fexecve pinning
 * or an OS sandbox. A malicious program can have effects despite metadata argv.
 * Returns transport/parse status; out is published after supervisor invocation,
 * including failed execution details, and preserved for preflight failures.
 * Probe output is CLAIMED only, never a host observation or execution permission. */
golem_status golem_harness_probe(const golem_harness_probe_options *options,
                                 golem_harness_probe_result *out);
/* Read-only canonical receipt projection; persists no logs or CAS objects.
 * Contains digests/exit/timeout/duration, never raw stderr or environment. */
golem_status golem_harness_probe_encode(const golem_harness_probe_result *result, void *buffer,
                                        size_t capacity, size_t *required);
#ifdef __cplusplus
}
#endif
#endif
