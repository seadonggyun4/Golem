#include "work.h"
#include "golem/workflow.h"
#include <stdlib.h>
#include <string.h>
static bool number(const char *s,uint64_t max,uint64_t *out)
{
    if(!s || !*s) return false;
    uint64_t n=0;
    for(;*s;++s) { if(*s<'0'||*s>'9'||n>(max-(unsigned)(*s-'0'))/10) return false; n=n*10+(unsigned)(*s-'0'); }
    if(!n || n>max) return false;
    *out=n; return true;
}
int golem_cli_workflow(int argc,char **argv)
{
    if(argc<5) return 2;
    bool select=strcmp(argv[2],"select")==0 && argc==7;
    bool inputs=strcmp(argv[2],"inputs")==0 && argc==8;
    bool trace=strcmp(argv[2],"trace")==0 && argc==6;
    bool next=strcmp(argv[2],"next")==0 && argc==5;
    if(!select && !inputs && !trace && !next) return 2;
    uint64_t revision=0,budget=0; golem_digest source;
    if((select||trace) && !number(argv[5],GOLEM_DOCUMENT_MAX_REVISIONS,&revision)) return 2;
    if(inputs && (!number(argv[7],GOLEM_WORKFLOW_CONTEXT_MAX,&budget) ||
        golem_digest_parse((golem_string_view){argv[6],strlen(argv[6])},&source)!=GOLEM_OK)) return 2;
    golem_document_store *s=NULL;
    golem_status st=golem_document_store_open(argv[3],false,NULL,&s,NULL);
    uint8_t *buffer=NULL; size_t n=0,capacity=0;
    for(int pass=0;st==GOLEM_OK && pass<2;++pass) {
        if(select) st=golem_workflow_select(s,argv[4],(uint32_t)revision,argv[6],buffer,capacity,&n,NULL);
        if(inputs) st=golem_workflow_inputs(s,argv[4],argv[5],&source,budget,buffer,capacity,&n,NULL);
        if(trace) st=golem_workflow_trace(s,argv[4],(uint32_t)revision,buffer,capacity,&n,NULL);
        if(next) st=golem_workflow_next(s,argv[4],buffer,capacity,&n,NULL);
        if(st==GOLEM_ERR_BUFFER_TOO_SMALL && pass==0) {
            buffer=malloc(n); capacity=n; st=buffer?GOLEM_OK:GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    struct json_object *o=NULL;
    if(st==GOLEM_OK) st=cli_json_parse((golem_bytes){buffer,n},&o);
    golem_status closed=golem_document_store_close(s); if(st==GOLEM_OK) st=closed;
    free(buffer); return cli_emit(st,o);
}
