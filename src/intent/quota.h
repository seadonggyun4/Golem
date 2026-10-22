#ifndef GOLEM_INTENT_QUOTA_INTERNAL_H
#define GOLEM_INTENT_QUOTA_INTERNAL_H

#include "golem/evidence.h"

/* Private, pure ADR-D08 accounting. Not an authorization or filesystem scan.
 * Caller must authenticate the lane and supply verified inventory under its
 * authority lock. No store, reservations, refunds or publication occur here. */
typedef enum gi_quota_lane {
    GI_QUOTA_INTAKE, GI_QUOTA_RESOLUTION, GI_QUOTA_RECOVERY, GI_QUOTA_LANES
} gi_quota_lane;
typedef enum gi_quota_axis {
    GI_QUOTA_EVENTS, GI_QUOTA_PAYLOAD, GI_QUOTA_BYTES, GI_QUOTA_ENTRIES, GI_QUOTA_AXES
} gi_quota_axis;
typedef struct gi_quota_usage { uint64_t value[GI_QUOTA_AXES]; } gi_quota_usage;
typedef struct gi_quota_state { gi_quota_usage lane[GI_QUOTA_LANES]; } gi_quota_state;

golem_status gi_quota_limit(gi_quota_lane lane, gi_quota_usage *out);
/* peak is additional occupancy including retained, not a second additive cost.
 * Both vectors are nonnegative; peak >= retained on every axis. Existing CAS
 * reuse may be zero only after verification by the caller. Pending/orphan
 * occupancy stays in current until independently reconciled by a future store.
 * Input may alias output. All outputs unchanged on failure. */
golem_status gi_quota_project(const gi_quota_state *current, gi_quota_lane lane,
    const gi_quota_usage *retained, const gi_quota_usage *peak, gi_quota_state *out);

#endif
