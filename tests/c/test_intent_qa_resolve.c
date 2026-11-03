#include "../../src/intent/qa_resolve.h"
#include "../../src/document/internal.h"
#include "test.h"
#include "golem/execution.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static golem_bytes raw(struct json_object *o){return (golem_bytes){(const uint8_t *)json_object_get_string(o),(size_t)json_object_get_string_len(o)};}
static golem_status observe(void *p,golem_digest *registration,golem_digest *policy,golem_digest *bundle,uint64_t *now)
{
    struct json_object *f=p;*now=110;
    return dw_digest(f,"registration",registration)&&dw_digest(f,"policy_pin",policy)&&dw_digest(f,"bundle_pin",bundle)?GOLEM_OK:GOLEM_ERR_PARSE;
}
int main(void)
{
    FILE *file=fopen(INTENT_QA_FIXTURE,"rb");CHECK(file!=NULL);
    char *buffer=malloc(262144);CHECK(buffer!=NULL);size_t n=fread(buffer,1,262144,file);CHECK(!ferror(file)&&feof(file));fclose(file);
    struct json_object *f=NULL;CHECK(golem_json_parse((golem_bytes){(uint8_t *)buffer,n},262144,&f)==GOLEM_OK);free(buffer);
    golem_digest registration,policy,bundle;uint64_t now;CHECK(observe(f,&registration,&policy,&bundle,&now)==GOLEM_OK);
    gi_review_host *host=NULL;CHECK(gi_review_host_open(raw(dw_get(f,"policy")),&policy,raw(dw_get(f,"bundle")),&bundle,raw(dw_get(f,"control")),&registration,observe,f,&host)==GOLEM_OK);
    gi_source_input source={raw(dw_get(f,"source")),raw(dw_get(f,"text"))};golem_bytes definition=raw(dw_get(f,"definition"));
    gi_qa_paths_inputs inputs={{raw(dw_get(f,"baseline")),&source,1,&definition,1},raw(dw_get(f,"applicability")),raw(dw_get(f,"obligations")),raw(dw_get(f,"mapping")),raw(dw_get(f,"contract"))};
    /* Contract identity follows native compact JSON (including its escaping),
     * rather than a foreign JSON serializer's approximation. */
    struct json_object *mapping=NULL;golem_digest contract_digest;
    CHECK(golem_execution_contract_validate(inputs.execution_contract,&contract_digest,NULL)==GOLEM_OK);
    CHECK(golem_json_parse(inputs.mapping,GI_CONTROL_MAX,&mapping)==GOLEM_OK);
    CHECK(dw_add_digest(dw_get(mapping,"body"),"execution_contract_digest",&contract_digest));
    const char *mapping_bytes=json_object_to_json_string_ext(mapping,JSON_C_TO_STRING_PLAIN);
    inputs.mapping=(golem_bytes){(const uint8_t *)mapping_bytes,strlen(mapping_bytes)};
    golem_bytes objects[4];for(size_t i=0;i<4;++i)objects[i]=raw(json_object_array_get_idx(dw_get(f,"objects"),i));
    gi_qa_paths_result result={0};
    CHECK(gi_qa_paths_resolve(&inputs,objects,4,host,&result,NULL)==GOLEM_OK);
    CHECK(result.structurally_complete&&result.unsupported_references==0&&!result.execution_authorized&&!result.qa_accepted);
    gi_qa_paths_result prior=result;
    CHECK(gi_qa_paths_resolve(&inputs,objects,3,host,&result,NULL)!=GOLEM_OK);CHECK(!memcmp(&prior,&result,sizeof(result)));
    /* Each selected object is required; omission never becomes an empty PASS. */
    for(size_t omit=0;omit<4;++omit){golem_bytes subset[3];size_t used=0;
        for(size_t i=0;i<4;++i)if(i!=omit)subset[used++]=objects[i];
        CHECK(gi_qa_paths_resolve(&inputs,subset,3,host,&result,NULL)!=GOLEM_OK);
        CHECK(!memcmp(&prior,&result,sizeof(result)));
    }
    /* Provided bytes cannot silently replace a pinned object. */
    golem_bytes saved=objects[0];objects[0]=(golem_bytes){(const uint8_t *)"{}",2};
    CHECK(gi_qa_paths_resolve(&inputs,objects,4,host,&result,NULL)!=GOLEM_OK);objects[0]=saved;
    /* Same object set in another order is the same closed reference graph. */
    golem_bytes reversed[4];for(size_t i=0;i<4;++i)reversed[i]=objects[3-i];
    CHECK(gi_qa_paths_resolve(&inputs,reversed,4,host,&result,NULL)==GOLEM_OK);
    CHECK(result.structurally_complete&&!result.execution_authorized&&!result.qa_accepted);
    objects[3]=objects[0];CHECK(gi_qa_paths_resolve(&inputs,objects,4,host,&result,NULL)!=GOLEM_OK);
    gi_review_host_close(host);json_object_put(mapping);json_object_put(f);return 0;
}
