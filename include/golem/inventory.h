#ifndef GOLEM_INVENTORY_H
#define GOLEM_INVENTORY_H
#include "golem/evidence.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_INVENTORY_MAX_JSON 1048576u
#define GOLEM_INVENTORY_MAX_PATHS 1024u
#define GOLEM_INVENTORY_PATH_MAX 1024u
typedef struct golem_inventory_reply {
    uint8_t *data;
    size_t size;
} golem_inventory_reply;
/* Versioned policy/snapshot JSON, strict schemas. Borrow inputs for the call;
 * owned reply is freed ONLY with reply_free. Outputs unchanged on failure.
 * Local read-only observation, not execution permission or atomic filesystem
 * isolation. Root must be a canonical, private, quiescent Git top-level directory.
 * No symlink traversal.
 * Two matching observations are required; mutation, unsupported entries, resource
 * limits and unknown versions fail closed. Ignored files are included unless an
 * explicit policy exclusion matches. Paths are encoded as lowercase hex bytes.
 * Git listing output per command is streamed with a 64 MiB bound; overflow is not
 * a complete inventory. At most 1024 paths, 1024 bytes/path, 64 MiB content/pass,
 * 4096 filesystem visits, 64 directory levels and 60 seconds/capture.
 * Submodules/unmerged index are incomplete in v1. */
golem_status golem_inventory_policy_validate(golem_bytes policy, golem_diagnostic *diagnostic);
golem_status golem_inventory_capture(const char *root, golem_bytes policy,
                                     golem_inventory_reply *out, golem_diagnostic *diagnostic);
/* Pure comparison of structurally valid snapshots with equal root/scope identity.
 * Does not attest caller-authored snapshots; runtime consumers must use issued CAS
 * receipts. Count is the path union whose HEAD/index/worktree state changed since
 * baseline. Preexisting dirty paths are reported separately, never silently reset.
 * allowed=false is a valid finding, not a parse error. HEAD movement also denies.
 * Case-fold ambiguity (ASCII), unknown types and malformed byte paths are refused.
 * EXACT/DIR_PREFIX/SEGMENT_GLOB matching is byte-based, case-sensitive, anchored.
 * Glob * and ? do not cross '/', ** must be a whole segment; no regex/negation. */
golem_status golem_inventory_compare(golem_bytes baseline, golem_bytes current, golem_bytes policy,
                                     golem_inventory_reply *out, golem_diagnostic *diagnostic);
void golem_inventory_reply_free(golem_inventory_reply *reply);
#ifdef __cplusplus
}
#endif
#endif
