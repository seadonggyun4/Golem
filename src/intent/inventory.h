#ifndef GOLEM_INTENT_INVENTORY_INTERNAL_H
#define GOLEM_INTENT_INVENTORY_INTERNAL_H
#include "quota.h"

typedef struct gi_inventory {
    uint64_t logical_bytes;
    uint64_t files;
    uint64_t directories;
} gi_inventory;

/* Read-only descriptor-relative scan. No lane attribution or CAS verification.
 * Caller holds authority owner lock and supplies a trusted open root descriptor.
 * Counts every regular-file name, including pending/orphan and hardlink names.
 * Rejects symlinks/special files/cross-device traversal. No publication or
 * deletion. Budget counts all child entries (files AND directories), excludes
 * root. Depth is 1..64, root depth 0. Output unchanged on any failure.
 * Detectable races fail; this is not a snapshot against hostile same-uid writes. */
golem_status gi_inventory_scan(int root_fd, uint64_t entry_budget, unsigned max_depth,
    gi_inventory *out);
#endif
