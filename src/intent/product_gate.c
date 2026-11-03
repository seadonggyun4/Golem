#include "product_access.h"
#include "product_gate.h"
#include "../document/internal.h"
#include "../execution/internal.h"
#include <string.h>
#include <stdlib.h>
static bool eq(struct json_object *o,const char *key,const char *value)
{return !strcmp(dw_text(o,key),value);}
static bool digest_eq(struct json_object *o,const char *key,const golem_digest *d)
{golem_digest a;return dw_digest(o,key,&a)&&dw_equal(&a,d);}
static bool v3(golem_document_store *s){return s&&dw_uint(s->spec,"schema_version")==3;}
golem_status gi_product_spec(struct json_object *s)
{
    const char *keys[]={"registration_ref","baseline_ref","policy_ref"};golem_digest d;
    struct json_object *b=dw_get(s,"intent_binding");
    if(!eq(s,"support_profile","LOCAL_NO_MERGE")||!dw_keys(b,keys,3)||
        !dw_digest(b,"registration_ref",&d)||!dw_digest(b,"baseline_ref",&d)||!dw_digest(b,"policy_ref",&d))return GOLEM_ERR_PARSE;
    return GOLEM_OK;
}
golem_status gi_product_check(golem_document_store *s,gi_product_boundary boundary)
{
    if(!s||boundary<GI_PRODUCT_DEVELOPMENT||boundary>GI_PRODUCT_PUBLICATION)return GOLEM_ERR_INVALID_ARGUMENT;
    if(!v3(s))return GOLEM_OK;
    if(gi_product_spec(s->spec)!=GOLEM_OK)return GOLEM_ERR_POLICY_DENIED;
    if(!s->intent_enrollment)return GOLEM_ERR_REQUIREMENTS_UNMET; /* ENROLLMENT_PENDING */
    /* Historical binding alone never grants permission. The private scope
     * resolves exact material and current stage authority at each boundary. */
    return s->intent_access ? gi_product_access_check(s,boundary) : GOLEM_ERR_UNSUPPORTED_VERSION;
}
golem_status gi_product_record(golem_document_store *s,struct json_object *event)
{
    if(!s)return GOLEM_ERR_INVALID_ARGUMENT;
    if(!v3(s))return GOLEM_OK;
    /* Document publication preserves observations. It is not acceptance. */
    if(eq(event,"type","document"))return GOLEM_OK;
    if(eq(event,"type","intent-qa-observation")&&s->intent_accepting)return gi_product_check(s,GI_PRODUCT_QA_ACCEPTANCE);
    if(eq(event,"type","intent-enrollment")&&s->intent_enrolling)return GOLEM_OK;
    return gi_product_access_record(s,event);
}
static golem_status shape(golem_document_store *s,struct json_object *e)
{
    const char *root[]={"schema","project_id","work_id","created_by_assertion","baseline_digest","body"};
    const char *keys[]={"baseline_ref","work_spec_digest","requirement_mapping","support_profile","policy_ref","activation_decision_ref","predecessor_ref"};
    struct json_object *body=dw_get(e,"body"),*binding=dw_get(s->spec,"intent_binding");golem_digest spec,d;
    golem_status st=ex_hash(s->spec,&spec);if(st!=GOLEM_OK)return st;
    if(!dw_keys(e,root,6)||!eq(e,"schema","golem.intent.work-enrollment.v1")||!dw_id(dw_text(e,"project_id"))||
        !eq(e,"work_id",dw_text(s->spec,"work_id"))||!*dw_text(e,"created_by_assertion")||!dw_keys(body,keys,7)||
        !json_object_equal(dw_get(e,"baseline_digest"),dw_get(binding,"baseline_ref"))||
        !json_object_equal(dw_get(body,"baseline_ref"),dw_get(binding,"baseline_ref"))||
        !json_object_equal(dw_get(body,"policy_ref"),dw_get(binding,"policy_ref"))||
        !digest_eq(body,"work_spec_digest",&spec)||!eq(body,"support_profile","LOCAL_NO_MERGE")||
        !dw_digest(body,"activation_decision_ref",&d))return GOLEM_ERR_IDENTITY_MISMATCH;
    if(!json_object_is_type(dw_get(body,"predecessor_ref"),json_type_null)&&!dw_digest(body,"predecessor_ref",&d))return GOLEM_ERR_PARSE;
    struct json_object *map=dw_get(body,"requirement_mapping"),*acceptance=dw_get(s->spec,"acceptance");
    if(!json_object_is_type(map,json_type_array)||json_object_array_length(map)!=json_object_array_length(acceptance))return GOLEM_ERR_REQUIREMENTS_UNMET;
    for(size_t i=0;i<json_object_array_length(map);++i){struct json_object *r=json_object_array_get_idx(map,i);const char *mk[]={"requirement_ref","acceptance_id"};
        if(!dw_keys(r,mk,2)||!dw_digest(r,"requirement_ref",&d)||!dw_id(dw_text(r,"acceptance_id")))return GOLEM_ERR_PARSE;
        bool found=false;for(size_t j=0;j<json_object_array_length(acceptance);++j)if(eq(json_object_array_get_idx(acceptance,j),"id",dw_text(r,"acceptance_id")))found=true;
        if(!found)return GOLEM_ERR_REQUIREMENTS_UNMET;
        for(size_t j=0;j<i;++j){struct json_object *old=json_object_array_get_idx(map,j);
            if(eq(old,"requirement_ref",dw_text(r,"requirement_ref"))||eq(old,"acceptance_id",dw_text(r,"acceptance_id")))return GOLEM_ERR_REQUIREMENTS_UNMET;}
    }
    return GOLEM_OK;
}
golem_status gi_product_apply(golem_document_store *s,struct json_object *event,const golem_digest *frame)
{
    const char *keys[]={"schema_version","type","enrollment","authority_operation","authority_request","authority_sequence","authority_event","registration_ref"};golem_digest d;
    if(!v3(s)||s->intent_enrollment||!dw_keys(event,keys,8)||dw_uint(event,"schema_version")!=1||
        !eq(event,"type","intent-enrollment")||!dw_digest(event,"authority_operation",&d)||!dw_digest(event,"authority_request",&d)||
        !dw_digest(event,"authority_event",&d)||dw_uint(event,"authority_sequence")==0||dw_uint(event,"authority_sequence")==UINT64_MAX||
        !json_object_equal(dw_get(event,"registration_ref"),dw_get(dw_get(s->spec,"intent_binding"),"registration_ref")))return GOLEM_ERR_CORRUPT_JOURNAL;
    golem_status st=shape(s,dw_get(event,"enrollment"));if(st!=GOLEM_OK)return st;
    s->intent_enrollment=json_object_get(event);s->last=*frame;++s->event_count;return GOLEM_OK;
}
golem_status gi_product_enrollment_approval(golem_document_store *s,const golem_digest *request,
    const golem_digest *base_op,const golem_digest *base_request,const golem_digest *op,uint64_t sequence,
    const golem_digest *head,uint64_t work_sequence,const golem_digest *work_head,golem_digest *out)
{
    if(!s||!request||!base_op||!base_request||!op||!head||!work_head||!out||!v3(s))return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *o=json_object_new_object();golem_digest spec;golem_status st=ex_hash(s->spec,&spec);
    if(st==GOLEM_OK&&(!dw_add(o,"domain",json_object_new_string("golem.intent.enrollment-approval.v1"))||
        !dw_add_digest(o,"request",request)||!dw_add_digest(o,"spec",&spec)||
        !dw_add(o,"registration",json_object_get(dw_get(dw_get(s->spec,"intent_binding"),"registration_ref")))||
        !dw_add_digest(o,"baseline_operation",base_op)||!dw_add_digest(o,"baseline_request",base_request)||
        !dw_add_digest(o,"operation",op)||!dw_add(o,"authority_sequence",json_object_new_uint64(sequence))||
        !dw_add_digest(o,"authority_head",head)||!dw_add(o,"work_sequence",json_object_new_uint64(work_sequence))||
        !dw_add_digest(o,"work_head",work_head)))st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK)st=ex_hash(o,out);json_object_put(o);return st;
}
static golem_status enroll(golem_document_store *s,int fd,const gi_review_inputs *inputs,golem_bytes bytes,
    const golem_digest *owner,const golem_digest *base_op,const golem_digest *base_request,const golem_digest *op,
    uint64_t sequence,const golem_digest *head,uint64_t work_sequence,const golem_digest *work_head,
    gi_journal_guard guard,void *context,gi_journal_receipt *out)
{
    if(!s||!inputs||!owner||!base_op||!base_request||!op||!head||!work_head||!guard||!out)return GOLEM_ERR_INVALID_ARGUMENT;
    if(!v3(s)||!s->writable||s->poisoned||s->intent_enrollment||s->intent_enrolling)return GOLEM_ERR_POLICY_DENIED;
    if(s->event_count!=work_sequence||!dw_equal(work_head,&s->last))return GOLEM_ERR_STALE_RESULT;
    golem_digest request;golem_status st=golem_digest_bytes(bytes,&request);
    if(st!=GOLEM_OK)return st;
    golem_digest approval;
    st=gi_product_enrollment_approval(s,&request,base_op,base_request,op,sequence,head,work_sequence,work_head,&approval);
    if(st!=GOLEM_OK)return st;if(!dw_equal(owner,&approval))return GOLEM_ERR_APPROVAL_REQUIRED;
    struct json_object *e=NULL,*base=NULL,*event=NULL;gi_journal *journal=NULL;gi_review_state *state=NULL;
    gi_review_binding bound;gi_journal_receipt receipt={0};bool attempted=false;
    st=guard(context);if(st!=GOLEM_OK)return st;
    st=gi_review_bind(inputs,&bound,NULL);if(st!=GOLEM_OK)return st;
    st=golem_json_parse(bytes,GI_CONTROL_MAX,&e);if(st==GOLEM_OK)st=shape(s,e);
    if(st==GOLEM_OK&&!json_object_is_type(dw_get(dw_get(e,"body"),"predecessor_ref"),json_type_null))st=GOLEM_ERR_UNSUPPORTED_VERSION;
    if(st==GOLEM_OK&&!digest_eq(e,"baseline_digest",&bound.baseline))st=GOLEM_ERR_IDENTITY_MISMATCH;
    if(st==GOLEM_OK)st=golem_json_parse(inputs->baseline,GI_CONTROL_MAX,&base);
    if(st==GOLEM_OK&&(!eq(e,"project_id",dw_text(base,"project_id"))||!eq(e,"work_id",dw_text(base,"work_id"))||!json_object_equal(dw_get(dw_get(base,"body"),"issuer_policy_ref"),dw_get(dw_get(s->spec,"intent_binding"),"policy_ref"))))st=GOLEM_ERR_IDENTITY_MISMATCH;
    struct json_object *map=dw_get(dw_get(e,"body"),"requirement_mapping");
    if(st==GOLEM_OK&&json_object_array_length(map)!=inputs->definition_count)st=GOLEM_ERR_REQUIREMENTS_UNMET;
    for(size_t i=0;st==GOLEM_OK&&i<inputs->definition_count;++i){golem_digest definition;st=gi_domain_digest(inputs->definitions[i],&definition,NULL);bool found=false;
        for(size_t j=0;j<json_object_array_length(map);++j)if(digest_eq(json_object_array_get_idx(map,j),"requirement_ref",&definition))found=true;
        if(st==GOLEM_OK&&!found)st=GOLEM_ERR_REQUIREMENTS_UNMET;}
    if(st==GOLEM_OK)st=gi_journal_open(fd,&journal); /* Work lock already held */
    if(st==GOLEM_OK)st=gi_review_load(journal,base_op,base_request,&bound.baseline,inputs->definitions,inputs->definition_count,&state);
    gi_review_status status;
    if(st==GOLEM_OK)st=gi_review_inspect(state,&status);
    if(st==GOLEM_OK&&(!status.active||status.open_questions||!digest_eq(dw_get(e,"body"),"activation_decision_ref",&status.activation_decision)))st=GOLEM_ERR_REQUIREMENTS_UNMET;
    if(st==GOLEM_OK){gi_journal_operation prior;golem_status looked=gi_journal_lookup(journal,op,&request,&prior);
        if(looked==GOLEM_OK)st=GOLEM_ERR_INVALID_STATE;else if(looked!=GOLEM_ERR_NOT_FOUND)st=looked;}
    /* Exact historical activation is required, but does not authorize product work. */
    if(st==GOLEM_OK){attempted=true;st=gi_journal_append(journal,GI_QUOTA_INTAKE,op,&request,sequence,head,bytes,guard,context,&receipt);}
    if(st==GOLEM_OK){event=json_object_new_object();
        if(!dw_add(event,"schema_version",json_object_new_int(1))||!dw_add(event,"type",json_object_new_string("intent-enrollment"))||
            !dw_add(event,"enrollment",json_object_get(e))||!dw_add_digest(event,"authority_operation",op)||!dw_add_digest(event,"authority_request",&request)||
            !dw_add(event,"authority_sequence",json_object_new_uint64(receipt.sequence))||!dw_add_digest(event,"authority_event",&receipt.digest)||
            !dw_add(event,"registration_ref",json_object_get(dw_get(dw_get(s->spec,"intent_binding"),"registration_ref"))))st=GOLEM_ERR_OUT_OF_MEMORY;}
    if(st==GOLEM_OK){golem_digest payload,frame;s->intent_enrolling=true;
        st=guard(context);
        if(st==GOLEM_OK&&(s->event_count!=work_sequence||!dw_equal(work_head,&s->last)))st=GOLEM_ERR_STALE_RESULT;
        if(st==GOLEM_OK)st=dw_record_prepare(s,event,GOLEM_DOCUMENT_MAX_JSON,&payload);
        if(st==GOLEM_OK)st=dw_event_write_guarded(s,&payload,&frame,guard,context);
        if(st==GOLEM_OK)st=gi_product_apply(s,event,&frame);
        s->intent_enrolling=false;}
    if(st==GOLEM_OK)*out=receipt;
    else if(attempted)s->poisoned=true; /* authority may be committed: no retry */
    gi_review_free(state);gi_journal_close(journal);json_object_put(e);json_object_put(base);json_object_put(event);return st;
}

