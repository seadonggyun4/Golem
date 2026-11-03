#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "review_host.h"
#include "../common/json.h"
#include "../document/internal.h"
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <time.h>
#include <errno.h>

struct gi_review_host {
    struct json_object *policy, *bundle, *control;
    uint8_t *wire;
    size_t size;
    golem_digest policy_pin, bundle_pin, registration, control_digest, baseline;
    gi_review_host_observe observe;
    void *context;
    uint64_t last_time;
    bool busy;
};
static bool equal(const golem_digest *a, const golem_digest *b)
{ return memcmp(a->bytes,b->bytes,32)==0; }
static bool eq(struct json_object *o,const char *k,const char *v)
{ return json_object_is_type(dw_get(o,k),json_type_string)&&!strcmp(dw_text(o,k),v); }
static bool number(struct json_object *o,const char *k,uint64_t *v)
{
    struct json_object *n=dw_get(o,k);
    if(!json_object_is_type(n,json_type_int)||json_object_get_int64(n)<0)return false;
    *v=json_object_get_uint64(n);return true;
}
static bool arr(struct json_object *a,size_t lo,size_t hi)
{ return json_object_is_type(a,json_type_array)&&json_object_array_length(a)>=lo&&json_object_array_length(a)<=hi; }
static bool digest_eq(struct json_object *o,const char *k,const golem_digest *d)
{ golem_digest parsed;return dw_digest(o,k,&parsed)&&equal(&parsed,d); }
static const char *purpose_name(gi_review_purpose p)
{
    switch(p){
    case GI_REVIEW_CONTROL:return "CONTROL";
    case GI_REVIEW_SOURCE_ADOPTION:return "SOURCE_ADOPTION";
    case GI_REVIEW_STAGE:return "STAGE";
    case GI_REVIEW_ACTIVATION:return "ACTIVATION";
    case GI_REVIEW_ANSWER:return "ANSWER";
    case GI_REVIEW_RESOLUTION:return "RESOLUTION";
    }
    return NULL;
}
static struct json_object *principal(gi_review_host *h,const char *id,const char *role,const char *session)
{
    struct json_object *a=dw_get(h->policy,"principals");
    for(size_t i=0;i<json_object_array_length(a);++i){
        struct json_object *p=json_object_array_get_idx(a,i);
        if(eq(p,"id",id)&&eq(p,"role",role)&&eq(p,"session",session)&&eq(p,"status","ACTIVE"))return p;
    }
    return NULL;
}
static bool scope(gi_review_host *h,struct json_object *o)
{
    return json_object_equal(dw_get(o,"project_id"),dw_get(h->policy,"project_id"))&&
        json_object_equal(dw_get(o,"work_id"),dw_get(h->policy,"work_id"))&&
        digest_eq(o,"baseline_digest",&h->baseline)&&digest_eq(o,"policy_digest",&h->policy_pin);
}
/* The policy is baseline-independent, avoiding policy<->baseline hash cycles.
 * The separately owner-selected bundle is action-specific and binds both. */
