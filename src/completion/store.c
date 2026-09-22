#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include "../reentry/internal.h"
#include "golem/agent_session.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static golem_status root_hash(struct json_object *assessment,struct json_object *boundary,golem_digest *out)
{
    struct json_object *o=json_object_new_object(); golem_status st=GOLEM_OK;
    if(!dw_add(o,"assessment",json_object_get(assessment)) || !dw_add(o,"boundary",json_object_get(boundary))) st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK) st=ex_hash(o,out);
    json_object_put(o); return st;
}
golem_status co_apply(golem_document_store *s,struct json_object *event,const golem_digest *payload,const golem_digest *frame)
{
    const char *keys[]={"schema_version","type","request","record","report_digest"};
    const char *rk[]={"schema_version","sequence","event_sequence","completed_at_unix_seconds","assessment","boundary","evidence_root"};
    struct json_object *r=dw_get(event,"record"),*expected=NULL; golem_digest report,root,declared;
    if(!dw_keys(event,keys,5) || dw_uint(event,"schema_version")!=1 || strcmp(dw_text(event,"type"),"completion") ||
       !dw_keys(r,rk,7) || dw_uint(r,"schema_version")!=1 || !dw_uint(r,"completed_at_unix_seconds") ||
       dw_uint(r,"completed_at_unix_seconds")>INT64_MAX ||
       dw_uint(r,"sequence")!=s->completion_count+1 || dw_uint(r,"event_sequence")!=s->event_count+1 ||
       s->completion_count>=CO_MAX_RECORDS || !dw_digest(event,"report_digest",&report) ||
       !dw_digest(r,"evidence_root",&declared)) return GOLEM_ERR_CORRUPT_JOURNAL;
    for(size_t i=0;i<s->completion_count;++i)
        if(!strcmp(dw_text(dw_get(s->completions[i],"request"),"key"),dw_text(dw_get(event,"request"),"key"))) return GOLEM_ERR_CORRUPT_JOURNAL;
    struct json_object *boundary=dw_get(r,"boundary"),*attempts=dw_get(boundary,"attempts");
    const char *bk[]={"session_sequence","session_head","session","attempts"}; golem_digest session_head;
    if(!dw_keys(boundary,bk,4) || dw_uint(boundary,"session_sequence")>GOLEM_AGENT_MAX_EVENTS ||
       !dw_digest(boundary,"session_head",&session_head) || dw_get(dw_get(boundary,"session"),"active") ||
       !ds_array(attempts,0,256)) return GOLEM_ERR_CORRUPT_JOURNAL;
    for(size_t i=0;i<json_object_array_length(attempts);++i) {
        struct json_object *a=json_object_array_get_idx(attempts,i); const char *ak[]={"attempt_id","state"};
        if(!dw_keys(a,ak,2) || !dw_id(dw_text(a,"attempt_id")) || strcmp(dw_text(a,"state"),"SUBMITTED")) return GOLEM_ERR_CORRUPT_JOURNAL;
    }
    golem_status st=co_evaluate(s,dw_get(event,"request"),false,&expected);
    if(st==GOLEM_OK && !json_object_equal(expected,dw_get(r,"assessment"))) st=GOLEM_ERR_CORRUPT_JOURNAL;
    if(st==GOLEM_OK) st=root_hash(expected,dw_get(r,"boundary"),&root);
    if(st==GOLEM_OK && !dw_equal(&root,&declared)) st=GOLEM_ERR_DIGEST_MISMATCH;
    if(st==GOLEM_OK) st=co_boundary_verify(s,boundary);
    golem_execution_reply md={0}; uint64_t size; golem_digest mdkey;
    if(st==GOLEM_OK) st=co_markdown(r,&md);
    if(st==GOLEM_OK) st=golem_digest_bytes((golem_bytes){md.data,md.size},&mdkey);
    if(st==GOLEM_OK && !dw_equal(&mdkey,&report)) st=GOLEM_ERR_DIGEST_MISMATCH;
    if(st==GOLEM_OK) st=golem_evidence_verify(s->cas,&report,&size,NULL);
    if(st==GOLEM_OK) {
        s->completions[s->completion_count]=json_object_get(event);
        s->completion_digests[s->completion_count++]=*payload; s->last=*frame; ++s->event_count;
    }
    json_object_put(expected); golem_execution_reply_free(&md); return st;
}
static golem_status projected(golem_document_store *s,size_t index)
{
    struct json_object *event=s->completions[index],*docs=dw_get(dw_get(dw_get(event,"record"),"assessment"),"documents");
    golem_status st=GOLEM_OK;
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(docs);++i) {
        struct json_object *v=json_object_array_get_idx(docs,i);
        dw_entry *e=dw_find(s,dw_text(v,"document_id"),(uint32_t)dw_uint(v,"revision"));
        st=e?dw_project(s,e,false):GOLEM_ERR_MISSING_RECORD;
    }
    int top=-1,dir=-1; char name[32]; (void)snprintf(name,sizeof(name),"r%04u",(unsigned)(index+1));
    if(st==GOLEM_OK) st=dw_dir(s->root,"completions",false,&top);
    if(st==GOLEM_OK) st=dw_dir(top,name,false,&dir);
    uint8_t *bytes=NULL; size_t n=0; golem_digest actual,expected;
    if(st==GOLEM_OK) st=dw_read_at(dir,"completion.md",GOLEM_DOCUMENT_MAX_BODY,&bytes,&n);
    if(st==GOLEM_OK) st=golem_digest_bytes((golem_bytes){bytes,n},&actual);
    if(st==GOLEM_OK && (!dw_digest(event,"report_digest",&expected) || !dw_equal(&actual,&expected))) st=GOLEM_ERR_DIGEST_MISMATCH;
    free(bytes); if(dir>=0) close(dir); if(top>=0) close(top); return st;
}
static size_t latest(golem_document_store *s,const char *id)
{
    for(size_t i=s->completion_count;i>0;--i)
        if(!strcmp(dw_text(dw_get(s->completions[i-1],"request"),"selection_id"),id)) return i-1;
    return SIZE_MAX;
}
golem_status co_hint(golem_document_store *s,const char *id,const char **action)
{
    *action=NULL; size_t i=latest(s,id); if(i==SIZE_MAX) return GOLEM_OK;
    struct json_object *event=s->completions[i],*observed=NULL,*boundary=NULL;
    golem_status st=co_boundary_verify(s,dw_get(dw_get(event,"record"),"boundary"));
    if(st!=GOLEM_OK) return st;
    st=co_evaluate(s,dw_get(event,"request"),true,&observed);
    if(st==GOLEM_ERR_STALE_RESULT || st==GOLEM_ERR_REQUIREMENTS_UNMET || st==GOLEM_ERR_NOT_FOUND) {
        *action="REVALIDATE_COMPLETION"; st=GOLEM_OK;
    } else if(st==GOLEM_OK) {
        if(!json_object_equal(observed,dw_get(dw_get(event,"record"),"assessment"))) *action="REVALIDATE_COMPLETION";
        else {
            st=co_quiescent(s,action,&boundary);
            if(st==GOLEM_OK && !*action) {
                st=projected(s,i);
                if(st==GOLEM_ERR_NOT_FOUND) { *action="RECOVER_REPORT"; st=GOLEM_OK; }
                else if(st==GOLEM_OK) *action="DONE";
            }
        }
    }
    json_object_put(observed); json_object_put(boundary); return st;
}
static golem_status receipt_value(struct json_object *event,const golem_digest *digest,golem_execution_reply *out)
{
    struct json_object *o=json_object_new_object(); golem_status st=GOLEM_OK;
    if(!dw_add_digest(o,"receipt_digest",digest) ||
       !dw_add(o,"record",json_object_get(event)) ||
       !ex_text(o,"state","RECORDED") || !ex_text(o,"next_action","RESUME_TO_VERIFY_PROJECTION")) st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK) st=ex_emit(o,out);
    json_object_put(o); return st;
}
static golem_status receipt(golem_document_store *s,size_t i,golem_execution_reply *out)
{ return receipt_value(s->completions[i],&s->completion_digests[i],out); }
static golem_status resume(golem_document_store *s,const char *id,golem_execution_reply *out)
{
    dw_entry *plan=dw_find(s,id,0);
    if(!plan || dw_uint(plan->meta,"schema_version")!=3 || strcmp(dw_text(plan->meta,"kind"),"stage-selection")) return GOLEM_ERR_NOT_FOUND;
    const char *action=NULL; struct json_object *boundary=NULL,*o=json_object_new_object(),*next=NULL;
    golem_status st=co_quiescent(s,&action,&boundary);
    if(st==GOLEM_OK && !action) st=co_hint(s,id,&action);
    if(st==GOLEM_OK && !action) {
        size_t n=0; st=golem_workflow_next(s,id,NULL,0,&n,NULL);
        if(st==GOLEM_ERR_BUFFER_TOO_SMALL) {
            uint8_t *bytes=malloc(n); st=bytes?GOLEM_OK:GOLEM_ERR_OUT_OF_MEMORY;
            if(st==GOLEM_OK) st=golem_workflow_next(s,id,bytes,n,&n,NULL);
            if(st==GOLEM_OK) st=golem_json_parse((golem_bytes){bytes,n},GOLEM_DOCUMENT_MAX_JSON,&next);
            free(bytes);
        }
        if(st==GOLEM_OK) action=dw_text(next,"action");
    }
    struct json_object *docs=json_object_new_array(),*history=json_object_new_array(),*results=json_object_new_array();
    if(!o || !docs || !history || !results) st=GOLEM_ERR_OUT_OF_MEMORY;
    wf_graph g={0}; if(st==GOLEM_OK) st=wf_graph_make(s,&g);
    for(size_t i=0;st==GOLEM_OK && i<s->count;++i) if(g.states[i]==GOLEM_DOCUMENT_CURRENT) {
        struct json_object *v=wf_ref(&s->entries[i]);
        if(!ex_text(v,"kind",dw_text(s->entries[i].meta,"kind"))) { json_object_put(v); st=GOLEM_ERR_OUT_OF_MEMORY; }
        else if(!wf_append(docs,v)) st=GOLEM_ERR_OUT_OF_MEMORY;
        if(st==GOLEM_OK && dw_uint(s->entries[i].meta,"schema_version")==5) {
            golem_digest key; struct json_object *r=NULL,*item=json_object_new_object();
            if(!dw_digest(s->entries[i].meta,"execution_receipt",&key)) st=GOLEM_ERR_PARSE;
            if(st==GOLEM_OK) st=ex_load(s,&key,NULL,&r);
            golem_status fresh=st==GOLEM_OK?ex_live(s,s->entries[i].meta):st;
            if(fresh!=GOLEM_OK && fresh!=GOLEM_ERR_STALE_RESULT) st=fresh;
            if(st==GOLEM_OK && (!dw_add_digest(item,"receipt_digest",&key) ||
               !ex_text(item,"kind",dw_text(s->entries[i].meta,"kind")) ||
               !ex_text(item,"status",dw_text(r,"status")) ||
               !ex_text(item,"freshness",fresh==GOLEM_OK?"CURRENT":"STALE"))) st=GOLEM_ERR_OUT_OF_MEMORY;
            if(st==GOLEM_OK) { if(!wf_append(results,item)) st=GOLEM_ERR_OUT_OF_MEMORY; } else json_object_put(item);
            json_object_put(r);
        }
    }
    for(size_t i=0;st==GOLEM_OK && i<s->reentry_count;++i) {
        struct json_object *v=json_object_new_object();
        if(!dw_add_digest(v,"decision_digest",&s->reentry_digests[i]) ||
           !dw_add(v,"report_digest",json_object_get(dw_get(s->reentries[i],"report_digest")))) { json_object_put(v); st=GOLEM_ERR_OUT_OF_MEMORY; }
        else if(!wf_append(history,v)) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    size_t i=latest(s,id);
    if(st==GOLEM_OK && (!ex_uint(o,"schema_version",1) || !ex_text(o,"action",action) ||
       !ex_uint(o,"generation",s->count+1) || json_object_object_add(o,"next",json_object_get(next))!=0 ||
       !dw_add(o,"boundary",json_object_get(boundary)) || !dw_add(o,"current_documents",json_object_get(docs)) ||
       !dw_add(o,"failure_history",json_object_get(history)) ||
       !dw_add(o,"result_evidence",json_object_get(results)) || !dw_add(o,"selection",wf_ref(plan)) ||
       !dw_add(o,"scope",json_object_get(dw_get(dw_get(plan->meta,"selection"),"scope"))) ||
       !dw_add(o,"acceptance_verified",json_object_new_boolean(!strcmp(action,"DONE"))) ||
       !dw_add(o,"execution_authorized",json_object_new_boolean(false)) ||
       !ex_uint(o,"completion_sequence",i==SIZE_MAX?0:i+1))) st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK && i!=SIZE_MAX && (!dw_add_digest(o,"receipt_digest",&s->completion_digests[i]) ||
       !dw_add(o,"completion",json_object_get(s->completions[i])))) st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK) st=ex_emit(o,out);
    wf_graph_free(s,&g); json_object_put(o); json_object_put(next); json_object_put(boundary); json_object_put(docs); json_object_put(history); json_object_put(results);
    return st;
}
golem_status golem_completion_call(golem_document_store *s,golem_bytes b,golem_execution_reply *out,golem_diagnostic *d)
{
    if(!s || !out || s->poisoned) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    struct json_object *r=NULL,*assessment=NULL,*boundary=NULL,*record=NULL,*event=NULL;
    golem_status st=golem_json_parse(b,GOLEM_DOCUMENT_MAX_JSON,&r);
    if(st==GOLEM_OK) st=co_validate(r);
    bool read=!strcmp(dw_text(r,"operation"),"resume");
    if(st==GOLEM_OK && read) { st=resume(s,dw_text(r,"selection_id"),out); json_object_put(r); return dw_report(d,st,NULL); }
    for(size_t i=0;st==GOLEM_OK && i<s->completion_count;++i) {
        struct json_object *old=dw_get(s->completions[i],"request");
        if(strcmp(dw_text(old,"key"),dw_text(r,"key"))) continue;
        st=json_object_equal(old,r)?receipt(s,i,out):GOLEM_ERR_IDENTITY_MISMATCH;
        json_object_put(r); return dw_report(d,st,NULL);
    }
    if(st==GOLEM_OK && (!s->writable || !strcmp(dw_text(s->spec,"permission"),"DENY"))) st=GOLEM_ERR_POLICY_DENIED;
    if(st==GOLEM_OK && !strcmp(dw_text(s->spec,"permission"),"ASK_ALWAYS")) st=GOLEM_ERR_APPROVAL_REQUIRED;
    if(st==GOLEM_OK && s->completion_count>=CO_MAX_RECORDS) st=GOLEM_ERR_BUDGET_EXHAUSTED;
    for(size_t i=0;st==GOLEM_OK && i<s->completion_count;++i) {
        struct json_object *old=dw_get(s->completions[i],"request");
        if(!strcmp(dw_text(old,"selection_id"),dw_text(r,"selection_id")) &&
           dw_uint(old,"expected_generation")==dw_uint(r,"expected_generation")) st=GOLEM_ERR_IDENTITY_MISMATCH;
    }
    if(st==GOLEM_OK) st=re_deadline(s);
    const char *action=NULL;
    if(st==GOLEM_OK) st=co_quiescent(s,&action,&boundary);
    if(st==GOLEM_OK && action) st=GOLEM_ERR_INCOMPLETE_WORK;
    if(st==GOLEM_OK) st=co_evaluate(s,r,true,&assessment);
    golem_digest root,payload,frame; golem_execution_reply md={0},encoded={0},response={0}; golem_receipt report;
    if(st==GOLEM_OK) st=root_hash(assessment,boundary,&root);
    if(st==GOLEM_OK) {
        time_t now=time(NULL); record=json_object_new_object();
        if(now<=0) st=GOLEM_ERR_IO;
        else if(!ex_uint(record,"schema_version",1) || !ex_uint(record,"sequence",s->completion_count+1) ||
           !ex_uint(record,"event_sequence",s->event_count+1) || !ex_uint(record,"completed_at_unix_seconds",(uint64_t)now) ||
           !dw_add(record,"assessment",json_object_get(assessment)) || !dw_add(record,"boundary",json_object_get(boundary)) ||
           !dw_add_digest(record,"evidence_root",&root)) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK) st=co_markdown(record,&md);
    if(st==GOLEM_OK) st=golem_evidence_put(s->cas,(golem_bytes){md.data,md.size},&report,NULL);
    if(st==GOLEM_OK) {
        event=json_object_new_object();
        if(!ex_uint(event,"schema_version",1) || !ex_text(event,"type","completion") ||
           !dw_add(event,"request",json_object_get(r)) || !dw_add(event,"record",json_object_get(record)) ||
           !dw_add_digest(event,"report_digest",&report.digest)) st=GOLEM_ERR_OUT_OF_MEMORY;
    }
    if(st==GOLEM_OK) st=ex_emit(event,&encoded);
    if(st==GOLEM_OK) st=dw_put_json(s,event,&payload);
    if(st==GOLEM_OK) st=receipt_value(event,&payload,&response);
    if(st==GOLEM_OK) st=dw_event_write(s,&payload,&frame);
    if(st==GOLEM_OK) {
        s->completions[s->completion_count]=json_object_get(event);
        s->completion_digests[s->completion_count++]=payload; s->last=frame; ++s->event_count;
        *out=response; response=(golem_execution_reply){0};
    }
    if(st==GOLEM_ERR_IO) s->poisoned=true;
    golem_execution_reply_free(&md); golem_execution_reply_free(&encoded); golem_execution_reply_free(&response);
    json_object_put(r); json_object_put(assessment); json_object_put(boundary); json_object_put(record); json_object_put(event);
    return dw_report(d,st,NULL);
}