golem_status gi_product_enroll(golem_document_store *s,int fd,const gi_review_inputs *inputs,golem_bytes bytes,
    const golem_digest *owner,const golem_digest *base_op,const golem_digest *base_request,const golem_digest *op,
    uint64_t sequence,const golem_digest *head,uint64_t work_sequence,const golem_digest *work_head,
    gi_journal_guard guard,void *context,gi_journal_receipt *out)
{
    if(!bytes.data||!bytes.size||bytes.size>GI_CONTROL_MAX)return GOLEM_ERR_INVALID_ARGUMENT;
    uint8_t *copy=malloc(bytes.size);if(!copy)return GOLEM_ERR_OUT_OF_MEMORY;
    memcpy(copy,bytes.data,bytes.size);
    golem_status st=enroll(s,fd,inputs,(golem_bytes){copy,bytes.size},owner,base_op,base_request,op,
        sequence,head,work_sequence,work_head,guard,context,out);
    free(copy);return st;
}

typedef struct enrollment_match {
    golem_digest operation,request;
    struct json_object *enrollment;
    bool found;
} enrollment_match;
static golem_status match_enrollment(void *opaque,const golem_digest *op,const golem_digest *request,
    const gi_journal_operation *record,golem_bytes bytes)
{
    enrollment_match *m=opaque;if(!dw_equal(op,&m->operation))return GOLEM_OK;
    if(m->found||!dw_equal(request,&m->request)||!record->committed||record->pending||record->lane!=GI_QUOTA_INTAKE)return GOLEM_ERR_CORRUPT_JOURNAL;
    struct json_object *o=NULL;golem_digest raw;golem_status st=golem_digest_bytes(bytes,&raw);
    if(st==GOLEM_OK&&!dw_equal(&raw,request))st=GOLEM_ERR_IDENTITY_MISMATCH;
    if(st==GOLEM_OK)st=golem_json_parse(bytes,GI_CONTROL_MAX,&o);
    if(st==GOLEM_OK&&!json_object_equal(o,m->enrollment))st=GOLEM_ERR_IDENTITY_MISMATCH;
    if(st==GOLEM_OK)m->found=true;json_object_put(o);return st;
}
golem_status gi_product_enrollment_verify(golem_document_store *s,int authority_fd,gi_journal_guard guard,void *context)
{
    if(!s||!guard||!v3(s))return GOLEM_ERR_INVALID_ARGUMENT;
    if(!s->intent_enrollment)return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *e=s->intent_enrollment;enrollment_match m={0};
    if(!dw_digest(e,"authority_operation",&m.operation)||!dw_digest(e,"authority_request",&m.request))return GOLEM_ERR_CORRUPT_JOURNAL;
    m.enrollment=dw_get(e,"enrollment");golem_status st=guard(context);gi_journal *j=NULL;
    if(st==GOLEM_OK)st=gi_journal_open(authority_fd,&j);
    gi_journal_operation record;
    if(st==GOLEM_OK)st=gi_journal_lookup(j,&m.operation,&m.request,&record);
    if(st==GOLEM_OK&&(!record.committed||record.pending||record.sequence!=dw_uint(e,"authority_sequence")||
        !digest_eq(e,"authority_event",&record.digest)))st=GOLEM_ERR_REQUIREMENTS_UNMET;
    if(st==GOLEM_OK)st=gi_journal_visit_payloads(j,match_enrollment,&m);
    if(st==GOLEM_OK&&!m.found)st=GOLEM_ERR_REQUIREMENTS_UNMET;
    if(st==GOLEM_OK)st=guard(context);
    gi_journal_close(j);return st; /* binding integrity only, never product readiness */
}
