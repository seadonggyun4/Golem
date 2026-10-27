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
    bool inspect=argc==5 && !strcmp(argv[2],"inspect");
    if(!validate && !call && !report && !inspect) {
        fputs("usage: golem reentry validate REQUEST.json\n"
              "       golem reentry call WORK REQUEST.json\n"
              "       golem reentry report WORK SEQUENCE\n"
              "       golem reentry inspect WORK SEQUENCE (read-only; no projection)\n",stderr); return 2;
    }
    golem_document_store *store=NULL; cli_blob input={0}; golem_execution_reply reply={0};
    golem_status st=GOLEM_OK;
    if(!report && !inspect) st=cli_read(argv[validate?3:4],GOLEM_DOCUMENT_MAX_JSON,&input);
    if(st==GOLEM_OK && validate) st=golem_reentry_validate((golem_bytes){input.data,input.size},NULL);
    struct json_object *request=NULL;
    if(st==GOLEM_OK && call) st=cli_json_parse((golem_bytes){input.data,input.size},&request);
    const char *op=request?cli_json_text(json_object_object_get(request,"operation")):"";
    if(st==GOLEM_OK && call && !op) st=GOLEM_ERR_INVALID_ARGUMENT;
    bool readonly=inspect || (call && op && !strcmp(op,"status"));
    if(st==GOLEM_OK && !validate) st=golem_document_store_open(argv[3],!readonly,NULL,&store,NULL);
    if(st==GOLEM_OK && call) st=golem_reentry_call(store,(golem_bytes){input.data,input.size},&reply,NULL);
    if(st==GOLEM_OK && (report || inspect)) {
        char *end; unsigned long seq=strtoul(argv[4],&end,10);
        if(!*argv[4] || *end || seq<1 || seq>64) st=GOLEM_ERR_INVALID_ARGUMENT;
        else st=golem_reentry_report(store,(uint32_t)seq,report,&reply,NULL);
    }
    if (st == GOLEM_OK && reply.size) st = report || inspect
        ? (fwrite(reply.data, 1, reply.size, stdout) == reply.size ? GOLEM_OK : GOLEM_ERR_IO)
        : cli_output_write((golem_bytes){reply.data, reply.size});
    if(st==GOLEM_OK && validate && puts("{\"schema_version\":1,\"structurally_valid\":true,\"acceptance_verified\":false}")<0) st=GOLEM_ERR_IO;
    if(st==GOLEM_OK && !report && !inspect) fputc('\n',stdout);
    json_object_put(request);
    free(input.data); golem_execution_reply_free(&reply);
    golem_status closed=golem_document_store_close(store); if(st==GOLEM_OK) st=closed;
    cli_error_note(st, "reentry", NULL);
    if(st!=GOLEM_OK) fprintf(stderr,"reentry: %s\n",golem_status_string(st));
    return st==GOLEM_OK?0:1;
}
