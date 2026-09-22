#include "work.h"
#include "golem/completion.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int golem_cli_completion(int argc,char **argv)
{
    bool validate=argc==4 && !strcmp(argv[2],"validate");
    bool call=argc==5 && !strcmp(argv[2],"call");
    bool report=argc==5 && !strcmp(argv[2],"report");
    if(!validate && !call && !report) {
        fputs("usage: golem completion validate REQUEST.json\n"
              "       golem completion call WORK REQUEST.json\n"
              "       golem completion report WORK SEQUENCE\n",stderr); return 2;
    }
    golem_document_store *s=NULL; cli_blob b={0}; golem_execution_reply out={0}; golem_status st=GOLEM_OK;
    if(!report) st=cli_read(argv[validate?3:4],GOLEM_DOCUMENT_MAX_JSON,&b);
    if(st==GOLEM_OK && validate) st=golem_completion_validate((golem_bytes){b.data,b.size},NULL);
    if(st==GOLEM_OK && !validate) st=golem_document_store_open(argv[3],true,NULL,&s,NULL);
    if(st==GOLEM_OK && call) st=golem_completion_call(s,(golem_bytes){b.data,b.size},&out,NULL);
    if(st==GOLEM_OK && report) {
        char *end; unsigned long n=strtoul(argv[4],&end,10);
        if(!*argv[4] || *end || n<1 || n>64) st=GOLEM_ERR_INVALID_ARGUMENT;
        else st=golem_completion_report(s,(uint32_t)n,true,&out,NULL);
    }
    if(st==GOLEM_OK && out.size && fwrite(out.data,1,out.size,stdout)!=out.size) st=GOLEM_ERR_IO;
    if(st==GOLEM_OK && !report) fputc('\n',stdout);
    free(b.data); golem_execution_reply_free(&out);
    golem_status closed=golem_document_store_close(s); if(st==GOLEM_OK) st=closed;
    if(st!=GOLEM_OK) fprintf(stderr,"completion: %s\n",golem_status_string(st));
    return st==GOLEM_OK?0:1;
}
