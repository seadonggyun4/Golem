/* QC5 authored fixtures. Execution is NOT_RUN while validation is on HOLD. */
#include "../../src/completion/internal.h"
#include "../../src/intent/qa_result.h"
#include "../../src/workflow/role_internal.h"
#include "test.h"
#include <stdlib.h>
#include <string.h>
static struct json_object *parse(const char *s)
{
    struct json_object *o = NULL;
    if (golem_json_parse((golem_bytes){(const uint8_t *)s, strlen(s)}, 65536, &o) != GOLEM_OK)
        abort();
    return o;
}
int main(void)
{
    struct json_object *r = parse(
        "{\"schema_version\":3,\"operation\":\"finalize\",\"selection_id\":\"selection\",\"key\":\"finish\",\"expected_generation\":1,\"issues\":[],\"predicate\":\"golem.completion.intent.local-no-merge.v1\",\"intent_qa_observation\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}");
    CHECK(co_validate(r) == GOLEM_OK);
    struct json_object *copy = NULL;
    CHECK(json_object_deep_copy(r, &copy, NULL) == 0);
    json_object_object_del(copy, "intent_qa_observation");
    CHECK(co_validate(copy) != GOLEM_OK);
    json_object_put(copy);
    copy = NULL;
    CHECK(json_object_deep_copy(r, &copy, NULL) == 0);
    CHECK(ex_text(copy, "predicate", CO_EVALUATOR_V1));
    CHECK(co_validate(copy) != GOLEM_OK);
    json_object_put(copy);
    copy = NULL;
    CHECK(json_object_deep_copy(r, &copy, NULL) == 0);
    CHECK(ex_text(copy, "unexpected", "permission"));
    CHECK(co_validate(copy) != GOLEM_OK);
    json_object_put(copy);
    copy = NULL;
    golem_document_store store = {0};
    store.spec = parse("{\"schema_version\":3,\"support_profile\":\"LOCAL_NO_MERGE\"}");
    struct json_object *out = NULL;
    CHECK(co_evaluate_v1(&store, r, false, &out) == GOLEM_ERR_UNSUPPORTED_VERSION);
    CHECK(rc_completion(&store, r, false, &out) == GOLEM_ERR_UNSUPPORTED_VERSION);
    CHECK(co_intent_evaluate(&store, r, true, &out) != GOLEM_OK);
    CHECK(co_intent_evaluate(&store, r, false, &out) != GOLEM_OK);
    CHECK(gi_qa_accepted(&store, &out) == GOLEM_ERR_REQUIREMENTS_UNMET);
    /* QC6 ordinary reads cannot promote historical completion without a scope. */
    const char *next = NULL;
    CHECK(co_hint(&store, "selection", &next) == GOLEM_OK);
    CHECK(next == NULL);
    store.completions[0] = parse("{\"request\":{\"selection_id\":\"selection\"}}");
    store.completion_count = 1;
    CHECK(co_hint(&store, "selection", &next) == GOLEM_OK);
    CHECK(!strcmp(next, "VERIFY_INTENT_COMPLETION"));
    json_object_put(store.completions[0]);
    store.completion_count = 0;

    struct json_object *resume =
        parse("{\"schema_version\":3,\"operation\":\"resume\",\"selection_id\":\"selection\"}");
    CHECK(co_validate(resume) == GOLEM_OK);
    CHECK(co_intent_evaluate(&store, resume, false, &out) != GOLEM_OK);
    json_object_put(resume);
    json_object_put(store.spec);
    json_object_put(r);
    /* Existing request schema stays supported; it cannot authorize Work v3. */
    r = parse(
        "{\"schema_version\":1,\"operation\":\"finalize\",\"selection_id\":\"selection\",\"key\":\"finish\",\"expected_generation\":1,\"issues\":[]}");
    CHECK(co_validate(r) == GOLEM_OK);
    json_object_put(r);
    return 0;
}