static golem_status policy_shape(gi_review_host *h)
{
    const char *pk[]={"schema","project_id","work_id","assurance","policy_epoch","principals"};
    const char *ik[]={"id","role","session","status"};uint64_t epoch;
    struct json_object *p=h->policy,*a=dw_get(p,"principals");
    if(!dw_keys(p,pk,6)||!eq(p,"schema","golem.intent.review-host-policy.v1")||
        !dw_id(dw_text(p,"project_id"))||!dw_id(dw_text(p,"work_id"))||
        !eq(p,"assurance","LOCAL_COOPERATIVE")||!number(p,"policy_epoch",&epoch)||!epoch||!arr(a,1,256))return GOLEM_ERR_PARSE;
    for(size_t i=0;i<json_object_array_length(a);++i){
        struct json_object *r=json_object_array_get_idx(a,i);
        if(!dw_keys(r,ik,4)||!dw_id(dw_text(r,"id"))||!dw_id(dw_text(r,"session"))||
            (!eq(r,"role","OWNER")&&!eq(r,"role","PRODUCER")&&!eq(r,"role","REVIEWER"))||
            (!eq(r,"status","ACTIVE")&&!eq(r,"status","REVOKED")))return GOLEM_ERR_PARSE;
        for(size_t j=0;j<i;++j){struct json_object *old=json_object_array_get_idx(a,j);
            if(eq(old,"id",dw_text(r,"id"))&&eq(old,"role",dw_text(r,"role"))&&eq(old,"session",dw_text(r,"session")))return GOLEM_ERR_PARSE;}
    }
    return GOLEM_OK;
}
static golem_status bundle_shape(gi_review_host *h)
{
    const char *bk[]={"schema","project_id","work_id","baseline_digest","policy_digest","registration_digest",
        "control_digest","owner","owner_session","not_before","expires_at","evidence",
        "publication_operation","expected_sequence","expected_head"};
    struct json_object *b=h->bundle,*a=dw_get(b,"evidence");uint64_t begin,end,sequence;golem_digest d;
    if(!dw_keys(b,bk,15)||!dw_digest(b,"publication_operation",&d)||!dw_digest(b,"expected_head",&d)||!number(b,"expected_sequence",&sequence)||!eq(b,"schema","golem.intent.review-host-bundle.v1")||!scope(h,b)||
        !digest_eq(b,"registration_digest",&h->registration)||!digest_eq(b,"control_digest",&h->control_digest)||
        !principal(h,dw_text(b,"owner"),"OWNER",dw_text(b,"owner_session"))||
        !number(b,"not_before",&begin)||!number(b,"expires_at",&end)||end<=begin||end-begin>3600||!arr(a,0,256))return GOLEM_ERR_POLICY_DENIED;
    const char *ek[]={"sha256","bytes"};
    for(size_t i=0;i<json_object_array_length(a);++i){
        struct json_object *row=json_object_array_get_idx(a,i);golem_digest expected,actual;
        struct json_object *raw=dw_get(row,"bytes");
        if(!dw_keys(row,ek,2)||!dw_digest(row,"sha256",&expected)||!json_object_is_type(raw,json_type_string))return GOLEM_ERR_PARSE;
        const char *wire=json_object_get_string(raw);size_t n=(size_t)json_object_get_string_len(raw);
        if(n==0||n>GI_CONTROL_MAX||strlen(wire)!=n)return GOLEM_ERR_PARSE;
        golem_status st=golem_digest_bytes((golem_bytes){(const uint8_t *)wire,n},&actual);
        if(st!=GOLEM_OK)return st;
        if(!equal(&expected,&actual))return GOLEM_ERR_IDENTITY_MISMATCH;
        for(size_t j=0;j<i;++j)if(eq(json_object_array_get_idx(a,j),"sha256",dw_text(row,"sha256")))return GOLEM_ERR_PARSE;
    }
    return GOLEM_OK;
}
golem_status gi_review_host_guard(void *opaque)
{
    gi_review_host *h=opaque;
    if(!h||!h->observe||h->busy)return GOLEM_ERR_INVALID_ARGUMENT;
    golem_digest registration={{0}},policy={{0}},bundle={{0}};uint64_t now=0;
    h->busy=true;golem_status st=h->observe(h->context,&registration,&policy,&bundle,&now);h->busy=false;
    if(st!=GOLEM_OK)return st;
    if(!equal(&registration,&h->registration)||!equal(&policy,&h->policy_pin)||!equal(&bundle,&h->bundle_pin))return GOLEM_ERR_POLICY_DENIED;
    uint64_t begin,end;
    if(!number(h->bundle,"not_before",&begin)||!number(h->bundle,"expires_at",&end)||
        now<begin||now>=end||now<h->last_time)return GOLEM_ERR_STALE_RESULT;
    h->last_time=now;return GOLEM_OK;
}
golem_status gi_review_host_open(golem_bytes policy,const golem_digest *policy_pin,golem_bytes bundle,
    const golem_digest *bundle_pin,golem_bytes control,const golem_digest *registration,
    gi_review_host_observe observe,void *context,gi_review_host **out)
{
    if(!policy.data||!policy.size||policy.size>GI_CONTROL_MAX||!bundle.data||!bundle.size||bundle.size>GI_CONTROL_MAX||!policy_pin||!bundle_pin||!registration||!observe||!out||!control.data||!control.size||control.size>GI_CONTROL_MAX)return GOLEM_ERR_INVALID_ARGUMENT;
    gi_review_host *h=calloc(1,sizeof(*h));if(!h)return GOLEM_ERR_OUT_OF_MEMORY;
    h->policy_pin=*policy_pin;h->bundle_pin=*bundle_pin;h->registration=*registration;h->observe=observe;h->context=context;
    golem_digest actual;golem_status st=golem_digest_bytes(policy,&actual);
    if(st==GOLEM_OK&&!equal(&actual,policy_pin))st=GOLEM_ERR_IDENTITY_MISMATCH;
    if(st==GOLEM_OK)st=golem_digest_bytes(bundle,&actual);
    if(st==GOLEM_OK&&!equal(&actual,bundle_pin))st=GOLEM_ERR_IDENTITY_MISMATCH;
    if(st==GOLEM_OK)st=golem_json_parse(policy,GI_CONTROL_MAX,&h->policy);
    if(st==GOLEM_OK)st=golem_json_parse(bundle,GI_CONTROL_MAX,&h->bundle);
    if(st==GOLEM_OK)st=golem_json_parse(control,GI_CONTROL_MAX,&h->control);
    if(st==GOLEM_OK)st=golem_digest_bytes(control,&h->control_digest);
    if(st==GOLEM_OK&&!dw_digest(h->control,"baseline_digest",&h->baseline))st=GOLEM_ERR_PARSE;
    if(st==GOLEM_OK)st=policy_shape(h);
    if(st==GOLEM_OK&&(!eq(h->control,"project_id",dw_text(h->policy,"project_id"))||!eq(h->control,"work_id",dw_text(h->policy,"work_id"))))st=GOLEM_ERR_POLICY_DENIED;
    if(st==GOLEM_OK)st=bundle_shape(h);
    if(st==GOLEM_OK)st=gi_review_host_guard(h);
    if(st==GOLEM_OK){h->wire=malloc(control.size);if(!h->wire)st=GOLEM_ERR_OUT_OF_MEMORY;}
    if(st==GOLEM_OK){memcpy(h->wire,control.data,control.size);h->size=control.size;*out=h;}else gi_review_host_close(h);
    return st;
}
void gi_review_host_close(gi_review_host *h)
{ if(h){json_object_put(h->policy);json_object_put(h->bundle);json_object_put(h->control);free(h->wire);free(h);} }

