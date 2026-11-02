#include "../../src/document/internal.h"
#include "golem/workpack.h"
#include "test.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int publish_then_fail;
static golem_status interrupted(golem_document_store *s, const golem_digest *payload, golem_digest *frame)
{
    if (publish_then_fail) { golem_status st = dw_event_write(s,payload,frame); if(st!=GOLEM_OK)return st; }
    return GOLEM_ERR_IO;
}
#include "golem/version.h"
static const char *test_core_version = GOLEM_VERSION_STRING;
#undef GOLEM_VERSION_STRING
#define GOLEM_VERSION_STRING test_core_version
#define dw_event_write interrupted
#include "../../src/workpack/binding.c"
#undef dw_event_write
int main(int argc,char **argv)
{
    CHECK(argc==4);publish_then_fail=atoi(argv[3]);
    FILE *f=fopen(argv[2],"rb");CHECK(f);uint8_t input[131073];size_t n=fread(input,1,sizeof(input),f);CHECK(!ferror(f)&&n<sizeof(input));CHECK(fclose(f)==0);
    golem_document_store *s=NULL;golem_execution_reply out={0};golem_diagnostic d;
    CHECK(golem_document_store_open(argv[1],false,NULL,&s,&d)==GOLEM_OK);
    CHECK(golem_workpack_resolve(s,(golem_bytes){input,n},&out,&d)==GOLEM_OK);
    struct json_object *o=NULL;CHECK(golem_json_parse((golem_bytes){out.data,out.size},GOLEM_DOCUMENT_MAX_JSON,&o)==GOLEM_OK);
    golem_digest approval;CHECK(dw_digest(o,"binding_digest",&approval));json_object_put(o);golem_execution_reply_free(&out);
    uint8_t sentinel=42;out=(golem_execution_reply){&sentinel,1};
    CHECK(golem_workpack_bind(s,(golem_bytes){input,n},&approval,&out,&d)==GOLEM_ERR_POLICY_DENIED);CHECK(out.data==&sentinel&&out.size==1);
    CHECK(golem_document_store_close(s)==GOLEM_OK);
    CHECK(golem_document_store_open(argv[1],true,NULL,&s,&d)==GOLEM_OK);
    struct json_object *permission=json_object_get(dw_get(s->spec,"permission"));
    CHECK(ex_text(s->spec,"permission","DENY"));
    CHECK(golem_workpack_bind(s,(golem_bytes){input,n},&approval,&out,&d)==GOLEM_ERR_POLICY_DENIED);
    CHECK(ex_text(s->spec,"permission","ASK_ALWAYS"));
    CHECK(golem_workpack_bind(s,(golem_bytes){input,n},&approval,&out,&d)==GOLEM_ERR_APPROVAL_REQUIRED);
    CHECK(dw_add(s->spec,"permission",permission));
    CHECK(out.data==&sentinel&&out.size==1);
    CHECK(golem_workpack_bind(s,(golem_bytes){input,n},&approval,&out,&d)==GOLEM_ERR_IO);
    CHECK(s->poisoned&&out.data==&sentinel&&out.size==1);
    CHECK(golem_workpack_bind(s,(golem_bytes){input,n},&approval,&out,&d)==GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_document_store_close(s)==GOLEM_OK);
    /* Historical replay uses the approved version; current applicability uses this reader. */
    test_core_version="99.0.0";
    CHECK(golem_document_store_open(argv[1],false,NULL,&s,&d)==GOLEM_OK);
    if(publish_then_fail) {
        CHECK(golem_workpack_explain(s,&out,&d)==GOLEM_OK);
        CHECK(golem_json_parse((golem_bytes){out.data,out.size},GOLEM_DOCUMENT_MAX_JSON,&o)==GOLEM_OK);
        CHECK(!strcmp(dw_text(o,"current_mapping"),"BLOCKED"));
        CHECK(!strcmp(dw_text(o,"blocker"),golem_status_string(GOLEM_ERR_UNSUPPORTED_VERSION)));
        json_object_put(o);golem_execution_reply_free(&out);
    }
    else {CHECK(golem_workpack_explain(s,&out,&d)==GOLEM_ERR_NOT_FOUND);CHECK(out.data==&sentinel&&out.size==1);}
    CHECK(golem_document_store_close(s)==GOLEM_OK);return 0;
}
