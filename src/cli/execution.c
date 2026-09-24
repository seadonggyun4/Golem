#include "work.h"
#include "golem/execution.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int bundle(int argc, char **argv)
{
    bool inspect = argc == 6 && !strcmp(argv[3], "inspect");
    bool verify = argc == 6 && !strcmp(argv[3], "verify");
    if (!inspect && !verify) {
        fputs("usage: golem execution bundle inspect WORK QA_RECEIPT_SHA256\n"
              "       golem execution bundle verify WORK BUNDLE.json\n", stderr);
        return 2;
    }
    golem_document_store *store = NULL;
    golem_execution_reply reply = {0};
    cli_blob bytes = {0};
    golem_digest key;
    golem_status st = inspect
        ? golem_digest_parse((golem_string_view){argv[5], strlen(argv[5])}, &key)
        : cli_read(argv[5], GOLEM_DOCUMENT_MAX_JSON, &bytes);
    if (st == GOLEM_OK)
        st = golem_document_store_open(argv[4], false, NULL, &store, NULL);
    if (st == GOLEM_OK)
        st = inspect ? golem_execution_bundle_inspect(store, &key, &reply, NULL)
                     : golem_execution_bundle_verify(store, (golem_bytes){bytes.data, bytes.size}, NULL);
    if (st == GOLEM_OK && inspect &&
        (fwrite(reply.data, 1, reply.size, stdout) != reply.size || fputc('\n', stdout) == EOF))
        st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && verify &&
        puts("{\"integrity_verified\":true,\"acceptance_verified\":false}") < 0)
        st = GOLEM_ERR_IO;
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK)
        st = closed;
    free(bytes.data);
    golem_execution_reply_free(&reply);
    return st == GOLEM_OK ? 0 : cli_emit(st, NULL);
}

int golem_cli_execution(int argc,char **argv)
{
    if (argc >= 3 && !strcmp(argv[2], "bundle"))
        return bundle(argc, argv);
    bool validate=argc==4 && strcmp(argv[2],"validate")==0;
    bool render=argc==5 && strcmp(argv[2],"render")==0;
    bool call=(argc==5 || argc==7 || argc==9) && strcmp(argv[2],"call")==0;
    if(!validate && !render && !call) {
        fputs("usage: golem execution validate CONTRACT.json\n"
            "       golem execution call WORK REQUEST.json [--approve-contract SHA256] [--approve-shell-contract SHA256]\n"
            "       golem execution render WORK METADATA.json\n",stderr); return 2;
    }
    golem_digest approval, shell;
    golem_execution_approval approved = {.struct_size = sizeof(approved), .version = 1};
    for (int i = 5; call && i < argc; i += 2) {
        golem_digest *value;
        if (!strcmp(argv[i], "--approve-contract") && !approved.contract) {
            value = &approval;
            approved.contract = value;
        } else if (!strcmp(argv[i], "--approve-shell-contract") && !approved.shell_contract) {
            value = &shell;
            approved.shell_contract = value;
        } else
            return 2;
        if (golem_digest_parse((golem_string_view){argv[i + 1], strlen(argv[i + 1])}, value) != GOLEM_OK)
            return 2;
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
            golem_execution_call_authorized(store,(golem_bytes){input.data,input.size},&approved,&reply,NULL);
        if(st==GOLEM_OK && (fwrite(reply.data,1,reply.size,stdout)!=reply.size || (!render && fputc('\n',stdout)==EOF))) st=GOLEM_ERR_IO;
    }
    golem_status closed=golem_document_store_close(store); if(st==GOLEM_OK) st=closed;
    free(input.data); golem_execution_reply_free(&reply); return st==GOLEM_OK?0:cli_emit(st,NULL);
}