static bool fields_equal(struct json_object *a,struct json_object *b,const char **keys,size_t n)
{
    for(size_t i=0;i<n;++i)if(!dw_get(a,keys[i])||!dw_get(b,keys[i])||
        !json_object_equal(dw_get(a,keys[i]),dw_get(b,keys[i])))return false;
    return true;
}
/* Evidence is an owner-selected attestation, not proof of semantic truth.
 * It never includes the consuming control hash (which includes its hash).
 * The separately pinned bundle binds both without a circular digest. */
static bool statement(gi_review_host *h,struct json_object *e,gi_review_purpose purpose,
    const char *producer,const char *reviewer)
{
    const char *keys[]={"schema","purpose","project_id","work_id","baseline_digest","policy_digest",
        "policy_epoch","issuer","issuer_session","producer","producer_session","body"};
    if(!dw_keys(e,keys,12)||!eq(e,"schema","golem.intent.review-host-evidence.v1")||
        !eq(e,"purpose",purpose_name(purpose))||!scope(h,e)||
        !json_object_equal(dw_get(e,"policy_epoch"),dw_get(h->policy,"policy_epoch")))return false;
    struct json_object *b=dw_get(e,"body"),*c=dw_get(h->control,"body");
    bool review=purpose==GI_REVIEW_STAGE||purpose==GI_REVIEW_RESOLUTION;
    if(!principal(h,dw_text(e,"issuer"),review?"REVIEWER":"OWNER",dw_text(e,"issuer_session")))return false;
    if(review){
        if(!principal(h,dw_text(e,"producer"),"PRODUCER",dw_text(e,"producer_session"))||
            eq(e,"producer",dw_text(e,"issuer"))||eq(e,"producer_session",dw_text(e,"issuer_session")))return false;
    }else if(!eq(e,"producer","")||!eq(e,"producer_session",""))return false;
    if(purpose==GI_REVIEW_STAGE){
        const char *bk[]={"stage","input_manifest","definitions_digest","verdict","original_source_reviewed"};
        golem_digest d;
        if(!dw_keys(b,bk,5)||!eq(e,"producer",producer)||!eq(e,"issuer",reviewer)||
            !dw_digest(b,"input_manifest",&d)||!dw_digest(b,"definitions_digest",&d)||
            !json_object_is_type(dw_get(b,"original_source_reviewed"),json_type_boolean)||
            !json_object_get_boolean(dw_get(b,"original_source_reviewed")))return false;
        const char *match[]={"stage","input_manifest","definitions_digest","verdict"};
        if(eq(h->control,"operation","review"))return fields_equal(b,c,match,4);
        return eq(h->control,"operation","activate")&&eq(b,"stage","REQUIREMENTS")&&eq(b,"verdict","PASS");
    }
    if(purpose==GI_REVIEW_SOURCE_ADOPTION){
        const char *bk[]={"disposition","all_source_decisions_reviewed"};
        return eq(h->control,"operation","activate")&&dw_keys(b,bk,2)&&eq(b,"disposition","ADOPT_EXACT_BASELINE")&&
            json_object_is_type(dw_get(b,"all_source_decisions_reviewed"),json_type_boolean)&&
            json_object_get_boolean(dw_get(b,"all_source_decisions_reviewed"));
    }
    if(purpose==GI_REVIEW_ACTIVATION){
        const char *bk[]={"review_digest","policy_digest"};
        return eq(h->control,"operation","activate")&&dw_keys(b,bk,2)&&fields_equal(b,c,bk,2);
    }
    if(purpose==GI_REVIEW_ANSWER){
        const char *bk[]={"question_digest","disposition"};golem_digest q;
        if(!dw_keys(b,bk,2)||!dw_digest(b,"question_digest",&q)||!eq(b,"disposition","SAME_BASELINE"))return false;
        if(eq(h->control,"operation","answer"))return json_object_equal(dw_get(b,"question_digest"),dw_get(c,"question_digest"));
        if(eq(h->control,"operation","resolve")){
            struct json_object *a=dw_get(c,"close");if(!arr(a,0,256))return false;
            for(size_t i=0;i<json_object_array_length(a);++i)
                if(json_object_equal(dw_get(b,"question_digest"),json_object_array_get_idx(a,i)))return true;
        }
        return false;
    }
    if(purpose==GI_REVIEW_RESOLUTION){
        const char *bk[]={"close","carry","disposition"};const char *match[]={"close","carry"};
        /* A resolution reviewer may not attest their own owner answer. */
        struct json_object *records=dw_get(h->bundle,"evidence");
        for(size_t i=0;i<json_object_array_length(records);++i){
            struct json_object *raw=dw_get(json_object_array_get_idx(records,i),"bytes"),*answer=NULL;
            golem_status parsed=golem_json_parse((golem_bytes){(const uint8_t *)json_object_get_string(raw),
                (size_t)json_object_get_string_len(raw)},GI_CONTROL_MAX,&answer);
            if(parsed!=GOLEM_OK)return false;
            bool self=eq(answer,"purpose","ANSWER")&&(eq(answer,"issuer",dw_text(e,"issuer"))||
                eq(answer,"issuer_session",dw_text(e,"issuer_session")));
            json_object_put(answer);if(self)return false;
        }
        return eq(h->control,"operation","resolve")&&dw_keys(b,bk,3)&&eq(b,"disposition","SAME_BASELINE")&&fields_equal(b,c,match,2);
    }
    return false;
}
golem_status gi_review_host_authorize(void *opaque,gi_review_purpose purpose,const golem_digest *baseline,
    const golem_digest *evidence,const char *project,const char *work,const char *producer,const char *reviewer)
{
    gi_review_host *h=opaque;
    if(!h||!baseline||!evidence||!project||!work||!producer||!reviewer||!purpose_name(purpose))return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status st=gi_review_host_guard(h);if(st!=GOLEM_OK)return st;
    if(!equal(baseline,&h->baseline)||!eq(h->policy,"project_id",project)||!eq(h->policy,"work_id",work))return GOLEM_ERR_POLICY_DENIED;
    if(purpose==GI_REVIEW_CONTROL)return equal(evidence,&h->control_digest)?GOLEM_OK:GOLEM_ERR_POLICY_DENIED;
    struct json_object *a=dw_get(h->bundle,"evidence");size_t matches=0;
    for(size_t i=0;i<json_object_array_length(a);++i){
        struct json_object *row=json_object_array_get_idx(a,i),*e=NULL;
        if(purpose!=GI_REVIEW_SOURCE_ADOPTION&&!digest_eq(row,"sha256",evidence))continue;
        if(purpose==GI_REVIEW_SOURCE_ADOPTION&&!equal(evidence,baseline))return GOLEM_ERR_POLICY_DENIED;
        struct json_object *raw=dw_get(row,"bytes");
        st=golem_json_parse((golem_bytes){(const uint8_t *)json_object_get_string(raw),(size_t)json_object_get_string_len(raw)},GI_CONTROL_MAX,&e);
        if(st!=GOLEM_OK)return st;
        if(statement(h,e,purpose,producer,reviewer))++matches;
        json_object_put(e);
    }
    return matches==1?GOLEM_OK:GOLEM_ERR_POLICY_DENIED;
}
golem_status gi_review_host_publish(gi_review_host *h,gi_journal *journal,const golem_digest *base_op,
    const golem_digest *base_request,const golem_digest *baseline,const golem_bytes *definitions,size_t count,
    const golem_digest *operation,uint64_t sequence,const golem_digest *head,gi_journal_receipt *out)
{
    uint64_t selected_sequence;
    if(!h||!journal||!baseline||!operation||!head||!equal(baseline,&h->baseline))return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status st=gi_review_host_guard(h);if(st!=GOLEM_OK)return st;
    if(!digest_eq(h->bundle,"publication_operation",operation)||!digest_eq(h->bundle,"expected_head",head)||
        !number(h->bundle,"expected_sequence",&selected_sequence)||sequence!=selected_sequence)return GOLEM_ERR_POLICY_DENIED;
    gi_baseline_read read;st=gi_journal_read_baseline(journal,base_op,base_request,baseline,&read);
    if(st!=GOLEM_OK)return st;
    struct json_object *base=NULL;st=golem_json_parse(read.graph.baseline,GI_CONTROL_MAX,&base);
    if(st==GOLEM_OK&&(!eq(base,"project_id",dw_text(h->policy,"project_id"))||
        !eq(base,"work_id",dw_text(h->policy,"work_id"))||
        !digest_eq(dw_get(base,"body"),"issuer_policy_ref",&h->policy_pin)))st=GOLEM_ERR_POLICY_DENIED;
    json_object_put(base);gi_object_graph_dispose(&read.graph);
    if(st!=GOLEM_OK)return st;
    return gi_review_publish(journal,base_op,base_request,baseline,definitions,count,
        (golem_bytes){h->wire,h->size},operation,sequence,head,gi_review_host_guard,gi_review_host_authorize,h,out);
}

