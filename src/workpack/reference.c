#include "golem/workpack.h"
#include "../workflow/role_internal.h"
#include <string.h>
#include <math.h>

static bool count(struct json_object *o,const char *key,bool nullable)
{
    struct json_object *v=dw_get(o,key);
    return (!v&&nullable)||(json_object_is_type(v,json_type_int)&&json_object_get_int64(v)>=0);
}
static bool text(struct json_object *o,const char *key,size_t max)
{
    struct json_object *v=dw_get(o,key);
    return json_object_is_type(v,json_type_string)&&strlen(dw_text(o,key))>0&&strlen(dw_text(o,key))<=max;
}
static bool boolean(struct json_object *o,const char *key,bool nullable)
{ return (!dw_get(o,key)&&nullable)||json_object_is_type(dw_get(o,key),json_type_boolean); }
static bool digest(struct json_object *o,const char *key,const golem_digest *expected)
{ golem_digest d;return dw_digest(o,key,&d)&&dw_equal(&d,expected); }
static bool checks(struct json_object *d)
{
    const char *keys[]={"row_count","column_count","success","issue_count","execution_issue_count","checks"};
    struct json_object *a=dw_get(d,"checks");
    if(!dw_keys(d,keys,6)||!count(d,"row_count",true)||!count(d,"column_count",true)||!boolean(d,"success",true)||!count(d,"issue_count",true)||!count(d,"execution_issue_count",true)||!ds_array(a,0,100))return false;
    for(size_t i=0;i<json_object_array_length(a);++i){struct json_object *r=json_object_array_get_idx(a,i);const char *k[]={"name","success","issue_count"};
        if(!dw_keys(r,k,3)||!text(r,"name",128)||!boolean(r,"success",true)||!count(r,"issue_count",true))return false;
        for(size_t j=0;j<i;++j)if(!strcmp(dw_text(r,"name"),dw_text(json_object_array_get_idx(a,j),"name")))return false;
    }return true;
}
static bool profile(struct json_object *d)
{
    const char *keys[]={"row_count","column_count","columns"};struct json_object *a=dw_get(d,"columns");
    if(!dw_keys(d,keys,3)||!count(d,"row_count",true)||!count(d,"column_count",true)||!ds_array(a,0,100))return false;
    for(size_t i=0;i<json_object_array_length(a);++i){struct json_object *r=json_object_array_get_idx(a,i);const char *k[]={"name","dtype","null_pct","unique_pct"};
        if(!dw_keys(r,k,4)||!text(r,"name",256)||!text(r,"dtype",32)|| (dw_get(r,"null_pct")&&!text(r,"null_pct",32))||(dw_get(r,"unique_pct")&&!text(r,"unique_pct",32)))return false;
        for(size_t j=0;j<i;++j)if(!strcmp(dw_text(r,"name"),dw_text(json_object_array_get_idx(a,j),"name")))return false;
    }return !dw_get(d,"column_count")||dw_uint(d,"column_count")>=json_object_array_length(a);
}
static bool scan(struct json_object *d)
{
    const char *keys[]={"row_count","finding_count","count_semantics","findings"};struct json_object *a=dw_get(d,"findings");
    if(!dw_keys(d,keys,4)||!count(d,"row_count",true)||!count(d,"finding_count",true)||strcmp(dw_text(d,"count_semantics"),"estimated_from_first_1000_non_null_values")||!ds_array(a,0,100))return false;
    for(size_t i=0;i<json_object_array_length(a);++i){struct json_object *r=json_object_array_get_idx(a,i);const char *k[]={"column","pii_type","count","confidence"};struct json_object *c=dw_get(r,"confidence");
        if(!dw_keys(r,k,4)||!text(r,"column",256)||!text(r,"pii_type",128)||!count(r,"count",true))return false;
        if(c&&(!json_object_is_type(c,json_type_int)&&!json_object_is_type(c,json_type_double)))return false;
        if(c&&(!isfinite(json_object_get_double(c))||json_object_get_double(c)<0||json_object_get_double(c)>100))return false;
    }return !dw_get(d,"finding_count")||dw_uint(d,"finding_count")>=json_object_array_length(a);
}
static const char *quality(struct json_object *response)
{
    struct json_object *d=dw_get(response,"data"),*a=dw_get(d,"checks");
    if(!json_object_get_boolean(dw_get(response,"ok")))return "TOOL_FAILED";
    if(json_object_get_boolean(dw_get(response,"truncated"))||!dw_get(d,"success")||!dw_get(d,"execution_issue_count")||dw_uint(d,"execution_issue_count")||!dw_get(d,"issue_count")||!dw_get(d,"row_count")||!dw_uint(d,"row_count")||!dw_get(d,"column_count")||!dw_uint(d,"column_count")||json_object_array_length(a)!=2)return "UNKNOWN";
    bool null=false,duplicate=false,all=true;uint64_t issues=0;
    for(size_t i=0;i<2;++i){struct json_object *r=json_object_array_get_idx(a,i);const char *name=dw_text(r,"name");
        if(!strcmp(name,"null"))null=true;else if(!strcmp(name,"duplicate"))duplicate=true;else return "UNKNOWN";
        if(!dw_get(r,"success")||!dw_get(r,"issue_count"))return "UNKNOWN";
        bool success=json_object_get_boolean(dw_get(r,"success"));if(success!=(dw_uint(r,"issue_count")==0))return "UNKNOWN";
        if(dw_uint(r,"issue_count")>UINT64_MAX-issues)return "UNKNOWN";issues+=dw_uint(r,"issue_count");all=all&&success;
    }
    if(!null||!duplicate||issues!=dw_uint(d,"issue_count")||all!=json_object_get_boolean(dw_get(d,"success")))return "UNKNOWN";
    return all?"DECLARED_CHECKS_SATISFIED":"DECLARED_CHECKS_FAILED";
}
golem_status golem_workpack_reference_observe(golem_bytes input,const golem_digest *source,const golem_digest *config,const golem_digest *pack,golem_execution_reply *out,golem_diagnostic *diagnostic)
{
    if(!source||!config||!pack||!out)return dw_report(diagnostic,GOLEM_ERR_INVALID_ARGUMENT,"REFERENCE_INPUT");
    struct json_object *r=NULL,*p=NULL,*c=NULL,*responses[3]={0},*o=NULL,*observations=json_object_new_array();golem_digest exact,hash;golem_status st=golem_json_parse(input,262144,&r);
    const char *keys[]={"schema","mode","pack_json","source","config_json","results"},*sk[]={"digest","size"};
    if(st==GOLEM_OK&&(!dw_keys(r,keys,6)||strcmp(dw_text(r,"schema"),"golem.workpack.truthound-capture.v0")||(strcmp(dw_text(r,"mode"),"MOCK")&&strcmp(dw_text(r,"mode"),"CAPTURED_EXTERNAL"))||!text(r,"pack_json",65536)||!text(r,"config_json",4096)||!dw_keys(dw_get(r,"source"),sk,2)||!digest(dw_get(r,"source"),"digest",source)||!count(dw_get(r,"source"),"size",false)||!dw_uint(dw_get(r,"source"),"size")||dw_uint(dw_get(r,"source"),"size")>104857600||!ds_array(dw_get(r,"results"),3,3)))st=GOLEM_ERR_PARSE;
    const char *raw=dw_text(r,"pack_json");
    if(st==GOLEM_OK)st=golem_workpack_validate((golem_bytes){(const uint8_t*)raw,strlen(raw)},&hash,NULL);
    if(st==GOLEM_OK&&!dw_equal(&hash,pack))st=GOLEM_ERR_DIGEST_MISMATCH;
    if(st==GOLEM_OK)st=golem_json_parse((golem_bytes){(const uint8_t*)raw,strlen(raw)},65536,&p);
    if(st==GOLEM_OK&&(strcmp(dw_text(p,"id"),"io.styxis.golem.dataset-release-gate")||strcmp(dw_text(p,"version"),"0.1.0")))st=GOLEM_ERR_UNSUPPORTED_VERSION;
    raw=dw_text(r,"config_json");
    if(st==GOLEM_OK)st=golem_digest_bytes((golem_bytes){(const uint8_t*)raw,strlen(raw)},&hash);
    if(st==GOLEM_OK&&!dw_equal(&hash,config))st=GOLEM_ERR_DIGEST_MISMATCH;
    if(st==GOLEM_OK)st=golem_json_parse((golem_bytes){(const uint8_t*)raw,strlen(raw)},4096,&c);
    const char *ck[]={"schema","producer_version","producer_digest","max_file_bytes","max_items","max_response_bytes","timeout_seconds"};
    if(st==GOLEM_OK&&(!dw_keys(c,ck,7)||strcmp(dw_text(c,"schema"),"golem.workpack.truthound-config.v0")||strcmp(dw_text(c,"producer_version"),"3.3.1")||!dw_digest(c,"producer_digest",&hash)||!count(c,"max_file_bytes",false)||dw_uint(c,"max_file_bytes")!=104857600||!count(c,"max_items",false)||dw_uint(c,"max_items")!=100||!count(c,"max_response_bytes",false)||dw_uint(c,"max_response_bytes")!=65536||!count(c,"timeout_seconds",false)||dw_uint(c,"timeout_seconds")!=30))st=GOLEM_ERR_UNSUPPORTED_VERSION;
    const char *tools[]={"check_file","profile_file","scan_pii"},*ops[]={"check","profile","scan"};bool complete=true;
    for(size_t i=0;st==GOLEM_OK&&i<3;++i){struct json_object *row=json_object_array_get_idx(dw_get(r,"results"),i);const char *rk[]={"tool","response_json"};
        if(!dw_keys(row,rk,2)||strcmp(dw_text(row,"tool"),tools[i])||!text(row,"response_json",65536)){st=GOLEM_ERR_PARSE;break;}
        raw=dw_text(row,"response_json");st=golem_json_parse((golem_bytes){(const uint8_t*)raw,strlen(raw)},65536,&responses[i]);if(st!=GOLEM_OK)break;
        struct json_object *e=responses[i],*data=dw_get(e,"data");const char *ek[]={"schema_version","operation","ok","data","truncated","error"};
        if(!dw_keys(e,ek,6)||!count(e,"schema_version",false)||dw_uint(e,"schema_version")!=1||strcmp(dw_text(e,"operation"),ops[i])||!boolean(e,"ok",false)||!boolean(e,"truncated",false)){st=GOLEM_ERR_PARSE;break;}
        bool success=json_object_get_boolean(dw_get(e,"ok")),truncated=json_object_get_boolean(dw_get(e,"truncated"));
        if(success){if(dw_get(e,"error")||!(i==0?checks(data):i==1?profile(data):scan(data))){st=GOLEM_ERR_PARSE;break;}}
        else {const char *error_keys[]={"code"};if(data||!dw_keys(dw_get(e,"error"),error_keys,1)||!text(dw_get(e,"error"),"code",128)){st=GOLEM_ERR_PARSE;break;}}
        if(success&&!truncated&&i==1&&dw_get(data,"column_count")&&dw_uint(data,"column_count")!=json_object_array_length(dw_get(data,"columns"))){st=GOLEM_ERR_PARSE;break;}
        if(success&&!truncated&&i==2&&dw_get(data,"finding_count")&&dw_uint(data,"finding_count")!=json_object_array_length(dw_get(data,"findings"))){st=GOLEM_ERR_PARSE;break;}
        for(size_t j=0;success&&st==GOLEM_OK&&j<i;++j){struct json_object *prior=dw_get(responses[j],"data");
            if(prior&&dw_get(prior,"row_count")&&dw_get(data,"row_count")&&dw_uint(prior,"row_count")!=dw_uint(data,"row_count"))st=GOLEM_ERR_STALE_RESULT;
            if(prior&&dw_get(prior,"column_count")&&dw_get(data,"column_count")&&dw_uint(prior,"column_count")!=dw_uint(data,"column_count"))st=GOLEM_ERR_STALE_RESULT;
        }
        if(st!=GOLEM_OK)break;
        complete=complete&&success&&!truncated;
        st=golem_digest_bytes((golem_bytes){(const uint8_t*)raw,strlen(raw)},&hash);
        struct json_object *item=json_object_new_object();
        if(st==GOLEM_OK&&(!ex_text(item,"tool",tools[i])||!dw_add_digest(item,"response_digest",&hash)||!dw_add(item,"response",json_object_get(e))||!ex_text(item,"execution",success?"DECLARED_SUCCEEDED":"DECLARED_FAILED")))st=GOLEM_ERR_OUT_OF_MEMORY;
        if(st==GOLEM_OK){if(!wf_append(observations,item))st=GOLEM_ERR_OUT_OF_MEMORY;}else json_object_put(item);
    }
    if(st==GOLEM_OK)st=golem_digest_bytes(input,&exact);
    if(st==GOLEM_OK){o=json_object_new_object();if(!ex_text(o,"schema","golem.workpack.reference-observation.v0")||!dw_add_digest(o,"capture_digest",&exact)||!dw_add_digest(o,"pack_digest",pack)||!dw_add_digest(o,"config_digest",config)||!dw_add(o,"source",json_object_get(dw_get(r,"source")))||!ex_text(o,"mode_declared",dw_text(r,"mode"))||!ex_text(o,"source_binding","UNAUTHENTICATED_CAPTURE_ATTESTATION")||!ex_text(o,"quality",quality(responses[0]))||!ex_text(o,"pii_scope","SAMPLED_ESTIMATES_NOT_ABSENCE_PROOF")||!dw_add(o,"complete_untruncated_delivery",json_object_new_boolean(complete))||!dw_add(o,"observations",json_object_get(observations))||!ex_text(o,"release_readiness","NOT_EVALUATED")||!dw_add(o,"authorized",json_object_new_boolean(false))||!dw_add(o,"identity_verified",json_object_new_boolean(false))||!dw_add(o,"completion_verified",json_object_new_boolean(false)))st=GOLEM_ERR_OUT_OF_MEMORY;}
    if(st==GOLEM_OK)st=ex_emit(o,out);
    for(size_t i=0;i<3;++i)json_object_put(responses[i]);json_object_put(observations);json_object_put(r);json_object_put(p);json_object_put(c);json_object_put(o);return dw_report(diagnostic,st,"REFERENCE_OBSERVATION_NOT_AUTHORITY");
}
