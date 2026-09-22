#include "internal.h"
#include <stdlib.h>
#include <string.h>

static const struct { const char *name, *target; } classes[]={
    {"REQUIREMENTS","planning"},{"UX","ux"},{"PUBLISHING","publishing"},
    {"IMPLEMENTATION","development-plan"},{"TEST_DEFECT","qa-plan"},
    {"ENVIRONMENT",""},{"PERMISSION",""},{"BUDGET",""},{"LEASE",""},
    {"UNKNOWN",""},{"EXTERNAL_EFFECT_UNKNOWN",""}
};
static int category(const char *name)
{ for(size_t i=0;i<sizeof(classes)/sizeof(*classes);++i) if(!strcmp(name,classes[i].name)) return (int)i; return -1; }
static bool member(struct json_object *a,struct json_object *v)
{ for(size_t i=0;i<json_object_array_length(a);++i) if(json_object_equal(json_object_array_get_idx(a,i),v)) return true; return false; }
golem_status re_validate(struct json_object *r)
{
    const char *status[]={"schema_version","operation"};
    if(dw_uint(r,"schema_version")!=1) return GOLEM_ERR_UNSUPPORTED_VERSION;
    if(!strcmp(dw_text(r,"operation"),"status")) return dw_keys(r,status,2)?GOLEM_OK:GOLEM_ERR_PARSE;
    const char *keys[]={"schema_version","operation","key","expected_sequence","failure_receipt","classification",
        "hypothesis","confidence","verification","affected_requirements","evidence_refs","policy","previous_decision"};
    const char *pk[]={"max_total","max_stage","max_no_progress","max_elapsed_ms"};
    struct json_object *p=dw_get(r,"policy"),*req=dw_get(r,"affected_requirements"),*evidence=dw_get(r,"evidence_refs");
    golem_digest digest;
    bool reconsider=dw_get(r,"previous_decision")!=NULL;
    if(reconsider && !dw_digest(r,"previous_decision",&digest)) return GOLEM_ERR_PARSE;
    if(strcmp(dw_text(r,"operation"),"decide") || !dw_keys(r,keys,reconsider?13:12) || !dw_id(dw_text(r,"key")) ||
       dw_uint(r,"expected_sequence")>=RE_MAX_EVENTS || !dw_digest(r,"failure_receipt",&digest) ||
       category(dw_text(r,"classification"))<0 || !ds_prose(r,"hypothesis") || !ds_prose(r,"verification") ||
       (strcmp(dw_text(r,"confidence"),"LOW") && strcmp(dw_text(r,"confidence"),"MEDIUM") && strcmp(dw_text(r,"confidence"),"HIGH")) ||
       !ds_array(req,1,64) || !ds_array(evidence,1,8) || !dw_keys(p,pk,4) ||
       dw_uint(p,"max_total")<1 || dw_uint(p,"max_total")>32 || dw_uint(p,"max_stage")<1 || dw_uint(p,"max_stage")>16 ||
       dw_uint(p,"max_no_progress")<1 || dw_uint(p,"max_no_progress")>8 ||
       dw_uint(p,"max_elapsed_ms")<1 || dw_uint(p,"max_elapsed_ms")>86400000) return GOLEM_ERR_PARSE;
    for(size_t i=0;i<json_object_array_length(req);++i) {
        struct json_object *v=json_object_array_get_idx(req,i);
        if(!json_object_is_type(v,json_type_string) || !dw_id(json_object_get_string(v))) return GOLEM_ERR_PARSE;
        for(size_t j=0;j<i;++j) if(json_object_equal(json_object_array_get_idx(req,i),json_object_array_get_idx(req,j))) return GOLEM_ERR_PARSE;
    }
    for(size_t i=0;i<json_object_array_length(evidence);++i) {
        struct json_object *v=json_object_array_get_idx(evidence,i);
        const char *text=json_object_get_string(v);
        if(!json_object_is_type(v,json_type_string) || golem_digest_parse((golem_string_view){text,strlen(text)},&digest)!=GOLEM_OK) return GOLEM_ERR_PARSE;
        for(size_t j=0;j<i;++j) if(json_object_equal(v,json_object_array_get_idx(evidence,j))) return GOLEM_ERR_PARSE;
    }
    return member(evidence,dw_get(r,"failure_receipt"))?GOLEM_OK:GOLEM_ERR_REQUIREMENTS_UNMET;
}
golem_status golem_reentry_validate(golem_bytes b,golem_diagnostic *d)
{
    struct json_object *r=NULL; golem_status st=golem_json_parse(b,GOLEM_DOCUMENT_MAX_JSON,&r);
    if(st==GOLEM_OK) st=re_validate(r);
    json_object_put(r); return dw_report(d,st,NULL);
}
/* Ignore volatile timing, attempt IDs and agent prose. The signature describes
 * observed failed gates and their pinned requirement/case identities. */
