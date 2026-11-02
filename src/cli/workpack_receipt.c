#include "work.h"
#include "golem/workpack.h"
#include <stdio.h>
#include <string.h>
int golem_cli_workpack_receipt(int argc,char **argv)
{
    if(argc<3)return 2;
    golem_status st=GOLEM_OK;golem_execution_reply reply={0};golem_digest expected,manifest;golem_document_store *store=NULL;
    if(!strcmp(argv[2],"verify")){
        if(argc!=6||strcmp(argv[4],"--expect-manifest"))return 2;
        st=golem_digest_parse((golem_string_view){argv[5],strlen(argv[5])},&expected);
        if(st==GOLEM_OK)st=golem_workpack_receipt_verify(argv[3],&expected,&reply,NULL);
    }else{
        bool publish=!strcmp(argv[2],"export");if((!publish&&strcmp(argv[2],"manifest"))||argc<6)return 2;
        const char *format="json";bool approved=false,formatted=false;
        for(int i=6;i<argc;i+=2){
            if(i+1==argc)return 2;
            if(!strcmp(argv[i],"--format")&&!formatted){format=argv[i+1];formatted=true;}
            else if(publish&&!strcmp(argv[i],"--approve-export")&&!approved){st=golem_digest_parse((golem_string_view){argv[i+1],strlen(argv[i+1])},&expected);approved=true;}
            else return 2;
        }
        if(strcmp(format,"json")&&strcmp(format,"markdown"))return 2;
        uint8_t request[65536];size_t n=0;
        if(st==GOLEM_OK)st=golem_workpack_read(argv[4],request,sizeof(request),&n,NULL);
        if(st==GOLEM_OK)st=golem_document_store_open(argv[3],false,NULL,&store,NULL);
        if(st==GOLEM_OK&&publish)st=golem_workpack_receipt_export(store,(golem_bytes){request,n},argv[5],format,approved?&expected:NULL,&manifest,NULL);
        if(st==GOLEM_OK&&!publish)st=golem_workpack_receipt_manifest(store,(golem_bytes){request,n},argv[5],format,&reply,NULL);
        golem_status close=golem_document_store_close(store);if(st==GOLEM_OK)st=close;
        if(st==GOLEM_OK&&publish){char hex[65];size_t required;st=golem_digest_format(&manifest,hex,sizeof(hex),&required);if(st==GOLEM_OK&&(printf("{\"manifest_digest\":\"%s\",\"published\":true,\"execution_authorized\":false}\n",hex)<0||fflush(stdout)))st=GOLEM_ERR_IO;}
    }
    if(st==GOLEM_OK&&reply.data&&(fwrite(reply.data,1,reply.size,stdout)!=reply.size||puts("")==EOF||fflush(stdout)))st=GOLEM_ERR_IO;
    golem_execution_reply_free(&reply);cli_error_note(st,"workpack.receipt",NULL);return st==GOLEM_OK?0:1;
}
