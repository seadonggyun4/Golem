#ifndef GOLEM_INTERNAL_JSON_H
#define GOLEM_INTERNAL_JSON_H
#include "golem/types.h"
#include <json-c/json.h>
/* Owned output, borrowed bounded input; strict UTF-8, object root, duplicate-key
 * and embedded NUL rejection. Unknown keys are the caller's schema decision. */
golem_status golem_json_parse(golem_bytes bytes, size_t limit, struct json_object **out);
#endif