static golem_status pinned_file(int directory,const char *name,golem_digest *digest)
{
    if(!name||!*name||strchr(name,'/')||!strcmp(name,".")||!strcmp(name,".."))return GOLEM_ERR_INVALID_ARGUMENT;
    int fd=openat(directory,name,O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK);
    if(fd<0)return GOLEM_ERR_POLICY_DENIED;
    struct stat before,after,path;golem_status st=GOLEM_ERR_POLICY_DENIED;uint8_t *buffer=NULL;
    if(fstat(fd,&before)!=0||!S_ISREG(before.st_mode)||before.st_uid!=geteuid()||
        (before.st_mode&0077)||before.st_nlink!=1||before.st_size<=0||before.st_size>GI_CONTROL_MAX)goto done;
    size_t size=(size_t)before.st_size,used=0;
    buffer=malloc(size);if(!buffer){st=GOLEM_ERR_OUT_OF_MEMORY;goto done;}
    while(used<size){ssize_t n=read(fd,buffer+used,size-used);if(n<0&&errno==EINTR)continue;if(n<=0)goto done;used+=(size_t)n;}
    uint8_t tail;if(read(fd,&tail,1)!=0)goto done;
    if(fstat(fd,&after)!=0||fstatat(directory,name,&path,AT_SYMLINK_NOFOLLOW)!=0||
        before.st_dev!=after.st_dev||before.st_ino!=after.st_ino||before.st_size!=after.st_size||
        after.st_dev!=path.st_dev||after.st_ino!=path.st_ino||after.st_size!=path.st_size||
        !S_ISREG(path.st_mode)||path.st_uid!=geteuid()||(path.st_mode&0077)||path.st_nlink!=1)goto done;
    st=golem_digest_bytes((golem_bytes){buffer,size},digest);
done:
    free(buffer);close(fd);return st;
}
golem_status gi_review_host_observe_files(void *opaque,golem_digest *registration,
    golem_digest *policy,golem_digest *bundle,uint64_t *now)
{
    gi_review_host_files *f=opaque;
    if(!f||!f->d01_guard||!registration||!policy||!bundle||!now)return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status st=f->d01_guard(f->d01_context);if(st!=GOLEM_OK)return st;
    struct stat sb;
    if(fstat(f->directory_fd,&sb)!=0||!S_ISDIR(sb.st_mode)||sb.st_uid!=geteuid()||(sb.st_mode&0077))return GOLEM_ERR_POLICY_DENIED;
    golem_digest p,b;
    st=pinned_file(f->directory_fd,f->policy_name,&p);
    if(st==GOLEM_OK)st=pinned_file(f->directory_fd,f->bundle_name,&b);
    if(st==GOLEM_OK)st=f->d01_guard(f->d01_context);
    if(st!=GOLEM_OK)return st;
    time_t clock=time(NULL);if(clock<0)return GOLEM_ERR_STALE_RESULT;
    *registration=f->registration;*policy=p;*bundle=b;*now=(uint64_t)clock;return GOLEM_OK;
}

