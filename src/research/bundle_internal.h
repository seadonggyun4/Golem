#ifndef GOLEM_RESEARCH_BUNDLE_INTERNAL_H
#define GOLEM_RESEARCH_BUNDLE_INTERNAL_H
#include "internal.h"
#define RB_FILES 10u
#define RB_PAYLOADS 8u
#define RB_MAX_EVIDENCE 2048u
extern const char *const rb_names[RB_FILES];
golem_status rb_policy(golem_bytes bytes, struct json_object **out);
golem_status rb_checksums(struct json_object *files, char **out, size_t *size);
bool rb_file(struct json_object *files, const char *name, struct json_object *value);
#endif
