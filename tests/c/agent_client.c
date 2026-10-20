#include "golem/agent_session.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
typedef struct test_clock {
    uint64_t now;
    unsigned boot, calls;
    bool crash_before_commit, expire_before_publication, rollback_before_publication, boot_before_publication;
} test_clock;
static golem_status clock_read(void *ctx,uint64_t *now,golem_digest *boot)
{
    test_clock *c=ctx;
    ++c->calls;
    if (c->crash_before_commit && c->calls == 2) _exit(86);
    *now=c->now; memset(boot,0,sizeof(*boot)); boot->bytes[0]=(uint8_t)c->boot;
    if (c->expire_before_publication && c->calls == 2) c->now += 10000;
    if (c->rollback_before_publication && c->calls == 2) --c->now;
    if (c->boot_before_publication && c->calls == 2) ++c->boot;
    return GOLEM_OK;
}
/* Fixture-only executable, never installed. The real CLI has no clock override. */
int main(int argc,char **argv)
{
    if(argc!=5 && argc!=6) return 2;
    if(argc==6 && strcmp(argv[5],"crash_before_commit") && strcmp(argv[5],"crash_after_commit") &&
       strcmp(argv[5],"expire_before_publication") && strcmp(argv[5],"rollback_before_publication") &&
       strcmp(argv[5],"boot_before_publication")) return 2;
    FILE *f=fopen(argv[2],"rb"); if(!f) return 2;
    uint8_t *data=malloc(GOLEM_DOCUMENT_MAX_JSON+1); if(!data) { fclose(f); return 2; }
    size_t n=fread(data,1,GOLEM_DOCUMENT_MAX_JSON+1,f); int bad=ferror(f); fclose(f);
    if(bad || n>GOLEM_DOCUMENT_MAX_JSON) { free(data); return 2; }
    test_clock c={.now=strtoull(argv[3],NULL,10),.boot=(unsigned)strtoul(argv[4],NULL,10),
                  .crash_before_commit=argc==6 && !strcmp(argv[5],"crash_before_commit"),
                  .expire_before_publication=argc==6 && !strcmp(argv[5],"expire_before_publication"),
                  .rollback_before_publication=argc==6 && !strcmp(argv[5],"rollback_before_publication"),
                  .boot_before_publication=argc==6 && !strcmp(argv[5],"boot_before_publication")};
    golem_agent_clock clock={clock_read,&c}; golem_document_store *s=NULL; golem_agent_reply reply={0};
    golem_diagnostic diagnostic;
    (void)golem_diagnostic_clear(&diagnostic);
    golem_status st=golem_document_store_open(argv[1],true,NULL,&s,&diagnostic);
    if(st==GOLEM_OK) st=golem_agent_session_call(s,(golem_bytes){data,n},&clock,&reply,&diagnostic);
    if(st==GOLEM_OK && argc==6 && !strcmp(argv[5],"crash_after_commit")) _exit(87);
    golem_status closed=golem_document_store_close(s); if(st==GOLEM_OK) st=closed;
    if(st==GOLEM_OK) { (void)fwrite(reply.data,1,reply.size,stdout); (void)fputc('\n',stdout); }
    else fprintf(stderr,"%s: %s\n",golem_status_string(st),diagnostic.message);
    free(data); golem_agent_reply_free(&reply); return st==GOLEM_OK?0:1;
}