static golem_status selected_evidence(gi_review_host *h,const golem_digest *digest,struct json_object **out)
{
    golem_status st=gi_review_host_guard(h);if(st!=GOLEM_OK)return st;
    struct json_object *a=dw_get(h->bundle,"evidence");
    for(size_t i=0;i<json_object_array_length(a);++i){struct json_object *row=json_object_array_get_idx(a,i);
        if(!digest_eq(row,"sha256",digest))continue;
        struct json_object *raw=dw_get(row,"bytes");return golem_json_parse((golem_bytes){(const uint8_t *)json_object_get_string(raw),
            (size_t)json_object_get_string_len(raw)},GI_CONTROL_MAX,out);}
    return GOLEM_ERR_POLICY_DENIED;
}
golem_status gi_review_host_selected(gi_review_host *h,golem_bytes control)
{
    if(!h)return GOLEM_ERR_INVALID_ARGUMENT;golem_digest d;golem_status st=golem_digest_bytes(control,&d);
    if(st==GOLEM_OK&&!equal(&d,&h->control_digest))st=GOLEM_ERR_POLICY_DENIED;
    return st==GOLEM_OK?gi_review_host_guard(h):st;
}
static golem_status selected_subject(gi_review_host *h,const golem_digest *identity,struct json_object **out)
{
    golem_status st=gi_review_host_guard(h);if(st!=GOLEM_OK)return st;
    struct json_object *a=dw_get(h->bundle,"evidence"),*selected=NULL;
    for(size_t i=0;i<json_object_array_length(a);++i){struct json_object *raw=dw_get(json_object_array_get_idx(a,i),"bytes"),*o=NULL;
        golem_bytes bytes={(const uint8_t *)json_object_get_string(raw),(size_t)json_object_get_string_len(raw)};golem_digest d;
        st=golem_json_parse(bytes,GI_CONTROL_MAX,&o);if(st!=GOLEM_OK){json_object_put(selected);return st;}
        if(eq(o,"schema","golem.intent.review-host-evidence.v1")&&gi_domain_digest(bytes,&d,NULL)==GOLEM_OK&&equal(&d,identity)){
            if(selected){json_object_put(o);json_object_put(selected);return GOLEM_ERR_POLICY_DENIED;}selected=o;
        }else json_object_put(o);
    }
    if(!selected)return GOLEM_ERR_POLICY_DENIED;*out=selected;return GOLEM_OK;
}
golem_status gi_review_host_subject(gi_review_host *h,const golem_digest *evidence,const golem_digest *subject,bool owner)
{
    if(!h||!evidence||!subject)return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *e=NULL;golem_status st=selected_subject(h,evidence,&e);
    const char *keys[]={"schema","purpose","project_id","work_id","baseline_digest","policy_digest","policy_epoch",
        "issuer","issuer_session","producer","producer_session","body"};
    const char *bk[]={"subject_digest","verdict","original_source_reviewed"};
    struct json_object *b=dw_get(e,"body");
    if(st==GOLEM_OK&&(!dw_keys(e,keys,12)||!eq(e,"schema","golem.intent.review-host-evidence.v1")||!scope(h,e)||
        !eq(e,"purpose",owner?"APPLICABILITY_DECISION":"APPLICABILITY_REVIEW")||
        !json_object_equal(dw_get(e,"policy_epoch"),dw_get(h->policy,"policy_epoch"))||
        !principal(h,dw_text(e,"issuer"),owner?"OWNER":"REVIEWER",dw_text(e,"issuer_session"))||
        !dw_keys(b,bk,3)||!digest_eq(b,"subject_digest",subject)||!eq(b,"verdict","PASS")||
        !json_object_is_type(dw_get(b,"original_source_reviewed"),json_type_boolean)||!json_object_get_boolean(dw_get(b,"original_source_reviewed"))))st=GOLEM_ERR_POLICY_DENIED;
    if(st==GOLEM_OK&&!owner&&(!principal(h,dw_text(e,"producer"),"PRODUCER",dw_text(e,"producer_session"))||
        eq(e,"producer",dw_text(e,"issuer"))||eq(e,"producer_session",dw_text(e,"issuer_session"))))st=GOLEM_ERR_POLICY_DENIED;
    if(st==GOLEM_OK&&owner&&(!eq(e,"producer","")||!eq(e,"producer_session","")))st=GOLEM_ERR_POLICY_DENIED;
    json_object_put(e);return st;
}
golem_status gi_review_host_stage(gi_review_host *h,const golem_digest *evidence,const char *stage,
    const char *producer,const char *reviewer,const golem_digest *input,const golem_digest *definitions)
{
    if(!h||!evidence||!stage||!producer||!reviewer||!input||!definitions)return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *e=NULL;golem_status st=selected_evidence(h,evidence,&e);
    const char *keys[]={"schema","purpose","project_id","work_id","baseline_digest","policy_digest","policy_epoch",
        "issuer","issuer_session","producer","producer_session","body"};
    const char *bk[]={"stage","input_manifest","definitions_digest","verdict","original_source_reviewed"};
    struct json_object *b=dw_get(e,"body");
    if(st==GOLEM_OK&&(!dw_keys(e,keys,12)||!eq(e,"schema","golem.intent.review-host-evidence.v1")||!scope(h,e)||!eq(e,"purpose","STAGE")||
        !json_object_equal(dw_get(e,"policy_epoch"),dw_get(h->policy,"policy_epoch"))||!eq(e,"producer",producer)||!eq(e,"issuer",reviewer)||
        !principal(h,producer,"PRODUCER",dw_text(e,"producer_session"))||!principal(h,reviewer,"REVIEWER",dw_text(e,"issuer_session"))||
        !strcmp(producer,reviewer)||eq(e,"producer_session",dw_text(e,"issuer_session"))||!dw_keys(b,bk,5)||!eq(b,"stage",stage)||
        !digest_eq(b,"input_manifest",input)||!digest_eq(b,"definitions_digest",definitions)||!eq(b,"verdict","PASS")||
        !json_object_is_type(dw_get(b,"original_source_reviewed"),json_type_boolean)||!json_object_get_boolean(dw_get(b,"original_source_reviewed"))))st=GOLEM_ERR_POLICY_DENIED;
    json_object_put(e);return st;
}

