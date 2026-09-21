#ifndef GOLEM_ADAPTER_SCHEMA_H
#define GOLEM_ADAPTER_SCHEMA_H
#include "internal.h"

/* Stable v1 wire IDs. Never renumber or reuse. */
typedef enum golem_wire_field {
    W_TYPE = 0, W_VERSION = 1, W_REQUEST_ID = 2, W_RUN_ID = 3, W_ADAPTER_ID = 4,
    W_STAGE = 5, W_SEQUENCE = 6, W_ATTEMPT = 7, W_CONTEXT_VERSION = 8,
    W_CONTEXT_ALGORITHM = 9, W_CONTEXT_SIZE = 10, W_CONTEXT_DIGEST = 11,
    W_HAS_PREDECESSOR = 12, W_PREDECESSOR_DIGEST = 13, W_STAGES = 14,
    W_EFFECT = 15, W_SIMULATION = 16, W_OUTCOME = 17, W_FAILURE = 18,
    W_EVIDENCE_VERSION = 19, W_EVIDENCE_ALGORITHM = 20, W_EVIDENCE_SIZE = 21,
    W_EVIDENCE_DIGEST = 22, W_INPUT_TOKENS = 23, W_CACHED_INPUT_TOKENS = 24,
    W_OUTPUT_TOKENS = 25, W_REASONING_TOKENS = 26, W_TOOL_CALLS = 27,
    W_NANO_COST = 28, W_USAGE_KNOWN = 29, W_COST_KNOWN = 30, W_FIELD_COUNT = 31
} golem_wire_field;
typedef enum golem_wire_kind { W_UINT, W_BOOL, W_TEXT, W_DIGEST } golem_wire_kind;
typedef struct golem_wire_value {
    golem_wire_kind kind;
    uint64_t number;
    char text[GOLEM_ADAPTER_ID_CAPACITY];
    golem_digest digest;
} golem_wire_value;
typedef struct golem_wire_codec {
    void *context;
    bool reading;
    golem_status status;
    golem_status (*field)(void *context, golem_wire_field id, golem_wire_value *value);
} golem_wire_codec;
const char *golem_wire_name(golem_wire_field id);
golem_status golem_adapter_envelope_valid(const golem_adapter_envelope *e);
void golem_wire_visit(golem_wire_codec *c, golem_adapter_envelope *e);
#endif
