#ifndef GOLEM_POLICY_H
#define GOLEM_POLICY_H

#include "golem/core.h"
#include "golem/types.h"
#ifdef __cplusplus
extern "C" {
#endif

#define GOLEM_POLICY_VERSION 1
typedef struct golem_policy golem_policy;
typedef enum golem_policy_verdict {
    GOLEM_POLICY_DENY = 0,
    GOLEM_POLICY_ASK = 1,
    GOLEM_POLICY_ALLOW = 2
} golem_policy_verdict;
typedef enum golem_effect {
    /* Unclassified effects never imply local safety. */
    GOLEM_EFFECT_UNKNOWN = 0,
    GOLEM_EFFECT_LOCAL = 1,
    GOLEM_EFFECT_EXTERNAL = 2
} golem_effect;
typedef enum golem_authorization {
    GOLEM_AUTHORIZATION_NONE = 0,
    GOLEM_AUTHORIZATION_GRANTED = 1,
    GOLEM_AUTHORIZATION_REJECTED = 2
} golem_authorization;
typedef enum golem_policy_reason {
    GOLEM_POLICY_STAGE_DENIED = 0,
    GOLEM_POLICY_EFFECT_UNKNOWN,
    GOLEM_POLICY_AUTHORIZATION_REJECTED,
    GOLEM_POLICY_ALWAYS_ASK,
    GOLEM_POLICY_EXTERNAL_ASK,
    GOLEM_POLICY_APPROVED,
    GOLEM_POLICY_LOCAL_ALLOWED
} golem_policy_reason;
typedef struct golem_policy_spec {
    uint32_t version;
    golem_autonomy permissions[GOLEM_STAGE_COUNT];
} golem_policy_spec;

#define GOLEM_POLICY_ARTIFACT_SIZE 32u
#define GOLEM_POLICY_ARTIFACT_VERSION 1u
typedef struct golem_policy_artifact {
    uint64_t revision; /* Positive host-assigned revision; not proof of freshness. */
    golem_policy_spec policy;
} golem_policy_artifact;
/* GPOL v1, exactly 32 bytes: magic[4], LE u16 version, zero u16 flags,
 * LE u64 revision, six u8 permissions in stage order, ten zero reserved bytes.
 * No native struct serialization, allocation, I/O or implicit policy installation.
 * Decode validates structure only: callers must authenticate provenance, enforce
 * revision/freshness and explicitly apply trusted policy. No signature/approval.
 * Inputs borrowed for call; independent caller-owned outputs, no aliasing.
 * Errors preserve outputs, except required on BUFFER_TOO_SMALL. NULL/0 encode
 * is a size query. Future layouts require a new version; unknown versions fail. */
golem_status golem_policy_artifact_encode(const golem_policy_artifact *artifact,
    void *buffer, size_t capacity, size_t *required);
golem_status golem_policy_artifact_decode(golem_bytes bytes, golem_policy_artifact *out);
typedef struct golem_policy_request {
    golem_stage stage;
    golem_effect effect;
    golem_authorization authorization;
} golem_policy_request;
typedef struct golem_policy_decision {
    uint32_t version;
    golem_policy_verdict verdict;
    golem_policy_reason reason;
    golem_autonomy mode;
    golem_policy_request request;
} golem_policy_decision;
typedef struct golem_stage_permission_request {
    const char *run_id;
    golem_stage stage;
    uint64_t sequence;
    uint32_t attempt;
    golem_effect effect;
    golem_authorization authorization;
} golem_stage_permission_request;

/* Pure permission decisions, not a sandbox, identity service or signed approval.
 * Caller classifies effects and attests authorization truthfully. GRANTED cannot
 * override DENY or UNKNOWN; REJECTED denies even otherwise autonomous requests.
 * AUTO_LOCAL and ASK_ON_EXTERNAL_EFFECT both allow local work and ask before
 * external effects, preserving the existing Core contract. ASK_ALWAYS asks for
 * all effects. Validation errors never imply permission: check status first.
 * Inputs borrowed for call; output value structs are independent copies. Inputs,
 * outputs and diagnostics must not alias. Outputs unchanged on error, except
 * optional diagnostics and the explicit begin_authorized exception below.
 * Evaluation performs no allocation, I/O, clock access or global mutation. */
/* Initialize current version with every stage DENY. NULL output is invalid. */
golem_status golem_policy_spec_init(golem_policy_spec *out);
golem_status golem_policy_spec_validate(const golem_policy_spec *spec);
/* Copies the fixed-size spec and allocator into an immutable owner. Context must
 * outlive free; NULL allocator selects default. *out unchanged on failure. */
golem_status golem_policy_create(const golem_policy_spec *spec, const golem_allocator *allocator,
    golem_policy **out, golem_diagnostic *diagnostic);
void golem_policy_free(golem_policy *policy); /* NULL is a no-op. */
golem_status golem_policy_spec_get(const golem_policy *policy, golem_policy_spec *out);
/* Shared primitive for standalone policy and the actual Core execution gate. */
golem_status golem_autonomy_evaluate(golem_autonomy mode, const golem_policy_request *request,
    golem_policy_decision *out);
golem_status golem_policy_evaluate(const golem_policy *policy, const golem_policy_request *request,
    golem_policy_decision *out);
/* Immutable process-lifetime strings; unknown values return "unknown". */
const char *golem_policy_verdict_name(golem_policy_verdict verdict);
const char *golem_policy_reason_name(golem_policy_reason reason);

/* READY run only. Derives current stage and next sequence/attempt, with NONE
 * authorization. run_id in the output BORROWS immutable run storage until free;
 * copy it if queuing the request beyond that lifetime. UNKNOWN effect is valid
 * input but will be denied at execution. No counters/state are changed.
 * Caller must reauthorize when any request field, scope or effect changes. */
golem_status golem_work_run_permission_request(const golem_work_run *run, golem_effect effect,
    golem_stage_permission_request *out, golem_diagnostic *diagnostic);
/* Checks current run identity and next attempt, then reevaluates the immutable
 * Capsule permissions (never trusts a caller-supplied decision). On ALLOW starts
 * exactly one StageRun. ASK returns APPROVAL_REQUIRED; DENY returns POLICY_DENIED.
 * Both leave Core state/counters/stage output unchanged and write the OPTIONAL
 * decision output. Other errors preserve both outputs. Success writes both.
 * Calls must be serialized with all mutations of this WorkRun. The request is a
 * trusted-caller attestation, not a tamper-proof/replay-proof approval capability.
 * Enabled cost accounting also checks capacity/budgets before starting; those
 * failures preserve both outputs. Does not launch an agent, persist decisions
 * or enforce effects after start. */
golem_status golem_work_run_begin_authorized(golem_work_run *run,
    const golem_stage_permission_request *request, golem_stage_snapshot *out,
    golem_policy_decision *decision, golem_diagnostic *diagnostic);

#ifdef __cplusplus
}
#endif

#endif