golem_status gi_review_host_binding(gi_review_host *h,const golem_digest *registration,
    const golem_digest *baseline,const golem_digest *policy)
{
    if(!h||!registration||!baseline||!policy)return GOLEM_ERR_INVALID_ARGUMENT;
    if(!equal(registration,&h->registration)||!equal(baseline,&h->baseline)||!equal(policy,&h->policy_pin))return GOLEM_ERR_IDENTITY_MISMATCH;
    return gi_review_host_guard(h);
}
golem_status gi_review_host_activation(gi_review_host *h,const golem_digest *decision)
{
    if(!h||!decision)return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *e=NULL;golem_status st=selected_evidence(h,decision,&e);
    const char *keys[]={"schema","purpose","project_id","work_id","baseline_digest","policy_digest","policy_epoch","issuer","issuer_session","producer","producer_session","body"};
    const char *bk[]={"review_digest","policy_digest"};golem_digest review;
    if(st==GOLEM_OK&&(!dw_keys(e,keys,12)||!eq(e,"schema","golem.intent.review-host-evidence.v1")||!eq(e,"purpose","ACTIVATION")||!scope(h,e)||
        !json_object_equal(dw_get(e,"policy_epoch"),dw_get(h->policy,"policy_epoch"))||
        !principal(h,dw_text(e,"issuer"),"OWNER",dw_text(e,"issuer_session"))||!eq(e,"producer","")||!eq(e,"producer_session","")||
        !dw_keys(dw_get(e,"body"),bk,2)||!dw_digest(dw_get(e,"body"),"review_digest",&review)||!digest_eq(dw_get(e,"body"),"policy_digest",&h->policy_pin)))st=GOLEM_ERR_POLICY_DENIED;
    json_object_put(e);if(st!=GOLEM_OK)return st;
    size_t found=0;struct json_object *a=dw_get(h->bundle,"evidence");
    for(size_t i=0;i<json_object_array_length(a);++i){struct json_object *row=json_object_array_get_idx(a,i),*raw=dw_get(row,"bytes");e=NULL;
        st=golem_json_parse((golem_bytes){(const uint8_t *)json_object_get_string(raw),(size_t)json_object_get_string_len(raw)},GI_CONTROL_MAX,&e);
        if(st!=GOLEM_OK)return st;
        const char *sk[]={"disposition","all_source_decisions_reviewed"};struct json_object *b=dw_get(e,"body");
        if(dw_keys(e,keys,12)&&eq(e,"schema","golem.intent.review-host-evidence.v1")&&eq(e,"purpose","SOURCE_ADOPTION")&&scope(h,e)&&
            json_object_equal(dw_get(e,"policy_epoch"),dw_get(h->policy,"policy_epoch"))&&
            principal(h,dw_text(e,"issuer"),"OWNER",dw_text(e,"issuer_session"))&&eq(e,"producer","")&&eq(e,"producer_session","")&&
            dw_keys(b,sk,2)&&eq(b,"disposition","ADOPT_EXACT_BASELINE")&&json_object_is_type(dw_get(b,"all_source_decisions_reviewed"),json_type_boolean)&&
            json_object_get_boolean(dw_get(b,"all_source_decisions_reviewed")))++found;
        json_object_put(e);
    }
    return found==1?GOLEM_OK:GOLEM_ERR_POLICY_DENIED;
}

