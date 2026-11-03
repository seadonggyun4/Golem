#include "../../src/intent/qa_paths.h"
#include "../../src/common/json.h"
#include "golem/execution.h"
#include "test.h"
#include <string.h>
#include <stdlib.h>
static golem_bytes bytes(const char *s) { return (golem_bytes){(const uint8_t *)s, strlen(s)}; }
static struct json_object *get(struct json_object *o, const char *k)
{ struct json_object *v = NULL; (void)json_object_object_get_ex(o,k,&v); return v; }
static golem_bytes wire(struct json_object *o)
{ return bytes(json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN)); }
static void put(struct json_object *o, const char *k, const char *v)
{ (void)json_object_object_add(o,k,json_object_new_string(v)); }
static int hex(const golem_digest *d, char out[65])
{ size_t n; CHECK(golem_digest_format(d,out,65,&n)==GOLEM_OK); return 0; }

static struct json_object *parse(const char *s)
{struct json_object *o=NULL;if(golem_json_parse(bytes(s),GI_CONTROL_MAX,&o)!=GOLEM_OK)abort();return o;}
static struct json_object *envelope(const char *schema,const char *baseline,struct json_object *body)
{struct json_object *o=json_object_new_object();put(o,"schema",schema);put(o,"project_id","demo");put(o,"work_id","work");put(o,"created_by_assertion","fixture");put(o,"baseline_digest",baseline);json_object_object_add(o,"body",body);return o;}
static int link_digest(struct json_object *body,const char *key,struct json_object *o)
{golem_digest d;char s[65];CHECK(gi_domain_digest(wire(o),&d,NULL)==GOLEM_OK);CHECK(hex(&d,s)==0);put(body,key,s);return 0;}
int main(void)
{
    golem_digest raw,sd,rd,bd;char rh[65],sh[65],dh[65],bh[65],defs[65];
    CHECK(golem_digest_bytes(bytes("abc"),&raw)==GOLEM_OK);CHECK(hex(&raw,rh)==0);
    char source[2048],definition[2048],baseline[4096];
    int n=snprintf(source,sizeof(source),
        "{\"schema\":\"golem.intent.source.v1\",\"project_id\":\"demo\",\"work_id\":\"work\","
        "\"created_by_assertion\":\"fixture\",\"body\":{\"body_cas\":\"%s\",\"byte_length\":3,"
        "\"media_type\":\"text/plain\",\"encoding\":\"UTF-8\",\"origin\":\"MODEL_DRAFT\","
        "\"capture_ref\":\"fixture\",\"designation\":{\"scope_id\":\"scope\",\"ranges\":[{\"start\":0,\"end\":3}],"
        "\"purpose\":\"PRODUCT_REQUIREMENT\",\"decision_ref\":\"%s\"},\"execution_authority\":false}}",rh,rh);
    CHECK(n>0&&(size_t)n<sizeof(source));gi_source_input si={bytes(source),bytes("abc")};
    CHECK(gi_source_identity(si.control,si.text,&sd,NULL)==GOLEM_OK);CHECK(hex(&sd,sh)==0);
    n=snprintf(definition,sizeof(definition),
        "{\"schema\":\"golem.intent.requirement.v1\",\"project_id\":\"demo\",\"work_id\":\"work\","
        "\"created_by_assertion\":\"fixture\",\"body\":{\"id\":\"REQ-1\",\"exact_text\":\"abc\","
        "\"source_spans\":[{\"source_ref\":\"%s\",\"start\":0,\"end\":3}],\"modality\":\"MUST\","
        "\"quantifier\":\"ALL\",\"negative\":false,\"conditions\":[],\"acceptance_oracle_refs\":[],"
        "\"derivation_rationale\":\"fixture only\"}}",sh);
    CHECK(n>0&&(size_t)n<sizeof(definition));CHECK(gi_domain_digest(bytes(definition),&rd,NULL)==GOLEM_OK);CHECK(hex(&rd,dh)==0);
    n=snprintf(baseline,sizeof(baseline),
        "{\"schema\":\"golem.intent.baseline.v1\",\"project_id\":\"demo\",\"work_id\":\"work\","
        "\"created_by_assertion\":\"fixture\",\"body\":{\"source_refs\":[\"%s\"],\"previous_baseline_digest\":null,"
        "\"decision_refs\":[],\"requirement_refs\":[\"%s\"],\"constraint_refs\":[],\"issuer_policy_ref\":\"%s\","
        "\"coverage_manifest\":[{\"source_ref\":\"%s\",\"rows\":[{\"start\":0,\"end\":3,\"classification\":\"REQUIREMENT\","
        "\"requirement_refs\":[\"%s\"],\"constraint_refs\":[],\"rationale\":\"fixture\",\"review_refs\":[]}]}]}}",sh,dh,rh,sh,dh);
    CHECK(n>0&&(size_t)n<sizeof(baseline));CHECK(gi_baseline_identity(bytes(baseline),&bd,NULL)==GOLEM_OK);CHECK(hex(&bd,bh)==0);
    golem_bytes def=bytes(definition);gi_review_inputs in={bytes(baseline),&si,1,&def,1};gi_review_binding binding;
    CHECK(gi_review_bind(&in,&binding,NULL)==GOLEM_OK);CHECK(hex(&binding.definitions,defs)==0);

    struct json_object *ab=json_object_new_object(),*rows=json_object_new_array();json_object_object_add(ab,"rows",rows);
    const char *routes[]={"UI","API","BATCH","STATE_TRANSITION","OTHER_LOCAL"};
    for(size_t i=0;i<5;++i){struct json_object *r=json_object_new_object(),*targets=json_object_new_array();
        put(r,"requirement_ref",dh);put(r,"route",routes[i]);put(r,"disposition",i==0?"REQUIRED":"NOT_APPLICABLE");
        put(r,"rationale","exact fixture disposition");put(r,"review_ref",rh);put(r,"decision_ref",rh);
        if(i==0)json_object_array_add(targets,json_object_new_string(rh));json_object_object_add(r,"target_refs",targets);json_object_array_add(rows,r);}
    struct json_object *app=envelope("golem.intent.qa-applicability.v1",bh,ab);
    struct json_object *ob=json_object_new_object(),*obligations=json_object_new_array(),*o=json_object_new_object();
    put(o,"id","ob1");put(o,"requirement_ref",dh);put(o,"route","UI");put(o,"target_ref",rh);put(o,"condition","valid request");put(o,"expected_outcome","accepted response");put(o,"oracle_ref",rh);put(o,"stage","TEST_DESIGN");put(o,"evidence_kind","NATIVE_QA");
    json_object_array_add(obligations,o);json_object_object_add(ob,"obligations",obligations);put(ob,"oracle_plan_ref",rh);CHECK(link_digest(ob,"applicability_ref",app)==0);
    struct json_object *obs=envelope("golem.intent.qa-obligations.v1",bh,ob);
    struct json_object *contract=parse("{\"schema_version\":1,\"selection_id\":\"selection\",\"development_plan\":{\"document_id\":\"plan\",\"revision\":1},\"snapshot_plan\":{\"schema_version\":1,\"timeout_seconds\":1,\"repositories\":[{\"id\":\"repo\",\"root\":\"/tmp/not-executed\",\"paths\":[\"src\"],\"toolchain\":\"fixture\",\"test_configuration\":\"fixture\"}]},\"gates\":[{\"id\":\"gate\",\"version\":1,\"repository\":\"repo\",\"argv\":[\"/not-executed\"],\"timeout_ms\":1,\"cases\":[{\"id\":\"case\",\"requirement_id\":\"REQ-1\"}],\"protected_paths\":[\"src\"]}]}");
    put(get(contract,"development_plan"),"digest",rh);golem_digest cd;char ch[65];CHECK(golem_execution_contract_validate(wire(contract),&cd,NULL)==GOLEM_OK);CHECK(hex(&cd,ch)==0);
    struct json_object *mb=json_object_new_object(),*mappings=json_object_new_array(),*m=parse("{\"obligation_id\":\"ob1\",\"gate_id\":\"gate\",\"gate_version\":1,\"case_id\":\"case\"}");
    json_object_array_add(mappings,m);json_object_object_add(mb,"mappings",mappings);put(mb,"execution_contract_digest",ch);CHECK(link_digest(mb,"obligations_ref",obs)==0);
    struct json_object *map=envelope("golem.intent.qa-mapping.v1",bh,mb);
    gi_qa_paths_inputs input={in,wire(app),wire(obs),wire(map),wire(contract)};gi_qa_paths_result result={0};
    CHECK(gi_qa_paths_inspect(&input,&result,NULL)==GOLEM_OK);CHECK(result.structurally_complete&&result.unsupported_references>0&&!result.qa_accepted&&!result.execution_authorized);
    gi_qa_paths_result saved=result;
    put(m,"case_id","absent");input.mapping=wire(map);CHECK(gi_qa_paths_inspect(&input,&result,NULL)!=GOLEM_OK);CHECK(!memcmp(&result,&saved,sizeof(result)));put(m,"case_id","case");
    put(o,"evidence_kind","SEMANTIC_REVIEW");CHECK(link_digest(mb,"obligations_ref",obs)==0);input.obligations=wire(obs);input.mapping=wire(map);CHECK(gi_qa_paths_inspect(&input,&result,NULL)!=GOLEM_OK);
    put(o,"evidence_kind","NATIVE_QA");put(o,"condition","TBD");CHECK(link_digest(mb,"obligations_ref",obs)==0);input.obligations=wire(obs);input.mapping=wire(map);CHECK(gi_qa_paths_inspect(&input,&result,NULL)!=GOLEM_OK);
    const char *placeholders[]={" tbd ","\tToDo\n"," n/a ","..."};
    for(size_t i=0;i<4;++i){put(o,"condition",placeholders[i]);
        CHECK(link_digest(mb,"obligations_ref",obs)==0);input.obligations=wire(obs);input.mapping=wire(map);
        CHECK(gi_qa_paths_inspect(&input,&result,NULL)!=GOLEM_OK);}
    put(o,"condition","valid request");put(json_object_array_get_idx(rows,1),"route","UI");CHECK(link_digest(ob,"applicability_ref",app)==0);CHECK(link_digest(mb,"obligations_ref",obs)==0);input.applicability=wire(app);input.obligations=wire(obs);input.mapping=wire(map);CHECK(gi_qa_paths_inspect(&input,&result,NULL)!=GOLEM_OK);
    json_object_put(app);json_object_put(obs);json_object_put(map);json_object_put(contract);return 0;
}
