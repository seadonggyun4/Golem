#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
#include "../discovery/internal.h"
#include "../workflow/internal.h"
#include "../evidence/internal.h"
#include "../execution/internal.h"
#include "../reentry/internal.h"
#include "../completion/internal.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <unistd.h>

dw_entry *dw_find(golem_document_store *s,const char *id,uint32_t revision)
{
    for(size_t i=s->count;i>0;--i) {
        dw_entry *e=&s->entries[i-1];
        if(strcmp(dw_text(e->meta,"document_id"),id)==0 && (revision==0 || e->result.revision==revision)) return e;
    }
    return NULL;
}
golem_status dw_preconditions(golem_document_store *s,struct json_object *m)
{
    if(strcmp(dw_text(s->spec,"work_id"),dw_text(m,"work_id"))!=0) return GOLEM_ERR_IDENTITY_MISMATCH;
    if(dw_uint(m,"expected_generation")!=s->count+1) return GOLEM_ERR_STALE_RESULT;
    const char *permission=dw_text(s->spec,"permission");
    if(strcmp(permission,"DENY")==0) return GOLEM_ERR_POLICY_DENIED;
    if(strcmp(permission,"ASK_ALWAYS")==0) return GOLEM_ERR_APPROVAL_REQUIRED;
    /* This operation is a local-only immutable registration; no external effects. */
    if(s->count>=dw_uint(s->spec,"max_revisions") || s->count>=GOLEM_DOCUMENT_MAX_REVISIONS) return GOLEM_ERR_BUDGET_EXHAUSTED;
    dw_entry *prior=dw_find(s,dw_text(m,"document_id"),0);
    golem_digest supersedes;
    if(prior) {
        if(dw_uint(m,"revision")!=prior->result.revision+1 ||
            !dw_digest(m,"supersedes",&supersedes) || !dw_equal(&supersedes,&prior->result.manifest_digest))
            return GOLEM_ERR_STALE_RESULT;
        if(strcmp(dw_text(prior->meta,"kind"),dw_text(m,"kind"))!=0) return GOLEM_ERR_INVALID_ARGUMENT;
    } else if(dw_uint(m,"revision")!=1) return GOLEM_ERR_STALE_RESULT;
    struct json_object *parents=dw_get(m,"parents");
    if(json_object_array_length(parents)>GOLEM_DOCUMENT_MAX_EDGES-s->edges) return GOLEM_ERR_BUDGET_EXHAUSTED;
    for(size_t i=0;i<json_object_array_length(parents);++i) {
        struct json_object *p=json_object_array_get_idx(parents,i);
        dw_entry *e=dw_find(s,dw_text(p,"document_id"),0);
        golem_digest digest;
        if(!e) return GOLEM_ERR_NOT_FOUND;
        if(e->result.revision!=dw_uint(p,"revision") || !dw_digest(p,"digest",&digest) ||
            !dw_equal(&digest,&e->result.manifest_digest)) return GOLEM_ERR_STALE_RESULT;
    }
    struct json_object *req=dw_get(m,"requirement_ids"), *acceptance=dw_get(s->spec,"acceptance");
    for(size_t i=0;i<json_object_array_length(req);++i) {
        const char *id=json_object_get_string(json_object_array_get_idx(req,i)); bool found=false;
        for(size_t j=0;j<json_object_array_length(acceptance);++j)
            if(strcmp(id,dw_text(json_object_array_get_idx(acceptance,j),"id"))==0) found=true;
        if(!found) return GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    golem_status st=ds_evidence(s,m);
    return st==GOLEM_OK?wf_preconditions(s,m):st;
}
golem_status dw_apply(golem_document_store *s,struct json_object *event,const golem_digest *payload,
    const golem_digest *frame)
{
    if(dw_uint(event,"schema_version")!=1) return GOLEM_ERR_UNSUPPORTED_VERSION;
    golem_status st=GOLEM_OK; golem_digest key;
    if(!s->spec) {
        const char *keys[]={"schema_version","type","spec_digest"};
        if(!dw_keys(event,keys,3) || strcmp(dw_text(event,"type"),"work")!=0 ||
            !dw_digest(event,"spec_digest",&key)) return GOLEM_ERR_CORRUPT_JOURNAL;
        uint8_t *data=NULL; size_t n=0; struct json_object *spec=NULL;
        st=golem_evidence_read(s->cas,&key,GOLEM_DOCUMENT_MAX_JSON,NULL,&data,&n,NULL);
        if(st==GOLEM_OK) st=dw_spec((golem_bytes){data,n},&spec);
        free(data);
        if(st==GOLEM_OK) { s->spec=spec; s->last=*frame; ++s->event_count; }
        return st;
    }
    if(strcmp(dw_text(event,"type"),"reentry")==0) return re_apply(s,event,payload,frame);
    if(strcmp(dw_text(event,"type"),"completion")==0) return co_apply(s,event,payload,frame);
    const char *keys[]={"schema_version","type","metadata_digest","body_digest","idempotency_key"};
    dw_entry entry={0};
    if(!dw_keys(event,keys,5) || strcmp(dw_text(event,"type"),"document")!=0 ||
        !dw_digest(event,"metadata_digest",&entry.request_digest) ||
        !dw_digest(event,"body_digest",&entry.result.body_digest) || !dw_id(dw_text(event,"idempotency_key")))
        return GOLEM_ERR_CORRUPT_JOURNAL;
    strcpy(entry.key,dw_text(event,"idempotency_key"));
    for(size_t i=0;i<s->count;++i) if(strcmp(entry.key,s->entries[i].key)==0) return GOLEM_ERR_CORRUPT_JOURNAL;
    uint8_t *meta=NULL,*body=NULL; size_t mn=0,bn=0;
    st=golem_evidence_read(s->cas,&entry.request_digest,GOLEM_DOCUMENT_MAX_JSON,NULL,&meta,&mn,NULL);
    if(st==GOLEM_OK) st=dw_meta((golem_bytes){meta,mn},&entry.meta);
    if(st==GOLEM_OK) st=dw_preconditions(s,entry.meta);
    if(st==GOLEM_OK) st=golem_evidence_read(s->cas,&entry.result.body_digest,GOLEM_DOCUMENT_MAX_BODY,NULL,&body,&bn,NULL);
    if(st==GOLEM_OK) st=dw_markdown(entry.meta,(golem_bytes){body,bn});
    if(st==GOLEM_OK) st=ex_document(s,entry.meta,(golem_bytes){body,bn});
    free(meta); free(body);
    if(st==GOLEM_OK) {
        entry.result.revision=(uint32_t)dw_uint(entry.meta,"revision");
        entry.result.generation=s->count+2;
        entry.result.manifest_digest=*payload; entry.result.event_digest=*frame;
        entry.result.projection_status=GOLEM_ERR_NOT_FOUND;
        s->edges+=json_object_array_length(dw_get(entry.meta,"parents"));
        s->entries[s->count++]=entry; s->last=*frame; ++s->event_count;
    } else json_object_put(entry.meta);
    return st;
}
static golem_status empty_root(int root)
{
    int scan=openat(root,".",O_RDONLY|O_DIRECTORY|O_CLOEXEC);
    if(scan<0) return GOLEM_ERR_IO;
    DIR *d=fdopendir(scan);
    if(!d) { close(scan); return GOLEM_ERR_IO; }
    golem_status st=GOLEM_OK; struct dirent *e; errno=0;
    while((e=readdir(d))!=NULL)
        if(strcmp(e->d_name,".")!=0 && strcmp(e->d_name,"..")!=0) { st=GOLEM_ERR_INVALID_STATE; break; }
    if(errno && st==GOLEM_OK) st=GOLEM_ERR_IO;
    closedir(d); return st;
}
static golem_status allocate_store(const char *root,bool writable,bool create,
    const golem_allocator *allocator,golem_document_store **out)
{
    if(!root || !out || golem_allocator_validate(allocator)!=GOLEM_OK) return GOLEM_ERR_INVALID_ARGUMENT;
    void *mem=NULL;
    golem_status st=golem_allocator_alloc(allocator,sizeof(golem_document_store),&mem);
    if(st!=GOLEM_OK) return st;
    golem_document_store *s=mem; memset(s,0,sizeof(*s)); s->root=-1; s->events=-1;
    s->allocator=allocator?*allocator:golem_allocator_default(); s->writable=writable;
    mem=NULL; st=golem_allocator_alloc(&s->allocator,GOLEM_DOCUMENT_MAX_REVISIONS*sizeof(dw_entry),&mem);
    if(st==GOLEM_OK) { s->entries=mem; memset(mem,0,GOLEM_DOCUMENT_MAX_REVISIONS*sizeof(dw_entry)); }
    if(st==GOLEM_OK) {
        s->root=golem_evidence_path_open(root,true);
        if(s->root<0) st=GOLEM_ERR_IO;
    }
    if(st==GOLEM_OK && flock(s->root,(writable?LOCK_EX:LOCK_SH)|LOCK_NB)<0) st=GOLEM_ERR_JOURNAL_BUSY;
    if(st==GOLEM_OK && create) st=empty_root(s->root);
    if(st==GOLEM_OK) st=dw_dir(s->root,"events",create,&s->events);
    if(st==GOLEM_OK) st=golem_evidence_open(root,create||writable,NULL,&s->cas,NULL);
    if(st!=GOLEM_OK) (void)golem_document_store_close(s);
    else *out=s;
    return st;
}
golem_status golem_document_store_create(const char *root,golem_bytes spec,const golem_allocator *a,
    golem_document_store **out,golem_diagnostic *d)
{
    if(!out) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    struct json_object *validated=NULL;
    golem_status st=dw_spec(spec,&validated); json_object_put(validated);
    golem_document_store *s=NULL;
    if(st==GOLEM_OK) st=allocate_store(root,true,true,a,&s);
    struct json_object *event=NULL; golem_receipt receipt; golem_digest payload,frame;
    if(st==GOLEM_OK) st=golem_evidence_put(s->cas,spec,&receipt,NULL);
    if(st==GOLEM_OK) {
        event=json_object_new_object();
        if(!dw_add(event,"schema_version",json_object_new_int(1)) ||
            !dw_add(event,"type",json_object_new_string("work")) ||
            !dw_add_digest(event,"spec_digest",&receipt.digest)) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK) st=dw_put_json(s,event,&payload);
    if(st==GOLEM_OK) st=dw_event_write(s,&payload,&frame);
    if(st==GOLEM_OK) st=dw_apply(s,event,&payload,&frame);
    json_object_put(event);
    if(st==GOLEM_OK) *out=s; else (void)golem_document_store_close(s);
    return dw_report(d,st,NULL);
}
golem_status golem_document_store_open(const char *root,bool writable,const golem_allocator *a,
    golem_document_store **out,golem_diagnostic *d)
{
    if(!out) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    golem_document_store *s=NULL;
    golem_status st=allocate_store(root,writable,false,a,&s);
    if(st==GOLEM_OK) st=dw_replay(s);
    if(st==GOLEM_OK) *out=s; else (void)golem_document_store_close(s);
    return dw_report(d,st,NULL);
}
golem_status golem_document_store_close(golem_document_store *s)
{
    if(!s) return GOLEM_OK;
    for(size_t i=0;i<s->count;++i) json_object_put(s->entries[i].meta);
    for(size_t i=0;i<s->reentry_count;++i) json_object_put(s->reentries[i]);
    for(size_t i=0;i<s->completion_count;++i) json_object_put(s->completions[i]);
    json_object_put(s->spec);
    golem_status st=golem_evidence_close(s->cas);
    if(s->events>=0 && close(s->events)<0) st=GOLEM_ERR_IO;
    if(s->root>=0 && close(s->root)<0) st=GOLEM_ERR_IO;
    golem_allocator a=s->allocator;
    (void)golem_allocator_free(&a,s->entries); (void)golem_allocator_free(&a,s);
    return st;
}
golem_status golem_document_generation(const golem_document_store *s,uint64_t *out)
{
    if(!s || !out) return GOLEM_ERR_INVALID_ARGUMENT;
    if(s->poisoned) return GOLEM_ERR_INVALID_STATE;
    *out=s->count+1; return GOLEM_OK;
}
golem_status golem_document_submit(golem_document_store *s,golem_bytes metadata,golem_bytes body,
    const char *key,golem_document_result *out,golem_diagnostic *d)
{
    if(!s || !out || !dw_id(key)) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    if(!s->writable) return dw_report(d,GOLEM_ERR_POLICY_DENIED,NULL);
    if(s->poisoned) return dw_report(d,GOLEM_ERR_INVALID_STATE,"close/reopen after uncertain commit");
    struct json_object *m=NULL;
    golem_status st=dw_meta(metadata,&m);
    if(st==GOLEM_OK) st=dw_markdown(m,body);
    golem_digest md,bd;
    if(st==GOLEM_OK) st=golem_digest_bytes(metadata,&md);
    if(st==GOLEM_OK) st=golem_digest_bytes(body,&bd);
    if(st==GOLEM_OK) for(size_t i=0;i<s->count;++i) {
        dw_entry *e=&s->entries[i];
        if(strcmp(e->key,key)!=0) continue;
        json_object_put(m);
        if(!dw_equal(&md,&e->request_digest) || !dw_equal(&bd,&e->result.body_digest))
            return dw_report(d,GOLEM_ERR_IDENTITY_MISMATCH,"idempotency key already binds different bytes");
        golem_document_result result=e->result;
        result.projection_status=dw_project(s,e,true); *out=result;
        return dw_report(d,GOLEM_OK,"committed registration, not semantic acceptance");
    }
    if(st==GOLEM_OK) st=dw_preconditions(s,m);
    if(st==GOLEM_OK) st=re_guard(s,dw_text(m,"kind"),true);
    if(st==GOLEM_OK) st=ex_required(s,m);
    if(st==GOLEM_OK) st=ex_document(s,m,body);
    struct json_object *event=NULL; golem_receipt receipt; golem_digest payload,frame;
    if(st==GOLEM_OK) st=golem_evidence_put(s->cas,body,&receipt,NULL);
    if(st==GOLEM_OK) st=golem_evidence_put(s->cas,metadata,&receipt,NULL);
    if(st==GOLEM_OK) {
        event=json_object_new_object();
        if(!dw_add(event,"schema_version",json_object_new_int(1)) ||
           !dw_add(event,"type",json_object_new_string("document")) ||
           !dw_add_digest(event,"metadata_digest",&md) || !dw_add_digest(event,"body_digest",&bd) ||
           !dw_add(event,"idempotency_key",json_object_new_string(key))) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK) st=dw_put_json(s,event,&payload);
    if(st==GOLEM_OK) st=dw_event_write(s,&payload,&frame);
    if(st==GOLEM_OK) {
        /* All validation and allocations precede the commit; commit adoption
         * cannot fail. Replay performs the same validation when reopening. */
        dw_entry e={0}; e.meta=m; m=NULL; strcpy(e.key,key); e.request_digest=md;
        e.result=(golem_document_result){s->count+2,(uint32_t)dw_uint(e.meta,"revision"),bd,payload,frame,GOLEM_OK};
        s->edges+=json_object_array_length(dw_get(e.meta,"parents"));
        s->entries[s->count++]=e; s->last=frame; ++s->event_count;
        golem_document_result result=e.result;
        result.projection_status=dw_project(s,&s->entries[s->count-1],true); *out=result;
    }
    if(st==GOLEM_ERR_IO) s->poisoned=true;
    json_object_put(m); json_object_put(event);
    return dw_report(d,st,st==GOLEM_OK?"committed registration, not semantic acceptance":NULL);
}
static golem_status lookup(golem_document_store *s,const char *id,uint32_t revision,dw_entry **out)
{
    if(!s || !dw_id(id) || !revision) return GOLEM_ERR_INVALID_ARGUMENT;
    if(s->poisoned) return GOLEM_ERR_INVALID_STATE;
    dw_entry *e=dw_find(s,id,revision);
    if(!e) return GOLEM_ERR_NOT_FOUND;
    *out=e; return GOLEM_OK;
}
golem_status golem_document_inspect(golem_document_store *s,const char *id,uint32_t revision,
    golem_document_result *out,golem_diagnostic *d)
{
    if(!out) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    dw_entry *e=NULL; golem_status st=lookup(s,id,revision,&e);
    if(st==GOLEM_OK) {
        uint64_t size;
        st=golem_evidence_verify(s->cas,&e->result.body_digest,&size,NULL);
    }
    if(st==GOLEM_OK) { golem_document_result result=e->result; result.projection_status=dw_project(s,e,false); *out=result; }
    return dw_report(d,st,NULL);
}
static golem_status content(golem_document_store *s,const char *id,uint32_t revision,
    void *buffer,size_t capacity,size_t *required,bool metadata,golem_diagnostic *d)
{
    if(!required || (!buffer && capacity)) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    dw_entry *e=NULL; golem_status st=lookup(s,id,revision,&e);
    uint8_t *body=NULL; size_t n=0;
    if(st==GOLEM_OK) st=golem_evidence_read(s->cas,metadata?&e->request_digest:&e->result.body_digest,
        metadata?GOLEM_DOCUMENT_MAX_JSON:GOLEM_DOCUMENT_MAX_BODY,NULL,&body,&n,NULL);
    if(st==GOLEM_OK) {
        *required=n;
        if(capacity<n) st=GOLEM_ERR_BUFFER_TOO_SMALL;
        else if(n) memcpy(buffer,body,n);
    }
    free(body); return dw_report(d,st,NULL);
}
golem_status golem_document_body(golem_document_store *s,const char *id,uint32_t revision,
    void *buffer,size_t capacity,size_t *required,golem_diagnostic *d)
{ return content(s,id,revision,buffer,capacity,required,false,d); }
golem_status golem_document_metadata(golem_document_store *s,const char *id,uint32_t revision,
    void *buffer,size_t capacity,size_t *required,golem_diagnostic *d)
{ return content(s,id,revision,buffer,capacity,required,true,d); }
golem_status golem_document_project(golem_document_store *s,const char *id,uint32_t revision,golem_diagnostic *d)
{
    dw_entry *e=NULL; golem_status st=lookup(s,id,revision,&e);
    if(st==GOLEM_OK && !s->writable) st=GOLEM_ERR_POLICY_DENIED;
    if(st==GOLEM_OK) st=dw_project(s,e,true);
    return dw_report(d,st,NULL);
}
