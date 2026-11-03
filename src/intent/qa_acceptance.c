#include "qa_result.h"
#include "../document/internal.h"
#include "../execution/internal.h"
#include <stdlib.h>
#include <string.h>
static bool eq(struct json_object *o,const char *k,const char *v){return !strcmp(dw_text(o,k),v);}
static golem_bytes wire(struct json_object *o){const char *s=json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN);return (golem_bytes){(const uint8_t *)s,s?strlen(s):0};}
/* json-c represents JSON null as NULL; dw_add intentionally rejects it. */
static bool nullable(struct json_object *o,const char *key,struct json_object *value)
{if(!o||json_object_object_add(o,key,value)!=0){json_object_put(value);return false;}return true;}
static bool digest_is(struct json_object *o,const char *k,const golem_digest *d){golem_digest x;return dw_digest(o,k,&x)&&dw_equal(&x,d);}
static golem_status host_guard(void *ctx){return gi_review_host_guard(ctx);}
static bool block(struct json_object *a,const char *code,struct json_object *subject,struct json_object *cause)
{
    struct json_object *b=json_object_new_object();
    if(!dw_add(b,"code",json_object_new_string(code))||!nullable(b,"subject_ref",json_object_get(subject))||!nullable(b,"cause_ref",json_object_get(cause))||json_object_array_add(a,b)!=0){json_object_put(b);return false;}return true;
}
static golem_status request_shape(struct json_object *r)
{
    const char *keys[]={"schema","operation","execution_receipt_ref","semantic_reviews","authority_sequence","authority_head","prepare_operation","accept_operation"};golem_digest d;
    struct json_object *rows=dw_get(r,"semantic_reviews");
    if(!dw_keys(r,keys,8)||!eq(r,"schema","golem.intent.qa-request.v1")||(!eq(r,"operation","assess")&&!eq(r,"operation","accept"))||
        (!json_object_is_type(dw_get(r,"execution_receipt_ref"),json_type_null)&&!dw_digest(r,"execution_receipt_ref",&d))||
        !json_object_is_type(rows,json_type_array)||json_object_array_length(rows)>254||dw_uint(r,"authority_sequence")==UINT64_MAX||
        !dw_digest(r,"authority_head",&d)||!dw_digest(r,"prepare_operation",&d)||!dw_digest(r,"accept_operation",&d)||
        eq(r,"prepare_operation",dw_text(r,"accept_operation")))return GOLEM_ERR_PARSE;
    for(size_t i=0;i<json_object_array_length(rows);++i){struct json_object *row=json_object_array_get_idx(rows,i);const char *k[]={"obligation_id","review_ref"};
        if(!dw_keys(row,k,2)||!dw_id(dw_text(row,"obligation_id"))||!dw_digest(row,"review_ref",&d))return GOLEM_ERR_PARSE;
        for(size_t j=0;j<i;++j)if(eq(json_object_array_get_idx(rows,j),"obligation_id",dw_text(row,"obligation_id")))return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}
/* Receipt-specific review input has no epoch/head/result-publication reference,
 * avoiding a FINAL_VALIDATION -> own publication digest cycle. */
golem_status gi_qa_review_digest(const golem_digest *material,struct json_object *receipt,struct json_object *obligation,golem_digest *out)
{
    struct json_object *o=json_object_new_object();golem_status st=GOLEM_OK;
    if(!dw_add(o,"domain",json_object_new_string(obligation?"golem.intent.qa-semantic-input.v1":"golem.intent.qa-review-input.v1"))||
        !dw_add_digest(o,"material_sha256",material)||!nullable(o,"execution_receipt_ref",json_object_get(receipt))||
        (obligation&&!dw_add(o,"obligation",json_object_get(obligation))))st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK)st=ex_hash(o,out);json_object_put(o);return st;
}
static golem_status final_reviews(gi_product_qa_view *v,struct json_object *receipt,struct json_object *refs)
{
    gi_review_binding binding;golem_status st=gi_review_bind(&v->inputs->baseline,&binding,NULL);gi_journal *j=NULL;gi_review_state *s=NULL;
    if(st==GOLEM_OK)st=gi_journal_open(v->authority_fd,&j);
    if(st==GOLEM_OK)st=gi_review_load(j,&v->baseline_operation,&v->baseline_request,&binding.baseline,v->inputs->baseline.definitions,v->inputs->baseline.definition_count,&s);
    gi_review_status status;if(st==GOLEM_OK)st=gi_review_inspect(s,&status);
    if(st==GOLEM_OK&&(!status.active||status.open_questions||status.epoch!=v->review_epoch))st=GOLEM_ERR_STALE_RESULT;
    golem_digest input;if(st==GOLEM_OK)st=gi_qa_review_digest(&v->material,receipt,NULL,&input);
    const char *names[]={"INTEGRATION","FINAL_VALIDATION"};
    for(unsigned i=0;st==GOLEM_OK&&i<2;++i){gi_review_stage_status stage;st=gi_review_stage_inspect(s,i+5,&stage);
        if(st==GOLEM_OK&&(!stage.passed||!dw_equal(&stage.input,&input)||!dw_equal(&stage.definitions,&binding.definitions)))st=GOLEM_ERR_REQUIREMENTS_UNMET;
        if(st==GOLEM_OK)st=gi_review_host_stage(v->host,&stage.evidence,names[i],stage.producer,stage.reviewer,&input,&binding.definitions);
        if(st==GOLEM_OK){char hex[65];size_t n;st=golem_digest_format(&stage.evidence,hex,sizeof(hex),&n);
            if(st==GOLEM_OK&&json_object_array_add(refs,json_object_new_string(hex))!=0)st=GOLEM_ERR_OUT_OF_MEMORY;}
    }
    gi_review_free(s);gi_journal_close(j);return st;
}
static golem_status evaluate(golem_document_store *s,struct json_object *request,struct json_object **out,bool *eligible)
{
    gi_product_qa_view v;golem_status st=gi_product_qa_scope(s,&v);if(st!=GOLEM_OK)return st;
    struct json_object *ob=NULL,*mp=NULL,*contract=NULL,*receipt=NULL,*cp=NULL,*rows=NULL;
    struct json_object *blockers=json_object_new_array(),*reviews=json_object_new_array(),*tuple=json_object_new_object(),*body=NULL,*assessment=NULL;
    if(!blockers||!reviews||!tuple){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
    st=golem_json_parse(v.inputs->obligations,GI_CONTROL_MAX,&ob);
    if(st==GOLEM_OK)st=golem_json_parse(v.inputs->mapping,GI_CONTROL_MAX,&mp);
    if(st==GOLEM_OK)st=golem_json_parse(v.inputs->execution_contract,GI_CONTROL_MAX,&contract);
    if(st!=GOLEM_OK)goto done;
    golem_digest key;bool has=dw_digest(request,"execution_receipt_ref",&key);struct json_object *receipt_ref=dw_get(request,"execution_receipt_ref");
    const char *execution=NULL;bool stale=false,uncertain=false;
    if(has){golem_status load=ex_load(s,&key,"qa",&receipt);
        if(load!=GOLEM_OK){uncertain=true;if(!block(blockers,"RECEIPT_UNAVAILABLE",receipt_ref,NULL)){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}}
        else {
            if(eq(receipt,"status","PASS")||eq(receipt,"status","FAIL")||eq(receipt,"status","ERROR"))execution=dw_text(receipt,"status");
            else {uncertain=true;if(!block(blockers,"EXECUTION_STATUS_UNKNOWN",receipt_ref,NULL)){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}}
            golem_digest checkpoint,expected;
            golem_status fresh=dw_digest(receipt,"checkpoint",&checkpoint)?ex_load(s,&checkpoint,"checkpoint",&cp):GOLEM_ERR_PARSE;
            if(fresh==GOLEM_OK)fresh=golem_execution_contract_validate(v.inputs->execution_contract,&expected,NULL);
            if(fresh==GOLEM_OK&&(!digest_is(cp,"contract_digest",&expected)||gi_qa_manifest_matches(dw_get(receipt,"manifest"),v.native_inputs)!=GOLEM_OK))fresh=GOLEM_ERR_STALE_RESULT;
            if(fresh==GOLEM_OK)fresh=ex_receipt_current(s,receipt);
            if(fresh!=GOLEM_OK){stale=true;if(!block(blockers,"RECEIPT_NOT_CURRENT",receipt_ref,NULL)){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}}
        }
    }else if(!block(blockers,"EXECUTION_NOT_RUN",NULL,NULL)){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
    st=gi_qa_native_results(dw_get(dw_get(ob,"body"),"obligations"),dw_get(dw_get(mp,"body"),"mappings"),contract,receipt,&rows);if(st!=GOLEM_OK)goto done;
    struct json_object *obligations=dw_get(dw_get(ob,"body"),"obligations"),*semantic=dw_get(request,"semantic_reviews");size_t used=0;
    for(size_t i=0;i<json_object_array_length(rows);++i){struct json_object *row=json_object_array_get_idx(rows,i),*o=json_object_array_get_idx(obligations,i),*evidence=dw_get(row,"evidence_refs");
        if(eq(o,"evidence_kind","NATIVE_QA")){if(has&&json_object_array_add(evidence,json_object_get(receipt_ref))!=0){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}}
        else {struct json_object *r=NULL;for(size_t j=0;j<json_object_array_length(semantic);++j)if(eq(json_object_array_get_idx(semantic,j),"obligation_id",dw_text(o,"id")))r=json_object_array_get_idx(semantic,j);
            if(r){++used;golem_digest subject,review;char result[16]="UNKNOWN";
                golem_status checked=gi_qa_review_digest(&v.material,receipt_ref,o,&subject);
                if(checked==GOLEM_OK&&!dw_digest(r,"review_ref",&review))checked=GOLEM_ERR_PARSE;
                if(checked==GOLEM_OK)checked=gi_review_host_qa_result(v.host,&review,&subject,result);
                if(checked!=GOLEM_OK)strcpy(result,"UNKNOWN");
                if(json_object_array_add(reviews,json_object_get(dw_get(r,"review_ref")))!=0){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
                if(!dw_add(row,"status",json_object_new_string(result))||json_object_array_add(evidence,json_object_get(dw_get(r,"review_ref")))!=0){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
            }
        }
        if(stale&&!dw_add(row,"status",json_object_new_string("STALE"))){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
        if(!eq(row,"status","PASS")&&!block(blockers,dw_text(row,"status"),dw_get(o,"requirement_ref"),receipt_ref)){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
    }
    if(used!=json_object_array_length(semantic)&&!block(blockers,"UNUSED_SEMANTIC_REVIEW",NULL,NULL)){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
    golem_status checked=final_reviews(&v,receipt_ref,reviews);
    if(checked!=GOLEM_OK&&!block(blockers,"FINAL_REVIEW_MISSING_OR_STALE",NULL,receipt_ref)){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
    checked=gi_product_access_check(s,GI_PRODUCT_QA_INSPECTION);
    if(checked!=GOLEM_OK){stale=true;if(!block(blockers,"INPUTS_OR_AUTHORITY_CHANGED",NULL,NULL)){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}}
    if((!execution||strcmp(execution,"PASS"))&&!block(blockers,"NATIVE_QA_NOT_PASS",receipt_ref,NULL)){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
    struct json_object *binding=dw_get(s->spec,"intent_binding"),*c=dw_get(v.control,"body");
    golem_digest app,obid,mapid;st=gi_domain_digest(v.inputs->applicability,&app,NULL);
    if(st==GOLEM_OK)st=gi_domain_digest(v.inputs->obligations,&obid,NULL);
    if(st==GOLEM_OK)st=gi_domain_digest(v.inputs->mapping,&mapid,NULL);if(st!=GOLEM_OK)goto done;
    if(!dw_add(tuple,"baseline_ref",json_object_get(dw_get(binding,"baseline_ref")))||!dw_add(tuple,"policy_ref",json_object_get(dw_get(binding,"policy_ref")))||
        !dw_add(tuple,"constraint_epoch",json_object_new_int(0))||!dw_add(tuple,"constraint_scope",json_object_new_string("IMMUTABLE_LOCAL_BASELINE"))||
        !dw_add(tuple,"review_epoch",json_object_new_uint64(v.review_epoch))||!dw_add_digest(tuple,"material_sha256",&v.material)||
        !dw_add_digest(tuple,"applicability_ref",&app)||!dw_add_digest(tuple,"obligations_ref",&obid)||!dw_add_digest(tuple,"mapping_ref",&mapid)||
        !dw_add(tuple,"work_spec",json_object_get(dw_get(c,"work_spec")))||!dw_add(tuple,"work_id",json_object_get(dw_get(s->spec,"work_id")))||
        !dw_add(tuple,"selection_id",json_object_get(dw_get(contract,"selection_id")))||!dw_add(tuple,"document_generation",json_object_new_uint64(s->count+1))||
        !dw_add(tuple,"source_inputs",json_object_get(v.native_inputs))||!nullable(tuple,"checkpoint_ref",json_object_get(dw_get(receipt,"checkpoint")))||
        !nullable(tuple,"artifact_inventory",json_object_get(dw_get(receipt,"snapshot")))||!nullable(tuple,"oracle_plan_ref",json_object_get(dw_get(dw_get(ob,"body"),"oracle_plan_ref")))||
        !dw_add(tuple,"reviewer_policy_ref",json_object_get(dw_get(binding,"policy_ref")))){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
    body=json_object_new_object();assessment=json_object_new_object();
    *eligible=json_object_array_length(blockers)==0;
    if(!dw_add(body,"input_tuple",json_object_get(tuple))||!nullable(body,"execution_receipt_ref",json_object_get(receipt_ref))||
        !dw_add(body,"review_refs",json_object_get(reviews))||!dw_add(body,"obligation_results",json_object_get(rows))||!dw_add(body,"blockers",json_object_get(blockers))||
        !nullable(body,"execution_status",execution?json_object_new_string(execution):NULL)||
        !dw_add(body,"intent_qa_status",json_object_new_string(stale?"STALE":uncertain?"UNCERTAIN":"BLOCKED"))||
        !dw_add(body,"assurance",json_object_new_string("LOCAL_COOPERATIVE_REVIEWED_NOT_PROVEN"))||
        !dw_add(assessment,"schema",json_object_new_string("golem.intent.qa-assessment.v1"))||!dw_add(assessment,"project_id",json_object_get(dw_get(v.control,"project_id")))||
        !dw_add(assessment,"work_id",json_object_get(dw_get(s->spec,"work_id")))||!dw_add(assessment,"created_by_assertion",json_object_new_string("native-qc4"))||
        !dw_add(assessment,"baseline_digest",json_object_get(dw_get(binding,"baseline_ref")))||!dw_add(assessment,"body",json_object_get(body))){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
    if(wire(assessment).size>GI_CONTROL_MAX){st=GOLEM_ERR_INVALID_ARGUMENT;goto done;}
    *out=assessment;assessment=NULL;
done:
    json_object_put(ob);json_object_put(mp);json_object_put(contract);json_object_put(receipt);json_object_put(cp);json_object_put(rows);
    json_object_put(blockers);json_object_put(reviews);json_object_put(tuple);json_object_put(body);json_object_put(assessment);return st;
}
golem_status gi_qa_assess(golem_document_store *s,golem_bytes bytes,golem_execution_reply *out)
{
    if(!s||!out)return GOLEM_ERR_INVALID_ARGUMENT;struct json_object *r=NULL,*a=NULL;bool eligible=false;
    golem_status st=golem_json_parse(bytes,GI_CONTROL_MAX,&r);if(st==GOLEM_OK)st=request_shape(r);
    if(st==GOLEM_OK&&!eq(r,"operation","assess"))st=GOLEM_ERR_INVALID_ARGUMENT;
    if(st==GOLEM_OK)st=gi_product_request(s,GI_PRODUCT_QA_INSPECTION,bytes,"QA");
    if(st==GOLEM_OK)st=evaluate(s,r,&a,&eligible);
    if(st==GOLEM_OK&&eligible&&!block(dw_get(dw_get(a,"body"),"blockers"),"ACCEPTANCE_NOT_PUBLISHED",NULL,NULL))st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK)st=ex_emit(a,out);json_object_put(r);json_object_put(a);return st;
}

golem_status gi_qa_observation_apply(golem_document_store *s,struct json_object *e,const golem_digest *frame)
{
    const char *keys[]={"schema_version","type","request","request_digest","assessment","assessment_digest","prepare_operation","prepare_sequence","prepare_event","accept_operation","previous_work_head","previous_work_sequence"};
    if(!s||!frame||dw_uint(s->spec,"schema_version")!=3||s->intent_qa_count>=64||!dw_keys(e,keys,12)||dw_uint(e,"schema_version")!=1||!eq(e,"type","intent-qa-observation")||
        dw_uint(e,"previous_work_sequence")!=s->event_count||!digest_is(e,"previous_work_head",&s->last)||dw_uint(e,"prepare_sequence")==0||dw_uint(e,"prepare_sequence")==UINT64_MAX)return GOLEM_ERR_CORRUPT_JOURNAL;
    struct json_object *raw=dw_get(e,"request"),*r=NULL,*a=dw_get(e,"assessment");golem_digest request,d,assessment;
    if(!json_object_is_type(raw,json_type_string)||!dw_digest(e,"prepare_operation",&d)||!dw_digest(e,"accept_operation",&d)||!dw_digest(e,"prepare_event",&d))return GOLEM_ERR_PARSE;
    golem_bytes bytes={(const uint8_t *)json_object_get_string(raw),(size_t)json_object_get_string_len(raw)};
    golem_status st=golem_digest_bytes(bytes,&request);if(st==GOLEM_OK&&!digest_is(e,"request_digest",&request))st=GOLEM_ERR_IDENTITY_MISMATCH;
    if(st==GOLEM_OK)st=golem_json_parse(bytes,GI_CONTROL_MAX,&r);if(st==GOLEM_OK)st=request_shape(r);
    if(st==GOLEM_OK&&(!eq(r,"operation","accept")||!eq(e,"prepare_operation",dw_text(r,"prepare_operation"))||!eq(e,"accept_operation",dw_text(r,"accept_operation"))))st=GOLEM_ERR_IDENTITY_MISMATCH;
    const char *ak[]={"schema","project_id","work_id","created_by_assertion","baseline_digest","body"};
    const char *bk[]={"input_tuple","execution_receipt_ref","review_refs","obligation_results","blockers","execution_status","intent_qa_status","assurance"};
    struct json_object *body=dw_get(a,"body");
    if(st==GOLEM_OK&&(!dw_keys(a,ak,6)||!dw_keys(body,bk,8)||
        !eq(a,"created_by_assertion","native-qc4")||!eq(body,"execution_status","PASS")||
        !eq(body,"assurance","LOCAL_COOPERATIVE_REVIEWED_NOT_PROVEN")||
        !json_object_is_type(dw_get(body,"blockers"),json_type_array)||json_object_array_length(dw_get(body,"blockers"))!=0||
        !json_object_equal(dw_get(body,"execution_receipt_ref"),dw_get(r,"execution_receipt_ref"))||
        dw_uint(e,"prepare_sequence")!=dw_uint(r,"authority_sequence")+1))st=GOLEM_ERR_CORRUPT_JOURNAL;
    if(st==GOLEM_OK)st=gi_domain_digest(wire(a),&assessment,NULL);
    if(st==GOLEM_OK&&(!eq(a,"schema","golem.intent.qa-assessment.v1")||!digest_is(e,"assessment_digest",&assessment)||
        !eq(a,"work_id",dw_text(s->spec,"work_id"))||!json_object_equal(dw_get(a,"baseline_digest"),dw_get(dw_get(s->spec,"intent_binding"),"baseline_ref"))||
        !eq(dw_get(a,"body"),"intent_qa_status","BLOCKED")))st=GOLEM_ERR_CORRUPT_JOURNAL;
    for(size_t i=0;st==GOLEM_OK&&i<s->intent_qa_count;++i)if(digest_is(s->intent_qa[i],"request_digest",&request))st=GOLEM_ERR_INVALID_STATE;
    if(st==GOLEM_OK){s->intent_qa[s->intent_qa_count]=json_object_get(e);s->intent_qa_frames[s->intent_qa_count++]=*frame;s->last=*frame;++s->event_count;}
    json_object_put(r);return st;
}
static struct json_object *publication(struct json_object *observation,const golem_digest *work_frame,bool accepted)
{
    struct json_object *p=json_object_new_object();
    if(!dw_add(p,"schema",json_object_new_string(accepted?"golem.intent.qa-acceptance.v1":"golem.intent.qa-acceptance-prepared.v1"))||
        !dw_add(p,"request_digest",json_object_get(dw_get(observation,"request_digest")))||!dw_add(p,"assessment_digest",json_object_get(dw_get(observation,"assessment_digest")))||
        !dw_add(p,accepted?"prepared_event":"work_head",json_object_get(dw_get(observation,accepted?"prepare_event":"previous_work_head")))||
        !dw_add(p,"work_sequence",json_object_new_uint64(dw_uint(observation,"previous_work_sequence")+(accepted?1u:0u)))||
        (accepted&&!dw_add_digest(p,"work_observation",work_frame))){json_object_put(p);return NULL;}return p;
}
typedef struct match_publication {golem_digest operation,request,payload;bool found;} match_publication;
static golem_status match(void *ctx,const golem_digest *operation,const golem_digest *request,const gi_journal_operation *record,golem_bytes bytes)
{
    match_publication *m=ctx;if(!dw_equal(operation,&m->operation))return GOLEM_OK;
    golem_digest d;golem_status st=golem_digest_bytes(bytes,&d);
    if(st==GOLEM_OK&&(m->found||!record->committed||record->pending||record->lane!=GI_QUOTA_INTAKE||!dw_equal(request,&m->request)||!dw_equal(&d,&m->payload)))st=GOLEM_ERR_IDENTITY_MISMATCH;
    if(st==GOLEM_OK)m->found=true;return st;
}
static golem_status verify_publications(golem_document_store *s,gi_product_qa_view *v)
{
    if(!s->intent_qa_count)return GOLEM_ERR_REQUIREMENTS_UNMET;
    size_t i=s->intent_qa_count-1;struct json_object *e=s->intent_qa[i];gi_journal *j=NULL;
    golem_status st=gi_review_host_guard(v->host);if(st==GOLEM_OK)st=gi_journal_open(v->authority_fd,&j);
    for(unsigned accepted=0;st==GOLEM_OK&&accepted<2;++accepted){
        struct json_object *p=publication(e,&s->intent_qa_frames[i],accepted!=0);match_publication m={0};gi_journal_operation found;
        if(!p){st=GOLEM_ERR_OUT_OF_MEMORY;break;}
        if(!dw_digest(e,accepted?"accept_operation":"prepare_operation",&m.operation)||!dw_digest(e,"request_digest",&m.request))st=GOLEM_ERR_PARSE;
        if(st==GOLEM_OK)st=golem_digest_bytes(wire(p),&m.payload);json_object_put(p);
        if(st==GOLEM_OK)st=gi_journal_lookup(j,&m.operation,&m.request,&found);
        if(st==GOLEM_OK&&(!found.committed||found.pending||found.sequence!=dw_uint(e,"prepare_sequence")+accepted||(!accepted&&!digest_is(e,"prepare_event",&found.digest))))st=GOLEM_ERR_REQUIREMENTS_UNMET;
        if(st==GOLEM_OK)st=gi_journal_visit_payloads(j,match,&m);
        if(st==GOLEM_OK&&!m.found)st=GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    if(st==GOLEM_OK)st=gi_review_host_guard(v->host);gi_journal_close(j);return st;
}
static golem_status current(golem_document_store *s,struct json_object *r,golem_execution_reply *out)
{
    gi_product_qa_view v;golem_status st=gi_product_qa_scope(s,&v);struct json_object *assessment=NULL;bool eligible=false;
    if(st==GOLEM_OK)st=evaluate(s,r,&assessment,&eligible);
    if(st==GOLEM_OK){golem_status linked=verify_publications(s,&v);
        if(linked!=GOLEM_OK){eligible=false;if(!block(dw_get(dw_get(assessment,"body"),"blockers"),"ACCEPTANCE_PENDING_OR_INVALID",NULL,NULL))st=GOLEM_ERR_OUT_OF_MEMORY;}
        else if(s->intent_qa_count&&!json_object_equal(assessment,dw_get(s->intent_qa[s->intent_qa_count-1],"assessment"))){
            eligible=false;if(!dw_add(dw_get(assessment,"body"),"intent_qa_status",json_object_new_string("STALE"))||
                !block(dw_get(dw_get(assessment,"body"),"blockers"),"ASSESSMENT_CHANGED",NULL,NULL))st=GOLEM_ERR_OUT_OF_MEMORY;}
    }
    if(st==GOLEM_OK&&eligible&&!dw_add(dw_get(assessment,"body"),"intent_qa_status",json_object_new_string("ACCEPTED")))st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK)st=ex_emit(assessment,out);json_object_put(assessment);return st;
}
typedef struct work_guard {golem_document_store *s;struct json_object *r,*assessment;} work_guard;
static golem_status recheck_work(void *context)
{
    work_guard *g=context;struct json_object *now=NULL;bool eligible=false;golem_status st=evaluate(g->s,g->r,&now,&eligible);
    if(st==GOLEM_OK&&(!eligible||!json_object_equal(now,g->assessment)))st=GOLEM_ERR_STALE_RESULT;
    json_object_put(now);return st;
}
static golem_status accept_owned(golem_document_store *s,golem_bytes bytes,golem_execution_reply *out)
{
    if(!s||!out||!s->writable||s->poisoned||s->intent_qa_count>=64)return GOLEM_ERR_INVALID_ARGUMENT;
    /* Exact Intent selection adds a condition; it never overrides native Work
     * permission. Match completion's existing conservative policy semantics. */
    if(eq(s->spec,"permission","DENY"))return GOLEM_ERR_POLICY_DENIED;
    if(eq(s->spec,"permission","ASK_ALWAYS"))return GOLEM_ERR_APPROVAL_REQUIRED;
    struct json_object *r=NULL,*assessment=NULL,*event=NULL,*prepared=NULL,*accepted=NULL;gi_journal *j=NULL;gi_product_qa_view v;
    bool eligible=false,attempted=false;golem_digest request,assessment_id,prepare_op,accept_op,head,frame;
    gi_journal_receipt receipt={0},accept_receipt={0};
    golem_status st=golem_json_parse(bytes,GI_CONTROL_MAX,&r);if(st==GOLEM_OK)st=request_shape(r);
    if(st==GOLEM_OK&&!eq(r,"operation","accept"))st=GOLEM_ERR_INVALID_ARGUMENT;
    if(st==GOLEM_OK)st=gi_product_request(s,GI_PRODUCT_QA_INSPECTION,bytes,"QA");
    if(st==GOLEM_OK)st=gi_product_qa_scope(s,&v);
    if(st==GOLEM_OK)st=evaluate(s,r,&assessment,&eligible);
    if(st==GOLEM_OK&&!eligible){st=ex_emit(assessment,out);goto done;}
    if(st==GOLEM_OK)st=golem_digest_bytes(bytes,&request);
    if(st==GOLEM_OK)st=gi_domain_digest(wire(assessment),&assessment_id,NULL);
    if(st==GOLEM_OK&&(!dw_digest(r,"prepare_operation",&prepare_op)||!dw_digest(r,"accept_operation",&accept_op)||!dw_digest(r,"authority_head",&head)))st=GOLEM_ERR_PARSE;
    if(st==GOLEM_OK){event=json_object_new_object();
        if(!dw_add(event,"schema_version",json_object_new_int(1))||!dw_add(event,"type",json_object_new_string("intent-qa-observation"))||
            !dw_add(event,"request",json_object_new_string_len((const char *)bytes.data,(int)bytes.size))||!dw_add_digest(event,"request_digest",&request)||
            !dw_add(event,"assessment",json_object_get(assessment))||!dw_add_digest(event,"assessment_digest",&assessment_id)||
            !dw_add_digest(event,"prepare_operation",&prepare_op)||!dw_add_digest(event,"accept_operation",&accept_op)||
            !dw_add_digest(event,"previous_work_head",&s->last)||!dw_add(event,"previous_work_sequence",json_object_new_uint64(s->event_count)))st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK){prepared=publication(event,NULL,false);if(!prepared)st=GOLEM_ERR_OUT_OF_MEMORY;}
    if(st==GOLEM_OK)st=gi_journal_open(v.authority_fd,&j);
    for(unsigned i=0;st==GOLEM_OK&&i<2;++i){gi_journal_operation old;golem_status exists=gi_journal_lookup(j,i?&accept_op:&prepare_op,&request,&old);
        if(exists==GOLEM_OK)st=GOLEM_ERR_INVALID_STATE;else if(exists!=GOLEM_ERR_NOT_FOUND)st=exists;}
    if(st==GOLEM_OK){attempted=true;st=gi_journal_append(j,GI_QUOTA_INTAKE,&prepare_op,&request,dw_uint(r,"authority_sequence"),&head,wire(prepared),host_guard,v.host,&receipt);}
    gi_journal_close(j);j=NULL; /* never reacquire authority recursively from Work guard */
    if(st==GOLEM_OK&&(!dw_add(event,"prepare_sequence",json_object_new_uint64(receipt.sequence))||!dw_add_digest(event,"prepare_event",&receipt.digest)))st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK){work_guard guard={s,r,assessment};golem_digest payload;s->intent_accepting=true;
        st=recheck_work(&guard);
        if(st==GOLEM_OK)st=dw_record_prepare(s,event,GOLEM_DOCUMENT_MAX_JSON,&payload);
        if(st==GOLEM_OK)st=dw_event_write_guarded(s,&payload,&frame,recheck_work,&guard);
        if(st==GOLEM_OK)st=gi_qa_observation_apply(s,event,&frame);
        s->intent_accepting=false;
    }
    if(st==GOLEM_OK){work_guard guard={s,r,assessment};st=recheck_work(&guard);}
    if(st==GOLEM_OK){accepted=publication(event,&frame,true);if(!accepted)st=GOLEM_ERR_OUT_OF_MEMORY;}
    if(st==GOLEM_OK)st=gi_journal_open(v.authority_fd,&j);
    if(st==GOLEM_OK)st=gi_journal_append(j,GI_QUOTA_INTAKE,&accept_op,&request,receipt.sequence,&receipt.digest,wire(accepted),host_guard,v.host,&accept_receipt);
    gi_journal_close(j);j=NULL;
    if(st==GOLEM_OK)st=current(s,r,out);
    if(st!=GOLEM_OK&&attempted)s->poisoned=true;
done:
    gi_journal_close(j);json_object_put(r);json_object_put(assessment);json_object_put(event);json_object_put(prepared);json_object_put(accepted);return st;
}
golem_status gi_qa_current(golem_document_store *s,golem_execution_reply *out)
{
    if(!s||!out||!s->intent_qa_count)return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *raw=dw_get(s->intent_qa[s->intent_qa_count-1],"request"),*r=NULL;
    golem_bytes bytes={(const uint8_t *)json_object_get_string(raw),(size_t)json_object_get_string_len(raw)};
    golem_status st=golem_json_parse(bytes,GI_CONTROL_MAX,&r);if(st==GOLEM_OK)st=request_shape(r);
    if(st==GOLEM_OK)st=gi_product_request(s,GI_PRODUCT_QA_INSPECTION,bytes,"QA");
    if(st==GOLEM_OK)st=current(s,r,out);json_object_put(r);return st;
}

/* Preserve the selected request bytes across host callbacks and publication. */
golem_status gi_qa_accept(golem_document_store *s,golem_bytes bytes,golem_execution_reply *out)
{
    if(!bytes.data||!bytes.size||bytes.size>GI_CONTROL_MAX)return GOLEM_ERR_INVALID_ARGUMENT;
    uint8_t *copy=malloc(bytes.size);if(!copy)return GOLEM_ERR_OUT_OF_MEMORY;
    memcpy(copy,bytes.data,bytes.size);
    golem_status st=accept_owned(s,(golem_bytes){copy,bytes.size},out);
    free(copy);return st;
}

/* QC5 uses an already armed exact completion scope; no new action or QA run. */
golem_status gi_qa_accepted(golem_document_store *s,struct json_object **out)
{
    if(!s||!out||!s->intent_qa_count)return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *r=NULL,*a=NULL;golem_execution_reply reply={0};
    struct json_object *raw=dw_get(s->intent_qa[s->intent_qa_count-1],"request");
    golem_status st=golem_json_parse((golem_bytes){(const uint8_t *)json_object_get_string(raw),(size_t)json_object_get_string_len(raw)},GI_CONTROL_MAX,&r);
    if(st==GOLEM_OK)st=request_shape(r);
    if(st==GOLEM_OK)st=current(s,r,&reply);
    if(st==GOLEM_OK)st=golem_json_parse((golem_bytes){reply.data,reply.size},GI_CONTROL_MAX,&a);
    if(st==GOLEM_OK&&!eq(dw_get(a,"body"),"intent_qa_status","ACCEPTED"))st=GOLEM_ERR_REQUIREMENTS_UNMET;
    if(st==GOLEM_OK){*out=a;a=NULL;}
    json_object_put(a);json_object_put(r);golem_execution_reply_free(&reply);return st;
}
