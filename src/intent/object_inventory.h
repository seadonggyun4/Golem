#ifndef GOLEM_INTENT_OBJECT_INVENTORY_H
#define GOLEM_INTENT_OBJECT_INVENTORY_H
#include "inventory.h"

/* Journal replay supplies ordered, binding-verified manifests under the owner
 * lock. committed is not a caller authorization or a manifest assertion. */
typedef struct gi_object_manifest_input {
    golem_bytes bytes;
    bool committed;
} gi_object_manifest_input;
typedef struct gi_object_inventory {
    gi_inventory actual;
    gi_quota_usage intake;
    bool pending;
} gi_object_inventory;
/* Scans only objects/, never journal/host metadata. Verifies original creation
 * attribution, earlier committed reuse, exact bytes identity and safe paths.
 * Domain identity is not source coverage or baseline adoption verification.
 * No writes, cleanup or recovery. Output is unchanged on failure. */
golem_status gi_object_inventory_scan(int root, const gi_object_manifest_input *, size_t,
    gi_object_inventory *);
typedef enum gi_object_kind { GI_OBJECT_RAW, GI_OBJECT_SOURCE, GI_OBJECT_BASELINE } gi_object_kind;
golem_status gi_object_path(gi_object_kind, const golem_digest *, char *, size_t);
/* Exact immutable bytes; caller owns the returned allocation. This verifies
 * identity/protected layout, not provenance, authorization or graph semantics. */
golem_status gi_object_load(int root, gi_object_kind, const golem_digest *, size_t limit,
    uint8_t **out, size_t *size);
#endif
