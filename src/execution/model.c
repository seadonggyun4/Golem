#include "internal.h"
#include "../agent_session/internal.h"
#include <stdlib.h>
#include <string.h>

bool ex_text(struct json_object *o,const char *key,const char *text)
{ return dw_add(o,key,json_object_new_string(text)); }
bool ex_uint(struct json_object *o,const char *key,uint64_t n)
{ return dw_add(o,key,json_object_new_uint64(n)); }
golem_status ex_hash(struct json_object *o,golem_digest *out)
{
    const char *p=json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN);
    return p?golem_digest_bytes((golem_bytes){(const uint8_t *)p,strlen(p)},out):GOLEM_ERR_OUT_OF_MEMORY;
}
golem_status ex_emit(struct json_object *o,golem_execution_reply *out)
{
    const char *p=json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN);
    if(!p) return GOLEM_ERR_OUT_OF_MEMORY;
    size_t n=strlen(p);
    if(n>GOLEM_DOCUMENT_MAX_JSON) return GOLEM_ERR_BUDGET_EXHAUSTED;
    uint8_t *copy=malloc(n?n:1); if(!copy) return GOLEM_ERR_OUT_OF_MEMORY;
    memcpy(copy,p,n); *out=(golem_execution_reply){copy,n}; return GOLEM_OK;
}
void golem_execution_reply_free(golem_execution_reply *r)
{ if(r) { free(r->data); *r=(golem_execution_reply){0}; } }
static bool string_array(struct json_object *a,size_t min,size_t max,bool paths)
{
    if(!ds_array(a,min,max)) return false;
    for(size_t i=0;i<json_object_array_length(a);++i) {
        struct json_object *v=json_object_array_get_idx(a,i);
        if(!json_object_is_type(v,json_type_string)) return false;
        const char *p=json_object_get_string(v);
        if(!*p || strlen(p)>2048 || (paths && !ds_path(p))) return false;
        for(const char *q=p;*q;++q) if((unsigned char)*q<32) return false;
    }
    return true;
}
golem_status ex_contract(struct json_object *o)
{
    const char *keys[]={"schema_version","selection_id","development_plan","snapshot_plan","gates"};
    struct json_object *gates=dw_get(o,"gates"),*plan=dw_get(o,"snapshot_plan");
    const char *pk[]={"schema_version","timeout_seconds","repositories"};
    if(!dw_keys(o,keys,5) || dw_uint(o,"schema_version")!=1 || !dw_id(dw_text(o,"selection_id")) ||
        !wf_reference(dw_get(o,"development_plan")) || !ds_array(gates,1,8) ||
        !dw_keys(plan,pk,3) || dw_uint(plan,"schema_version")!=1 || dw_uint(plan,"timeout_seconds")<1 ||
        dw_uint(plan,"timeout_seconds")>60 || !ds_array(dw_get(plan,"repositories"),1,8)) return GOLEM_ERR_PARSE;
    struct json_object *repos=dw_get(plan,"repositories");
    for(size_t i=0;i<json_object_array_length(repos);++i) {
        struct json_object *r=json_object_array_get_idx(repos,i);
        const char *rk[]={"id","root","paths","toolchain","test_configuration"};
        if(!dw_keys(r,rk,5) || !dw_id(dw_text(r,"id")) || dw_text(r,"root")[0]!='/' ||
            strlen(dw_text(r,"root"))>3000 || !string_array(dw_get(r,"paths"),1,64,true) ||
            !ds_prose(r,"toolchain") || !ds_prose(r,"test_configuration")) return GOLEM_ERR_PARSE;
        for(size_t j=0;j<i;++j) if(strcmp(dw_text(r,"id"),dw_text(json_object_array_get_idx(repos,j),"id"))==0) return GOLEM_ERR_PARSE;
    }
    for(size_t i=0;i<json_object_array_length(gates);++i) {
        struct json_object *g=json_object_array_get_idx(gates,i),*cases=dw_get(g,"cases"),*paths=dw_get(g,"protected_paths");
        const char *gk[]={"id","version","repository","argv","timeout_ms","cases","protected_paths"};
        if(!dw_keys(g,gk,7) || !dw_id(dw_text(g,"id")) || dw_uint(g,"version")<1 || dw_uint(g,"version")>UINT32_MAX ||
            !dw_id(dw_text(g,"repository")) || !string_array(dw_get(g,"argv"),1,32,false) ||
            json_object_get_string(json_object_array_get_idx(dw_get(g,"argv"),0))[0]!='/' ||
            dw_uint(g,"timeout_ms")<1 || dw_uint(g,"timeout_ms")>60000 || !ds_array(cases,1,64) ||
            !string_array(paths,1,64,true)) return GOLEM_ERR_PARSE;
        struct json_object *repo=NULL;
        for(size_t j=0;j<json_object_array_length(repos);++j)
            if(strcmp(dw_text(json_object_array_get_idx(repos,j),"id"),dw_text(g,"repository"))==0) repo=json_object_array_get_idx(repos,j);
        if(!repo) return GOLEM_ERR_REQUIREMENTS_UNMET;
        for(size_t j=0;j<json_object_array_length(paths);++j) {
            bool found=false; struct json_object *all=dw_get(repo,"paths");
            for(size_t k=0;k<json_object_array_length(all);++k)
                if(json_object_equal(json_object_array_get_idx(paths,j),json_object_array_get_idx(all,k))) found=true;
            if(!found) return GOLEM_ERR_REQUIREMENTS_UNMET;
        }
        for(size_t j=0;j<json_object_array_length(cases);++j) {
            struct json_object *c=json_object_array_get_idx(cases,j); const char *ck[]={"id","requirement_id"};
            if(!dw_keys(c,ck,2) || !dw_id(dw_text(c,"id")) || !dw_id(dw_text(c,"requirement_id"))) return GOLEM_ERR_PARSE;
            for(size_t k=0;k<j;++k) if(strcmp(dw_text(c,"id"),dw_text(json_object_array_get_idx(cases,k),"id"))==0) return GOLEM_ERR_PARSE;
        }
        for(size_t j=0;j<i;++j) if(strcmp(dw_text(g,"id"),dw_text(json_object_array_get_idx(gates,j),"id"))==0) return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}
golem_status golem_execution_contract_validate(golem_bytes b,golem_digest *digest,golem_diagnostic *d)
{
    if(!digest) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    struct json_object *o=NULL; golem_status st=golem_json_parse(b,GOLEM_DOCUMENT_MAX_JSON,&o);
    if(st==GOLEM_OK) st=ex_contract(o);
    if(st==GOLEM_OK) st=ex_hash(o,digest);
    json_object_put(o); return dw_report(d,st,NULL);
}
golem_status ex_snapshot(struct json_object *plan,struct json_object **out)
{
    const char *p=json_object_to_json_string_ext(plan,JSON_C_TO_STRING_PLAIN);
    if(!p) return GOLEM_ERR_OUT_OF_MEMORY;
    uint8_t *data=NULL; size_t n=0;
    golem_status st=golem_discovery_snapshot((golem_bytes){(const uint8_t *)p,strlen(p)},NULL,&data,&n,NULL);
    if(st==GOLEM_OK) st=golem_json_parse((golem_bytes){data,n},GOLEM_DOCUMENT_MAX_JSON,out);
    free(data); return st;
}
golem_status ex_current(golem_document_store *s,struct json_object *manifest)
{
    struct json_object *docs=dw_get(manifest,"documents");
    wf_graph g={0}; golem_status st=wf_graph_make(s,&g);
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(docs);++i) {
        struct json_object *r=json_object_array_get_idx(docs,i); golem_digest key;
        dw_entry *e=dw_find(s,dw_text(r,"document_id"),(uint32_t)dw_uint(r,"revision"));
        if(!e || !dw_digest(r,"digest",&key) || !dw_equal(&key,&e->result.manifest_digest) ||
            g.states[e-s->entries]!=GOLEM_DOCUMENT_CURRENT) st=GOLEM_ERR_STALE_RESULT;
        else { uint64_t bytes; st=wf_integrity(s,(size_t)(e-s->entries),&bytes); }
    }
    wf_graph_free(s,&g); return st;
}
golem_status ex_inputs(golem_document_store *s,struct json_object *c,const char *kind,struct json_object **out)
{
    dw_entry *dev=wf_resolve(s,dw_get(c,"development_plan"));
    if(!dev || strcmp(dw_text(dev->meta,"kind"),"development-plan")!=0 || dw_uint(dev->meta,"schema_version")!=4)
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    golem_digest source;
    if(!dw_digest(dev->meta,"source_snapshot",&source)) return GOLEM_ERR_PARSE;
    uint64_t budget=GOLEM_WORKFLOW_CONTEXT_MAX;
    as_log log={.directory=-1}; golem_status loaded=as_load(s,NULL,NULL,&log);
    struct json_object *active=dw_get(log.state,"active"),*pinned=NULL;
    if(loaded==GOLEM_OK && active && strcmp(dw_text(active,"kind"),kind)==0) {
        golem_digest key;
        if(!dw_digest(active,"manifest_digest",&key)) loaded=GOLEM_ERR_PARSE;
        else loaded=dw_cas_json(s,&key,&pinned);
        if(loaded==GOLEM_OK) budget=dw_uint(pinned,"byte_budget");
    }
    json_object_put(pinned); as_close(&log);
    if(loaded!=GOLEM_OK) return loaded;
    size_t n=0; golem_status st=golem_workflow_inputs(s,dw_text(c,"selection_id"),kind,&source,
        budget,NULL,0,&n,NULL);
    if(st!=GOLEM_ERR_BUFFER_TOO_SMALL) return st;
    uint8_t *b=malloc(n); if(!b) return GOLEM_ERR_OUT_OF_MEMORY;
    st=golem_workflow_inputs(s,dw_text(c,"selection_id"),kind,&source,budget,b,n,&n,NULL);
    struct json_object *m=NULL;
    if(st==GOLEM_OK) st=golem_json_parse((golem_bytes){b,n},GOLEM_DOCUMENT_MAX_JSON,&m);
    free(b);
    bool found=false; struct json_object *direct=dw_get(m,"direct");
    for(size_t i=0;i<json_object_array_length(direct);++i)
        if(json_object_equal(json_object_array_get_idx(direct,i),dw_get(c,"development_plan"))) found=true;
    if(st==GOLEM_OK && !found) st=GOLEM_ERR_STALE_RESULT;
    struct json_object *req=dw_get(dev->meta,"requirement_ids"),*gates=dw_get(c,"gates");
    for(size_t j=0;st==GOLEM_OK && j<json_object_array_length(gates);++j) {
        struct json_object *cases=dw_get(json_object_array_get_idx(gates,j),"cases");
        for(size_t k=0;st==GOLEM_OK && k<json_object_array_length(cases);++k) {
            bool declared=false;
            for(size_t i=0;i<json_object_array_length(req);++i)
                if(strcmp(json_object_get_string(json_object_array_get_idx(req,i)),dw_text(json_object_array_get_idx(cases,k),"requirement_id"))==0) declared=true;
            if(!declared) st=GOLEM_ERR_REQUIREMENTS_UNMET;
        }
    }
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(req);++i) {
        found=false;
        for(size_t j=0;j<json_object_array_length(gates);++j) {
            struct json_object *cases=dw_get(json_object_array_get_idx(gates,j),"cases");
            for(size_t k=0;k<json_object_array_length(cases);++k)
                if(strcmp(json_object_get_string(json_object_array_get_idx(req,i)),dw_text(json_object_array_get_idx(cases,k),"requirement_id"))==0) found=true;
        }
        if(!found) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    if(st==GOLEM_OK) *out=m; else json_object_put(m);
    return st;
}
