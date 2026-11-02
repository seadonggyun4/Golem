#include "golem/workpack.h"
#include "test.h"
#include <stdio.h>
#include <string.h>
int main(int argc, char **argv)
{
    CHECK(argc==2 || argc==3);
    FILE *f=fopen(argv[argc-1],"rb"); CHECK(f);
    uint8_t bytes[GOLEM_WORKPACK_PROPOSAL_MAX_JSON+1];size_t n=fread(bytes,1,sizeof(bytes),f);CHECK(!ferror(f)&&n<sizeof(bytes));CHECK(fclose(f)==0);
    golem_digest d, expected, saved;memset(&d,0xa5,sizeof(d));saved=d;
    CHECK(golem_workpack_proposal_validate((golem_bytes){bytes,n},&d,NULL)==GOLEM_OK);
    CHECK(golem_digest_bytes((golem_bytes){bytes,n},&expected)==GOLEM_OK);CHECK(!memcmp(&d,&expected,sizeof(d)));
    d=saved;CHECK(golem_workpack_proposal_validate((golem_bytes){(const uint8_t *)"{}",2},&d,NULL)==GOLEM_ERR_PARSE);CHECK(!memcmp(&d,&saved,sizeof(d)));
    uint8_t sentinel=42;golem_execution_reply reply={&sentinel,1};golem_bytes input={bytes,n};
    if(argc==3) {
        golem_document_store *s=NULL;CHECK(golem_document_store_open(argv[1],false,NULL,&s,NULL)==GOLEM_OK);
        CHECK(golem_workpack_assess(s,&input,1,&reply,NULL)==GOLEM_ERR_STALE_RESULT);
        CHECK(reply.data==&sentinel&&reply.size==1);CHECK(golem_document_store_close(s)==GOLEM_OK);
    } else {
        CHECK(golem_workpack_assess(NULL,&input,1,&reply,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(reply.data==&sentinel&&reply.size==1);
    }
    return 0;
}
