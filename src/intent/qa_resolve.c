#include "qa_resolve.h"
#include "../document/internal.h"
#include "../execution/internal.h"
#include <stdlib.h>
#include <string.h>
typedef struct object {struct json_object *json;golem_digest digest;bool used;} object;
typedef struct resolver {object *objects;size_t count;struct json_object *base;} resolver;
static bool eq(struct json_object *o,const char *k,const char *s){return !strcmp(dw_text(o,k),s);}
static bool same(struct json_object *a,struct json_object *b,const char *k){return json_object_equal(dw_get(a,k),dw_get(b,k));}
static struct json_object *resolve(resolver *r,struct json_object *ref,const char *schema)
{
    golem_digest d;if(!json_object_is_type(ref,json_type_string)||golem_digest_parse((golem_string_view){json_object_get_string(ref),(size_t)json_object_get_string_len(ref)},&d)!=GOLEM_OK)return NULL;
    for(size_t i=0;i<r->count;++i)if(dw_equal(&r->objects[i].digest,&d)&&eq(r->objects[i].json,"schema",schema)){
        r->objects[i].used=true;return dw_get(r->objects[i].json,"body");}
    return NULL;
}
static bool root_shape(struct json_object *o,struct json_object *base)
{
    const char *keys[]={"schema","project_id","work_id","created_by_assertion","body"};
    return dw_keys(o,keys,5)&&same(o,base,"project_id")&&same(o,base,"work_id")&&*dw_text(o,"created_by_assertion");
}
static golem_status target(resolver *r,struct json_object *ref,const char *route)
{
    struct json_object *t=resolve(r,ref,"golem.intent.qa-target.v1");const char *tk[]={"id","route","locality","locator","artifact_ref"};
    if(!dw_keys(t,tk,5)||!dw_id(dw_text(t,"id"))||!eq(t,"route",route)||!eq(t,"locality","LOCAL")||!*dw_text(t,"locator")||strlen(dw_text(t,"locator"))>4096)return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *a=resolve(r,dw_get(t,"artifact_ref"),"golem.intent.qa-artifact.v1");const char *ak[]={"media_type","content","sha256"};golem_digest expected,actual;
    struct json_object *content=dw_get(a,"content");
    if(!dw_keys(a,ak,3)||!eq(a,"media_type","text/plain")||!json_object_is_type(content,json_type_string)||!dw_digest(a,"sha256",&expected))return GOLEM_ERR_UNSUPPORTED_VERSION;
    golem_bytes bytes={(const uint8_t *)json_object_get_string(content),(size_t)json_object_get_string_len(content)};
    golem_status st=gi_text_validate(bytes,NULL);if(st==GOLEM_OK)st=golem_digest_bytes(bytes,&actual);
    return st==GOLEM_OK&&!dw_equal(&actual,&expected)?GOLEM_ERR_IDENTITY_MISMATCH:st;
}
golem_status gi_qa_paths_resolve(const gi_qa_paths_inputs *in,const golem_bytes *objects,size_t count,
    gi_review_host *host,gi_qa_paths_result *out,golem_diagnostic *diagnostic)
{
    if(!in||!objects||!count||count>4096||!host||!out)return GOLEM_ERR_INVALID_ARGUMENT;
    gi_qa_paths_result result;golem_status st=gi_qa_paths_inspect(in,&result,diagnostic);if(st!=GOLEM_OK)return st;
    if(result.undecided)return GOLEM_ERR_REQUIREMENTS_UNMET;
    resolver r={calloc(count,sizeof(object)),count,NULL};if(!r.objects)return GOLEM_ERR_OUT_OF_MEMORY;
    struct json_object *app=NULL,*obs=NULL;size_t total=0;
    st=golem_json_parse(in->baseline.baseline,GI_CONTROL_MAX,&r.base);
    for(size_t i=0;st==GOLEM_OK&&i<count;++i){
        if(objects[i].size>GI_CONTROL_MAX||objects[i].size>GI_DISPATCH_MAX-total){st=GOLEM_ERR_OVERFLOW;break;}total+=objects[i].size;
        st=golem_json_parse(objects[i],GI_CONTROL_MAX,&r.objects[i].json);
        if(st==GOLEM_OK&&!root_shape(r.objects[i].json,r.base))st=GOLEM_ERR_PARSE;
        if(st==GOLEM_OK)st=gi_domain_digest(objects[i],&r.objects[i].digest,diagnostic);
        for(size_t j=0;st==GOLEM_OK&&j<i;++j)if(dw_equal(&r.objects[j].digest,&r.objects[i].digest))st=GOLEM_ERR_PARSE;
    }
    if(st==GOLEM_OK)st=golem_json_parse(in->applicability,GI_CONTROL_MAX,&app);
    if(st==GOLEM_OK)st=golem_json_parse(in->obligations,GI_CONTROL_MAX,&obs);
    struct json_object *rows=dw_get(dw_get(app,"body"),"rows"),*obligations=dw_get(dw_get(obs,"body"),"obligations");
    for(size_t i=0;st==GOLEM_OK&&i<json_object_array_length(rows);++i){
        struct json_object *row=json_object_array_get_idx(rows,i),*subject=json_object_new_object();golem_digest subject_id,review,decision;
        const char *fields[]={"requirement_ref","route","target_refs","disposition","rationale"};
        if(!dw_add(subject,"domain",json_object_new_string("golem.intent.applicability-subject.v1"))||
            !dw_add(subject,"baseline_digest",json_object_get(dw_get(app,"baseline_digest"))))st=GOLEM_ERR_OUT_OF_MEMORY;
        for(size_t j=0;st==GOLEM_OK&&j<5;++j)if(!dw_add(subject,fields[j],json_object_get(dw_get(row,fields[j]))))st=GOLEM_ERR_OUT_OF_MEMORY;
        if(st==GOLEM_OK)st=ex_hash(subject,&subject_id);json_object_put(subject);
        if(st==GOLEM_OK&&(!dw_digest(row,"review_ref",&review)||!dw_digest(row,"decision_ref",&decision)))st=GOLEM_ERR_PARSE;
        if(st==GOLEM_OK)st=gi_review_host_subject(host,&review,&subject_id,false);
        if(st==GOLEM_OK)st=gi_review_host_subject(host,&decision,&subject_id,true);
        struct json_object *targets=dw_get(row,"target_refs");
        for(size_t j=0;st==GOLEM_OK&&j<json_object_array_length(targets);++j)st=target(&r,json_object_array_get_idx(targets,j),dw_text(row,"route"));
    }
    struct json_object *plan=NULL,*plan_refs=NULL;bool *used=NULL;
    if(st==GOLEM_OK){plan=resolve(&r,dw_get(dw_get(obs,"body"),"oracle_plan_ref"),"golem.intent.qa-oracle-plan.v1");
        const char *keys[]={"oracle_refs"};plan_refs=dw_get(plan,"oracle_refs");
        if(!dw_keys(plan,keys,1)||!json_object_is_type(plan_refs,json_type_array)||json_object_array_length(plan_refs)>GI_PARENT_MAX)st=GOLEM_ERR_PARSE;
        else {used=calloc(json_object_array_length(plan_refs)+1,sizeof(bool));if(!used)st=GOLEM_ERR_OUT_OF_MEMORY;}}
    for(size_t i=0;st==GOLEM_OK&&i<json_object_array_length(obligations);++i){
        struct json_object *o=json_object_array_get_idx(obligations,i),*oracle=resolve(&r,dw_get(o,"oracle_ref"),"golem.intent.qa-oracle.v1");
        const char *keys[]={"target_ref","condition","expected_outcome","stage","evidence_kind"};
        if(!dw_keys(oracle,keys,5)){st=GOLEM_ERR_UNSUPPORTED_VERSION;break;}
        for(size_t j=0;j<5;++j)if(!same(o,oracle,keys[j]))st=GOLEM_ERR_IDENTITY_MISMATCH;
        bool found=false;for(size_t j=0;j<json_object_array_length(plan_refs);++j)if(json_object_equal(dw_get(o,"oracle_ref"),json_object_array_get_idx(plan_refs,j))){
            if(found){st=GOLEM_ERR_PARSE;break;}used[j]=true;found=true;}
        if(!found)st=GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    for(size_t i=0;st==GOLEM_OK&&i<json_object_array_length(plan_refs);++i)if(!used[i])st=GOLEM_ERR_REQUIREMENTS_UNMET;
    for(size_t i=0;st==GOLEM_OK&&i<count;++i)if(!r.objects[i].used)st=GOLEM_ERR_REQUIREMENTS_UNMET;
    if(st==GOLEM_OK){result.unsupported_references=0;*out=result;}
    free(used);for(size_t i=0;i<count;++i)json_object_put(r.objects[i].json);free(r.objects);
    json_object_put(r.base);json_object_put(app);json_object_put(obs);return st;
}
