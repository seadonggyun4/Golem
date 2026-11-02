#include "receipt_internal.h"
#include "binding_internal.h"
#include <string.h>

static bool integer(struct json_object *o,const char *key,uint64_t lo,uint64_t hi)
{ return json_object_is_type(dw_get(o,key),json_type_int)&&json_object_get_int64(dw_get(o,key))>=0&&dw_uint(o,key)>=lo&&dw_uint(o,key)<=hi; }
static bool digest_equal(struct json_object *a,const char *ak,struct json_object *b,const char *bk)
{ golem_digest x,y;return dw_digest(a,ak,&x)&&dw_digest(b,bk,&y)&&dw_equal(&x,&y); }
static int object(wp_bundle *b,struct json_object *o,const char *key,const char *type,bool *used)
{
    golem_digest d;if(!dw_digest(o,key,&d))return -1;
    for(size_t i=0;i<b->count;++i)if(dw_equal(&d,&b->objects[i].digest)&&!strcmp(type,b->objects[i].type)){used[i]=true;return (int)i;}
    return -1;
}
static bool history_digest(struct json_object *o,const char *key)
{ golem_digest d;return !dw_get(o,key)||dw_digest(o,key,&d); }
static bool known_type(const char *s)
{
    const char *types[]={"work-spec","pack","binding","role-contract","history-observation","document-event","document-metadata","document-body"};
    for(size_t i=0;i<8;++i)if(!strcmp(s,types[i]))return true;
    return false;
}
golem_status wp_receipt_validate(wp_bundle *b,const golem_digest *expected)
{
    if(!expected||!b||!b->encoded.data||b->encoded.size>65536||!b->count||b->count>256)return GOLEM_ERR_INVALID_ARGUMENT;
    golem_digest actual;golem_status st=golem_digest_bytes((golem_bytes){b->encoded.data,b->encoded.size},&actual);
    if(st!=GOLEM_OK)return st;
    if(!dw_equal(&actual,expected))return GOLEM_ERR_DIGEST_MISMATCH;
    struct json_object *m=b->manifest,*parsed[256]={0};bool used[256]={false};
    const char *keys[]={"schema","renderer_version","format","work","pack","binding_receipt","refs","documents","inventory","scope","current_applicability","missing_objects","signature","projection","limitations"};
    const char *wk[]={"identity","generation","head"},*pk[]={"id","version","digest"},*rk[]={"work_spec","role_contract","observation"};
    struct json_object *w=dw_get(m,"work"),*p=dw_get(m,"pack"),*refs=dw_get(m,"refs"),*docs=dw_get(m,"documents"),*inventory=dw_get(m,"inventory");
    st=GOLEM_ERR_PARSE;
    if(!dw_keys(m,keys,15)||strcmp(dw_text(m,"schema"),"golem.workpack.receipt-manifest.v0")||!integer(m,"renderer_version",1,1)||
        (strcmp(dw_text(m,"format"),"json")&&strcmp(dw_text(m,"format"),"markdown"))||!dw_keys(w,wk,3)||!dw_id(dw_text(w,"identity"))||!integer(w,"generation",1,GOLEM_DOCUMENT_MAX_REVISIONS+1)||!dw_digest(w,"head",&actual)||
        !dw_keys(p,pk,3)||!dw_keys(refs,rk,3)||!ds_array(docs,1,83)||!ds_array(inventory,b->count,b->count)||
        strcmp(dw_text(m,"scope"),"NATIVE_DOCUMENT_CLOSURE_ONLY")||strcmp(dw_text(m,"current_applicability"),"NOT_EVALUATED_OFFLINE")||
        strcmp(dw_text(m,"limitations"),"UNSIGNED_ORIGIN;NON_DOCUMENT_DEPENDENCIES_NOT_EXPORTED;CURRENT_COMPLETION_NOT_EVALUATED")||!ds_array(dw_get(m,"missing_objects"),0,0)||dw_get(m,"signature"))goto done;
    size_t total=0;
    for(size_t i=0;i<b->count;++i){
        wp_object *o=&b->objects[i];struct json_object *row=json_object_array_get_idx(inventory,i);const char *ik[]={"digest","size","media_type","type"};
        if(!o->data||!dw_keys(row,ik,4)||!known_type(dw_text(row,"type"))||strcmp(o->type,dw_text(row,"type"))||
            !integer(row,"size",1,!strcmp(o->type,"document-body")?GOLEM_DOCUMENT_MAX_BODY:GOLEM_DOCUMENT_MAX_JSON)||o->size!=dw_uint(row,"size")||
            !dw_digest(row,"digest",&actual)||!dw_equal(&actual,&o->digest)||strcmp(dw_text(row,"media_type"),!strcmp(o->type,"document-body")?"text/markdown":"application/json")||o->size>16777216u-total)goto done;
        for(size_t j=0;j<i;++j)if(dw_equal(&o->digest,&b->objects[j].digest))goto done;
        total+=o->size;st=golem_digest_bytes((golem_bytes){o->data,o->size},&actual);
        if(st!=GOLEM_OK)goto done;
        if(!dw_equal(&actual,&o->digest)){st=GOLEM_ERR_DIGEST_MISMATCH;goto done;}
        if(strcmp(o->type,"document-body")){st=golem_json_parse((golem_bytes){o->data,o->size},GOLEM_DOCUMENT_MAX_JSON,&parsed[i]);if(st!=GOLEM_OK)goto done;}
        st=GOLEM_ERR_PARSE;
    }
    int spec=object(b,refs,"work_spec","work-spec",used),pack=object(b,p,"digest","pack",used),binding=object(b,m,"binding_receipt","binding",used),role=object(b,refs,"role_contract","role-contract",used),obs=object(b,refs,"observation","history-observation",used);
    if(spec<0||pack<0||binding<0||role<0||obs<0)goto done;
    st=golem_work_spec_validate((golem_bytes){b->objects[spec].data,b->objects[spec].size},NULL);if(st!=GOLEM_OK)goto done;
    st=golem_workpack_validate((golem_bytes){b->objects[pack].data,b->objects[pack].size},&actual,NULL);if(st!=GOLEM_OK)goto done;
    st=golem_role_validate((golem_bytes){b->objects[role].data,b->objects[role].size},&actual,NULL);if(st!=GOLEM_OK)goto done;
    st=GOLEM_ERR_PARSE;
    if(!dw_equal(&actual,&b->objects[role].digest)||strcmp(dw_text(w,"identity"),dw_text(parsed[spec],"work_id"))||strcmp(dw_text(p,"id"),dw_text(parsed[pack],"id"))||strcmp(dw_text(p,"version"),dw_text(parsed[pack],"version")))goto done;
    const char *bk[]={"schema_version","type","request_json","scope","approved_binding"};struct json_object *be=parsed[binding],*br=NULL;
    if(!dw_keys(be,bk,5)||!integer(be,"schema_version",1,1)||strcmp(dw_text(be,"type"),"workpack-binding")||!json_object_is_type(dw_get(be,"request_json"),json_type_string))goto done;
    const char *raw=dw_text(be,"request_json");struct json_object *bound_pack=NULL;
    st=wp_binding_request((golem_bytes){(const uint8_t *)raw,strlen(raw)},&br,&bound_pack,&actual);json_object_put(bound_pack);if(st!=GOLEM_OK)goto done;
    /* A historical binding's checksum/header references only. Never replay an
     * incomplete ledger or authenticate its approved_binding field offline. */
    const char *sk[]={"domain","native_core_version","request_digest","work_spec_digest","previous_work_frame","manifest_digest","selection_manifest_digest"};
    struct json_object *scope=dw_get(be,"scope");golem_digest request_hash,scope_hash,approval_hash;bool compatible=false;
    golem_status header=golem_digest_bytes((golem_bytes){(const uint8_t *)raw,strlen(raw)},&request_hash);
    if(header==GOLEM_OK)header=ex_hash(scope,&scope_hash);
    const char *core=dw_text(scope,"native_core_version");
    if(header==GOLEM_OK)header=golem_workpack_compatibility((golem_bytes){b->objects[pack].data,b->objects[pack].size},(golem_string_view){core,strlen(core)},&compatible,NULL);
    bool related=header==GOLEM_OK&&compatible&&dw_keys(scope,sk,7)&&!strcmp(dw_text(scope,"domain"),"golem.workpack.binding-approval.v1")&&dw_digest(scope,"previous_work_frame",&actual)&&
        dw_digest(scope,"request_digest",&actual)&&dw_equal(&actual,&request_hash)&&dw_digest(be,"approved_binding",&approval_hash)&&dw_equal(&approval_hash,&scope_hash)&&
        integer(br,"expected_generation",1,dw_uint(w,"generation"))&&digest_equal(br,"role_contract_digest",refs,"role_contract")&&digest_equal(dw_get(be,"scope"),"manifest_digest",p,"digest")&&digest_equal(dw_get(be,"scope"),"work_spec_digest",refs,"work_spec")&&
        !strcmp(dw_text(br,"mapping"),"native-documents-v1")&&dw_id(dw_text(br,"selection_id"))&&strlen(dw_text(br,"pack_json"))==b->objects[pack].size&&!memcmp(dw_text(br,"pack_json"),b->objects[pack].data,b->objects[pack].size);
    bool selection_found=false;const char *selection_id=dw_text(br,"selection_id");
    st=related?GOLEM_OK:GOLEM_ERR_IDENTITY_MISMATCH;
    for(size_t i=0;st==GOLEM_OK&&i<json_object_array_length(docs);++i){
        struct json_object *doc=json_object_array_get_idx(docs,i);const char *dk[]={"document_id","revision","event","metadata","body"};
        if(!dw_keys(doc,dk,5)||!dw_id(dw_text(doc,"document_id"))||!integer(doc,"revision",1,UINT32_MAX)){st=GOLEM_ERR_PARSE;break;}
        for(size_t j=0;j<i;++j)if(!strcmp(dw_text(doc,"document_id"),dw_text(json_object_array_get_idx(docs,j),"document_id")))st=GOLEM_ERR_IDENTITY_MISMATCH;
        int event=object(b,doc,"event","document-event",used),meta=object(b,doc,"metadata","document-metadata",used),body=object(b,doc,"body","document-body",used);
        if(event<0||meta<0||body<0){st=GOLEM_ERR_NOT_FOUND;break;}
        const char *ek[]={"schema_version","type","metadata_digest","body_digest","idempotency_key"};struct json_object *ev=parsed[event],*md=parsed[meta];
        if(!dw_keys(ev,ek,5)||!integer(ev,"schema_version",1,1)||strcmp(dw_text(ev,"type"),"document")||!dw_id(dw_text(ev,"idempotency_key"))||!digest_equal(ev,"metadata_digest",doc,"metadata")||!digest_equal(ev,"body_digest",doc,"body")||
            strcmp(dw_text(md,"work_id"),dw_text(w,"identity"))||strcmp(dw_text(md,"document_id"),dw_text(doc,"document_id"))||dw_uint(md,"revision")!=dw_uint(doc,"revision")){st=GOLEM_ERR_IDENTITY_MISMATCH;break;}
        if(st==GOLEM_OK)st=golem_document_validate((golem_bytes){b->objects[meta].data,b->objects[meta].size},(golem_bytes){b->objects[body].data,b->objects[body].size},NULL);
        if(!strcmp(dw_text(doc,"document_id"),selection_id)&&!strcmp(dw_text(md,"kind"),"stage-selection")&&digest_equal(doc,"event",dw_get(be,"scope"),"selection_manifest_digest"))selection_found=true;
        struct json_object *parents=dw_get(md,"parents");
        for(size_t j=0;st==GOLEM_OK&&j<json_object_array_length(parents);++j){struct json_object *parent=json_object_array_get_idx(parents,j);bool found=false;
            for(size_t k=0;k<json_object_array_length(docs);++k){struct json_object *candidate=json_object_array_get_idx(docs,k);if(!strcmp(dw_text(parent,"document_id"),dw_text(candidate,"document_id"))&&dw_uint(parent,"revision")==dw_uint(candidate,"revision")&&digest_equal(parent,"digest",candidate,"event"))found=true;}
            if(!found)st=GOLEM_ERR_NOT_FOUND;
        }
    }
    json_object_put(br);if(st!=GOLEM_OK)goto done;
    if(!selection_found){st=GOLEM_ERR_IDENTITY_MISMATCH;goto done;}
    const char *ok[]={"schema","semantics","role_receipt","completion_receipt"};struct json_object *ob=parsed[obs];
    st=GOLEM_ERR_PARSE;
    if(!dw_keys(ob,ok,4)||strcmp(dw_text(ob,"schema"),"golem.workpack.history-observation.v0")||strcmp(dw_text(ob,"semantics"),"HISTORICAL_REFERENCES_ONLY_NOT_EXPORTED")||!history_digest(ob,"role_receipt")||!history_digest(ob,"completion_receipt"))goto done;
    for(size_t i=0;i<b->count;++i)if(!used[i])goto done;
    if(!strcmp(dw_text(m,"format"),"json")){if(dw_get(m,"projection")||b->markdown.size)goto done;}
    else {struct json_object *projection=dw_get(m,"projection");const char *pr[]={"digest","size"};golem_execution_reply rendered={0};
        if(!dw_keys(projection,pr,2)||!integer(projection,"size",1,768)||!dw_digest(projection,"digest",&actual)||b->markdown.size!=dw_uint(projection,"size"))goto done;
        golem_digest hash;st=golem_digest_bytes((golem_bytes){b->markdown.data,b->markdown.size},&hash);
        if(st==GOLEM_OK&&!dw_equal(&actual,&hash))st=GOLEM_ERR_DIGEST_MISMATCH;
        if(st==GOLEM_OK)st=wp_receipt_markdown(m,&rendered);
        if(st==GOLEM_OK&&(rendered.size!=b->markdown.size||memcmp(rendered.data,b->markdown.data,rendered.size)))st=GOLEM_ERR_DIGEST_MISMATCH;
        golem_execution_reply_free(&rendered);if(st!=GOLEM_OK)goto done;
    }
    st=GOLEM_OK;
done:
    for(size_t i=0;i<256;++i)json_object_put(parsed[i]);
    return st;
}
