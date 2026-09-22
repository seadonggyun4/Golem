#include "internal.h"
#include "../discovery/internal.h"
#include <stdlib.h>
#include <string.h>

const char *const wf_stages[6]={"planning","ux","publishing","development","qa","audit"};
const char *const wf_kinds[8]={"planning","ux","publishing","development-plan","development-result","qa-plan","qa-result","completion"};
int wf_kind(const char *kind)
{ for(int i=0;i<8;++i) if(strcmp(kind,wf_kinds[i])==0) return i; return -1; }
int wf_stage(int k)
{ static const int stage[]={0,1,2,3,3,4,4,5}; return k<0 || k>=8?-1:stage[k]; }
bool wf_append(struct json_object *a,struct json_object *v)
{ if(!a || !v || json_object_array_add(a,v)!=0) { json_object_put(v); return false; } return true; }
bool wf_reference(struct json_object *r)
{
    const char *keys[]={"document_id","revision","digest"}; golem_digest d;
    return dw_keys(r,keys,3) && dw_id(dw_text(r,"document_id")) && dw_uint(r,"revision")>0 &&
        dw_uint(r,"revision")<=GOLEM_DOCUMENT_MAX_REVISIONS && dw_digest(r,"digest",&d);
}
struct json_object *wf_ref(dw_entry *e)
{
    struct json_object *r=json_object_new_object();
    if(!dw_add(r,"document_id",json_object_new_string(dw_text(e->meta,"document_id"))) ||
        !dw_add(r,"revision",json_object_new_int64(e->result.revision)) ||
        !dw_add_digest(r,"digest",&e->result.manifest_digest)) { json_object_put(r); return NULL; }
    return r;
}
dw_entry *wf_resolve(golem_document_store *s,struct json_object *r)
{
    if(!wf_reference(r)) return NULL;
    dw_entry *e=dw_find(s,dw_text(r,"document_id"),(uint32_t)dw_uint(r,"revision")); golem_digest digest;
    if(!e || !dw_digest(r,"digest",&digest) || !dw_equal(&digest,&e->result.manifest_digest)) return NULL;
    return e;
}
typedef struct lookup { const char *id; uint32_t revision; size_t index; } lookup;
static int compare(const void *a,const void *b)
{
    const lookup *x=a,*y=b; int c=strcmp(x->id,y->id);
    return c?c:x->revision<y->revision?-1:x->revision>y->revision?1:0;
}
golem_status wf_graph_make(golem_document_store *s,wf_graph *out)
{
    if(!s || !out || s->poisoned) return GOLEM_ERR_INVALID_STATE;
    if(!s->count) return GOLEM_ERR_NOT_FOUND;
    size_t n=s->count,bytes=n*(sizeof(golem_dependency_node)+sizeof(lookup)+sizeof(golem_document_freshness))+s->edges*sizeof(size_t);
    void *mem=NULL; golem_status st=golem_allocator_alloc(&s->allocator,bytes,&mem);
    if(st!=GOLEM_OK) return st;
    wf_graph g={0}; g.memory=mem; g.nodes=mem;
    lookup *map=(lookup *)(g.nodes+n); g.edges=(size_t *)(map+n);
    g.states=(golem_document_freshness *)(g.edges+s->edges);
    for(size_t i=0;i<n;++i) {
        dw_entry *e=&s->entries[i];
        g.nodes[i]=(golem_dependency_node){dw_text(e->meta,"work_id"),dw_text(e->meta,"document_id"),
            e->result.revision,e->result.manifest_digest,NULL,0};
        map[i]=(lookup){g.nodes[i].document_id,g.nodes[i].revision,i};
    }
    qsort(map,n,sizeof(*map),compare); size_t edge=0;
    for(size_t i=0;st==GOLEM_OK && i<n;++i) {
        struct json_object *parents=dw_get(s->entries[i].meta,"parents");
        g.nodes[i].parent_count=json_object_array_length(parents); g.nodes[i].parents=g.edges+edge;
        for(size_t j=0;j<g.nodes[i].parent_count;++j) {
            struct json_object *p=json_object_array_get_idx(parents,j);
            lookup key={dw_text(p,"document_id"),(uint32_t)dw_uint(p,"revision"),0};
            lookup *found=bsearch(&key,map,n,sizeof(*map),compare); golem_digest digest;
            if(!found || edge>=s->edges || !dw_digest(p,"digest",&digest) ||
                !dw_equal(&digest,&g.nodes[found->index].manifest_digest)) { st=GOLEM_ERR_INVALID_GRAPH; break; }
            g.edges[edge++]=found->index;
        }
    }
    if(st==GOLEM_OK && edge!=s->edges) st=GOLEM_ERR_INVALID_GRAPH;
    if(st==GOLEM_OK) st=golem_document_graph_evaluate(g.nodes,n,&s->allocator,g.states,n,NULL);
    if(st==GOLEM_OK) *out=g; else wf_graph_free(s,&g);
    return st;
}
void wf_graph_free(golem_document_store *s,wf_graph *g)
{ (void)golem_allocator_free(&s->allocator,g->memory); memset(g,0,sizeof(*g)); }
static bool contains(struct json_object *array,struct json_object *ref)
{
    for(size_t i=0;i<json_object_array_length(array);++i) if(json_object_equal(json_object_array_get_idx(array,i),ref)) return true;
    return false;
}
golem_status wf_metadata(struct json_object *m)
{
    if(dw_uint(m,"schema_version")==3) {
        struct json_object *p=dw_get(m,"selection"),*dec=dw_get(p,"decisions");
        const char *keys[]={"schema_version","mode","scope","decisions"};
        if(!dw_keys(p,keys,4) || dw_uint(p,"schema_version")!=1 ||
            (strcmp(dw_text(p,"mode"),"development")!=0 && strcmp(dw_text(p,"mode"),"documents")!=0) ||
            !wf_reference(dw_get(p,"scope")) || !contains(dw_get(m,"parents"),dw_get(p,"scope")) || !ds_array(dec,6,6)) return GOLEM_ERR_PARSE;
        for(size_t i=0;i<6;++i) {
            struct json_object *v=json_object_array_get_idx(dec,i),*reuse=dw_get(v,"reuse");
            const char *dk[]={"stage","status","reason","evidence","reuse"};
            const char *status=dw_text(v,"status");
            if(!dw_keys(v,dk,5) || strcmp(dw_text(v,"stage"),wf_stages[i])!=0 || !ds_prose(v,"reason") ||
                !wf_reference(dw_get(v,"evidence")) || !json_object_equal(dw_get(v,"evidence"),dw_get(p,"scope"))) return GOLEM_ERR_PARSE;
            if(strcmp(status,"REUSED")==0) {
                const char *rk[]={"document","review_digest"}; golem_digest digest;
                if((i!=1 && i!=2) || !dw_keys(reuse,rk,2) || !wf_reference(dw_get(reuse,"document")) ||
                    !dw_digest(reuse,"review_digest",&digest) || !contains(dw_get(m,"parents"),dw_get(reuse,"document"))) return GOLEM_ERR_PARSE;
            } else if((strcmp(status,"REQUIRED")!=0 && strcmp(status,"NOT_APPLICABLE")!=0) ||
                !json_object_is_type(reuse,json_type_null)) return GOLEM_ERR_PARSE;
            if(i!=1 && i!=2 && strcmp(status,"REQUIRED")!=0) return GOLEM_ERR_REQUIREMENTS_UNMET;
        }
        return GOLEM_OK;
    }
    struct json_object *p=dw_get(m,"input_manifest"),*direct=dw_get(p,"direct"),*docs=dw_get(p,"documents");
    const char *keys[]={"schema_version","work_id","generation","selection","target_kind","source_snapshot",
        "scope_revision","policy_version","template_version","byte_budget","total_bytes","direct","documents","reentry"};
    golem_digest a,b;
    bool reentry=dw_uint(p,"schema_version")==2;
    if(reentry) {
        const char *rk[]={"decision_digest","report_digest","failure_receipt"};
        struct json_object *r=dw_get(p,"reentry");
        if(!dw_keys(r,rk,3) || !dw_digest(r,"decision_digest",&a) || !dw_digest(r,"report_digest",&a) ||
            !dw_digest(r,"failure_receipt",&a)) return GOLEM_ERR_PARSE;
    }
    if(!dw_keys(p,keys,reentry?14:13) || (!reentry && dw_uint(p,"schema_version")!=1) ||
        strcmp(dw_text(m,"work_id"),dw_text(p,"work_id"))!=0 || strcmp(dw_text(m,"kind"),dw_text(p,"target_kind"))!=0 ||
        dw_uint(p,"generation")!=dw_uint(m,"expected_generation") || !wf_reference(dw_get(p,"selection")) ||
        !dw_digest(p,"source_snapshot",&a) || !dw_digest(m,"source_snapshot",&b) || !dw_equal(&a,&b) ||
        dw_uint(p,"scope_revision")!=1 || dw_uint(p,"policy_version")!=1 || dw_uint(p,"template_version")!=1 ||
        dw_uint(p,"byte_budget")==0 || dw_uint(p,"byte_budget")>GOLEM_WORKFLOW_CONTEXT_MAX ||
        dw_uint(p,"total_bytes")>dw_uint(p,"byte_budget") || !ds_array(direct,1,64) || !ds_array(docs,1,4096) ||
        !json_object_equal(direct,dw_get(m,"parents"))) return GOLEM_ERR_PARSE;
    for(size_t i=0;i<json_object_array_length(direct);++i) if(!wf_reference(json_object_array_get_idx(direct,i))) return GOLEM_ERR_PARSE;
    for(size_t i=0;i<json_object_array_length(docs);++i) {
        struct json_object *v=json_object_array_get_idx(docs,i); const char *dk[]={"document_id","revision","digest","body_digest","bytes"};
        if(!dw_keys(v,dk,5) || !dw_id(dw_text(v,"document_id")) || dw_uint(v,"revision")<1 || dw_uint(v,"revision")>4096 ||
            !dw_digest(v,"digest",&a) || !dw_digest(v,"body_digest",&a) || dw_uint(v,"bytes")>GOLEM_DOCUMENT_MAX_BODY) return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}
static golem_status review(golem_document_store *s,struct json_object *selection,struct json_object *meta,struct json_object *reuse,wf_graph *g)
{
    dw_entry *e=wf_resolve(s,dw_get(reuse,"document")); golem_digest key;
    if(!e || g->states[e-s->entries]!=GOLEM_DOCUMENT_CURRENT) return GOLEM_ERR_STALE_RESULT;
    if(strcmp(dw_text(e->meta,"source_snapshot"),dw_text(meta,"source_snapshot"))!=0) return GOLEM_ERR_STALE_RESULT;
    if(!dw_digest(reuse,"review_digest",&key)) return GOLEM_ERR_PARSE;
    struct json_object *r=NULL; golem_status st=dw_cas_json(s,&key,&r);
    const char *keys[]={"schema_version","work_id","document","scope","source_snapshot","policy_version","template_version","decision","reason"};
    if(st==GOLEM_OK && (!dw_keys(r,keys,9) || dw_uint(r,"schema_version")!=1 ||
        strcmp(dw_text(r,"work_id"),dw_text(meta,"work_id"))!=0 ||
        !json_object_equal(dw_get(r,"document"),dw_get(reuse,"document")) || !json_object_equal(dw_get(r,"scope"),dw_get(selection,"scope")) ||
        strcmp(dw_text(r,"source_snapshot"),dw_text(meta,"source_snapshot"))!=0 || dw_uint(r,"policy_version")!=1 ||
        dw_uint(r,"template_version")!=1 || strcmp(dw_text(r,"decision"),"REUSE")!=0 || !ds_prose(r,"reason"))) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    json_object_put(r); return st;
}
golem_status wf_selection(golem_document_store *s,struct json_object *m,wf_graph *g)
{
    struct json_object *p=dw_get(m,"selection"),*dec=dw_get(p,"decisions");
    dw_entry *scope=wf_resolve(s,dw_get(p,"scope"));
    if(!scope || dw_uint(scope->meta,"schema_version")!=2 || strcmp(dw_text(scope->meta,"kind"),"scope")!=0) return GOLEM_ERR_REQUIREMENTS_UNMET;
    if(g->states[scope-s->entries]!=GOLEM_DOCUMENT_CURRENT ||
        strcmp(dw_text(scope->meta,"source_snapshot"),dw_text(m,"source_snapshot"))!=0) return GOLEM_ERR_STALE_RESULT;
    golem_discovery_result assessment;
    golem_status st=ds_validate(dw_get(scope->meta,"assessment"),&assessment);
    if(st!=GOLEM_OK) return st;
    if(!assessment.scope_ready) return GOLEM_ERR_REQUIREMENTS_UNMET;
    bool needs[6]={true,false,false,true,true,true};
    struct json_object *choices=dw_get(dw_get(scope->meta,"assessment"),"selections");
    for(size_t i=0;i<json_object_array_length(choices);++i) {
        struct json_object *v=json_object_array_get_idx(choices,i);
        if(strcmp(dw_text(v,"decision"),"INCLUDE")!=0) continue;
        needs[1]|=json_object_get_boolean(dw_get(v,"needs_ux"));
        needs[2]|=json_object_get_boolean(dw_get(v,"needs_publishing"));
    }
    for(size_t i=0;i<6;++i) {
        struct json_object *v=json_object_array_get_idx(dec,i);
        const char *status=dw_text(v,"status");
        if(needs[i] && strcmp(status,"NOT_APPLICABLE")==0) return GOLEM_ERR_REQUIREMENTS_UNMET;
        if(strcmp(status,"REUSED")==0) {
            dw_entry *e=wf_resolve(s,dw_get(dw_get(v,"reuse"),"document"));
            if(!e || strcmp(dw_text(e->meta,"kind"),wf_stages[i])!=0) return GOLEM_ERR_REQUIREMENTS_UNMET;
            st=review(s,p,m,dw_get(v,"reuse"),g); if(st!=GOLEM_OK) return st;
        }
    }
    return GOLEM_OK;
}
