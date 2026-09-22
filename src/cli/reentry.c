#include "work.h"
#include "golem/reentry.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int golem_cli_reentry(int argc,char **argv)
{
    bool validate=argc==4 && !strcmp(argv[2],"validate");
    bool call=argc==5 && !strcmp(argv[2],"call");
    bool report=argc==5 && !strcmp(argv[2],"report");
    if(!validate && !call && !report) {
        fputs("usage: golem reentry validate REQUEST.json\n"
              "       golem reentry call WORK REQUEST.json\n"
              "       golem reentry report WORK SEQUENCE\n",stderr); return 2;
    }
    golem_document_store *store=NULL; cli_blob input={0}; golem_execution_reply reply={0};
    golem_status st=GOLEM_OK;
    if(!report) st=cli_read(argv[validate?3:4],GOLEM_DOCUMENT_MAX_JSON,&input);
    if(st==GOLEM_OK && validate) st=golem_reentry_validate((golem_bytes){input.data,input.size},NULL);
    if(st==GOLEM_OK && !validate) st=golem_document_store_open(argv[3],true,NULL,&store,NULL);
    if(st==GOLEM_OK && call) st=golem_reentry_call(store,(golem_bytes){input.data,input.size},&reply,NULL);
    if(st==GOLEM_OK && report) {
        char *end; unsigned long seq=strtoul(argv[4],&end,10);
        if(!*argv[4] || *end || seq<1 || seq>64) st=GOLEM_ERR_INVALID_ARGUMENT;
        else st=golem_reentry_report(store,(uint32_t)seq,true,&reply,NULL);
    }
    if(st==GOLEM_OK && reply.size && fwrite(reply.data,1,reply.size,stdout)!=reply.size) st=GOLEM_ERR_IO;
    if(st==GOLEM_OK && !report) fputc('\n',stdout);
    free(input.data); golem_execution_reply_free(&reply);
    golem_status closed=golem_document_store_close(store); if(st==GOLEM_OK) st=closed;
    if(st!=GOLEM_OK) fprintf(stderr,"reentry: %s\n",golem_status_string(st));
    return st==GOLEM_OK?0:1;
}
