#define _DARWIN_C_SOURCE

#define _POSIX_C_SOURCE 200809L
#include "../../src/intent/review_host.h"
#include "../../src/common/json.h"
#include "test.h"
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>

static golem_bytes wire(struct json_object *o)
{
    const char *s=json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN);
    return (golem_bytes){(const uint8_t *)s,strlen(s)};
}
static void put(struct json_object *o,const char *k,const char *v)
{ json_object_object_add(o,k,json_object_new_string(v)); }
static struct json_object *get(struct json_object *o,const char *k)
{ struct json_object *v=NULL;json_object_object_get_ex(o,k,&v);return v; }
static void pin(struct json_object *o,const char *k,const golem_digest *d)
{
    char s[65];size_t n;
    if(golem_digest_format(d,s,sizeof(s),&n)!=GOLEM_OK)abort();put(o,k,s);
}
static golem_digest digest(struct json_object *o)
{ golem_digest d;if(golem_digest_bytes(wire(o),&d)!=GOLEM_OK)abort();return d; }
static struct json_object *parse(const char *s)
{
    struct json_object *o=NULL;
    if(golem_json_parse((golem_bytes){(const uint8_t *)s,strlen(s)},GI_CONTROL_MAX,&o)!=GOLEM_OK)abort();return o;
}
typedef struct live {golem_digest registration,policy,bundle;uint64_t now;golem_status status;} live;
static golem_status observe(void *ctx,golem_digest *r,golem_digest *p,golem_digest *b,uint64_t *now)
{ live *v=ctx;*r=v->registration;*p=v->policy;*b=v->bundle;*now=v->now;return v->status; }
static golem_status d01(void *ctx){return *(golem_status *)ctx;}
static int files(void)
{
    char path[]="/tmp/golem-review-host-XXXXXX";CHECK(mkdtemp(path)!=NULL);
    int root=open(path,O_RDONLY|O_DIRECTORY);CHECK(root>=0);
    int fd=openat(root,"policy",O_WRONLY|O_CREAT|O_EXCL,0600);CHECK(fd>=0);
    CHECK(write(fd,"{}",2)==2);close(fd);
    fd=openat(root,"bundle",O_WRONLY|O_CREAT|O_EXCL,0600);CHECK(fd>=0);
    CHECK(write(fd,"{}",2)==2);close(fd);
    golem_status allowed=GOLEM_OK;gi_review_host_files f={root,"policy","bundle",{{0}},d01,&allowed};
    golem_digest r,p,b;uint64_t now;
    CHECK(gi_review_host_observe_files(&f,&r,&p,&b,&now)==GOLEM_OK);
    CHECK(fchmodat(root,"policy",0644,0)==0);
    CHECK(gi_review_host_observe_files(&f,&r,&p,&b,&now)==GOLEM_ERR_POLICY_DENIED);
    CHECK(unlinkat(root,"policy",0)==0);CHECK(symlinkat("bundle",root,"policy")==0);
    CHECK(gi_review_host_observe_files(&f,&r,&p,&b,&now)==GOLEM_ERR_POLICY_DENIED);
    f.policy_name="../policy";CHECK(gi_review_host_observe_files(&f,&r,&p,&b,&now)==GOLEM_ERR_INVALID_ARGUMENT);
    allowed=GOLEM_ERR_POLICY_DENIED;
    CHECK(gi_review_host_observe_files(&f,&r,&p,&b,&now)==GOLEM_ERR_POLICY_DENIED);
    CHECK(unlinkat(root,"policy",0)==0);CHECK(unlinkat(root,"bundle",0)==0);close(root);CHECK(rmdir(path)==0);return 0;
}
int main(void)
{
    struct json_object *policy=parse("{\"schema\":\"golem.intent.review-host-policy.v1\",\"project_id\":\"demo\",\"work_id\":\"work\",\"assurance\":\"LOCAL_COOPERATIVE\",\"policy_epoch\":1,\"principals\":[{\"id\":\"owner\",\"role\":\"OWNER\",\"session\":\"owner-session\",\"status\":\"ACTIVE\"},{\"id\":\"producer\",\"role\":\"PRODUCER\",\"session\":\"producer-session\",\"status\":\"ACTIVE\"},{\"id\":\"reviewer\",\"role\":\"REVIEWER\",\"session\":\"reviewer-session\",\"status\":\"ACTIVE\"}]}");
    golem_digest base={{1}},registration={{2}},input={{3}},defs={{4}},operation={{5}},head={{0}};
    live current={registration,digest(policy),{{0}},110,GOLEM_OK};
    struct json_object *e=parse("{\"schema\":\"golem.intent.review-host-evidence.v1\",\"purpose\":\"STAGE\",\"project_id\":\"demo\",\"work_id\":\"work\",\"policy_epoch\":1,\"issuer\":\"reviewer\",\"issuer_session\":\"reviewer-session\",\"producer\":\"producer\",\"producer_session\":\"producer-session\",\"body\":{\"stage\":\"REQUIREMENTS\",\"verdict\":\"PASS\",\"original_source_reviewed\":true}}");
    pin(e,"baseline_digest",&base);pin(e,"policy_digest",&current.policy);
    pin(get(e,"body"),"input_manifest",&input);pin(get(e,"body"),"definitions_digest",&defs);
    golem_digest evidence=digest(e);
    struct json_object *control=parse("{\"schema\":\"golem.intent.review-control.v1\",\"project_id\":\"demo\",\"work_id\":\"work\",\"expected_epoch\":0,\"operation\":\"review\",\"body\":{\"stage\":\"REQUIREMENTS\",\"producer\":\"producer\",\"reviewer\":\"reviewer\",\"verdict\":\"PASS\"}}");
    pin(control,"baseline_digest",&base);pin(get(control,"body"),"input_manifest",&input);
    pin(get(control,"body"),"definitions_digest",&defs);pin(get(control,"body"),"evidence_digest",&evidence);
    golem_digest request=digest(control);
    struct json_object *bundle=parse("{\"schema\":\"golem.intent.review-host-bundle.v1\",\"project_id\":\"demo\",\"work_id\":\"work\",\"owner\":\"owner\",\"owner_session\":\"owner-session\",\"not_before\":100,\"expires_at\":200,\"expected_sequence\":0,\"evidence\":[]}");
    pin(bundle,"baseline_digest",&base);pin(bundle,"policy_digest",&current.policy);pin(bundle,"registration_digest",&registration);
    pin(bundle,"control_digest",&request);pin(bundle,"publication_operation",&operation);pin(bundle,"expected_head",&head);
    struct json_object *row=json_object_new_object();pin(row,"sha256",&evidence);
    put(row,"bytes",(const char *)wire(e).data);json_object_array_add(get(bundle,"evidence"),row);
    current.bundle=digest(bundle);gi_review_host *host=NULL;
    CHECK(gi_review_host_open(wire(policy),&current.policy,wire(bundle),&current.bundle,wire(control),&registration,observe,&current,&host)==GOLEM_OK);
    CHECK(gi_review_host_authorize(host,GI_REVIEW_CONTROL,&base,&request,"demo","work","","")==GOLEM_OK);
    CHECK(gi_review_host_authorize(host,GI_REVIEW_STAGE,&base,&evidence,"demo","work","producer","reviewer")==GOLEM_OK);
    CHECK(gi_review_host_authorize(host,GI_REVIEW_STAGE,&base,&evidence,"demo","other","producer","reviewer")==GOLEM_ERR_POLICY_DENIED);
    CHECK(gi_review_host_authorize(host,GI_REVIEW_STAGE,&base,&evidence,"demo","work","reviewer","reviewer")==GOLEM_ERR_POLICY_DENIED);
    CHECK(gi_review_host_authorize(host,GI_REVIEW_ACTIVATION,&base,&evidence,"demo","work","","")==GOLEM_ERR_POLICY_DENIED);
    CHECK(gi_review_host_authorize(host,GI_REVIEW_CONTROL,&base,&evidence,"demo","work","","")==GOLEM_ERR_POLICY_DENIED);
    CHECK(gi_review_host_stage(host,&evidence,"REQUIREMENTS","producer","reviewer",&input,&defs)==GOLEM_OK);
    CHECK(gi_review_host_stage(host,&evidence,"DESIGN","producer","reviewer",&input,&defs)==GOLEM_ERR_POLICY_DENIED);
    CHECK(gi_review_host_stage(host,&evidence,"REQUIREMENTS","producer","reviewer",&base,&defs)==GOLEM_ERR_POLICY_DENIED);
    CHECK(gi_review_host_binding(host,&registration,&base,&current.policy)==GOLEM_OK);
    CHECK(gi_review_host_binding(host,&base,&base,&current.policy)==GOLEM_ERR_IDENTITY_MISMATCH);
    CHECK(gi_review_host_selected(host,wire(control))==GOLEM_OK);
    CHECK(gi_review_host_activation(host,&evidence)==GOLEM_ERR_POLICY_DENIED);
    current.now=109;CHECK(gi_review_host_guard(host)==GOLEM_ERR_STALE_RESULT);
    current.now=200;CHECK(gi_review_host_guard(host)==GOLEM_ERR_STALE_RESULT);current.now=110;
    current.bundle.bytes[0]^=1;CHECK(gi_review_host_guard(host)==GOLEM_ERR_POLICY_DENIED);current.bundle.bytes[0]^=1;
    CHECK(gi_review_host_guard(host)==GOLEM_OK); /* restoration of fixture observer only */
    current.policy.bytes[0]^=1;CHECK(gi_review_host_guard(host)==GOLEM_ERR_POLICY_DENIED);current.policy.bytes[0]^=1;
    current.status=GOLEM_ERR_POLICY_DENIED;CHECK(gi_review_host_guard(host)==GOLEM_ERR_POLICY_DENIED);current.status=GOLEM_OK;
    gi_review_host_close(host);host=NULL;
    put(row,"bytes","{}");current.bundle=digest(bundle);
    CHECK(gi_review_host_open(wire(policy),&current.policy,wire(bundle),&current.bundle,wire(control),&registration,observe,&current,&host)==GOLEM_ERR_IDENTITY_MISMATCH);
    CHECK(host==NULL);
    json_object_put(bundle);json_object_put(control);json_object_put(e);json_object_put(policy);
    CHECK(files()==0);return 0;
}
