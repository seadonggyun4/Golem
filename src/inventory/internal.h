#ifndef GOLEM_INVENTORY_INTERNAL_H
#define GOLEM_INVENTORY_INTERNAL_H
#include "golem/inventory.h"
#include "git_record.h"
#include "../workspace/internal.h"
#define IN_RULES 32
#define IN_PATTERN 256
typedef struct in_rule {
    unsigned kind;
    char pattern[IN_PATTERN + 1];
} in_rule;
typedef struct in_policy {
    in_rule protected[IN_RULES], excluded[IN_RULES];
    size_t protected_count, excluded_count;
    bool unlimited;
    uint64_t maximum;
    golem_digest digest;
} in_policy;
golem_status in_policy_parse(struct json_object *o, in_policy *out);
bool in_path(const char *p);
bool in_matches(const in_rule *rule, const char *path);
bool in_any(const in_rule *rules, size_t count, const char *path);
golem_status in_unhex(const char *hex, char *out, size_t capacity);
struct json_object *in_hex(const uint8_t *bytes, size_t size);
golem_status in_emit(struct json_object *o, golem_inventory_reply *out);
golem_status in_snapshot_validate(struct json_object *o, const in_policy *policy);
golem_status in_capture(const char *root, const in_policy *policy, struct json_object **out);
golem_status in_compare(struct json_object *base, struct json_object *now, const in_policy *policy,
                        struct json_object **out);
#endif
