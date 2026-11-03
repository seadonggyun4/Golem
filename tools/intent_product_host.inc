/* Private D01 host transport. Parent holds authorized_root common-dir lock.
 * No caller-supplied permission boolean; exact host/control checks remain native. */
#include "../src/intent/qa_result.h"
#include "../src/document/internal.h"
#include "golem/completion.h"
typedef struct product_guard {int fd;dev_t device;ino_t inode;} product_guard;
static golem_status product_root_guard(void *context)
{
    product_guard *g=context;struct stat st;
    if(!g||fstat(g->fd,&st)||st.st_dev!=g->device||st.st_ino!=g->inode||!S_ISDIR(st.st_mode)||st.st_uid!=geteuid()||(st.st_mode&077))return GOLEM_ERR_POLICY_DENIED;
    return GOLEM_OK; /* registration cannot change under parent's D01 lock */
}
static golem_bytes product_text(struct json_object *o,const char *key)
{struct json_object *v=dw_get(o,key);return json_object_is_type(v,json_type_string)?(golem_bytes){(const uint8_t *)json_object_get_string(v),(size_t)json_object_get_string_len(v)}:(golem_bytes){0};}
static int product_command(int argc,char **argv)
{
    if(argc!=5)return 2;char *end=NULL;long fd=strtol(argv[2],&end,10);if(!*argv[2]||*end||fd<3||fd>INT_MAX)return 2;
    long reviewfd=strtol(argv[4],&end,10);if(!*argv[4]||*end||reviewfd<3||reviewfd>INT_MAX)return 2;
    const size_t limit=GI_DISPATCH_MAX;uint8_t *data=malloc(limit+1);if(!data)return 1;
    size_t n=fread(data,1,limit+1,stdin);struct json_object *input=NULL;golem_status st=n&&n<=limit&&!ferror(stdin)?golem_json_parse((golem_bytes){data,n},limit,&input):GOLEM_ERR_OVERFLOW;
    const char *keys[]={"schema","work","operation","policy","bundle","control","material","request","policy_sha256","bundle_sha256","policy_name","bundle_name"};
    if(st==GOLEM_OK&&(!dw_keys(input,keys,12)||strcmp(dw_text(input,"schema"),"golem.intent-product-host.v1")))st=GOLEM_ERR_PARSE;
    const char *op=dw_text(input,"operation");
    if(st==GOLEM_OK&&strcmp(op,"assess")&&strcmp(op,"current")&&strcmp(op,"accept")&&strcmp(op,"finalize")&&strcmp(op,"resume"))st=GOLEM_ERR_PARSE;
    golem_digest registration={0},policy={0},bundle={0};gi_journal *j=NULL;authority_chain chain={0};
    if(st==GOLEM_OK)st=golem_digest_parse((golem_string_view){argv[3],strlen(argv[3])},&registration);
    const char domain[]="golem.intent.authority-registration.v1";
    if(st==GOLEM_OK)st=golem_digest_bytes((golem_bytes){(const uint8_t *)domain,sizeof(domain)-1},&chain.initial);
    if(st==GOLEM_OK)st=gi_journal_open((int)fd,&j);
    if(st==GOLEM_OK)st=gi_journal_visit(j,visit_binding,&chain);
    if(st==GOLEM_OK&&(!chain.found||!dw_equal(&chain.current,&registration)))st=GOLEM_ERR_POLICY_DENIED;
    gi_journal_close(j);j=NULL;
    product_guard guard={(int)fd,0,0};struct stat info;
    if(st==GOLEM_OK){if(fstat((int)fd,&info))st=GOLEM_ERR_IO;else {guard.device=info.st_dev;guard.inode=info.st_ino;st=product_root_guard(&guard);}}
    if(st==GOLEM_OK&&(!dw_digest(input,"policy_sha256",&policy)||!dw_digest(input,"bundle_sha256",&bundle)))st=GOLEM_ERR_PARSE;
    gi_review_host_files files={(int)reviewfd,dw_text(input,"policy_name"),dw_text(input,"bundle_name"),registration,product_root_guard,&guard};
    gi_review_host *host=NULL;golem_document_store *work=NULL;gi_product_access *access=NULL;golem_execution_reply reply={0};
    if(st==GOLEM_OK)st=gi_review_host_open(product_text(input,"policy"),&policy,product_text(input,"bundle"),&bundle,product_text(input,"control"),&registration,gi_review_host_observe_files,&files,&host);
    /* writable lock is required even for consistent read evaluation; read ops
     * below do not publish. D01 lock precedes Work; authority locks are short. */
    if(st==GOLEM_OK)st=golem_document_store_open(dw_text(input,"work"),true,NULL,&work,NULL);
    if(st==GOLEM_OK)st=gi_product_access_open(work,(int)fd,host,product_text(input,"control"),product_text(input,"material"),&access);
    golem_bytes request=product_text(input,"request");
    if(st==GOLEM_OK){
        if(!strcmp(op,"assess"))st=gi_qa_assess(work,request,&reply);
        else if(!strcmp(op,"accept"))st=gi_qa_accept(work,request,&reply);
        else if(!strcmp(op,"current"))st=gi_qa_current(work,&reply);
        else {struct json_object *r=NULL;st=golem_json_parse(request,GI_CONTROL_MAX,&r);
            if(st==GOLEM_OK&&strcmp(dw_text(r,"operation"),op))st=GOLEM_ERR_POLICY_DENIED;
            if(st==GOLEM_OK)st=golem_completion_call(work,request,&reply,NULL);json_object_put(r);}
    }
    gi_product_access_close(access);golem_status closed=golem_document_store_close(work);if(st==GOLEM_OK)st=closed;
    gi_review_host_close(host);
    if(st==GOLEM_OK&&(reply.size>GI_CONTROL_MAX||fwrite(reply.data,1,reply.size,stdout)!=reply.size))st=GOLEM_ERR_IO;
    if(st!=GOLEM_OK)fprintf(stderr,"intent.product code=%d uncertain_if_dispatched=true\n",(int)st);
    golem_execution_reply_free(&reply);json_object_put(input);free(data);return st==GOLEM_OK?0:1;
}
