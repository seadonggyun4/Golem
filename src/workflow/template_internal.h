#ifndef GOLEM_TEMPLATE_INTERNAL_H
#define GOLEM_TEMPLATE_INTERNAL_H
#include "internal.h"
#include "golem/workflow_template.h"
golem_status wt_model(struct json_object *object);
golem_status wt_selection(struct json_object *selection);
struct json_object *wt_definition(struct json_object *selection);
golem_status wt_guard(golem_document_store *store, const char *selection);
golem_status wt_revision(golem_document_store *store, struct json_object *metadata);
golem_status wt_execution(golem_document_store *store, struct json_object *contract);
#endif
