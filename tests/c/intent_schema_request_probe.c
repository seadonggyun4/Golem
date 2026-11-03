/* Test-only access; do not duplicate request parsing or create host authority. */
#include "../../src/intent/qa_acceptance.c"
golem_status qc_schema_request(struct json_object *value)
{
    return request_shape(value);
}
