#include "internal.h"
#include "../agent_session/internal.h"
#include <stdlib.h>
#include <string.h>

static struct json_object *latest(golem_document_store *s)
{ return s->reentry_count?dw_get(s->reentries[s->reentry_count-1],"decision"):NULL; }
golem_status re_next(golem_document_store *s,const char **action,const char **kind,const char **reason)
{
    struct json_object *d=latest(s);
    if(!d) return GOLEM_OK;
    *action=dw_text(d,"action"); *kind=dw_text(d,"target_kind"); *reason=dw_text(d,"reason");
    if(strcmp(*action,"REVISE_DOCUMENT")) return GOLEM_OK;
    dw_entry *selection=wf_resolve(s,dw_get(d,"selection"));
    if(!selection || dw_find(s,dw_text(selection->meta,"document_id"),0)!=selection) return GOLEM_ERR_STALE_RESULT;
    wf_graph g={0}; golem_status st=wf_graph_make(s,&g);
    struct json_object *invalid=dw_get(d,"invalidated"); bool pending=false;
    for(size_t i=0;st==GOLEM_OK && i<json_object_array_length(invalid);++i) {
        struct json_object *r=json_object_array_get_idx(invalid,i);
        dw_entry *e=dw_find(s,dw_text(r,"document_id"),0);
        if(!e) { st=GOLEM_ERR_NOT_FOUND; break; }
        if(e->result.revision<=dw_uint(r,"revision") || g.states[e-s->entries]!=GOLEM_DOCUMENT_CURRENT) {
            *kind=dw_text(e->meta,"kind"); *reason="IMPACTED_REVISION_REQUIRED"; pending=true; break;
        }
    }
    if(st==GOLEM_OK && !pending) {
        *action=NULL;
        for(size_t i=0;i<s->count;++i) {
            dw_entry *e=&s->entries[i];
            if(g.states[i]==GOLEM_DOCUMENT_CURRENT && !strcmp(dw_text(e->meta,"kind"),"qa-result") &&
               ex_pass(s,e->meta)==GOLEM_ERR_REQUIREMENTS_UNMET) {
                *action="CLASSIFY_FAILURE"; *kind=""; *reason="NEW_OBSERVED_FAILURE_REQUIRES_DECISION"; break;
            }
        }
    }
    wf_graph_free(s,&g); return st;
}
golem_status re_deadline(golem_document_store *s)
{
    if(!s->reentry_count) return GOLEM_OK;
    uint64_t now; golem_digest boot,firstboot;
    struct json_object *first=dw_get(s->reentries[0],"decision");
    golem_status st=as_clock_read(NULL,&now,&boot);
    if(st==GOLEM_OK && (!dw_digest(first,"boot",&firstboot) || !dw_equal(&boot,&firstboot) ||
        now<dw_uint(first,"observed_ms"))) st=GOLEM_ERR_STALE_RESULT;
    if(st==GOLEM_OK && now-dw_uint(first,"observed_ms")>=dw_uint(dw_get(first,"policy"),"max_elapsed_ms")) st=GOLEM_ERR_BUDGET_EXHAUSTED;
    return st;
}
golem_status re_guard(golem_document_store *s,const char *kind,bool live)
{
    if(!s->reentry_count) return GOLEM_OK;
    const char *action=NULL,*target=NULL,*reason=NULL;
    golem_status st=re_next(s,&action,&target,&reason); (void)reason;
    if(st==GOLEM_OK && action && (strcmp(action,"REVISE_DOCUMENT") || strcmp(target,kind))) st=GOLEM_ERR_REQUIREMENTS_UNMET;
    if(st==GOLEM_OK && live) st=re_deadline(s);
    return st;
}
golem_status re_context(golem_document_store *s,struct json_object *m,uint64_t *total,uint64_t budget)
{
    if(!s->reentry_count) return GOLEM_OK;
    struct json_object *event=s->reentries[s->reentry_count-1],*d=dw_get(event,"decision"),*ref=json_object_new_object();
    golem_digest report; uint64_t bytes=0; golem_status st=GOLEM_OK;
    if(!json_object_equal(dw_get(m,"selection"),dw_get(d,"selection"))) st=GOLEM_ERR_STALE_RESULT;
    if(st==GOLEM_OK && !dw_digest(event,"report_digest",&report)) st=GOLEM_ERR_PARSE;
    if(st==GOLEM_OK) st=golem_evidence_verify(s->cas,&report,&bytes,NULL);
    if(st==GOLEM_OK && (*total>budget || bytes>budget-*total)) st=GOLEM_ERR_BUDGET_EXHAUSTED;
    if(st==GOLEM_OK && (!dw_add_digest(ref,"decision_digest",&s->reentry_digests[s->reentry_count-1]) ||
        !dw_add_digest(ref,"report_digest",&report) || !dw_add(ref,"failure_receipt",json_object_get(dw_get(d,"failure_receipt"))) ||
        !ex_uint(m,"schema_version",2) || !dw_add(m,"reentry",json_object_get(ref)))) st=GOLEM_ERR_OUT_OF_MEMORY;
    if(st==GOLEM_OK) { *total+=bytes; if(!ex_uint(m,"total_bytes",*total)) st=GOLEM_ERR_OUT_OF_MEMORY; }
    json_object_put(ref); return st;
}
golem_status re_export(golem_document_store *s,struct json_object *m,struct json_object *reply)
{
    struct json_object *r=dw_get(m,"reentry"); if(!r) return GOLEM_OK;
    golem_digest key; uint8_t *body=NULL; size_t n=0;
    if(!dw_digest(r,"report_digest",&key)) return GOLEM_ERR_PARSE;
    golem_status st=golem_evidence_read(s->cas,&key,GOLEM_DOCUMENT_MAX_BODY,NULL,&body,&n,NULL);
    if(st==GOLEM_OK && !dw_add(reply,"failure_markdown",json_object_new_string_len((const char *)body,(int)n))) st=GOLEM_ERR_OUT_OF_MEMORY;
    free(body); return st;
}
golem_status re_rebase(golem_document_store *s,struct json_object *original,struct json_object *replacement)
{
    if(!latest(s)) return GOLEM_ERR_POLICY_DENIED;
    golem_status st=re_guard(s,"development-result",true);
    struct json_object *a=dw_get(original,"contract"),*b=dw_get(replacement,"contract");
    if(st==GOLEM_OK && (strcmp(dw_text(a,"selection_id"),dw_text(b,"selection_id")) ||
        !json_object_equal(dw_get(a,"gates"),dw_get(b,"gates")) ||
        !json_object_equal(dw_get(a,"snapshot_plan"),dw_get(b,"snapshot_plan")) ||
        !json_object_equal(dw_get(original,"executables"),dw_get(replacement,"executables")))) st=GOLEM_ERR_POLICY_DENIED;
    if(st==GOLEM_OK && !json_object_equal(dw_get(dw_get(replacement,"manifest"),"selection"),dw_get(latest(s),"selection"))) st=GOLEM_ERR_STALE_RESULT;
    /* Preserve the original test baseline. Replanning never grants new gates. */
    if(st==GOLEM_OK && !dw_add(replacement,"baseline",json_object_get(dw_get(original,"baseline")))) st=GOLEM_ERR_OUT_OF_MEMORY;
    return st;
}
