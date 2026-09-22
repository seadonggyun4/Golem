#include "golem/agent_session.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct test_clock { uint64_t now; unsigned boot; } test_clock;
static golem_status clock_read(void *ctx,uint64_t *now,golem_digest *boot)
{
    test_clock *c=ctx; *now=c->now; memset(boot,0,sizeof(*boot)); boot->bytes[0]=(uint8_t)c->boot;
    return GOLEM_OK;
}
/* Fixture-only executable, never installed. The real CLI has no clock override. */
int main(int argc,char **argv)
{
    if(argc!=5) return 2;
    FILE *f=fopen(argv[2],"rb"); if(!f) return 2;
    uint8_t *data=malloc(GOLEM_DOCUMENT_MAX_JSON+1); if(!data) { fclose(f); return 2; }
    size_t n=fread(data,1,GOLEM_DOCUMENT_MAX_JSON+1,f); int bad=ferror(f); fclose(f);
    if(bad || n>GOLEM_DOCUMENT_MAX_JSON) { free(data); return 2; }
    test_clock c={strtoull(argv[3],NULL,10),(unsigned)strtoul(argv[4],NULL,10)};
    golem_agent_clock clock={clock_read,&c}; golem_document_store *s=NULL; golem_agent_reply reply={0};
    golem_status st=golem_document_store_open(argv[1],true,NULL,&s,NULL);
    if(st==GOLEM_OK) st=golem_agent_session_call(s,(golem_bytes){data,n},&clock,&reply,NULL);
    golem_status closed=golem_document_store_close(s); if(st==GOLEM_OK) st=closed;
    if(st==GOLEM_OK) { (void)fwrite(reply.data,1,reply.size,stdout); (void)fputc('\n',stdout); }
    else fprintf(stderr,"%s\n",golem_status_string(st));
    free(data); golem_agent_reply_free(&reply); return st==GOLEM_OK?0:1;
}
