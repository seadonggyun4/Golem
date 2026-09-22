#include "internal.h"
#include "../discovery/internal.h"
#include "../execution/internal.h"
#include "../reentry/internal.h"
#include "../completion/internal.h"
#include <stdlib.h>
#include <string.h>

static const char *state_name(golem_document_freshness state)
{ return state==GOLEM_DOCUMENT_CURRENT?"CURRENT":state==GOLEM_DOCUMENT_STALE?"STALE":"SUPERSEDED"; }
static golem_status emit(struct json_object *o,void *buffer,size_t capacity,size_t *required)
{
    if(!required || (!buffer && capacity)) return GOLEM_ERR_INVALID_ARGUMENT;
    const char *text=json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN);
    if(!text) return GOLEM_ERR_OUT_OF_MEMORY;
    size_t n=strlen(text);
    if(n>GOLEM_DOCUMENT_MAX_JSON) return GOLEM_ERR_BUDGET_EXHAUSTED;
    *required=n;
    if(capacity<n) return GOLEM_ERR_BUFFER_TOO_SMALL;
    memcpy(buffer,text,n); return GOLEM_OK;
}
golem_status wf_integrity(golem_document_store *s,size_t i,uint64_t *size)
{
    dw_entry *e=&s->entries[i]; uint64_t ignored;
    golem_status st=golem_evidence_verify(s->cas,&e->request_digest,&ignored,NULL);
    if(st==GOLEM_OK) st=golem_evidence_verify(s->cas,&e->result.body_digest,size,NULL);
    if(st==GOLEM_OK) st=ds_evidence(s,e->meta);
    if(st==GOLEM_OK) { golem_status p=dw_project(s,e,false); if(p!=GOLEM_OK && p!=GOLEM_ERR_NOT_FOUND) st=p; }
    return st;
}
golem_status wf_closure(golem_document_store *s,wf_graph *g,const size_t *roots,size_t count,bool *selected)
{
    size_t queue[GOLEM_DOCUMENT_MAX_REVISIONS],read=0,write=0;
    memset(selected,0,s->count*sizeof(*selected));
    for(size_t i=0;i<count;++i) {
        if(roots[i]>=s->count) return GOLEM_ERR_INVALID_GRAPH;
        if(!selected[roots[i]]) { selected[roots[i]]=true; queue[write++]=roots[i]; }
    }
    while(read<write) {
        const golem_dependency_node *v=&g->nodes[queue[read++]];
        for(size_t j=0;j<v->parent_count;++j) if(!selected[v->parents[j]]) {
            selected[v->parents[j]]=true; queue[write++]=v->parents[j];
        }
    }
    return GOLEM_OK;
}
static struct json_object *decision(dw_entry *plan,int stage)
{ return json_object_array_get_idx(dw_get(dw_get(plan->meta,"selection"),"decisions"),(size_t)stage); }
static bool same_plan(struct json_object *meta,dw_entry *plan)
{
    struct json_object *r=dw_get(dw_get(meta,"input_manifest"),"selection"); golem_digest d;
    return (dw_uint(meta,"schema_version")==4 || dw_uint(meta,"schema_version")==5) && strcmp(dw_text(r,"document_id"),dw_text(plan->meta,"document_id"))==0 &&
        dw_uint(r,"revision")==plan->result.revision && dw_digest(r,"digest",&d) && dw_equal(&d,&plan->result.manifest_digest);
}
static golem_status pick(golem_document_store *s,dw_entry *plan,int kind,wf_graph *g,dw_entry **out)
{
    struct json_object *d=decision(plan,wf_stage(kind));
    if(strcmp(dw_text(d,"status"),"NOT_APPLICABLE")==0) return GOLEM_ERR_POLICY_DENIED;
    if(strcmp(dw_text(d,"status"),"REUSED")==0) {
        dw_entry *e=wf_resolve(s,dw_get(dw_get(d,"reuse"),"document"));
        if(!e || g->states[e-s->entries]!=GOLEM_DOCUMENT_CURRENT) return GOLEM_ERR_STALE_RESULT;
        *out=e; return GOLEM_OK;
    }
    dw_entry *found=NULL; bool stale=false;
    for(size_t i=0;i<s->count;++i) {
        dw_entry *e=&s->entries[i];
        if(strcmp(dw_text(e->meta,"kind"),wf_kinds[kind])!=0 || !same_plan(e->meta,plan)) continue;
        if(g->states[i]==GOLEM_DOCUMENT_CURRENT) { if(found) return GOLEM_ERR_INVALID_STATE; found=e; }
        else stale=true;
    }
    if(!found) return stale?GOLEM_ERR_STALE_RESULT:GOLEM_ERR_NOT_FOUND;
    *out=found; return GOLEM_OK;
}
static golem_status plan_get(golem_document_store *s,const char *id,wf_graph *g,dw_entry **out)
{
    if(!dw_id(id)) return GOLEM_ERR_INVALID_ARGUMENT;
    dw_entry *p=dw_find(s,id,0);
    if(!p || dw_uint(p->meta,"schema_version")!=3 || strcmp(dw_text(p->meta,"kind"),"stage-selection")!=0) return GOLEM_ERR_NOT_FOUND;
    if(g->states[p-s->entries]!=GOLEM_DOCUMENT_CURRENT) return GOLEM_ERR_STALE_RESULT;
    golem_status st=wf_selection(s,p->meta,g);
    bool selected[GOLEM_DOCUMENT_MAX_REVISIONS];
    size_t root=(size_t)(p-s->entries);
    if(st==GOLEM_OK) st=wf_closure(s,g,&root,1,selected);
    for(size_t i=0;st==GOLEM_OK && i<s->count;++i) if(selected[i]) {
        uint64_t bytes;
        st=wf_integrity(s,i,&bytes);
    }
    if(st==GOLEM_OK) *out=p;
    return st;
}
golem_status wf_manifest(golem_document_store *s,dw_entry *plan,const char *kind,const golem_digest *source,
    uint64_t budget,wf_graph *g,struct json_object **out)
{
    int k=wf_kind(kind);
    if(k<0 || !source || !budget || budget>GOLEM_WORKFLOW_CONTEXT_MAX) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_digest selected_source;
    if(!dw_digest(plan->meta,"source_snapshot",&selected_source) ||
        !dw_equal(source,&selected_source)) return GOLEM_ERR_STALE_RESULT;
    if(g->states[plan-s->entries]!=GOLEM_DOCUMENT_CURRENT) return GOLEM_ERR_STALE_RESULT;
    golem_status st=wf_selection(s,plan->meta,g);
    if(st!=GOLEM_OK) return st;
    bool documents=strcmp(dw_text(dw_get(plan->meta,"selection"),"mode"),"documents")==0;
    if((documents && k==4) || strcmp(dw_text(decision(plan,wf_stage(k)),"status"),"REQUIRED")!=0) return GOLEM_ERR_POLICY_DENIED;
    /* Direct handoff requirements, distinct from the complete transitive closure. */
    bool need[8]={false};
    if(k>=1) need[0]=true;
    if(k==2 || k==3) need[1]=strcmp(dw_text(decision(plan,1),"status"),"NOT_APPLICABLE")!=0;
    if(k==3) need[2]=strcmp(dw_text(decision(plan,2),"status"),"NOT_APPLICABLE")!=0;
    if(k>=4) need[3]=true;
    if(k>=5 && !documents) need[4]=true;
    if(k>=6) need[5]=true;
    if(k==7) need[6]=true;
    size_t roots[10],count=0; roots[count++]=(size_t)(plan-s->entries);
    if(k==0) {
        dw_entry *scope=wf_resolve(s,dw_get(dw_get(plan->meta,"selection"),"scope"));
        if(!scope) return GOLEM_ERR_NOT_FOUND;
        roots[count++]=(size_t)(scope-s->entries);
    }
    for(int i=0;i<8;++i) if(need[i]) {
        dw_entry *e=NULL; st=pick(s,plan,i,g,&e); if(st!=GOLEM_OK) return st;
        if(k==7 && i==6) { st=ex_pass(s,e->meta); if(st!=GOLEM_OK) return st; }
        roots[count++]=(size_t)(e-s->entries);
    }
    bool selected[GOLEM_DOCUMENT_MAX_REVISIONS]; st=wf_closure(s,g,roots,count,selected);
    struct json_object *m=json_object_new_object(),*direct=json_object_new_array(),*docs=json_object_new_array();
    if(!m || !direct || !docs) st=GOLEM_ERR_OUT_OF_MEMORY;
    uint64_t total=0;
    for(size_t i=0;st==GOLEM_OK && i<count;++i) if(!wf_append(direct,wf_ref(&s->entries[roots[i]]))) st=GOLEM_ERR_OUT_OF_MEMORY;
    for(size_t i=0;st==GOLEM_OK && i<s->count;++i) if(selected[i]) {
        if(g->states[i]!=GOLEM_DOCUMENT_CURRENT) { st=GOLEM_ERR_STALE_RESULT; break; }
        uint64_t bytes=0; st=wf_integrity(s,i,&bytes); if(st!=GOLEM_OK) break;
        if(bytes>budget-total) { st=GOLEM_ERR_BUDGET_EXHAUSTED; break; } total+=bytes;
        struct json_object *v=wf_ref(&s->entries[i]);
        if(!v || !dw_add_digest(v,"body_digest",&s->entries[i].result.body_digest) ||
           !dw_add(v,"bytes",json_object_new_uint64(bytes))) { json_object_put(v); st=GOLEM_ERR_OUT_OF_MEMORY; break; }
        if(!wf_append(docs,v)) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK && (!dw_add(m,"schema_version",json_object_new_int(1)) ||
        !dw_add(m,"work_id",json_object_new_string(dw_text(s->spec,"work_id"))) ||
        !dw_add(m,"generation",json_object_new_uint64(s->count+1)) || !dw_add(m,"selection",wf_ref(plan)) ||
        !dw_add(m,"target_kind",json_object_new_string(kind)) || !dw_add_digest(m,"source_snapshot",source) ||
        !dw_add(m,"scope_revision",json_object_new_int(1)) || !dw_add(m,"policy_version",json_object_new_int(1)) ||
        !dw_add(m,"template_version",json_object_new_int(1)) || !dw_add(m,"byte_budget",json_object_new_uint64(budget)) ||
        !dw_add(m,"total_bytes",json_object_new_uint64(total)))) st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK) { bool ok=dw_add(m,"direct",direct); direct=NULL; if(!ok) st=GOLEM_ERR_OUT_OF_MEMORY; }
    if(st==GOLEM_OK) { bool ok=dw_add(m,"documents",docs); docs=NULL; if(!ok) st=GOLEM_ERR_OUT_OF_MEMORY; }
    if(st==GOLEM_OK) st=re_context(s,m,&total,budget);
    json_object_put(direct); json_object_put(docs);
    if(st==GOLEM_OK) *out=m; else json_object_put(m);
    return st;
}
golem_status wf_preconditions(golem_document_store *s,struct json_object *m)
{
    uint64_t version=dw_uint(m,"schema_version");
    if(version<3) return GOLEM_OK;
    golem_status guard=re_guard(s,dw_text(m,"kind"),false);
    if(guard!=GOLEM_OK) return guard;
    wf_graph g={0}; golem_status st=wf_graph_make(s,&g);
    if(st!=GOLEM_OK) return st;
    struct json_object *parents=dw_get(m,"parents");
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(parents);++i) {
        dw_entry *p=wf_resolve(s,json_object_array_get_idx(parents,i));
        if(!p || g.states[p-s->entries]!=GOLEM_DOCUMENT_CURRENT) st=GOLEM_ERR_STALE_RESULT;
    }
    /* Publishing a revision must not invalidate its own transitive inputs. */
    size_t roots[GOLEM_DOCUMENT_MAX_PARENTS],count=json_object_array_length(parents);
    bool selected[GOLEM_DOCUMENT_MAX_REVISIONS];
    for(size_t i=0;st==GOLEM_OK && i<count;++i)
        roots[i]=(size_t)(wf_resolve(s,json_object_array_get_idx(parents,i))-s->entries);
    if(st==GOLEM_OK) st=wf_closure(s,&g,roots,count,selected);
    for(size_t i=0;st==GOLEM_OK && i<s->count;++i) if(selected[i]) {
        if(strcmp(dw_text(s->entries[i].meta,"document_id"),dw_text(m,"document_id"))==0)
            st=GOLEM_ERR_STALE_RESULT;
        else { uint64_t bytes; st=wf_integrity(s,i,&bytes); }
    }
    if(st==GOLEM_OK && version==3) st=wf_selection(s,m,&g);
    else if(st==GOLEM_OK) {
        struct json_object *input=dw_get(m,"input_manifest"),*expected=NULL;
        dw_entry *p=wf_resolve(s,dw_get(input,"selection")); golem_digest source;
        if(!p || dw_uint(p->meta,"schema_version")!=3 || !dw_digest(m,"source_snapshot",&source)) st=GOLEM_ERR_REQUIREMENTS_UNMET;
        if(st==GOLEM_OK) st=wf_manifest(s,p,dw_text(m,"kind"),&source,dw_uint(input,"byte_budget"),&g,&expected);
        if(st==GOLEM_OK && !json_object_equal(expected,input)) st=GOLEM_ERR_STALE_RESULT;
        json_object_put(expected);
    }
    /* The selected scope's requirements cannot disappear in a downstream stage. */
    if(st==GOLEM_OK) {
        dw_entry *parent=version==3?wf_resolve(s,dw_get(dw_get(m,"selection"),"scope")):
            wf_resolve(s,dw_get(dw_get(m,"input_manifest"),"selection"));
        struct json_object *required=dw_get(parent->meta,"requirement_ids"),*provided=dw_get(m,"requirement_ids");
        for(size_t i=0;i<json_object_array_length(required);++i) {
            bool found=false;
            for(size_t j=0;j<json_object_array_length(provided);++j)
                if(json_object_equal(json_object_array_get_idx(required,i),json_object_array_get_idx(provided,j))) found=true;
            if(!found) st=GOLEM_ERR_REQUIREMENTS_UNMET;
        }
    }
    wf_graph_free(s,&g); return st;
}
golem_status golem_workflow_select(golem_document_store *s,const char *scope_id,uint32_t revision,
    const char *mode,void *buffer,size_t capacity,size_t *required,golem_diagnostic *d)
{
    if(!s || !dw_id(scope_id) || !revision || !mode || (strcmp(mode,"development")!=0 && strcmp(mode,"documents")!=0)) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    wf_graph g={0}; golem_status st=wf_graph_make(s,&g); dw_entry *scope=dw_find(s,scope_id,revision);
    if(st==GOLEM_OK && (!scope || dw_uint(scope->meta,"schema_version")!=2 || strcmp(dw_text(scope->meta,"kind"),"scope")!=0)) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    if(st==GOLEM_OK && g.states[scope-s->entries]!=GOLEM_DOCUMENT_CURRENT) st=GOLEM_ERR_STALE_RESULT;
    golem_discovery_result assessment;
    if(st==GOLEM_OK) st=ds_validate(dw_get(scope->meta,"assessment"),&assessment);
    if(st==GOLEM_OK && !assessment.scope_ready) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *p=NULL,*dec=NULL;
    if(st==GOLEM_OK) {
        uint64_t bytes; st=wf_integrity(s,(size_t)(scope-s->entries),&bytes);
        p=json_object_new_object(); dec=json_object_new_array(); if(!p || !dec) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    bool needs[6]={true,false,false,true,true,true};
    if(st==GOLEM_OK) {
        struct json_object *choices=dw_get(dw_get(scope->meta,"assessment"),"selections");
        for(size_t i=0;i<json_object_array_length(choices);++i) {
            struct json_object *v=json_object_array_get_idx(choices,i);
            if(strcmp(dw_text(v,"decision"),"INCLUDE")!=0) continue;
            needs[1]|=json_object_get_boolean(dw_get(v,"needs_ux")); needs[2]|=json_object_get_boolean(dw_get(v,"needs_publishing"));
        }
        for(size_t i=0;st==GOLEM_OK && i<6;++i) {
            struct json_object *v=json_object_new_object();
            if(!dw_add(v,"stage",json_object_new_string(wf_stages[i])) ||
                !dw_add(v,"status",json_object_new_string(needs[i]?"REQUIRED":"NOT_APPLICABLE")) ||
                !dw_add(v,"reason",json_object_new_string(needs[i]?"Required by the selected scope or mandatory verification contract.":
                    "No included finding requests this interface stage; review this scope decision.")) ||
                !dw_add(v,"evidence",wf_ref(scope)) || json_object_object_add(v,"reuse",NULL)!=0) {
                json_object_put(v); st=GOLEM_ERR_OUT_OF_MEMORY; break;
            }
            if(!wf_append(dec,v)) st=GOLEM_ERR_OUT_OF_MEMORY;
        }
        if(st==GOLEM_OK && (!dw_add(p,"schema_version",json_object_new_int(1)) ||
            !dw_add(p,"mode",json_object_new_string(mode)) || !dw_add(p,"scope",wf_ref(scope)))) st=GOLEM_ERR_OUT_OF_MEMORY;
        if(st==GOLEM_OK) { bool ok=dw_add(p,"decisions",dec); dec=NULL; if(!ok) st=GOLEM_ERR_OUT_OF_MEMORY; }
    }
    if(st==GOLEM_OK) st=emit(p,buffer,capacity,required);
    json_object_put(p); json_object_put(dec); wf_graph_free(s,&g); return dw_report(d,st,NULL);
}
golem_status wf_inputs(golem_document_store *s,const char *id,const char *kind,const golem_digest *source,
    uint64_t budget,void *buffer,size_t capacity,size_t *required,golem_diagnostic *d,bool enforce_reentry)
{
    if(!s || !kind || !source) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    golem_status guard=enforce_reentry?re_guard(s,kind,true):GOLEM_OK;
    if(guard!=GOLEM_OK) return dw_report(d,guard,NULL);
    wf_graph g={0}; struct json_object *m=NULL; dw_entry *p=NULL;
    golem_status st=wf_graph_make(s,&g);
    if(st==GOLEM_OK) st=plan_get(s,id,&g,&p);
    if(st==GOLEM_OK) st=wf_manifest(s,p,kind,source,budget,&g,&m);
    if(st==GOLEM_OK && strcmp(kind,"completion")==0) {
        struct json_object *docs=dw_get(m,"documents");
        for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(docs);++i) {
            struct json_object *ref=json_object_array_get_idx(docs,i);
            dw_entry *e=dw_find(s,dw_text(ref,"document_id"),(uint32_t)dw_uint(ref,"revision"));
            if(!e) st=GOLEM_ERR_NOT_FOUND; else st=ex_live(s,e->meta);
        }
    }
    if(st==GOLEM_OK) st=emit(m,buffer,capacity,required);
    json_object_put(m); wf_graph_free(s,&g); return dw_report(d,st,NULL);
}
golem_status golem_workflow_inputs(golem_document_store *s,const char *id,const char *kind,const golem_digest *source,
    uint64_t budget,void *buffer,size_t capacity,size_t *required,golem_diagnostic *d)
{ return wf_inputs(s,id,kind,source,budget,buffer,capacity,required,d,true); }
golem_status golem_workflow_trace(golem_document_store *s,const char *id,uint32_t revision,
    void *buffer,size_t capacity,size_t *required,golem_diagnostic *d)
{
    if(!s || !dw_id(id) || !revision) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    wf_graph g={0}; golem_status st=wf_graph_make(s,&g); dw_entry *e=dw_find(s,id,revision);
    if(st==GOLEM_OK && !e) st=GOLEM_ERR_NOT_FOUND;
    struct json_object *o=NULL,*nodes=NULL; bool selected[GOLEM_DOCUMENT_MAX_REVISIONS];
    if(st==GOLEM_OK) { size_t root=(size_t)(e-s->entries); st=wf_closure(s,&g,&root,1,selected); }
    if(st==GOLEM_OK) {
        o=json_object_new_object(); nodes=json_object_new_array();
        if(!o || !nodes) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    for(size_t i=0;st==GOLEM_OK && i<s->count;++i) if(selected[i]) {
        uint64_t size; st=wf_integrity(s,i,&size); if(st!=GOLEM_OK) break;
        struct json_object *v=wf_ref(&s->entries[i]);
        if(!v || !dw_add(v,"state",json_object_new_string(state_name(g.states[i]))) ||
            !dw_add(v,"parents",json_object_get(dw_get(s->entries[i].meta,"parents")))) { json_object_put(v); st=GOLEM_ERR_OUT_OF_MEMORY; break; }
        if(!wf_append(nodes,v)) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK && (!dw_add(o,"schema_version",json_object_new_int(1)) ||
        !dw_add(o,"work_id",json_object_new_string(dw_text(s->spec,"work_id"))) ||
        !dw_add(o,"state",json_object_new_string(state_name(g.states[e-s->entries]))) ||
        !dw_add(o,"acceptance_verified",json_object_new_boolean(false)))) st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK) { bool ok=dw_add(o,"closure",nodes); nodes=NULL; if(!ok) st=GOLEM_ERR_OUT_OF_MEMORY; }
    if(st==GOLEM_OK) st=emit(o,buffer,capacity,required);
    json_object_put(o); json_object_put(nodes); wf_graph_free(s,&g); return dw_report(d,st,NULL);
}
golem_status wf_completed_documents(golem_document_store *s,const char *id,struct json_object **out)
{
    wf_graph g={0}; dw_entry *plan=NULL;
    golem_status st=wf_graph_make(s,&g);
    if(st==GOLEM_OK) st=plan_get(s,id,&g,&plan);
    size_t roots[9],count=0; bool selected[GOLEM_DOCUMENT_MAX_REVISIONS];
    if(st==GOLEM_OK) roots[count++]=(size_t)(plan-s->entries);
    for(int k=0;st==GOLEM_OK && k<8;++k) {
        if((k==4 && !strcmp(dw_text(dw_get(plan->meta,"selection"),"mode"),"documents")) ||
           !strcmp(dw_text(decision(plan,wf_stage(k)),"status"),"NOT_APPLICABLE")) continue;
        dw_entry *e=NULL; st=pick(s,plan,k,&g,&e);
        if(st==GOLEM_OK) roots[count++]=(size_t)(e-s->entries);
    }
    if(st==GOLEM_OK) st=wf_closure(s,&g,roots,count,selected);
    struct json_object *a=json_object_new_array();
    if(!a) st=GOLEM_ERR_OUT_OF_MEMORY;
    for(size_t i=0;st==GOLEM_OK && i<s->count;++i) if(selected[i]) {
        if(g.states[i]!=GOLEM_DOCUMENT_CURRENT) { st=GOLEM_ERR_STALE_RESULT; break; }
        uint64_t size; st=wf_integrity(s,i,&size);
        struct json_object *r=wf_ref(&s->entries[i]);
        if(!r || !ex_text(r,"kind",dw_text(s->entries[i].meta,"kind")) ||
           !dw_add_digest(r,"body_digest",&s->entries[i].result.body_digest)) st=GOLEM_ERR_OUT_OF_MEMORY;
        if(st==GOLEM_OK) { if(!wf_append(a,r)) st=GOLEM_ERR_OUT_OF_MEMORY; } else json_object_put(r);
    }
    if(st==GOLEM_OK) *out=a; else json_object_put(a);
    wf_graph_free(s,&g); return st;
}
golem_status golem_workflow_next(golem_document_store *s,const char *id,void *buffer,size_t capacity,size_t *required,golem_diagnostic *d)
{
    if(!s) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    wf_graph g={0}; golem_status st=wf_graph_make(s,&g); dw_entry *p=NULL;
    if(st==GOLEM_OK) st=plan_get(s,id,&g,&p);
    const char *action="VERIFY_COMPLETION",*kind="completion",*reason="All required documents are fresh; real completion gates must still verify outcomes.";
    const char *completed=NULL;
    if(st==GOLEM_OK) st=co_hint(s,id,&completed);
    bool settled=completed && strcmp(completed,"REVALIDATE_COMPLETION");
    if(st==GOLEM_OK && settled) { action=completed; reason="Consult completion resume for the durable receipt and recovery context."; }
    const char *reentry_action=NULL,*reentry_kind=NULL,*reentry_reason=NULL;
    if(st==GOLEM_OK && !settled) st=re_next(s,&reentry_action,&reentry_kind,&reentry_reason);
    if(st==GOLEM_OK && reentry_action) { action=reentry_action; kind=reentry_kind; reason=reentry_reason; }
    if(st==GOLEM_OK && !settled && s->reentry_count) {
        golem_status deadline=re_deadline(s);
        if(deadline!=GOLEM_OK) {
            reentry_action="BLOCKED"; action="BLOCKED"; kind="";
            reason=deadline==GOLEM_ERR_BUDGET_EXHAUSTED?"DEADLINE_EXHAUSTED":"CLOCK_RECONCILIATION_REQUIRED";
        }
    }
    for(int k=0;st==GOLEM_OK && !settled && !reentry_action && k<8;++k) {
        if((k==4 && strcmp(dw_text(dw_get(p->meta,"selection"),"mode"),"documents")==0) ||
           strcmp(dw_text(decision(p,wf_stage(k)),"status"),"NOT_APPLICABLE")==0) continue;
        dw_entry *e=NULL; golem_status found=pick(s,p,k,&g,&e);
        if(found==GOLEM_ERR_NOT_FOUND || found==GOLEM_ERR_STALE_RESULT) {
            action=found==GOLEM_ERR_NOT_FOUND?"AUTHOR_DOCUMENT":"REVISE_DOCUMENT"; kind=wf_kinds[k];
            reason=found==GOLEM_ERR_NOT_FOUND?"Required managed document has not been registered.":"A document or transitive input has been superseded; re-review before submitting."; break;
        }
        if(found!=GOLEM_OK) { st=found; break; }
        if(dw_uint(e->meta,"schema_version")==5) {
            golem_status live=ex_live(s,e->meta);
            if(live==GOLEM_ERR_STALE_RESULT) {
                action="REVISE_DOCUMENT"; kind=wf_kinds[k]; reason="Observed source changed since this result; re-observe and verify."; break;
            }
            if(live!=GOLEM_OK) { st=live; break; }
        }
        if(k==6 && ex_pass(s,e->meta)==GOLEM_ERR_REQUIREMENTS_UNMET) {
            action="CLASSIFY_FAILURE"; kind="qa-result";
            reason="Engine-observed QA did not pass; classify failure and revise affected inputs before retry."; break;
        }
        uint64_t size; st=wf_integrity(s,(size_t)(e-s->entries),&size);
    }
    if(st==GOLEM_OK && !settled && !strcmp(action,"VERIFY_COMPLETION") && completed) action=completed;
    struct json_object *o=NULL;
    if(st==GOLEM_OK) {
        o=json_object_new_object();
        if(!dw_add(o,"schema_version",json_object_new_int(1)) || !dw_add(o,"generation",json_object_new_uint64(s->count+1)) ||
            !dw_add(o,"action",json_object_new_string(action)) || !dw_add(o,"target_kind",json_object_new_string(kind)) ||
            !dw_add(o,"reason",json_object_new_string(reason)) || !dw_add(o,"execution_authorized",json_object_new_boolean(false)) ||
            !dw_add(o,"acceptance_verified",json_object_new_boolean(!strcmp(action,"DONE")))) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK) st=emit(o,buffer,capacity,required);
    json_object_put(o); wf_graph_free(s,&g); return dw_report(d,st,NULL);
}
