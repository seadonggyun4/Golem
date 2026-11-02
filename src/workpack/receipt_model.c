#include "receipt_internal.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

void wp_receipt_free(wp_bundle *b)
{
    for (size_t i=0;i<b->count;++i) free(b->objects[i].data);
    json_object_put(b->manifest);golem_execution_reply_free(&b->encoded);golem_execution_reply_free(&b->markdown);
    memset(b,0,sizeof(*b));
}
static golem_status add(wp_bundle *b, uint8_t *data, size_t size, const char *type, golem_digest *out)
{
    golem_digest digest;golem_status st=golem_digest_bytes((golem_bytes){data,size},&digest);
    for(size_t i=0;st==GOLEM_OK&&i<b->count;++i) if(dw_equal(&digest,&b->objects[i].digest)) {
        st=strcmp(type,b->objects[i].type)||size!=b->objects[i].size||memcmp(data,b->objects[i].data,size)?GOLEM_ERR_IDENTITY_MISMATCH:GOLEM_OK;
        free(data);if(st==GOLEM_OK)*out=digest;return st;
    }
    if(st==GOLEM_OK&&(b->count==256||size>GOLEM_DOCUMENT_MAX_BODY||size>16777216u-b->total))st=GOLEM_ERR_BUDGET_EXHAUSTED;
    if(st==GOLEM_OK){b->objects[b->count++]=(wp_object){data,size,digest,type};b->total+=size;*out=digest;}else free(data);
    return st;
}
static golem_status add_bytes(wp_bundle *b,golem_bytes bytes,const char *type,golem_digest *out)
{
    uint8_t *p=malloc(bytes.size?bytes.size:1);if(!p)return GOLEM_ERR_OUT_OF_MEMORY;
    memcpy(p,bytes.data,bytes.size);return add(b,p,bytes.size,type,out);
}
static golem_status add_json(wp_bundle *b,struct json_object *o,const char *type,golem_digest *out)
{
    const char *s=json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN);
    return s?add_bytes(b,(golem_bytes){(const uint8_t *)s,strlen(s)},type,out):GOLEM_ERR_OUT_OF_MEMORY;
}
static golem_status add_cas(wp_bundle *b,golem_document_store *s,const golem_digest *key,size_t limit,const char *type,golem_digest *out)
{
    uint8_t *p=NULL;size_t n=0;golem_status st=golem_evidence_read(s->cas,key,limit,NULL,&p,&n,NULL);
    return st==GOLEM_OK?add(b,p,n,type,out):st;
}
golem_status wp_receipt_markdown(struct json_object *m,golem_execution_reply *out)
{
    char text[768];const char *digest=dw_text(dw_get(m,"pack"),"digest");golem_digest check;
    if(!dw_digest(dw_get(m,"pack"),"digest",&check))return GOLEM_ERR_PARSE;
    int n=snprintf(text,sizeof(text),"# Work Pack evidence\n\nDerived projection; not a native receipt or approval.\n\nObjects: %zu\nDocuments: %zu\nPack SHA-256: %s\n\nUnsigned origin. Semantic truth and current completion are not evaluated.\nNon-document dependencies are not exported.\n",json_object_array_length(dw_get(m,"inventory")),json_object_array_length(dw_get(m,"documents")),digest);
    if(n<0||(size_t)n>=sizeof(text))return GOLEM_ERR_OVERFLOW;
    uint8_t *p=malloc((size_t)n);if(!p)return GOLEM_ERR_OUT_OF_MEMORY;memcpy(p,text,(size_t)n);*out=(golem_execution_reply){p,(size_t)n};return GOLEM_OK;
}
golem_status wp_receipt_build(golem_document_store *s,golem_bytes input,const char *format,wp_bundle *out)
{
    if(!s||!out||s->poisoned||!format||(strcmp(format,"json")&&strcmp(format,"markdown")))return GOLEM_ERR_INVALID_ARGUMENT;
    wp_bundle b={0};struct json_object *r=NULL,*binding=NULL,*pack=NULL,*view=NULL,*docs=json_object_new_array(),*inventory=json_object_new_array(),*refs=json_object_new_object(),*work=json_object_new_object(),*packref=json_object_new_object(),*obs=json_object_new_object();
    golem_execution_reply explained={0};golem_status st=golem_json_parse(input,65536,&r);
    const char *keys[]={"schema","expected_generation","binding_receipt","documents"};golem_digest expected;
    if(st==GOLEM_OK&&(!dw_keys(r,keys,4)||strcmp(dw_text(r,"schema"),"golem.workpack.receipt-request.v0")||!json_object_is_type(dw_get(r,"expected_generation"),json_type_int)||dw_uint(r,"expected_generation")!=s->count+1||!dw_digest(r,"binding_receipt",&expected)||!ds_array(dw_get(r,"documents"),1,64)))st=GOLEM_ERR_STALE_RESULT;
    if(st==GOLEM_OK)st=golem_workpack_explain(s,&explained,NULL);
    if(st==GOLEM_OK)st=golem_json_parse((golem_bytes){explained.data,explained.size},GOLEM_DOCUMENT_MAX_JSON,&view);
    if(st==GOLEM_OK&&(strcmp(dw_text(view,"current_mapping"),"APPLICABLE")||!dw_equal(&expected,&s->workpack_binding_digest)))st=GOLEM_ERR_REQUIREMENTS_UNMET;
    const char *raw=dw_text(s->workpack_binding,"request_json");
    if(st==GOLEM_OK)st=golem_json_parse((golem_bytes){(const uint8_t *)raw,strlen(raw)},131072,&binding);
    raw=dw_text(binding,"pack_json");
    if(st==GOLEM_OK)st=golem_json_parse((golem_bytes){(const uint8_t *)raw,strlen(raw)},65536,&pack);
    bool allowed[GOLEM_DOCUMENT_MAX_REVISIONS],selected[GOLEM_DOCUMENT_MAX_REVISIONS];size_t roots[65],count=0;
    if(st==GOLEM_OK)st=wp_document_closure(s,binding,allowed);
    if(st==GOLEM_OK){dw_entry *selection=dw_find(s,dw_text(binding,"selection_id"),0);if(!selection)st=GOLEM_ERR_NOT_FOUND;else roots[count++]=(size_t)(selection-s->entries);}
    struct json_object *a=dw_get(r,"documents");
    for(size_t i=0;st==GOLEM_OK&&i<json_object_array_length(a);++i){
        struct json_object *ref=json_object_array_get_idx(a,i);dw_entry *e=wf_reference(ref)?wf_resolve(s,ref):NULL;
        if(!e||!allowed[e-s->entries]){st=GOLEM_ERR_STALE_RESULT;break;}
        for(size_t j=0;j<i;++j)if(json_object_equal(ref,json_object_array_get_idx(a,j)))st=GOLEM_ERR_IDENTITY_MISMATCH;
        if((size_t)(e-s->entries)!=roots[0])roots[count++]=(size_t)(e-s->entries);
    }
    wf_graph graph={0};if(st==GOLEM_OK)st=wf_graph_make(s,&graph);
    if(st==GOLEM_OK)st=wf_closure(s,&graph,roots,count,selected);
    wf_graph_free(s,&graph);
    golem_digest spec,manifest,receipt,contract,observation;
    if(st==GOLEM_OK)st=add_json(&b,s->spec,"work-spec",&spec);
    if(st==GOLEM_OK)st=add_bytes(&b,(golem_bytes){(const uint8_t *)raw,strlen(raw)},"pack",&manifest);
    if(st==GOLEM_OK)st=add_cas(&b,s,&s->workpack_binding_digest,GOLEM_DOCUMENT_MAX_JSON,"binding",&receipt);
    struct json_object *enrollment=rc_enrollment(s,dw_text(binding,"selection_id"));
    if(st==GOLEM_OK)st=add_json(&b,dw_get(dw_get(enrollment,"request"),"contract"),"role-contract",&contract);
    if(st==GOLEM_OK&&(!ex_text(obs,"schema","golem.workpack.history-observation.v0")||!ex_text(obs,"semantics","HISTORICAL_REFERENCES_ONLY_NOT_EXPORTED")||json_object_object_add(obs,"role_receipt",NULL)||json_object_object_add(obs,"completion_receipt",NULL)))st=GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *last=rc_latest(s,dw_text(binding,"selection_id"));
    for(size_t i=0;st==GOLEM_OK&&last&&i<s->role_count;++i)if(s->roles[i]==last&&!dw_add_digest(obs,"role_receipt",&s->role_digests[i]))st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK&&s->completion_count&&!dw_add_digest(obs,"completion_receipt",&s->completion_digests[s->completion_count-1]))st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK)st=add_json(&b,obs,"history-observation",&observation);
    for(size_t i=0;st==GOLEM_OK&&i<s->count;++i)if(selected[i]){
        if(!allowed[i]){st=GOLEM_ERR_POLICY_DENIED;break;}
        dw_entry *e=&s->entries[i];golem_digest event,meta,body;
        st=add_cas(&b,s,&e->result.manifest_digest,GOLEM_DOCUMENT_MAX_JSON,"document-event",&event);
        if(st==GOLEM_OK)st=add_cas(&b,s,&e->request_digest,GOLEM_DOCUMENT_MAX_JSON,"document-metadata",&meta);
        if(st==GOLEM_OK)st=add_cas(&b,s,&e->result.body_digest,GOLEM_DOCUMENT_MAX_BODY,"document-body",&body);
        if(st==GOLEM_OK){struct json_object *doc=json_object_new_object();
            if(!ex_text(doc,"document_id",dw_text(e->meta,"document_id"))||!ex_uint(doc,"revision",e->result.revision)||!dw_add_digest(doc,"event",&event)||!dw_add_digest(doc,"metadata",&meta)||!dw_add_digest(doc,"body",&body)){json_object_put(doc);st=GOLEM_ERR_OUT_OF_MEMORY;}else if(!wf_append(docs,doc))st=GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    for(size_t i=0;st==GOLEM_OK&&i<b.count;++i){wp_object *o=&b.objects[i];struct json_object *row=json_object_new_object();
        if(!dw_add_digest(row,"digest",&o->digest)||!ex_uint(row,"size",o->size)||!ex_text(row,"type",o->type)||!ex_text(row,"media_type",!strcmp(o->type,"document-body")?"text/markdown":"application/json")){json_object_put(row);st=GOLEM_ERR_OUT_OF_MEMORY;}else if(!wf_append(inventory,row))st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    b.manifest=json_object_new_object();
    if(st==GOLEM_OK&&(!ex_text(work,"identity",dw_text(s->spec,"work_id"))||!ex_uint(work,"generation",s->count+1)||!dw_add_digest(work,"head",&s->last)||
        !ex_text(packref,"id",dw_text(pack,"id"))||!ex_text(packref,"version",dw_text(pack,"version"))||!dw_add_digest(packref,"digest",&manifest)||
        !dw_add_digest(refs,"work_spec",&spec)||!dw_add_digest(refs,"role_contract",&contract)||!dw_add_digest(refs,"observation",&observation)||
        !ex_text(b.manifest,"schema","golem.workpack.receipt-manifest.v0")||!ex_uint(b.manifest,"renderer_version",1)||!ex_text(b.manifest,"format",format)||
        !dw_add(b.manifest,"work",json_object_get(work))||!dw_add(b.manifest,"pack",json_object_get(packref))||!dw_add_digest(b.manifest,"binding_receipt",&receipt)||!dw_add(b.manifest,"refs",json_object_get(refs))||
        !dw_add(b.manifest,"documents",json_object_get(docs))||!dw_add(b.manifest,"inventory",json_object_get(inventory))||
        !ex_text(b.manifest,"limitations","UNSIGNED_ORIGIN;NON_DOCUMENT_DEPENDENCIES_NOT_EXPORTED;CURRENT_COMPLETION_NOT_EVALUATED")||!ex_text(b.manifest,"scope","NATIVE_DOCUMENT_CLOSURE_ONLY")||!ex_text(b.manifest,"current_applicability","NOT_EVALUATED_OFFLINE")||
        !dw_add(b.manifest,"missing_objects",json_object_new_array())||json_object_object_add(b.manifest,"signature",NULL)||json_object_object_add(b.manifest,"projection",NULL)))st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK&&!strcmp(format,"markdown")){
        st=wp_receipt_markdown(b.manifest,&b.markdown);golem_digest d;
        if(st==GOLEM_OK)st=golem_digest_bytes((golem_bytes){b.markdown.data,b.markdown.size},&d);
        if(st==GOLEM_OK){struct json_object *p=json_object_new_object();if(!dw_add_digest(p,"digest",&d)||!ex_uint(p,"size",b.markdown.size)){json_object_put(p);st=GOLEM_ERR_OUT_OF_MEMORY;}else if(!dw_add(b.manifest,"projection",p))st=GOLEM_ERR_OUT_OF_MEMORY;}
    }
    if(st==GOLEM_OK)st=ex_emit(b.manifest,&b.encoded);
    if(st==GOLEM_OK&&b.encoded.size>65536)st=GOLEM_ERR_BUDGET_EXHAUSTED;
    if(st==GOLEM_OK)st=golem_digest_bytes((golem_bytes){b.encoded.data,b.encoded.size},&b.digest);
    if(st==GOLEM_OK)st=wp_receipt_validate(&b,&b.digest);
    if(st==GOLEM_OK){*out=b;memset(&b,0,sizeof(b));}
    wp_receipt_free(&b);golem_execution_reply_free(&explained);json_object_put(r);json_object_put(binding);json_object_put(pack);json_object_put(view);json_object_put(docs);json_object_put(inventory);json_object_put(refs);json_object_put(work);json_object_put(packref);json_object_put(obs);return st;
}
