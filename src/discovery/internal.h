#ifndef GOLEM_DISCOVERY_INTERNAL_H
#define GOLEM_DISCOVERY_INTERNAL_H
#include "golem/discovery.h"
#include "../document/internal.h"
/* Shared document contract helpers keep parsing, IDs and digest rules aligned. */
bool ds_prose(struct json_object *o, const char *key);
bool ds_path(const char *path);
bool ds_array(struct json_object *a, size_t min, size_t max);
golem_status ds_validate(struct json_object *o, golem_discovery_result *out);
golem_status ds_metadata(struct json_object *m);
golem_status ds_evidence(golem_document_store *s, struct json_object *m);
#endif
