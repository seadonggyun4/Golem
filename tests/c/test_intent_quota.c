#include "../../src/intent/quota.h"
#include "test.h"
#include <string.h>

int main(void)
{
    gi_quota_state zero = {0}, out, sentinel;
    memset(&sentinel, 0xa5, sizeof(sentinel));
    gi_quota_usage delta = {{0}}, peak = {{0}}, limit;
    const uint64_t expected[GI_QUOTA_LANES][GI_QUOTA_AXES] = {
        {4096, 67108864, 1073741824, 16384},
        {2048, 536870912, 1073741824, 16384},
        {64, 16777216, 134217728, 1024}
    };
    uint64_t totals[GI_QUOTA_AXES] = {0};
    for (int l = 0; l < GI_QUOTA_LANES; ++l) {
        CHECK(gi_quota_limit((gi_quota_lane)l, &limit) == GOLEM_OK);
        CHECK(memcmp(limit.value, expected[l], sizeof(limit.value)) == 0);
        for (unsigned a = 0; a < GI_QUOTA_AXES; ++a) {
            totals[a] += limit.value[a];
            gi_quota_state current = zero;
            current.lane[l].value[a] = limit.value[a] - 1;
            delta = (gi_quota_usage){{0}};
            CHECK(gi_quota_project(&current, (gi_quota_lane)l, &delta, &delta, &out) == GOLEM_OK);
            delta.value[a] = 1;
            CHECK(gi_quota_project(&current, (gi_quota_lane)l, &delta, &delta, &out) == GOLEM_OK);
            CHECK(out.lane[l].value[a] == limit.value[a]);
            gi_quota_state full = out;
            out = sentinel;
            CHECK(gi_quota_project(&full, (gi_quota_lane)l, &delta, &delta, &out) == GOLEM_ERR_OVERFLOW);
            CHECK(memcmp(&out, &sentinel, sizeof(out)) == 0);
            CHECK(full.lane[l].value[a] == limit.value[a]);
            delta.value[a] = UINT64_MAX;
            CHECK(gi_quota_project(&current, (gi_quota_lane)l, &delta, &delta, &out) == GOLEM_ERR_OVERFLOW);
            CHECK(memcmp(&out, &sentinel, sizeof(out)) == 0);
            /* Transient staging must fit even if retained occupancy would fit. */
            delta.value[a] = 1; peak = delta; peak.value[a] = 2;
            CHECK(gi_quota_project(&current, (gi_quota_lane)l, &delta, &peak, &out) == GOLEM_ERR_OVERFLOW);
            peak.value[a] = 0;
            CHECK(gi_quota_project(&current, (gi_quota_lane)l, &delta, &peak, &out) == GOLEM_ERR_INVALID_ARGUMENT);
            full.lane[l].value[a]++;
            CHECK(gi_quota_project(&full, GI_QUOTA_RECOVERY, &delta, &delta, &out) == GOLEM_ERR_INVALID_STATE);
        }
    }
    CHECK(totals[0] == 6208 && totals[1] == UINT64_C(620756992));
    CHECK(totals[2] == UINT64_C(2281701376) && totals[3] == 33792);
    /* A bounded temporary peak is checked but not retained in the projection. */
    delta = (gi_quota_usage){{1, 1024, 2048, 2}};
    peak = (gi_quota_usage){{1, 1024, 4096, 4}};
    CHECK(gi_quota_project(&zero, GI_QUOTA_INTAKE, &delta, &peak, &out) == GOLEM_OK);
    CHECK(memcmp(&out.lane[0], &delta, sizeof(delta)) == 0);
    CHECK(memcmp(&out.lane[1], &zero.lane[1], sizeof(delta)) == 0);
    CHECK(memcmp(&out.lane[2], &zero.lane[2], sizeof(delta)) == 0);
    gi_quota_state current = zero;
    CHECK(gi_quota_limit(GI_QUOTA_INTAKE, &current.lane[0]) == GOLEM_OK);
    delta = (gi_quota_usage){{1, 1, 1, 1}};
    CHECK(gi_quota_project(&current, GI_QUOTA_INTAKE, &delta, &delta, &out) == GOLEM_ERR_OVERFLOW);
    CHECK(gi_quota_project(&current, GI_QUOTA_RESOLUTION, &delta, &delta, &current) == GOLEM_OK);
    CHECK(current.lane[0].value[0] == 4096 && current.lane[1].value[0] == 1);
    CHECK(gi_quota_limit(GI_QUOTA_RESOLUTION, &current.lane[1]) == GOLEM_OK);
    CHECK(gi_quota_project(&current, GI_QUOTA_RESOLUTION, &delta, &delta, &out) == GOLEM_ERR_OVERFLOW);
    CHECK(gi_quota_project(&current, GI_QUOTA_RECOVERY, &delta, &delta, &out) == GOLEM_OK);
    /* Verified reuse/lookup can require zero added occupancy at full capacity. */
    for (int l = 0; l < GI_QUOTA_LANES; ++l)
        CHECK(gi_quota_limit((gi_quota_lane)l, &current.lane[l]) == GOLEM_OK);
    delta = (gi_quota_usage){{0}};
    CHECK(gi_quota_project(&current, GI_QUOTA_INTAKE, &delta, &delta, &out) == GOLEM_OK);
    CHECK(memcmp(&current, &out, sizeof(out)) == 0);
    CHECK(gi_quota_project(&zero, (gi_quota_lane)-1, &delta, &delta, &out) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_quota_project(&zero, GI_QUOTA_LANES, &delta, &delta, &out) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_quota_project(NULL, GI_QUOTA_INTAKE, &delta, &delta, &out) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_quota_project(&zero, GI_QUOTA_INTAKE, NULL, &delta, &out) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_quota_project(&zero, GI_QUOTA_INTAKE, &delta, NULL, &out) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_quota_project(&zero, GI_QUOTA_INTAKE, &delta, &delta, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_quota_limit(GI_QUOTA_LANES, &limit) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_quota_limit(GI_QUOTA_INTAKE, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