static golem_status signature(struct json_object *qa,struct json_object *cp,golem_digest *out)
{
    struct json_object *o=json_object_new_object(),*a=json_object_new_array();
    golem_status st=o&&a?GOLEM_OK:GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *gates=dw_get(qa,"gates"),*definitions=dw_get(dw_get(cp,"contract"),"gates");
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(gates);++i) {
        struct json_object *g=json_object_array_get_idx(gates,i),*def=json_object_array_get_idx(definitions,i);
        if(!strcmp(dw_text(g,"status"),"PASS")) continue;
        struct json_object *v=json_object_new_object();
        if(!ex_text(v,"gate",dw_text(g,"gate_id")) || !ex_uint(v,"version",dw_uint(g,"version")) ||
           !ex_text(v,"reason",dw_text(g,"reason")) || !dw_add(v,"cases",json_object_get(dw_get(g,"cases"))) ||
           !dw_add(v,"requirements",json_object_get(dw_get(def,"cases")))) { json_object_put(v); st=GOLEM_ERR_OUT_OF_MEMORY; }
        else if(!wf_append(a,v)) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK && (!ex_text(o,"reason",dw_text(qa,"reason")) || !dw_add(o,"gates",json_object_get(a)))) st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK) st=ex_hash(o,out);
    json_object_put(o); json_object_put(a); return st;
}
static golem_status impact(golem_document_store *s,struct json_object *qa,int k,wf_graph *g,
    struct json_object *invalidated,struct json_object *reused)
{
    bool affected[GOLEM_DOCUMENT_MAX_REVISIONS]={false},within[GOLEM_DOCUMENT_MAX_REVISIONS]={false};
    struct json_object *docs=dw_get(dw_get(qa,"manifest"),"documents"); bool root=false;
    for(size_t i=0;i<json_object_array_length(docs);++i) {
        struct json_object *r=json_object_array_get_idx(docs,i);
        dw_entry *e=dw_find(s,dw_text(r,"document_id"),(uint32_t)dw_uint(r,"revision"));
        if(!e) return GOLEM_ERR_NOT_FOUND;
        within[e-s->entries]=true;
        if(k>=0 && !strcmp(dw_text(e->meta,"kind"),wf_kinds[k])) { affected[e-s->entries]=true; root=true; }
    }
    /* Registered QA results are descendants of qa-plan, not manifest inputs. */
    if(k>=0 && !root) return GOLEM_ERR_REQUIREMENTS_UNMET;
    for(size_t pass=0;pass<s->count;++pass) {
        bool changed=false;
        for(size_t i=0;i<s->count;++i) if(!affected[i]) {
            for(size_t j=0;j<g->nodes[i].parent_count;++j) if(affected[g->nodes[i].parents[j]]) {
                affected[i]=true; changed=true; break;
            }
        }
        if(!changed) break;
    }
    for(int kind=0;kind<8;++kind) for(size_t i=0;i<s->count;++i) {
        if(g->states[i]!=GOLEM_DOCUMENT_CURRENT || wf_kind(dw_text(s->entries[i].meta,"kind"))!=kind) continue;
        if(affected[i]) { if(!wf_append(invalidated,wf_ref(&s->entries[i]))) return GOLEM_ERR_OUT_OF_MEMORY; }
        else if(within[i]) { if(!wf_append(reused,wf_ref(&s->entries[i]))) return GOLEM_ERR_OUT_OF_MEMORY; }
    }
    return GOLEM_OK;
}
golem_status re_decide(golem_document_store *s,struct json_object *r,uint64_t now,const golem_digest *boot,struct json_object **out)
{
    golem_status st=re_validate(r);
    if(st==GOLEM_OK && (s->reentry_count>=RE_MAX_EVENTS || dw_uint(r,"expected_sequence")!=s->reentry_count)) st=GOLEM_ERR_STALE_RESULT;
    struct json_object *qa=NULL,*cp=NULL; golem_digest key,cpkey,sig,source;
    if(st==GOLEM_OK && !dw_digest(r,"failure_receipt",&key)) st=GOLEM_ERR_PARSE;
    if(st==GOLEM_OK) st=ex_load(s,&key,"qa",&qa);
    if(st==GOLEM_OK && (!strcmp(dw_text(qa,"status"),"PASS") || !dw_digest(qa,"checkpoint",&cpkey))) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    if(st==GOLEM_OK) st=ex_load(s,&cpkey,"checkpoint",&cp);
    wf_graph g={0}; if(st==GOLEM_OK) st=wf_graph_make(s,&g);
    dw_entry *selection=wf_resolve(s,dw_get(dw_get(qa,"manifest"),"selection")),*result=NULL;
    for(size_t i=0;st==GOLEM_OK && i<s->count;++i) {
        if(dw_uint(s->entries[i].meta,"schema_version")==5 && !strcmp(dw_text(s->entries[i].meta,"execution_receipt"),dw_text(r,"failure_receipt")) &&
           !strcmp(dw_text(s->entries[i].meta,"kind"),"qa-result") && g.states[i]==GOLEM_DOCUMENT_CURRENT) result=&s->entries[i];
    }
    if(st==GOLEM_OK && (!result || !selection || g.states[selection-s->entries]!=GOLEM_DOCUMENT_CURRENT)) st=GOLEM_ERR_STALE_RESULT;
    struct json_object *requirements=dw_get(r,"affected_requirements"),*evidence=dw_get(r,"evidence_refs");
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(requirements);++i)
        if(!member(dw_get(selection->meta,"requirement_ids"),json_object_array_get_idx(requirements,i))) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(evidence);++i) {
        const char *text=json_object_get_string(json_object_array_get_idx(evidence,i)); uint64_t size;
        st=golem_digest_parse((golem_string_view){text,strlen(text)},&key);
        if(st==GOLEM_OK) st=golem_evidence_verify(s->cas,&key,&size,NULL);
    }
    if(st==GOLEM_OK) st=signature(qa,cp,&sig);
    if(st==GOLEM_OK) st=ex_hash(dw_get(qa,"snapshot"),&source);
    int cat=category(dw_text(r,"classification")),k=cat<0?-1:wf_kind(classes[cat].target);
    const char *action="REVISE_DOCUMENT",*reason="CLASSIFIED_HYPOTHESIS",*target=cat<0?"":classes[cat].target;
    if(cat==10) { action="RECONCILE"; reason="EXTERNAL_EFFECT_UNCERTAIN"; }
    else if(cat==9 || !strcmp(dw_text(r,"confidence"),"LOW")) { action="INVESTIGATE"; reason="INSUFFICIENT_CONFIDENCE"; }
    else if(cat>=5) { action="BLOCKED"; reason="NON_PRODUCT_FAILURE"; }
    if(strcmp(dw_text(qa,"status"),"FAIL") && cat<5) { action="INVESTIGATE"; reason="EXECUTION_ERROR_IS_NOT_PRODUCT_CAUSAL_EVIDENCE"; }
    struct json_object *first=s->reentry_count?dw_get(s->reentries[0],"decision"):NULL;
    struct json_object *policy=dw_get(r,"policy"); size_t stages=0,repeats=0;
    if(st==GOLEM_OK && first && !json_object_equal(policy,dw_get(first,"policy"))) st=GOLEM_ERR_POLICY_DENIED;
    bool seen=false;
    for(size_t i=0;st==GOLEM_OK && i<s->reentry_count;++i) {
        struct json_object *prior=dw_get(s->reentries[i],"decision"); golem_digest a,b;
        if(!strcmp(dw_text(prior,"failure_receipt"),dw_text(r,"failure_receipt"))) seen=true;
        if(!strcmp(dw_text(prior,"target_kind"),target)) ++stages;
        if(!strcmp(dw_text(prior,"action"),"REVISE_DOCUMENT") && dw_digest(prior,"signature",&a) &&
            dw_digest(prior,"observed_source",&b) && dw_equal(&a,&sig) && dw_equal(&b,&source)) ++repeats;
    }
    if(st==GOLEM_OK && seen) {
        struct json_object *prior=dw_get(s->reentries[s->reentry_count-1],"decision"); golem_digest previous;
        bool new_evidence=false;
        for(size_t i=0;i<json_object_array_length(evidence);++i)
            if(!member(dw_get(dw_get(prior,"proposal"),"evidence_refs"),json_object_array_get_idx(evidence,i))) new_evidence=true;
        if(!dw_digest(r,"previous_decision",&previous) || !dw_equal(&previous,&s->reentry_digests[s->reentry_count-1]) ||
            strcmp(dw_text(prior,"failure_receipt"),dw_text(r,"failure_receipt")) || !new_evidence ||
            (strcmp(dw_text(prior,"action"),"INVESTIGATE") && strcmp(dw_text(prior,"reason"),"NON_PRODUCT_FAILURE"))) st=GOLEM_ERR_IDENTITY_MISMATCH;
    } else if(st==GOLEM_OK && dw_get(r,"previous_decision")) st=GOLEM_ERR_IDENTITY_MISMATCH;
    if(st==GOLEM_OK && first) {
        golem_digest firstboot;
        if(!dw_digest(first,"boot",&firstboot) || !dw_equal(boot,&firstboot) || now<dw_uint(first,"observed_ms")) {
            action="BLOCKED"; reason="CLOCK_RECONCILIATION_REQUIRED";
        } else if(now-dw_uint(first,"observed_ms")>=dw_uint(policy,"max_elapsed_ms")) { action="BLOCKED"; reason="DEADLINE_EXHAUSTED"; }
    }
    if(s->reentry_count>=dw_uint(policy,"max_total") || stages>=dw_uint(policy,"max_stage")) { action="BLOCKED"; reason="ATTEMPT_BUDGET_EXHAUSTED"; }
    if(repeats>=dw_uint(policy,"max_no_progress")) { action="BLOCKED"; reason="NO_OBSERVED_PROGRESS"; }
    if(st==GOLEM_OK && k>=0) {
        struct json_object *stage=json_object_array_get_idx(dw_get(dw_get(selection->meta,"selection"),"decisions"),(size_t)wf_stage(k));
        if(strcmp(dw_text(stage,"status"),"REQUIRED")) st=GOLEM_ERR_POLICY_DENIED;
    }
    struct json_object *o=json_object_new_object(),*invalid=json_object_new_array(),*reuse=json_object_new_array();
    if(!o || !invalid || !reuse) st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK) st=impact(s,qa,!strcmp(action,"REVISE_DOCUMENT")?k:-1,&g,invalid,reuse);
    if(st==GOLEM_OK && (!ex_uint(o,"schema_version",1) || !ex_uint(o,"sequence",s->reentry_count+1) ||
       !ex_uint(o,"document_generation",s->count+1) || !ex_uint(o,"observed_ms",now) || !dw_add_digest(o,"boot",boot) ||
       !ex_text(o,"work_id",dw_text(s->spec,"work_id")) || !dw_add(o,"selection",wf_ref(selection)) ||
       !dw_add(o,"failure_document",wf_ref(result)) || !dw_add(o,"failure_receipt",json_object_get(dw_get(r,"failure_receipt"))) ||
       !ex_text(o,"action",action) || !ex_text(o,"target_kind",target) || !ex_text(o,"reason",reason) ||
       !dw_add_digest(o,"signature",&sig) || !dw_add_digest(o,"observed_source",&source) ||
       !dw_add(o,"invalidated",json_object_get(invalid)) || !dw_add(o,"reused",json_object_get(reuse)) ||
       !dw_add(o,"proposal",json_object_get(r)) || !dw_add(o,"policy",json_object_get(policy)) ||
       !dw_add(o,"observations",json_object_get(dw_get(qa,"gates"))) ||
       !ex_text(o,"qa_status",dw_text(qa,"status")) || !ex_text(o,"qa_reason",dw_text(qa,"reason")) ||
       !ex_text(o,"usage","UNKNOWN") || !dw_add(o,"execution_authorized",json_object_new_boolean(false)))) st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK) *out=o; else json_object_put(o);
    json_object_put(invalid); json_object_put(reuse); json_object_put(qa); json_object_put(cp); wf_graph_free(s,&g); return st;
}
