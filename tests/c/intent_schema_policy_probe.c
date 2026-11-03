/* Test-only access to the production private shape checker. Never installed. */
#include "../../src/intent/review_host.c"
golem_status qc_schema_policy(struct json_object *value)
{
    gi_review_host host = {0};
    host.policy = value;
    return policy_shape(&host);
}
