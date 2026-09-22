#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/document.h"
#include "test.h"
#include <errno.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

typedef struct blob { uint8_t *data; size_t size; } blob;
static blob read_sample(const char *name)
{
    char path[4096];
    (void)snprintf(path,sizeof(path),"%s/%s",GOLEM_DOCUMENT_SAMPLES,name);
    FILE *f=fopen(path,"rb"); blob b={0};
    if(!f) return b;
    if(fseek(f,0,SEEK_END)!=0) { fclose(f); return b; }
    long n=ftell(f);
    if(n<0 || fseek(f,0,SEEK_SET)!=0) { fclose(f); return b; }
    b.data=malloc((size_t)n+1);
    if(b.data && fread(b.data,1,(size_t)n,f)==(size_t)n) b.size=(size_t)n;
    fclose(f); return b;
}
typedef struct memory { size_t calls, fail, live; } memory;
static void *alloc(void *ctx,size_t n)
{
    memory *m=ctx;
    if(m->calls++==m->fail) return NULL;
    void *p=malloc(n); if(p) ++m->live; return p;
}
static void dealloc(void *ctx,void *p)
{
    memory *m=ctx;
    if(p) { --m->live; free(p); }
}
int main(int argc,char **argv)
{
    CHECK(argc==2);
    char root[4096],path[4200];
    CHECK(snprintf(root,sizeof(root),"%s/document-api-XXXXXX",argv[1])<(int)sizeof(root));
    CHECK(mkdtemp(root)!=NULL);
    blob wb=read_sample("work.json"),mb=read_sample("planning.json"),bb=read_sample("planning.md");
    CHECK(wb.data && mb.data && bb.data);
    golem_bytes w={wb.data,wb.size},m={mb.data,mb.size},b={bb.data,bb.size};
    CHECK(golem_work_spec_validate(w,NULL)==GOLEM_OK);
    CHECK(golem_document_validate(m,b,NULL)==GOLEM_OK);
    CHECK(golem_document_validate((golem_bytes){NULL,0},b,NULL)!=GOLEM_OK);
    CHECK(golem_document_store_close(NULL)==GOLEM_OK);
    for(size_t fail=0;fail<2;++fail) {
        memory mem={0,fail,0}; golem_allocator a={&mem,alloc,dealloc};
        golem_document_store *out=(golem_document_store *)(uintptr_t)1;
        CHECK(golem_document_store_create(root,w,&a,&out,NULL)==GOLEM_ERR_OUT_OF_MEMORY);
        CHECK(out==(golem_document_store *)(uintptr_t)1 && mem.live==0);
    }
    memory mem={0,SIZE_MAX,0}; golem_allocator a={&mem,alloc,dealloc};
    golem_document_store *s=NULL,*other=NULL;
    CHECK(golem_document_store_create(root,w,&a,&s,NULL)==GOLEM_OK);
    CHECK(golem_document_store_open(root,true,NULL,&other,NULL)==GOLEM_ERR_JOURNAL_BUSY);
    CHECK(other==NULL);
    uint64_t generation=0;
    CHECK(golem_document_generation(s,&generation)==GOLEM_OK && generation==1);
    golem_document_result result;
    memset(&result,0x55,sizeof(result));
    golem_document_result saved=result;
    /* Force publication failure after CAS succeeds, without adding a valid event. */
    (void)snprintf(path,sizeof(path),"%s/events/00000002.evt",root);
    CHECK(mkdir(path,0700)==0);
    CHECK(golem_document_submit(s,m,b,"first",&result,NULL)!=GOLEM_OK);
    CHECK(memcmp(&result,&saved,sizeof(result))==0);
    CHECK(golem_document_generation(s,&generation)==GOLEM_ERR_INVALID_STATE);
    CHECK(golem_document_store_close(s)==GOLEM_OK && mem.live==0);
    CHECK(rmdir(path)==0);
    CHECK(golem_document_store_open(root,true,&a,&s,NULL)==GOLEM_OK);
    CHECK(golem_document_generation(s,&generation)==GOLEM_OK && generation==1);
    CHECK(golem_document_submit(s,m,b,"first",&result,NULL)==GOLEM_OK);
    CHECK(result.generation==2 && result.revision==1 && result.projection_status==GOLEM_OK);
    golem_document_result retry;
    CHECK(golem_document_submit(s,m,b,"first",&retry,NULL)==GOLEM_OK);
    CHECK(memcmp(result.body_digest.bytes,retry.body_digest.bytes,32)==0);
    size_t required=0;
    CHECK(golem_document_body(s,"planning",1,NULL,0,&required,NULL)==GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(required==b.size);
    unsigned char tiny[2]={1,2};
    CHECK(golem_document_body(s,"planning",1,tiny,sizeof(tiny),&required,NULL)==GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(tiny[0]==1 && tiny[1]==2);
    void *copy=malloc(required);
    CHECK(copy!=NULL);
    CHECK(golem_document_body(s,"planning",1,copy,required,&required,NULL)==GOLEM_OK);
    CHECK(memcmp(copy,b.data,b.size)==0); free(copy);
    CHECK(golem_document_store_close(s)==GOLEM_OK && mem.live==0);
    CHECK(golem_document_store_open(root,false,&a,&s,NULL)==GOLEM_OK);
    CHECK(golem_document_submit(s,m,b,"first",&retry,NULL)==GOLEM_ERR_POLICY_DENIED);
    CHECK(golem_document_project(s,"planning",1,NULL)==GOLEM_ERR_POLICY_DENIED);
    CHECK(golem_document_inspect(s,"planning",1,&retry,NULL)==GOLEM_OK);
    CHECK(golem_document_store_close(s)==GOLEM_OK && mem.live==0);
    free(wb.data); free(mb.data); free(bb.data);
    return EXIT_SUCCESS;
}