golem_status gi_review_host_qa_result(gi_review_host *h,const golem_digest *evidence,const golem_digest *subject,char status[16])
{
    if(!h||!evidence||!subject||!status)return GOLEM_ERR_INVALID_ARGUMENT;
    struct json_object *e=NULL;golem_status st=selected_subject(h,evidence,&e);
    const char *keys[]={"schema","purpose","project_id","work_id","baseline_digest","policy_digest","policy_epoch","issuer","issuer_session","producer","producer_session","body"};
    const char *bk[]={"subject_digest","verdict","original_source_reviewed"};struct json_object *b=dw_get(e,"body");
    if(st==GOLEM_OK&&(!dw_keys(e,keys,12)||!eq(e,"schema","golem.intent.review-host-evidence.v1")||!eq(e,"purpose","QA_SEMANTIC")||!scope(h,e)||
        !json_object_equal(dw_get(e,"policy_epoch"),dw_get(h->policy,"policy_epoch"))||
        !principal(h,dw_text(e,"issuer"),"REVIEWER",dw_text(e,"issuer_session"))||!principal(h,dw_text(e,"producer"),"PRODUCER",dw_text(e,"producer_session"))||
        eq(e,"issuer",dw_text(e,"producer"))||eq(e,"issuer_session",dw_text(e,"producer_session"))||!dw_keys(b,bk,3)||!digest_eq(b,"subject_digest",subject)||
        !json_object_is_type(dw_get(b,"original_source_reviewed"),json_type_boolean)||!json_object_get_boolean(dw_get(b,"original_source_reviewed"))||
        (!eq(b,"verdict","PASS")&&!eq(b,"verdict","FAIL")&&!eq(b,"verdict","ERROR")&&!eq(b,"verdict","INCONCLUSIVE"))))st=GOLEM_ERR_POLICY_DENIED;
    if(st==GOLEM_OK)strcpy(status,eq(b,"verdict","INCONCLUSIVE")?"UNKNOWN":dw_text(b,"verdict"));
    json_object_put(e);return st;
}
