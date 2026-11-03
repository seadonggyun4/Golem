/* QC7: pure Work observation replay is not authority acceptance. NOT_RUN. */
#include "../../src/intent/qa_result.h"
#include "../../src/document/internal.h"
#include "../../src/execution/internal.h"
#include "test.h"
#include <stdlib.h>
#include <string.h>
static struct json_object *parse(const char *text)
{struct json_object *o=NULL;if(golem_json_parse((golem_bytes){(const uint8_t *)text,strlen(text)},GI_CONTROL_MAX,&o)!=GOLEM_OK)abort();return o;}
static golem_bytes wire(struct json_object *o)
{const char *p=json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN);return (golem_bytes){(const uint8_t *)p,strlen(p)};}
static int denied(golem_document_store *s,struct json_object *event,golem_digest *frame)
{
    uint64_t count=s->event_count;size_t observed=s->intent_qa_count;golem_digest head=s->last;
    CHECK(gi_qa_observation_apply(s,event,frame)!=GOLEM_OK);
    CHECK(s->event_count==count&&s->intent_qa_count==observed&&dw_equal(&head,&s->last));return 0;
}
int main(void)
{
    /* Exact host selection must not override the native Work permission. */
    golem_document_store denied_work={0};denied_work.writable=true;
    denied_work.spec=parse("{\"schema_version\":3,\"permission\":\"DENY\"}");
    uint8_t sentinel=23;golem_execution_reply untouched={&sentinel,1};
    golem_bytes empty={(const uint8_t *)"{}",2};
    CHECK(gi_qa_accept(&denied_work,empty,&untouched)==GOLEM_ERR_POLICY_DENIED);
    CHECK(untouched.data==&sentinel&&untouched.size==1&&!denied_work.poisoned);
    CHECK(denied_work.event_count==0&&denied_work.intent_qa_count==0);
    CHECK(ex_text(denied_work.spec,"permission","ASK_ALWAYS"));
    CHECK(gi_qa_accept(&denied_work,empty,&untouched)==GOLEM_ERR_APPROVAL_REQUIRED);
    CHECK(untouched.data==&sentinel&&untouched.size==1&&!denied_work.poisoned);
    CHECK(denied_work.event_count==0&&denied_work.intent_qa_count==0);
    json_object_put(denied_work.spec);

    golem_document_store s={0};golem_digest zero={{0}},request_hash,assessment_hash,frame={{9}},prepare={{1}},accept={{2}};
    s.spec=parse("{\"schema_version\":3,\"work_id\":\"work\",\"intent_binding\":{}}");CHECK(dw_add_digest(dw_get(s.spec,"intent_binding"),"baseline_ref",&zero));
    struct json_object *r=parse("{\"schema\":\"golem.intent.qa-request.v1\",\"operation\":\"accept\",\"execution_receipt_ref\":null,\"semantic_reviews\":[],\"authority_sequence\":0}");
    CHECK(dw_add_digest(r,"authority_head",&zero));CHECK(dw_add_digest(r,"prepare_operation",&prepare));CHECK(dw_add_digest(r,"accept_operation",&accept));
    CHECK(dw_add_digest(r,"execution_receipt_ref",&prepare));
    struct json_object *a=parse("{\"schema\":\"golem.intent.qa-assessment.v1\",\"project_id\":\"p\",\"work_id\":\"work\",\"created_by_assertion\":\"native-qc4\",\"body\":{\"input_tuple\":{},\"review_refs\":[],\"obligation_results\":[],\"blockers\":[],\"execution_status\":\"PASS\",\"intent_qa_status\":\"BLOCKED\",\"assurance\":\"LOCAL_COOPERATIVE_REVIEWED_NOT_PROVEN\"}}");
    CHECK(dw_add_digest(a,"baseline_digest",&zero));CHECK(dw_add_digest(dw_get(a,"body"),"execution_receipt_ref",&prepare));
    CHECK(golem_digest_bytes(wire(r),&request_hash)==GOLEM_OK);CHECK(gi_domain_digest(wire(a),&assessment_hash,NULL)==GOLEM_OK);
    struct json_object *event=parse("{\"schema_version\":1,\"type\":\"intent-qa-observation\",\"prepare_sequence\":1,\"previous_work_sequence\":0}");
    CHECK(dw_add(event,"request",json_object_new_string_len((const char *)wire(r).data,(int)wire(r).size)));
    CHECK(dw_add(event,"assessment",json_object_get(a)));CHECK(dw_add_digest(event,"request_digest",&request_hash));CHECK(dw_add_digest(event,"assessment_digest",&assessment_hash));
    CHECK(dw_add_digest(event,"prepare_operation",&prepare));CHECK(dw_add_digest(event,"accept_operation",&accept));
    CHECK(dw_add_digest(event,"prepare_event",&prepare));CHECK(dw_add_digest(event,"previous_work_head",&zero));
    /* One fault at a time, preserving exact original bytes and state. */
    const char *digest_fields[]={"request_digest","assessment_digest","previous_work_head","prepare_operation","accept_operation"};
    for(size_t i=0;i<5;++i){struct json_object *bad=NULL;CHECK(!json_object_deep_copy(event,&bad,NULL));CHECK(dw_add_digest(bad,digest_fields[i],&frame));CHECK(denied(&s,bad,&frame)==0);json_object_put(bad);bad=NULL;}
    struct json_object *bad=NULL;CHECK(!json_object_deep_copy(event,&bad,NULL));CHECK(ex_uint(bad,"prepare_sequence",2));CHECK(denied(&s,bad,&frame)==0);json_object_put(bad);bad=NULL;
    CHECK(!json_object_deep_copy(event,&bad,NULL));CHECK(ex_text(dw_get(dw_get(bad,"assessment"),"body"),"intent_qa_status","ACCEPTED"));
    CHECK(gi_domain_digest(wire(dw_get(bad,"assessment")),&assessment_hash,NULL)==GOLEM_OK);CHECK(dw_add_digest(bad,"assessment_digest",&assessment_hash));CHECK(denied(&s,bad,&frame)==0);json_object_put(bad);bad=NULL;
    CHECK(gi_qa_observation_apply(&s,event,&frame)==GOLEM_OK);CHECK(s.intent_qa_count==1&&s.event_count==1);
    struct json_object *current=NULL;CHECK(gi_qa_accepted(&s,&current)!=GOLEM_OK);CHECK(current==NULL);
    CHECK(denied(&s,event,&frame)==0); /* no duplicate replay/automatic completion */
    json_object_put(s.intent_qa[0]);json_object_put(event);json_object_put(a);json_object_put(r);json_object_put(s.spec);return 0;
}
