#define _POSIX_C_SOURCE 200809L
#include "work.h"
#include "golem/document.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static bool digest_field(struct json_object *o,const char *name,const golem_digest *digest)
{
    char hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t n;
    return golem_digest_format(digest,hex,sizeof(hex),&n)==GOLEM_OK &&
        cli_json_add(o,name,json_object_new_string(hex));
}
int golem_cli_document(int argc,char **argv)
{
    bool start=argc==5 && strcmp(argv[1],"work")==0 && strcmp(argv[2],"start")==0;
    bool submit=argc==7 && strcmp(argv[1],"document")==0 && strcmp(argv[2],"submit")==0;
    bool inspect=argc==6 && strcmp(argv[1],"document")==0 && strcmp(argv[2],"inspect")==0;
    bool project=argc==6 && strcmp(argv[1],"document")==0 && strcmp(argv[2],"project")==0;
    bool validate=argc==5 && strcmp(argv[1],"document")==0 && strcmp(argv[2],"validate")==0;
    if(!start && !submit && !inspect && !project && !validate) return 2;
    cli_blob meta={0},body={0}; golem_status st=GOLEM_OK;
    golem_document_store *store=NULL; golem_diagnostic d; (void)golem_diagnostic_clear(&d);
    struct json_object *o=NULL; golem_document_result result={0};
    if(start) {
        st=cli_read(argv[4],GOLEM_DOCUMENT_MAX_JSON,&meta);
        if(st==GOLEM_OK) st=golem_work_spec_validate((golem_bytes){meta.data,meta.size},&d);
        int root=-1;
        if(st==GOLEM_OK) st=cli_mkdir_new(argv[3],&root);
        if(root>=0) close(root);
        if(st==GOLEM_OK) st=golem_document_store_create(argv[3],(golem_bytes){meta.data,meta.size},NULL,&store,&d);
    } else if(submit || validate) {
        st=cli_read(argv[validate?3:4],GOLEM_DOCUMENT_MAX_JSON,&meta);
        if(st==GOLEM_OK) st=cli_read(argv[validate?4:5],GOLEM_DOCUMENT_MAX_BODY,&body);
        if(validate && st==GOLEM_OK) st=golem_document_validate((golem_bytes){meta.data,meta.size},(golem_bytes){body.data,body.size},&d);
        if(submit && st==GOLEM_OK) st=golem_document_store_open(argv[3],true,NULL,&store,&d);
        if(submit && st==GOLEM_OK) st=golem_document_submit(store,(golem_bytes){meta.data,meta.size},
            (golem_bytes){body.data,body.size},argv[6],&result,&d);
    } else {
        uint32_t revision=0;
        for(const char *p=argv[5];*p;++p) {
            if(*p<'0' || *p>'9' || revision>GOLEM_DOCUMENT_MAX_REVISIONS) { st=GOLEM_ERR_INVALID_ARGUMENT; break; }
            revision=revision*10+(unsigned)(*p-'0');
        }
        if(!revision || revision>GOLEM_DOCUMENT_MAX_REVISIONS) st=GOLEM_ERR_INVALID_ARGUMENT;
        if(st==GOLEM_OK) st=golem_document_store_open(argv[3],project,NULL,&store,&d);
        if(project && st==GOLEM_OK) st=golem_document_project(store,argv[4],revision,&d);
        if(st==GOLEM_OK) st=golem_document_inspect(store,argv[4],revision,&result,&d);
    }
    if(st==GOLEM_OK) {
        o=json_object_new_object();
        bool ok=cli_json_add(o,"schema_version",json_object_new_int(1)) &&
            cli_json_add(o,"acceptance_verified",json_object_new_boolean(false)) &&
            cli_json_add(o,"authorization",json_object_new_string("trusted_local"));
        if(start) ok=ok && cli_json_add(o,"generation",json_object_new_int(1)) &&
            cli_json_add(o,"state",json_object_new_string("OPEN"));
        else if(validate) ok=ok && cli_json_add(o,"structurally_valid",json_object_new_boolean(true));
        else ok=ok && cli_json_add(o,"committed",json_object_new_boolean(true)) &&
            cli_json_add(o,"generation",cli_json_u64(result.generation)) &&
            cli_json_add(o,"revision",json_object_new_int64(result.revision)) &&
            digest_field(o,"body_digest",&result.body_digest) && digest_field(o,"manifest_digest",&result.manifest_digest) &&
            digest_field(o,"event_digest",&result.event_digest) &&
            cli_json_add(o,"projection_status",json_object_new_string(golem_status_string(result.projection_status))) &&
            cli_json_add(o,"projection_ready",json_object_new_boolean(result.projection_status==GOLEM_OK));
        if(!ok) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK && !start && !validate) {
        if(!submit) {
            st=golem_document_metadata(store,argv[4],result.revision,NULL,0,&meta.size,&d);
            if(st==GOLEM_ERR_BUFFER_TOO_SMALL) {
                meta.data=malloc(meta.size);
                st=meta.data?golem_document_metadata(store,argv[4],result.revision,
                    meta.data,meta.size,&meta.size,&d):GOLEM_ERR_OUT_OF_MEMORY;
            }
        }
        struct json_object *parsed=NULL;
        if(st==GOLEM_OK) st=cli_json_parse((golem_bytes){meta.data,meta.size},&parsed);
        if(st==GOLEM_OK && !cli_json_add(o,"metadata",parsed)) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    golem_status closed=golem_document_store_close(store);
    if(st==GOLEM_OK) st=closed;
    free(meta.data); free(body.data);
    return cli_emit(st,o);
}
