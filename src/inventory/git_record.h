#ifndef GOLEM_INVENTORY_GIT_RECORD_H
#define GOLEM_INVENTORY_GIT_RECORD_H
#include "golem/inventory.h"
typedef struct in_git_entry {
    char mode[7], oid[65], path[GOLEM_INVENTORY_PATH_MAX + 1];
} in_git_entry;
/* One NUL-terminated ls-tree/ls-files record; borrowed input, unchanged output
 * on failure. No Git process, allocation, or filesystem access. */
golem_status in_git_entry_parse(golem_bytes record, bool index, in_git_entry *out);
#endif
