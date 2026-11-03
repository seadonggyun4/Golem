#include "qa_result.h"
#include "product_access.h"
#include "../document/internal.h"
#include "../execution/internal.h"
#include "../completion/internal.h"
#include <stdlib.h>
#include <string.h>
struct gi_product_access {
    golem_document_store *work;int authority_fd;gi_review_host *host;
    struct json_object *control,*material,*request;
    gi_qa_paths_inputs inputs;golem_bytes *definitions,*objects;gi_source_input *sources;
    size_t object_count;golem_digest material_digest;
    bool armed,busy,attempted;
};
static bool eq(struct json_object *o,const char *k,const char *v){return !strcmp(dw_text(o,k),v);}
static bool is_digest(struct json_object *o,const char *k,const golem_digest *d)
{golem_digest got;return dw_digest(o,k,&got)&&dw_equal(&got,d);}
static golem_bytes raw(struct json_object *o)
{if(!json_object_is_type(o,json_type_string))return (golem_bytes){0};return (golem_bytes){(const uint8_t *)json_object_get_string(o),(size_t)json_object_get_string_len(o)};}
static golem_status guard(void *p){return gi_review_host_guard(p);}
static const char *stages[]={"REQUIREMENTS","DESIGN","TASK_DECOMPOSITION","IMPLEMENTATION","TEST_DESIGN","INTEGRATION","FINAL_VALIDATION"};
static golem_status acceptance_map(gi_product_access *a,struct json_object *contract)
{
    struct json_object *ob=NULL,*mp=NULL;golem_status st=golem_json_parse(a->inputs.obligations,GI_CONTROL_MAX,&ob);
    if(st==GOLEM_OK)st=golem_json_parse(a->inputs.mapping,GI_CONTROL_MAX,&mp);
    struct json_object *mappings=dw_get(dw_get(mp,"body"),"mappings"),*obligations=dw_get(dw_get(ob,"body"),"obligations"),
        *enrollment=dw_get(dw_get(dw_get(a->work->intent_enrollment,"enrollment"),"body"),"requirement_mapping"),*gates=dw_get(contract,"gates");
    for(size_t i=0;st==GOLEM_OK&&i<json_object_array_length(mappings);++i){
        struct json_object *m=json_object_array_get_idx(mappings,i),*ref=NULL;const char *acceptance=NULL;
        for(size_t j=0;j<json_object_array_length(obligations);++j){struct json_object *o=json_object_array_get_idx(obligations,j);
            if(eq(o,"id",dw_text(m,"obligation_id")))ref=dw_get(o,"requirement_ref");}
        for(size_t j=0;j<json_object_array_length(enrollment);++j){struct json_object *e=json_object_array_get_idx(enrollment,j);
            if(ref&&json_object_equal(ref,dw_get(e,"requirement_ref")))acceptance=dw_text(e,"acceptance_id");}
        bool found=false;
        for(size_t j=0;acceptance&&j<json_object_array_length(gates);++j){struct json_object *g=json_object_array_get_idx(gates,j);
            if(!eq(g,"id",dw_text(m,"gate_id"))||!json_object_equal(dw_get(g,"version"),dw_get(m,"gate_version")))continue;
            struct json_object *cases=dw_get(g,"cases");for(size_t k=0;k<json_object_array_length(cases);++k){struct json_object *c=json_object_array_get_idx(cases,k);
                if(eq(c,"id",dw_text(m,"case_id"))&&eq(c,"requirement_id",acceptance))found=true;}}
        if(!found)st=GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    json_object_put(ob);json_object_put(mp);return st;
}
static golem_status check(gi_product_access *a,gi_product_boundary boundary)
{
    if(!a->armed)return GOLEM_ERR_POLICY_DENIED;

    struct json_object *c=dw_get(a->control,"body"),*m=dw_get(a->material,"body");
    bool completion=eq(c,"channel","COMPLETION");
    bool qa=completion||eq(c,"boundary","QA_DISPATCH")||eq(c,"boundary","QA_ACCEPTANCE");
    if(boundary!=GI_PRODUCT_PUBLICATION&&!(boundary==GI_PRODUCT_QA_INSPECTION&&(eq(c,"channel","QA")||completion))&&boundary!=(completion?GI_PRODUCT_COMPLETION:eq(c,"boundary","QA_ACCEPTANCE")?GI_PRODUCT_QA_ACCEPTANCE:qa?GI_PRODUCT_QA_DISPATCH:GI_PRODUCT_DEVELOPMENT))return GOLEM_ERR_POLICY_DENIED;
    golem_document_store *s=a->work;
    bool original=s->event_count==dw_uint(c,"work_sequence")&&is_digest(c,"work_head",&s->last);
    bool own_observation=false;
    if(s->intent_qa_count){struct json_object *last=s->intent_qa[s->intent_qa_count-1];
        own_observation=s->event_count==dw_uint(c,"work_sequence")+1&&dw_equal(&s->last,&s->intent_qa_frames[s->intent_qa_count-1])&&
            json_object_equal(dw_get(last,"previous_work_head"),dw_get(c,"work_head"))&&
            json_object_equal(dw_get(last,"request_digest"),dw_get(c,"request_digest"));}
    if(!s->writable||s->poisoned||(!original&&!(eq(c,"channel","QA")&&own_observation)))return GOLEM_ERR_STALE_RESULT;
    golem_digest registration,baseline,policy;
    struct json_object *binding_ref=dw_get(s->spec,"intent_binding");
    if(!dw_digest(binding_ref,"registration_ref",&registration)||!dw_digest(binding_ref,"baseline_ref",&baseline)||!dw_digest(binding_ref,"policy_ref",&policy))return GOLEM_ERR_PARSE;
    golem_status st=gi_review_host_binding(a->host,&registration,&baseline,&policy);
    golem_digest spec;if(st==GOLEM_OK)st=ex_hash(s->spec,&spec);
    if(st==GOLEM_OK&&!is_digest(c,"work_spec",&spec))st=GOLEM_ERR_IDENTITY_MISMATCH;
    if(st==GOLEM_OK)st=gi_product_enrollment_verify(s,a->authority_fd,guard,a->host);
    gi_qa_paths_result paths;
    if(st==GOLEM_OK)st=gi_qa_paths_resolve(&a->inputs,a->objects,a->object_count,a->host,&paths,NULL);
    if(st==GOLEM_OK&&(!paths.structurally_complete||paths.unsupported_references))st=GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *contract=NULL,*current=NULL;
    if(st==GOLEM_OK)st=golem_json_parse(a->inputs.execution_contract,GI_CONTROL_MAX,&contract);
    if(st==GOLEM_OK)st=acceptance_map(a,contract);
    if(st==GOLEM_OK)st=ex_inputs(s,contract,dw_text(c,"input_kind"),&current);
    if(st==GOLEM_OK&&!json_object_equal(current,dw_get(m,"native_inputs")))st=GOLEM_ERR_STALE_RESULT;
    json_object_put(contract);json_object_put(current);
    gi_journal *j=NULL;gi_review_state *review=NULL;gi_review_binding binding={0};
    golem_digest base_op,base_request;
    if(st==GOLEM_OK&&(!dw_digest(c,"baseline_operation",&base_op)||!dw_digest(c,"baseline_request",&base_request)))st=GOLEM_ERR_PARSE;
    if(st==GOLEM_OK)st=gi_review_bind(&a->inputs.baseline,&binding,NULL);
    if(st==GOLEM_OK&&!is_digest(a->control,"baseline_digest",&binding.baseline))st=GOLEM_ERR_IDENTITY_MISMATCH;
    for(size_t i=binding.requirements;st==GOLEM_OK&&i<a->inputs.baseline.definition_count;++i){
        struct json_object *constraint=NULL;st=golem_json_parse(a->definitions[i],GI_CONTROL_MAX,&constraint);
        if(st==GOLEM_OK&&!eq(dw_get(constraint,"body"),"scope","LOCAL"))st=GOLEM_ERR_UNSUPPORTED_VERSION;
        json_object_put(constraint);
    }
    if(st==GOLEM_OK)st=gi_journal_open(a->authority_fd,&j);
    if(st==GOLEM_OK)st=gi_review_load(j,&base_op,&base_request,&binding.baseline,a->definitions,a->inputs.baseline.definition_count,&review);
    gi_review_status status;
    if(st==GOLEM_OK)st=gi_review_inspect(review,&status);
    if(st==GOLEM_OK&&(!status.active||status.open_questions||status.epoch!=dw_uint(c,"review_epoch")||!is_digest(dw_get(dw_get(s->intent_enrollment,"enrollment"),"body"),"activation_decision_ref",&status.activation_decision)))st=GOLEM_ERR_STALE_RESULT;
    if(st==GOLEM_OK)st=gi_review_host_activation(a->host,&status.activation_decision);
    unsigned needed=(boundary==GI_PRODUCT_QA_ACCEPTANCE||boundary==GI_PRODUCT_COMPLETION)?7u:qa?5u:3u;
    golem_digest review_input=a->material_digest;
    for(unsigned i=0;st==GOLEM_OK&&i<needed;++i){gi_review_stage_status stage;
        if(i==5){if(!a->request)st=GOLEM_ERR_POLICY_DENIED;
            else if(completion){struct json_object *q=NULL;
                if(!s->intent_qa_count)st=GOLEM_ERR_REQUIREMENTS_UNMET;
                else st=golem_json_parse(raw(dw_get(s->intent_qa[s->intent_qa_count-1],"request")),GI_CONTROL_MAX,&q);
                if(st==GOLEM_OK)st=gi_qa_review_digest(&a->material_digest,dw_get(q,"execution_receipt_ref"),NULL,&review_input);
                json_object_put(q);
            }else st=gi_qa_review_digest(&a->material_digest,dw_get(a->request,"execution_receipt_ref"),NULL,&review_input);}
        if(st!=GOLEM_OK)break;
        st=gi_review_stage_inspect(review,i,&stage);
        if(st==GOLEM_OK&&(!stage.passed||!dw_equal(&stage.input,&review_input)||!dw_equal(&stage.definitions,&binding.definitions)))st=GOLEM_ERR_REQUIREMENTS_UNMET;
        if(st==GOLEM_OK)st=gi_review_host_stage(a->host,&stage.evidence,stages[i],stage.producer,stage.reviewer,&review_input,&binding.definitions);
    }
    if(st==GOLEM_OK)st=gi_review_host_guard(a->host);
    gi_review_free(review);gi_journal_close(j);return st;
}
golem_status gi_product_access_check(golem_document_store *s,gi_product_boundary boundary)
{
    if(!s||!s->intent_access)return GOLEM_ERR_POLICY_DENIED;
    gi_product_access *a=s->intent_access;
    if(a->work!=s)return GOLEM_ERR_POLICY_DENIED;
    /* Busy covers the full caller, while check itself remains non-reentrant. */
    if(a->busy)return GOLEM_ERR_INVALID_STATE;
    a->busy=true;golem_status st=check(a,boundary);a->busy=false;return st;
}
golem_status gi_product_request(golem_document_store *s,gi_product_boundary boundary,golem_bytes request,const char *channel)
{
    if(!s||!channel)return GOLEM_ERR_INVALID_ARGUMENT;
    if(dw_uint(s->spec,"schema_version")!=3)return GOLEM_OK;
    gi_product_access *a=s->intent_access;if(!a||a->attempted)return GOLEM_ERR_POLICY_DENIED;
    a->attempted=true;
    golem_digest d;golem_status st=golem_digest_bytes(request,&d);struct json_object *c=dw_get(a->control,"body");
    if(st==GOLEM_OK&&(!is_digest(c,"request_digest",&d)||!eq(c,"channel",channel)))st=GOLEM_ERR_POLICY_DENIED;
    if(st==GOLEM_OK)st=golem_json_parse(request,GI_CONTROL_MAX,&a->request);
    if(st==GOLEM_OK&&eq(c,"channel","EXECUTION")){
        bool run=eq(a->request,"operation","run");
        if((run&&(!eq(c,"boundary","QA_DISPATCH")||!eq(c,"input_kind","qa-result")))||
            (!run&&(!eq(c,"boundary","DEVELOPMENT")||!eq(c,"input_kind","development-result"))))st=GOLEM_ERR_POLICY_DENIED;
        golem_digest expected,actual;struct json_object *cp=NULL;
        if(st==GOLEM_OK)st=golem_execution_contract_validate(a->inputs.execution_contract,&expected,NULL);
        if(st==GOLEM_OK&&eq(a->request,"operation","prepare"))st=ex_hash(dw_get(a->request,"contract"),&actual);
        else if(st==GOLEM_OK){golem_digest key;
            if(!dw_digest(a->request,"checkpoint",&key))st=GOLEM_ERR_PARSE;
            if(st==GOLEM_OK)st=ex_load(s,&key,"checkpoint",&cp);
            if(st==GOLEM_OK&&!dw_digest(cp,"contract_digest",&actual))st=GOLEM_ERR_PARSE;
        }
        if(st==GOLEM_OK&&!dw_equal(&expected,&actual))st=GOLEM_ERR_IDENTITY_MISMATCH;json_object_put(cp);
    }
    if(st==GOLEM_OK){a->armed=true;st=gi_product_access_check(s,boundary);}
    return st; /* one selected request per scope; failure is not retried */
}
void gi_product_access_close(gi_product_access *a)
{
    if(!a)return;
    if(a->work&&a->work->intent_access==a)a->work->intent_access=NULL;
    json_object_put(a->control);json_object_put(a->material);json_object_put(a->request);free(a->definitions);free(a->objects);free(a->sources);free(a);
}
golem_status gi_product_access_open(golem_document_store *s,int fd,gi_review_host *host,golem_bytes control,golem_bytes material,gi_product_access **out)
{
    if(!s||!host||!out||s->intent_access||!s->intent_enrollment||dw_uint(s->spec,"schema_version")!=3)return GOLEM_ERR_INVALID_ARGUMENT;
    gi_product_access *a=calloc(1,sizeof(*a));if(!a)return GOLEM_ERR_OUT_OF_MEMORY;
    a->work=s;a->host=host;a->authority_fd=fd;
    golem_status st=gi_review_host_selected(host,control);
    if(st==GOLEM_OK)st=golem_json_parse(control,GI_CONTROL_MAX,&a->control);
    if(st==GOLEM_OK)st=golem_json_parse(material,GI_DISPATCH_MAX,&a->material);
    if(st==GOLEM_OK)st=golem_digest_bytes(material,&a->material_digest);
    const char *ck[]={"schema","project_id","work_id","baseline_digest","body"};
    const char *bk[]={"material_sha256","work_spec","work_sequence","work_head","review_epoch","baseline_operation","baseline_request","boundary","channel","request_digest","input_kind"};
    const char *mk[]={"baseline","sources","definitions","applicability","obligations","mapping","execution_contract","objects","native_inputs"};
    struct json_object *c=dw_get(a->control,"body"),*m=dw_get(a->material,"body");
    golem_digest d;
    if(st==GOLEM_OK&&(!dw_keys(a->control,ck,5)||!eq(a->control,"schema","golem.intent.product-access.v1")||
        !dw_keys(a->material,ck,5)||!eq(a->material,"schema","golem.intent.product-material.v1")||!dw_keys(c,bk,11)||!dw_keys(m,mk,9)||
        !eq(a->control,"work_id",dw_text(s->spec,"work_id"))||!eq(a->material,"work_id",dw_text(s->spec,"work_id"))||
        !eq(a->control,"project_id",dw_text(a->material,"project_id"))||
        !json_object_equal(dw_get(a->control,"baseline_digest"),dw_get(dw_get(s->spec,"intent_binding"),"baseline_ref"))||
        !json_object_equal(dw_get(a->material,"baseline_digest"),dw_get(a->control,"baseline_digest"))||
        !is_digest(c,"material_sha256",&a->material_digest)||!dw_digest(c,"request_digest",&d)||!dw_digest(c,"work_spec",&d)||!dw_digest(c,"work_head",&d)||
        dw_uint(c,"work_sequence")==UINT64_MAX||dw_uint(c,"review_epoch")==UINT64_MAX||
        (!eq(c,"boundary","DEVELOPMENT")&&!eq(c,"boundary","QA_DISPATCH")&&!eq(c,"boundary","QA_ACCEPTANCE")&&!eq(c,"boundary","COMPLETION"))||
        (!eq(c,"channel","SESSION")&&!eq(c,"channel","EXECUTION")&&!eq(c,"channel","QA")&&!eq(c,"channel","COMPLETION"))||
        (!eq(c,"input_kind","development-result")&&!eq(c,"input_kind","qa-result"))||
        (eq(c,"channel","SESSION")&&(!eq(c,"boundary","DEVELOPMENT")||!eq(c,"input_kind","development-result")))||
        (eq(c,"channel","QA")!=eq(c,"boundary","QA_ACCEPTANCE"))||
        (eq(c,"channel","COMPLETION")!=eq(c,"boundary","COMPLETION"))||
        ((eq(c,"channel","QA")||eq(c,"channel","COMPLETION"))&&!eq(c,"input_kind","qa-result"))))st=GOLEM_ERR_PARSE;
    struct json_object *sources=dw_get(m,"sources"),*defs=dw_get(m,"definitions"),*objects=dw_get(m,"objects");
    if(st==GOLEM_OK&&(!json_object_is_type(sources,json_type_array)||!json_object_array_length(sources)||json_object_array_length(sources)>64||
        !json_object_is_type(defs,json_type_array)||json_object_array_length(defs)>256||!json_object_is_type(objects,json_type_array)||json_object_array_length(objects)>4096))st=GOLEM_ERR_OVERFLOW;
    if(st==GOLEM_OK){
        a->sources=calloc(json_object_array_length(sources),sizeof(*a->sources));a->definitions=calloc(json_object_array_length(defs)+1,sizeof(*a->definitions));
        a->objects=calloc(json_object_array_length(objects)+1,sizeof(*a->objects));if(!a->sources||!a->definitions||!a->objects)st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK){
        a->inputs.baseline.baseline=raw(dw_get(m,"baseline"));a->inputs.baseline.sources=a->sources;
        a->inputs.baseline.source_count=json_object_array_length(sources);a->inputs.baseline.definitions=a->definitions;a->inputs.baseline.definition_count=json_object_array_length(defs);
        a->inputs.applicability=raw(dw_get(m,"applicability"));a->inputs.obligations=raw(dw_get(m,"obligations"));a->inputs.mapping=raw(dw_get(m,"mapping"));a->inputs.execution_contract=raw(dw_get(m,"execution_contract"));
        for(size_t i=0;i<a->inputs.baseline.source_count;++i){struct json_object *o=json_object_array_get_idx(sources,i);const char *keys[]={"control","text"};
            if(!dw_keys(o,keys,2)){st=GOLEM_ERR_PARSE;break;}a->sources[i]=(gi_source_input){raw(dw_get(o,"control")),raw(dw_get(o,"text"))};}
        for(size_t i=0;i<a->inputs.baseline.definition_count;++i)a->definitions[i]=raw(json_object_array_get_idx(defs,i));
        a->object_count=json_object_array_length(objects);for(size_t i=0;i<a->object_count;++i)a->objects[i]=raw(json_object_array_get_idx(objects,i));
    }
    if(st==GOLEM_OK){s->intent_access=a;a->armed=true;st=gi_product_access_check(s,(eq(c,"boundary","QA_ACCEPTANCE")||eq(c,"boundary","COMPLETION"))?GI_PRODUCT_QA_INSPECTION:eq(c,"boundary","QA_DISPATCH")?GI_PRODUCT_QA_DISPATCH:GI_PRODUCT_DEVELOPMENT);a->armed=false;}
    if(st==GOLEM_OK)*out=a;else gi_product_access_close(a);return st;
}

golem_status gi_product_access_record(golem_document_store *s,struct json_object *event)
{
    if(!s||!s->intent_access)return s&&s->intent_enrollment?GOLEM_ERR_UNSUPPORTED_VERSION:GOLEM_ERR_REQUIREMENTS_UNMET;
    gi_product_access *a=s->intent_access;struct json_object *c=dw_get(a->control,"body");
    bool permitted=false;
    if(eq(c,"channel","SESSION")) {
        golem_digest request;if(dw_digest(c,"request_digest",&request)&&is_digest(event,"request_digest",&request))permitted=true;
    } else if(eq(c,"channel","COMPLETION")) {
        permitted=eq(event,"type","completion")&&eq(a->request,"operation","finalize")&&json_object_equal(dw_get(event,"request"),a->request);
    } else if(eq(c,"channel","EXECUTION")) {
        if(eq(event,"type","checkpoint")&&eq(a->request,"operation","prepare"))permitted=true;
        else if((eq(event,"type","development")&&eq(a->request,"operation","finish"))||
            (eq(event,"type","qa")&&eq(a->request,"operation","run")))
            permitted=json_object_equal(dw_get(event,"checkpoint"),dw_get(a->request,"checkpoint"));
    }
    if(!permitted)return GOLEM_ERR_POLICY_DENIED;
    golem_status st=gi_product_access_check(s,eq(c,"channel","COMPLETION")?GI_PRODUCT_COMPLETION:GI_PRODUCT_PUBLICATION);
    if(st==GOLEM_OK&&eq(c,"channel","COMPLETION")){
        struct json_object *assessment=NULL,*boundary=NULL;const char *action=NULL;
        st=co_evaluate(s,dw_get(event,"request"),true,&assessment);
        if(st==GOLEM_OK&&!json_object_equal(assessment,dw_get(dw_get(event,"record"),"assessment")))st=GOLEM_ERR_STALE_RESULT;
        if(st==GOLEM_OK)st=co_quiescent(s,&action,&boundary);
        if(st==GOLEM_OK&&(action||!json_object_equal(boundary,dw_get(dw_get(event,"record"),"boundary"))))st=GOLEM_ERR_INCOMPLETE_WORK;
        json_object_put(assessment);json_object_put(boundary);
    }
    return st;
}

golem_status gi_product_qa_scope(golem_document_store *s,gi_product_qa_view *out)
{
    if(!s||!out||!s->intent_access)return GOLEM_ERR_INVALID_ARGUMENT;
    gi_product_access *a=s->intent_access;struct json_object *c=dw_get(a->control,"body");
    if(!a->armed||(!eq(c,"channel","QA")&&!eq(c,"channel","COMPLETION")))return GOLEM_ERR_POLICY_DENIED;
    gi_product_qa_view v={0};v.inputs=&a->inputs;v.host=a->host;v.authority_fd=a->authority_fd;v.material=a->material_digest;
    v.review_epoch=dw_uint(c,"review_epoch");v.control=a->control;v.native_inputs=dw_get(dw_get(a->material,"body"),"native_inputs");
    if(!dw_digest(c,"baseline_operation",&v.baseline_operation)||!dw_digest(c,"baseline_request",&v.baseline_request))return GOLEM_ERR_PARSE;
    *out=v;return GOLEM_OK;
}
