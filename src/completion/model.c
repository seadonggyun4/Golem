#include "internal.h"
#include "../reentry/internal.h"
#include "../research/internal.h"
#include <string.h>

golem_status co_validate(struct json_object *r)
{
    const char *base[]={"schema_version","operation","selection_id"};
    const char *keys[]={"schema_version","operation","selection_id","key","expected_generation","issues"};
    if(dw_uint(r,"schema_version")!=1 || !dw_id(dw_text(r,"selection_id"))) return GOLEM_ERR_PARSE;
    if(!strcmp(dw_text(r,"operation"),"resume")) return dw_keys(r,base,3)?GOLEM_OK:GOLEM_ERR_PARSE;
    if(strcmp(dw_text(r,"operation"),"finalize") || !dw_keys(r,keys,6) ||
       !dw_id(dw_text(r,"key")) || !dw_uint(r,"expected_generation") ||
       dw_uint(r,"expected_generation")>GOLEM_DOCUMENT_MAX_REVISIONS+1 ||
       !ds_array(dw_get(r,"issues"),0,32)) return GOLEM_ERR_PARSE;
    struct json_object *a=dw_get(r,"issues");
    for(size_t i=0;i<json_object_array_length(a);++i) {
        struct json_object *v=json_object_array_get_idx(a,i); golem_digest d;
        const char *ik[]={"id","blocking","description","evidence_digest"};
        if(!dw_keys(v,ik,4) || !dw_id(dw_text(v,"id")) ||
           !json_object_is_type(dw_get(v,"blocking"),json_type_boolean) ||
           !ds_prose(v,"description") || strlen(dw_text(v,"description"))>4096 ||
           !dw_digest(v,"evidence_digest",&d)) return GOLEM_ERR_PARSE;
        for(size_t j=0;j<i;++j)
            if(!strcmp(dw_text(v,"id"),dw_text(json_object_array_get_idx(a,j),"id"))) return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}
golem_status golem_completion_validate(golem_bytes b,golem_diagnostic *d)
{
    struct json_object *r=NULL; golem_status st=golem_json_parse(b,GOLEM_DOCUMENT_MAX_JSON,&r);
    if(st==GOLEM_OK) st=co_validate(r);
    json_object_put(r); return dw_report(d,st,NULL);
}
/* Pure acceptance relative to the replay prefix; live source observation is
 * deliberately optional so later edits cannot invalidate historical replay. */
golem_status co_evaluate(golem_document_store *s,struct json_object *r,bool live,struct json_object **out)
{
    golem_status st=co_validate(r);
    if(st==GOLEM_OK && (strcmp(dw_text(r,"operation"),"finalize") ||
       dw_uint(r,"expected_generation")!=s->count+1)) st=GOLEM_ERR_STALE_RESULT;
    dw_entry *plan=dw_find(s,dw_text(r,"selection_id"),0);
    if(st==GOLEM_OK && (!plan || dw_uint(plan->meta,"schema_version")!=3 ||
       strcmp(dw_text(dw_get(plan->meta,"selection"),"mode"),"development"))) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    const char *action=NULL,*kind=NULL,*reason=NULL;
    if(st==GOLEM_OK) st=re_next(s,&action,&kind,&reason);
    if(st==GOLEM_OK && action) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *docs=NULL,*qa=NULL,*dev=NULL,*cp=NULL,*assessment=NULL;
    if(st==GOLEM_OK) st=wf_completed_documents(s,dw_text(r,"selection_id"),&docs);
    golem_digest qa_key={0},dev_key={0},cp_key={0};
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(docs);++i) {
        struct json_object *ref=json_object_array_get_idx(docs,i);
        dw_entry *e=dw_find(s,dw_text(ref,"document_id"),(uint32_t)dw_uint(ref,"revision"));
        if(!e) { st=GOLEM_ERR_CORRUPT_JOURNAL; break; }
        const char *k=dw_text(e->meta,"kind");
        bool isqa=!strcmp(k,"qa-result"),isdev=!strcmp(k,"development-result");
        if(isqa || isdev) {
            if(dw_uint(e->meta,"schema_version")!=5) { st=GOLEM_ERR_REQUIREMENTS_UNMET; break; }
            if((isqa && qa) || (isdev && dev)) { st=GOLEM_ERR_INVALID_STATE; break; }
            golem_digest *key=isqa?&qa_key:&dev_key;
            if(!dw_digest(e->meta,"execution_receipt",key)) st=GOLEM_ERR_PARSE;
            if(st==GOLEM_OK) st=ex_load(s,key,isqa?"qa":"development",isqa?&qa:&dev);
            if(st==GOLEM_OK && live) st=ex_live(s,e->meta);
        }
    }
    if(st==GOLEM_OK && (!qa || !dev || strcmp(dw_text(qa,"status"),"PASS") ||
       !json_object_equal(dw_get(qa,"snapshot"),dw_get(dev,"snapshot")) ||
       !json_object_equal(dw_get(qa,"checkpoint"),dw_get(dev,"checkpoint")))) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    if(st==GOLEM_OK && !dw_digest(qa,"checkpoint",&cp_key)) st=GOLEM_ERR_PARSE;
    if(st==GOLEM_OK) st=ex_load(s,&cp_key,"checkpoint",&cp);
    struct json_object *gates=dw_get(qa,"gates"),*definitions=dw_get(dw_get(cp,"contract"),"gates");
    if(st==GOLEM_OK && (!json_object_array_length(gates) ||
       json_object_array_length(gates)!=json_object_array_length(definitions))) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(gates);++i) {
        struct json_object *g=json_object_array_get_idx(gates,i),*def=json_object_array_get_idx(definitions,i);
        if(strcmp(dw_text(g,"status"),"PASS") || strcmp(dw_text(g,"gate_id"),dw_text(def,"id")) ||
           dw_uint(g,"version")!=dw_uint(def,"version")) st=GOLEM_ERR_REQUIREMENTS_UNMET;
        struct json_object *cases=dw_get(def,"cases"),*actual=dw_get(g,"cases");
        if(json_object_array_length(cases)!=json_object_array_length(actual)) st=GOLEM_ERR_REQUIREMENTS_UNMET;
        for(size_t j=0;st==GOLEM_OK && j<json_object_array_length(cases);++j) {
            const char *id=dw_text(json_object_array_get_idx(cases,j),"id"); size_t matches=0;
            for(size_t k=0;k<json_object_array_length(actual);++k) {
                struct json_object *c=json_object_array_get_idx(actual,k);
                if(!strcmp(id,dw_text(c,"id")) && !strcmp(dw_text(c,"status"),"PASS")) ++matches;
            }
            if(matches!=1) st=GOLEM_ERR_REQUIREMENTS_UNMET;
        }
    }
    struct json_object *issues=dw_get(r,"issues");
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(issues);++i) {
        struct json_object *v=json_object_array_get_idx(issues,i); golem_digest key; uint64_t size;
        if(json_object_get_boolean(dw_get(v,"blocking"))) st=GOLEM_ERR_REQUIREMENTS_UNMET;
        if(st==GOLEM_OK && !dw_digest(v,"evidence_digest",&key)) st=GOLEM_ERR_PARSE;
        if(st==GOLEM_OK) st=golem_evidence_verify(s->cas,&key,&size,NULL);
    }
    struct json_object *outcomes=NULL;
    if(st==GOLEM_OK) st=rs_outcome_completion(s,dw_text(r,"selection_id"),&qa_key,&outcomes);
    struct json_object *policy=json_object_new_object(); golem_digest pd;
    if(!policy || !ex_uint(policy,"schema_version",1) ||
       !ex_text(policy,"predicate","golem.completion.development.v1") ||
       !dw_add(policy,"contract_digest",json_object_get(dw_get(cp,"contract_digest"))) ||
       !dw_add(policy,"work_acceptance",json_object_get(dw_get(s->spec,"acceptance")))) {
        if(st==GOLEM_OK) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK) st=ex_hash(policy,&pd);
    if(st==GOLEM_OK) {
        assessment=json_object_new_object();
        if(!ex_text(assessment,"work_id",dw_text(s->spec,"work_id")) ||
           !ex_text(assessment,"goal",dw_text(s->spec,"request")) ||
           !ex_uint(assessment,"generation",s->count+1) || !dw_add(assessment,"selection",wf_ref(plan)) ||
           !dw_add(assessment,"scope",json_object_get(dw_get(dw_get(plan->meta,"selection"),"scope"))) ||
           !dw_add(assessment,"documents",json_object_get(docs)) ||
           !dw_add(assessment,"stage_decisions",json_object_get(dw_get(dw_get(plan->meta,"selection"),"decisions"))) ||
           !dw_add(assessment,"snapshot",json_object_get(dw_get(qa,"snapshot"))) ||
           !dw_add(assessment,"gates",json_object_get(gates)) || !dw_add_digest(assessment,"qa_receipt",&qa_key) ||
           !dw_add(assessment,"gate_definitions",json_object_get(definitions)) ||
           !dw_add(assessment,"requirement_ids",json_object_get(dw_get(plan->meta,"requirement_ids"))) ||
           !dw_add_digest(assessment,"development_receipt",&dev_key) || !dw_add_digest(assessment,"checkpoint",&cp_key) ||
           !dw_add(assessment,"policy",json_object_get(policy)) || !dw_add_digest(assessment,"policy_digest",&pd) ||
           !dw_add(assessment,"unresolved_nonblocking_items",json_object_get(issues)) ||
           !ex_uint(assessment,"reentry_count",s->reentry_count) ||
           !dw_add(assessment,"independent_review",json_object_new_boolean(false)) ||
           !ex_text(assessment,"assurance","DECLARED_GATES_ONLY")) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK && json_object_array_length(outcomes) &&
       !dw_add(assessment,"outcome_adjudications",json_object_get(outcomes))) st=GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(outcomes);
    if(st==GOLEM_OK) *out=assessment; else json_object_put(assessment);
    json_object_put(policy); json_object_put(docs); json_object_put(qa); json_object_put(dev); json_object_put(cp);
    return st;
}
