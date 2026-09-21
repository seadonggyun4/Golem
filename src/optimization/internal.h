#ifndef GOLEM_OPTIMIZATION_INTERNAL_H
#define GOLEM_OPTIMIZATION_INTERNAL_H
#include "golem/optimization.h"
typedef struct golem_optimizer_state {
    golem_optimization_policy policy;
    uint32_t fallbacks[GOLEM_STAGE_COUNT];
} golem_optimizer_state;
bool golem_optimization_fallback_valid(const golem_fallback_policy *policy);
#endif
