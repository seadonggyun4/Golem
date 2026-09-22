#include "work.h"
#include "golem/execution.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int golem_cli_execution(int argc,char **argv)
{
    bool validate=argc==4 && strcmp(argv[2],"validate")==0;
    bool render=argc==5 && strcmp(argv[2],"render")==0;
    bool call=(argc==5 || argc==7) && strcmp(argv[2],"call")==0;
    if(!validate && !render && !call) {
        fputs("usage: golem execution validate CONTRACT.json\n"
            "       golem execution call WORK REQUEST.json [--approve-contract SHA256]\n"
            "       golem execution render WORK METADATA.json\n",stderr); return 2;
    }
    golem_digest approval; const golem_digest *approved=NULL;
    if(argc==7) {
        if(strcmp(argv[5],"--approve-contract") || golem_digest_parse((golem_string_view){argv[6],strlen(argv[6])},&approval)!=GOLEM_OK) return 2;
        approved=&approval;
    }
    cli_blob input={0}; golem_execution_reply reply={0}; golem_document_store *store=NULL;
    golem_status st=cli_read(argv[validate?3:4],GOLEM_DOCUMENT_MAX_JSON,&input);
    if(st==GOLEM_OK && validate) {
        golem_digest digest; char hex[65]; size_t n;
        st=golem_execution_contract_validate((golem_bytes){input.data,input.size},&digest,NULL);
        if(st==GOLEM_OK) st=golem_digest_format(&digest,hex,sizeof(hex),&n);
        if(st==GOLEM_OK && printf("%s\n",hex)<0) st=GOLEM_ERR_IO;
    } else if(st==GOLEM_OK) {
        st=golem_document_store_open(argv[3],!render,NULL,&store,NULL);
        if(st==GOLEM_OK) st=render?golem_execution_render(store,(golem_bytes){input.data,input.size},&reply,NULL):
            golem_execution_call(store,(golem_bytes){input.data,input.size},approved,&reply,NULL);
        if(st==GOLEM_OK && (fwrite(reply.data,1,reply.size,stdout)!=reply.size || (!render && fputc('\n',stdout)==EOF))) st=GOLEM_ERR_IO;
    }
    golem_status closed=golem_document_store_close(store); if(st==GOLEM_OK) st=closed;
    free(input.data); golem_execution_reply_free(&reply); return st==GOLEM_OK?0:cli_emit(st,NULL);
}
