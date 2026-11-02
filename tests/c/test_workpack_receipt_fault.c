#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "../../src/workpack/receipt_internal.h"
#include "test.h"
#include <stdio.h>
#include <string.h>
static int mode;
static golem_status interrupted(int fd,const char *name,golem_bytes bytes)
{
    if(mode==0)return GOLEM_ERR_IO;
    golem_status st=dw_publish(fd,name,bytes);
    return st==GOLEM_OK&&!strcmp(name,"COMMIT.json")?GOLEM_ERR_IO:st;
}
#define dw_publish interrupted
#include "../../src/workpack/receipt_store.c"
#undef dw_publish
int main(int argc,char **argv)
{
    CHECK(argc==5);mode=atoi(argv[4]);
    FILE *f=fopen(argv[2],"rb");CHECK(f);uint8_t data[65537];size_t n=fread(data,1,sizeof(data),f);CHECK(!ferror(f)&&n<sizeof(data));CHECK(fclose(f)==0);
    golem_document_store *s=NULL;CHECK(golem_document_store_open(argv[1],false,NULL,&s,NULL)==GOLEM_OK);
    golem_execution_reply reply={0};CHECK(golem_workpack_receipt_manifest(s,(golem_bytes){data,n},argv[3],"json",&reply,NULL)==GOLEM_OK);
    struct json_object *p=NULL;CHECK(golem_json_parse((golem_bytes){reply.data,reply.size},GOLEM_DOCUMENT_MAX_JSON,&p)==GOLEM_OK);
    golem_digest approval,expected,result,saved;CHECK(dw_digest(p,"approval_digest",&approval));CHECK(dw_digest(p,"manifest_digest",&expected));json_object_put(p);golem_execution_reply_free(&reply);
    memset(&result,0xa5,sizeof(result));saved=result;
    CHECK(golem_workpack_receipt_export(s,(golem_bytes){data,n},argv[3],"json",&approval,&result,NULL)==GOLEM_ERR_IO);CHECK(dw_equal(&result,&saved));
    char hex[65],path[4096];size_t required;CHECK(golem_digest_format(&expected,hex,sizeof(hex),&required)==GOLEM_OK);CHECK(ws_join(path,argv[3],hex)==GOLEM_OK);
    uint8_t sentinel=42;reply=(golem_execution_reply){&sentinel,1};
    if(mode==0){CHECK(golem_workpack_receipt_verify(path,&expected,&reply,NULL)!=GOLEM_OK);CHECK(reply.data==&sentinel&&reply.size==1);}
    else{CHECK(golem_workpack_receipt_verify(path,&expected,&reply,NULL)==GOLEM_OK);golem_execution_reply_free(&reply);}
    CHECK(golem_workpack_receipt_export(s,(golem_bytes){data,n},argv[3],"json",&approval,&result,NULL)==GOLEM_ERR_IDENTITY_MISMATCH);CHECK(dw_equal(&result,&saved));
    CHECK(golem_document_store_close(s)==GOLEM_OK);return 0;
}
