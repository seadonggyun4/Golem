#include "quota.h"

#define MIB UINT64_C(1048576)
static const gi_quota_usage limits[GI_QUOTA_LANES] = {
    {{4096, 64 * MIB, 1024 * MIB, 16384}},
    {{2048, 512 * MIB, 1024 * MIB, 16384}},
    {{64, 16 * MIB, 128 * MIB, 1024}}
};

static bool valid_lane(gi_quota_lane lane)
{
    return lane >= GI_QUOTA_INTAKE && lane < GI_QUOTA_LANES;
}

golem_status gi_quota_limit(gi_quota_lane lane, gi_quota_usage *out)
{
    if (!valid_lane(lane) || !out) return GOLEM_ERR_INVALID_ARGUMENT;
    *out = limits[lane];
    return GOLEM_OK;
}

golem_status gi_quota_project(const gi_quota_state *current, gi_quota_lane lane,
    const gi_quota_usage *retained, const gi_quota_usage *peak, gi_quota_state *out)
{
    if (!current || !retained || !peak || !out || !valid_lane(lane))
        return GOLEM_ERR_INVALID_ARGUMENT;
    for (unsigned l = 0; l < GI_QUOTA_LANES; ++l)
        for (unsigned a = 0; a < GI_QUOTA_AXES; ++a)
            if (current->lane[l].value[a] > limits[l].value[a])
                return GOLEM_ERR_INVALID_STATE;
    for (unsigned a = 0; a < GI_QUOTA_AXES; ++a) {
        if (peak->value[a] < retained->value[a]) return GOLEM_ERR_INVALID_ARGUMENT;
        /* Subtraction after current validation avoids unsigned wraparound. */
        if (peak->value[a] > limits[lane].value[a] - current->lane[lane].value[a])
            return GOLEM_ERR_OVERFLOW;
    }
    gi_quota_state next = *current;
    for (unsigned a = 0; a < GI_QUOTA_AXES; ++a)
        next.lane[lane].value[a] += retained->value[a];
    *out = next;
    return GOLEM_OK;
}
