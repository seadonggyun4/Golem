#include "../../src/intent/product_gate.h"
#include "../../src/document/internal.h"
#include "../../src/execution/internal.h"
#include "../../src/completion/internal.h"
#include "test.h"
#include <stdlib.h>
#include <string.h>
static struct json_object *parse(const char *s)
{struct json_object *o=NULL;if(golem_json_parse((golem_bytes){(const uint8_t *)s,strlen(s)},GOLEM_DOCUMENT_MAX_JSON,&o)!=GOLEM_OK)abort();return o;}
static void put(struct json_object *o,const char *k,const char *s)
{json_object_object_add(o,k,json_object_new_string(s));}
int main(void)
{
    golem_document_store s={0};s.spec=parse("{\"schema_version\":1}");
    for(int i=GI_PRODUCT_DEVELOPMENT;i<=GI_PRODUCT_PUBLICATION;++i)CHECK(gi_product_check(&s,(gi_product_boundary)i)==GOLEM_OK);
    json_object_object_add(s.spec,"schema_version",json_object_new_int(3));
    CHECK(gi_product_check(&s,GI_PRODUCT_DEVELOPMENT)==GOLEM_ERR_POLICY_DENIED);
    struct json_object *binding=json_object_new_object();const char *zero="0000000000000000000000000000000000000000000000000000000000000000";
    put(binding,"registration_ref",zero);put(binding,"baseline_ref",zero);put(binding,"policy_ref",zero);
    json_object_object_add(s.spec,"intent_binding",binding);put(s.spec,"support_profile","LOCAL_NO_MERGE");
    CHECK(gi_product_spec(s.spec)==GOLEM_OK);
    for(int i=GI_PRODUCT_DEVELOPMENT;i<=GI_PRODUCT_PUBLICATION;++i)CHECK(gi_product_check(&s,(gi_product_boundary)i)==GOLEM_ERR_REQUIREMENTS_UNMET);
    struct json_object *event=parse("{\"type\":\"document\"}");
    CHECK(gi_product_record(&s,event)==GOLEM_OK);put(event,"type","completion");CHECK(gi_product_record(&s,event)==GOLEM_ERR_REQUIREMENTS_UNMET);
    put(event,"type","intent-enrollment");CHECK(gi_product_record(&s,event)==GOLEM_ERR_REQUIREMENTS_UNMET);
    CHECK(ex_authorize(&s,NULL,NULL)==GOLEM_ERR_REQUIREMENTS_UNMET);
    struct json_object *out=NULL,*request=parse("{}");
    CHECK(co_evaluate_v1(&s,request,false,&out)==GOLEM_ERR_UNSUPPORTED_VERSION);CHECK(out==NULL);
    /* Historical acknowledgment cannot enable product work without current proofs. */
    s.intent_enrollment=parse("{}");
    for(int i=GI_PRODUCT_DEVELOPMENT;i<=GI_PRODUCT_PUBLICATION;++i)CHECK(gi_product_check(&s,(gi_product_boundary)i)==GOLEM_ERR_UNSUPPORTED_VERSION);
    golem_digest d={{1}},a,b;
    CHECK(gi_product_enrollment_approval(&s,&d,&d,&d,&d,2,&d,3,&d,&a)==GOLEM_OK);
    CHECK(gi_product_enrollment_approval(&s,&d,&d,&d,&d,2,&d,4,&d,&b)==GOLEM_OK);CHECK(!dw_equal(&a,&b));
    put(s.spec,"support_profile","FULL_MERGE");CHECK(gi_product_spec(s.spec)!=GOLEM_OK);
    json_object_put(s.spec);json_object_put(s.intent_enrollment);json_object_put(event);json_object_put(request);return 0;
}
