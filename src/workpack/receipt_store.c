#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "receipt_internal.h"
#include "../workspace/internal.h"
#include "../common/record_internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

static golem_status closed(int fd,golem_status st)
{ if(fd>=0&&close(fd)&&st==GOLEM_OK)st=GOLEM_ERR_IO;
    return st; }
static golem_status ancestor(int fd,const struct stat *target,bool *found)
{
    int at=dup(fd);if(at<0)return GOLEM_ERR_IO;golem_status st=GOLEM_ERR_OVERFLOW;*found=false;
    for(size_t i=0;i<256;++i){struct stat here,up;if(fstat(at,&here)){st=GOLEM_ERR_IO;break;}
        if(here.st_dev==target->st_dev&&here.st_ino==target->st_ino){*found=true;st=GOLEM_OK;break;}
        int parent=openat(at,"..",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);if(parent<0){st=GOLEM_ERR_IO;break;}
        if(fstat(parent,&up)){close(parent);st=GOLEM_ERR_IO;break;}
        if(here.st_dev==up.st_dev&&here.st_ino==up.st_ino){close(parent);st=GOLEM_OK;break;}
        close(at);at=parent;
    }
    return closed(at,st);
}
static golem_status parent_open(golem_document_store *s,const char *path,int *out,struct json_object **identity)
{
    int fd=-1;struct stat parent,work;golem_status st=ws_directory(path,&fd);
    if(st==GOLEM_OK&&(fstat(fd,&parent)||fstat(s->root,&work)))st=GOLEM_ERR_IO;
    if(st==GOLEM_OK&&(parent.st_uid!=geteuid()||(parent.st_mode&0077)))st=GOLEM_ERR_POLICY_DENIED;
    bool overlap=false;
    if(st==GOLEM_OK)st=ancestor(fd,&work,&overlap);
    if(st==GOLEM_OK&&overlap)st=GOLEM_ERR_POLICY_DENIED;
    if(st==GOLEM_OK)st=ancestor(s->root,&parent,&overlap);
    if(st==GOLEM_OK&&overlap)st=GOLEM_ERR_POLICY_DENIED;
    struct json_object *o=json_object_new_object();
    if(st==GOLEM_OK&&(!ex_text(o,"path",path)||!ex_uint(o,"device",(uint64_t)parent.st_dev)||!ex_uint(o,"inode",(uint64_t)parent.st_ino)))st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK){*out=fd;*identity=o;}else{json_object_put(o);st=closed(fd,st);}return st;
}
static golem_status plan(wp_bundle *b,struct json_object *identity,struct json_object **out,golem_digest *digest)
{
    struct json_object *o=json_object_new_object();golem_status st=GOLEM_OK;
    if(!ex_text(o,"domain","golem.workpack.private-export-approval.v0")||!dw_add_digest(o,"manifest_digest",&b->digest)||!dw_add(o,"parent",json_object_get(identity)))st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK)st=ex_hash(o,digest);
    if(st==GOLEM_OK)*out=o;else json_object_put(o);return st;
}
golem_status golem_workpack_receipt_manifest(golem_document_store *s,golem_bytes request,const char *parent,const char *format,golem_execution_reply *out,golem_diagnostic *d)
{
    if(!s||!out||!parent)return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,"RECEIPT_INPUT");
    wp_bundle b={0};struct json_object *identity=NULL,*o=NULL;int fd=-1;golem_digest digest;
    golem_status st=wp_receipt_build(s,request,format,&b);
    if(st==GOLEM_OK)st=parent_open(s,parent,&fd,&identity);
    if(st==GOLEM_OK)st=plan(&b,identity,&o,&digest);
    if(st==GOLEM_OK&&(!dw_add_digest(o,"approval_digest",&digest)||!dw_add(o,"manifest",json_object_get(b.manifest))||!dw_add(o,"authorized",json_object_new_boolean(false))))st=GOLEM_ERR_OUT_OF_MEMORY;
    st=closed(fd,st);if(st==GOLEM_OK)st=ex_emit(o,out);
    json_object_put(identity);json_object_put(o);wp_receipt_free(&b);return dw_report(d,st,"RECEIPT_MANIFEST_REVIEW_REQUIRED");
}
GOLEM_RECORDED_API(golem_workpack_receipt_export,
    (golem_document_store *s,golem_bytes request,const char *parent,const char *format,const golem_digest *approval,golem_digest *out,golem_diagnostic *d),
    (s,request,parent,format,approval,out,d),d)
{
    if(!s||!parent||!out)return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,"RECEIPT_INPUT");
    wp_bundle b={0};struct json_object *identity=NULL,*o=NULL,*commit=NULL;int fd=-1,dir=-1;golem_digest digest;char name[65];size_t required;
    golem_status st=wp_receipt_build(s,request,format,&b);
    if(st==GOLEM_OK)st=parent_open(s,parent,&fd,&identity);
    if(st==GOLEM_OK)st=plan(&b,identity,&o,&digest);
    if(st==GOLEM_OK&&(!approval||!dw_equal(approval,&digest)))st=GOLEM_ERR_APPROVAL_REQUIRED;
    if(st==GOLEM_OK&&flock(fd,LOCK_EX|LOCK_NB))st=GOLEM_ERR_JOURNAL_BUSY;
    if(st==GOLEM_OK)st=golem_digest_format(&b.digest,name,sizeof(name),&required);
    /* New destination only. Never resume/repair a partial or uncertain export. */
    if(st==GOLEM_OK&&mkdirat(fd,name,0700))st=errno==EEXIST?GOLEM_ERR_IDENTITY_MISMATCH:GOLEM_ERR_IO;
    if(st==GOLEM_OK)st=dw_dir(fd,name,false,&dir);
    if(st==GOLEM_OK&&(flock(dir,LOCK_EX|LOCK_NB)||fsync(dir)||fsync(fd)))st=GOLEM_ERR_IO;
    for(size_t i=0;st==GOLEM_OK&&i<b.count;++i){st=golem_digest_format(&b.objects[i].digest,name,sizeof(name),&required);if(st==GOLEM_OK)st=dw_publish(dir,name,(golem_bytes){b.objects[i].data,b.objects[i].size});}
    if(st==GOLEM_OK&&b.markdown.size)st=dw_publish(dir,"summary.md",(golem_bytes){b.markdown.data,b.markdown.size});
    if(st==GOLEM_OK)st=dw_publish(dir,"manifest.json",(golem_bytes){b.encoded.data,b.encoded.size});
    golem_execution_reply marker={0};
    if(st==GOLEM_OK){commit=json_object_new_object();if(!ex_text(commit,"schema","golem.workpack.receipt-commit.v0")||!dw_add_digest(commit,"manifest",&b.digest))st=GOLEM_ERR_OUT_OF_MEMORY;}
    if(st==GOLEM_OK)st=ex_emit(commit,&marker);
    if(st==GOLEM_OK)st=dw_publish(dir,"COMMIT.json",(golem_bytes){marker.data,marker.size});
    st=closed(dir,st);st=closed(fd,st);if(st==GOLEM_OK)*out=b.digest;
    golem_execution_reply_free(&marker);json_object_put(commit);json_object_put(identity);json_object_put(o);wp_receipt_free(&b);return dw_report(d,st,"RECEIPT_EXPORT_NO_RETRY");
}
static bool pending(const char *n)
{
    if(strlen(n)!=33||strncmp(n,".pending-",9))return false;
    for(size_t i=9;i<33;++i)if(!((n[i]>='0'&&n[i]<='9')||(n[i]>='a'&&n[i]<='f')))return false;
    return true;
}
static golem_status inventory(int fd,wp_bundle *b)
{
    int copy=dup(fd);if(copy<0)return GOLEM_ERR_IO;DIR *directory=fdopendir(copy);if(!directory){close(copy);return GOLEM_ERR_IO;}
    golem_status st=GOLEM_OK;size_t count=0;
    for(;;){errno=0;struct dirent *e=readdir(directory);if(!e){if(errno)st=GOLEM_ERR_IO;break;}const char *n=e->d_name;if(!strcmp(n,".")||!strcmp(n,".."))continue;
        if(++count>1024){st=GOLEM_ERR_OVERFLOW;break;}bool known=pending(n)||!strcmp(n,"manifest.json")||!strcmp(n,"COMMIT.json")||(!strcmp(dw_text(b->manifest,"format"),"markdown")&&!strcmp(n,"summary.md"));
        for(size_t i=0;!known&&i<b->count;++i){char hex[65];size_t len;st=golem_digest_format(&b->objects[i].digest,hex,sizeof(hex),&len);known=st==GOLEM_OK&&!strcmp(n,hex);}
        if(!known){st=GOLEM_ERR_PARSE;break;}
    }
    if(closedir(directory)&&st==GOLEM_OK)st=GOLEM_ERR_IO;
    return st;
}
static golem_status read_file(int fd,const char *name,size_t limit,uint8_t **out,size_t *size)
{
    struct stat a,b;if(fstatat(fd,name,&a,AT_SYMLINK_NOFOLLOW))return errno==ENOENT?GOLEM_ERR_NOT_FOUND:GOLEM_ERR_IO;
    if(!S_ISREG(a.st_mode)||a.st_nlink!=1)return GOLEM_ERR_POLICY_DENIED;
    uint8_t *p=NULL;size_t n=0;golem_status st=dw_read_at(fd,name,limit,&p,&n);
    if(st==GOLEM_OK&&(fstatat(fd,name,&b,AT_SYMLINK_NOFOLLOW)||a.st_dev!=b.st_dev||a.st_ino!=b.st_ino||a.st_size!=b.st_size||a.st_mode!=b.st_mode||b.st_nlink!=1))st=GOLEM_ERR_STALE_RESULT;
    if(st==GOLEM_OK){*out=p;*size=n;}else free(p);return st;
}
golem_status golem_workpack_receipt_verify(const char *path,const golem_digest *expected,golem_execution_reply *out,golem_diagnostic *d)
{
    if(!path||!expected||!out)return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,"RECEIPT_VERIFY_INPUT");
    wp_bundle b={0};int fd=-1;struct json_object *marker=NULL,*report=NULL;uint8_t *raw=NULL;size_t n=0;
    golem_status st=ws_directory(path,&fd);if(st==GOLEM_OK&&flock(fd,LOCK_SH|LOCK_NB))st=GOLEM_ERR_JOURNAL_BUSY;
    if(st==GOLEM_OK)st=read_file(fd,"manifest.json",65536,&b.encoded.data,&b.encoded.size);
    if(st==GOLEM_OK)st=golem_digest_bytes((golem_bytes){b.encoded.data,b.encoded.size},&b.digest);
    if(st==GOLEM_OK&&!dw_equal(&b.digest,expected))st=GOLEM_ERR_DIGEST_MISMATCH;
    if(st==GOLEM_OK)st=golem_json_parse((golem_bytes){b.encoded.data,b.encoded.size},65536,&b.manifest);
    struct json_object *a=dw_get(b.manifest,"inventory");if(st==GOLEM_OK&&!ds_array(a,1,256))st=GOLEM_ERR_PARSE;
    for(size_t i=0;st==GOLEM_OK&&i<json_object_array_length(a);++i){struct json_object *row=json_object_array_get_idx(a,i);wp_object *obj=&b.objects[b.count++];char hex[65];size_t len;
        if(!dw_digest(row,"digest",&obj->digest)||!json_object_is_type(dw_get(row,"size"),json_type_int)||dw_uint(row,"size")>GOLEM_DOCUMENT_MAX_BODY||dw_uint(row,"size")>16777216u-b.total){st=GOLEM_ERR_PARSE;break;}
        obj->type=dw_text(row,"type");st=golem_digest_format(&obj->digest,hex,sizeof(hex),&len);
        if(st==GOLEM_OK)st=read_file(fd,hex,(size_t)dw_uint(row,"size"),&obj->data,&obj->size);
        b.total+=obj->size;
    }
    if(st==GOLEM_OK&&!strcmp(dw_text(b.manifest,"format"),"markdown"))st=read_file(fd,"summary.md",768,&b.markdown.data,&b.markdown.size);
    if(st==GOLEM_OK)st=inventory(fd,&b);
    if(st==GOLEM_OK)st=read_file(fd,"COMMIT.json",1024,&raw,&n);
    if(st==GOLEM_OK)st=golem_json_parse((golem_bytes){raw,n},1024,&marker);
    const char *keys[]={"schema","manifest"};golem_digest digest;
    if(st==GOLEM_OK&&(!dw_keys(marker,keys,2)||strcmp(dw_text(marker,"schema"),"golem.workpack.receipt-commit.v0")||!dw_digest(marker,"manifest",&digest)||!dw_equal(&digest,expected)))st=GOLEM_ERR_DIGEST_MISMATCH;
    if(st==GOLEM_OK)st=wp_receipt_validate(&b,expected);
    st=closed(fd,st);
    if(st==GOLEM_OK){report=json_object_new_object();if(!ex_text(report,"schema","golem.workpack.receipt-verification.v0")||!dw_add_digest(report,"manifest",expected)||!ex_text(report,"integrity","VERIFIED")||!ex_text(report,"origin","UNAUTHENTICATED")||!ex_text(report,"current_applicability","NOT_EVALUATED")||!dw_add(report,"semantic_truth_verified",json_object_new_boolean(false))||!dw_add(report,"completion_verified",json_object_new_boolean(false))||!dw_add(report,"authorized",json_object_new_boolean(false)))st=GOLEM_ERR_OUT_OF_MEMORY;}
    if(st==GOLEM_OK)st=ex_emit(report,out);
    free(raw);json_object_put(marker);json_object_put(report);wp_receipt_free(&b);return dw_report(d,st,"RECEIPT_INTEGRITY_NOT_AUTHORITY");
}
