#include "work.h"
#include "golem/discovery.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
int golem_cli_discovery(int argc,char **argv)
{
    if(argc!=4 && argc!=5) return 2;
    bool report=strcmp(argv[2],"report")==0;
    bool snapshot=strcmp(argv[2],"snapshot")==0,validate=strcmp(argv[2],"validate")==0;
    if((report && argc!=5) || (!report && (argc!=4 || (!snapshot && !validate)))) return 2;
    cli_blob b={0}; struct json_object *o=NULL;
    golem_status st=cli_read(argv[3],GOLEM_DOCUMENT_MAX_JSON,&b);
    if(report) {
        size_t size=0; void *output=NULL;
        if(st==GOLEM_OK) st=golem_discovery_report((golem_bytes){b.data,b.size},argv[4],NULL,0,&size,NULL);
        if(st==GOLEM_ERR_BUFFER_TOO_SMALL) {
            output=malloc(size);
            st=output?golem_discovery_report((golem_bytes){b.data,b.size},argv[4],output,size,&size,NULL):GOLEM_ERR_OUT_OF_MEMORY;
        }
        if(st==GOLEM_OK && (fwrite(output,1,size,stdout)!=size || fflush(stdout)!=0)) st=GOLEM_ERR_IO;
        free(output); free(b.data);
        return st==GOLEM_OK?0:cli_emit(st,NULL);
    }
    if(st==GOLEM_OK && snapshot) {
        uint8_t *output=NULL; size_t size=0;
        st=golem_discovery_snapshot((golem_bytes){b.data,b.size},NULL,&output,&size,NULL);
        if(st==GOLEM_OK) st=cli_json_parse((golem_bytes){output,size},&o);
        (void)golem_allocator_free(NULL,output);
    } else if(st==GOLEM_OK) {
        golem_discovery_result r;
        st=golem_discovery_validate((golem_bytes){b.data,b.size},&r,NULL);
        if(st==GOLEM_OK) {
            char hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t n;
            st=golem_digest_format(&r.snapshot_digest,hex,sizeof(hex),&n);
            o=json_object_new_object();
            if(st==GOLEM_OK && (!cli_json_add(o,"schema_version",json_object_new_int(1)) ||
                !cli_json_add(o,"scope_ready",json_object_new_boolean(r.scope_ready)) ||
                !cli_json_add(o,"execution_authorized",json_object_new_boolean(false)) ||
                !cli_json_add(o,"acceptance_verified",json_object_new_boolean(false)) ||
                !cli_json_add(o,"findings",json_object_new_int64(r.findings)) ||
                !cli_json_add(o,"selected",json_object_new_int64(r.selected)) ||
                !cli_json_add(o,"questions",json_object_new_int64(r.questions)) ||
                !cli_json_add(o,"references",json_object_new_int64(r.references)) ||
                !cli_json_add(o,"full_text_references",json_object_new_int64(r.full_text_references)) ||
                !cli_json_add(o,"snapshot_digest",json_object_new_string(hex)))) st=GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    free(b.data); return cli_emit(st,o);
}
