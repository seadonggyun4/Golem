#include "golem/workflow.h"
#include "test.h"
#include <string.h>
typedef struct memory { size_t calls,fail,live; } memory;
static void *allocate(void *ctx,size_t n)
{ memory *m=ctx; if(m->calls++==m->fail) return NULL; void *p=malloc(n); if(p) ++m->live; return p; }
static void release(void *ctx,void *p)
{ memory *m=ctx; if(p) { --m->live; free(p); } }
int main(void)
{
    golem_digest digest={{1}}; size_t parents[]={0,1};
    golem_dependency_node nodes[]={
        {"work","plan",1,digest,NULL,0}, {"work","dev",1,digest,parents,1},
        {"work","qa",1,digest,parents+1,1}, {"work","plan",2,digest,NULL,0}};
    golem_document_freshness out[4];
    CHECK(golem_document_graph_evaluate(nodes,4,NULL,out,4,NULL)==GOLEM_OK);
    CHECK(out[0]==GOLEM_DOCUMENT_SUPERSEDED && out[1]==GOLEM_DOCUMENT_STALE && out[2]==GOLEM_DOCUMENT_STALE && out[3]==GOLEM_DOCUMENT_CURRENT);
    memory mem={0,0,0}; golem_allocator a={&mem,allocate,release};
    golem_document_freshness saved[4]; memcpy(saved,out,sizeof(out));
    CHECK(golem_document_graph_evaluate(nodes,4,&a,out,4,NULL)==GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(memcmp(saved,out,sizeof(out))==0 && mem.live==0);
    nodes[0].parents=parents+1; nodes[0].parent_count=1;
    CHECK(golem_document_graph_evaluate(nodes,4,NULL,out,4,NULL)==GOLEM_ERR_INVALID_GRAPH);
    CHECK(memcmp(saved,out,sizeof(out))==0);
    nodes[0].parents=NULL; nodes[0].parent_count=0;
    nodes[1].work_id="another";
    CHECK(golem_document_graph_evaluate(nodes,4,NULL,out,4,NULL)==GOLEM_ERR_IDENTITY_MISMATCH);
    nodes[1].work_id="work"; nodes[3].revision=1;
    CHECK(golem_document_graph_evaluate(nodes,4,NULL,out,4,NULL)==GOLEM_ERR_INVALID_GRAPH);
    nodes[3].revision=2;
    size_t duplicate[]={0,0}; nodes[1].parents=duplicate; nodes[1].parent_count=2;
    CHECK(golem_document_graph_evaluate(nodes,4,NULL,out,4,NULL)==GOLEM_ERR_INVALID_GRAPH);
    nodes[1].parent_count=1; duplicate[0]=4;
    CHECK(golem_document_graph_evaluate(nodes,4,NULL,out,4,NULL)==GOLEM_ERR_INVALID_GRAPH);
    duplicate[0]=0; memset(&nodes[0].manifest_digest,0,sizeof(digest));
    CHECK(golem_document_graph_evaluate(nodes,4,NULL,out,4,NULL)==GOLEM_ERR_INVALID_GRAPH);
    size_t n=GOLEM_DOCUMENT_MAX_REVISIONS;
    golem_dependency_node *large=calloc(n,sizeof(*large)); size_t *links=malloc(n*sizeof(*links));
    char (*ids)[32]=calloc(n,sizeof(*ids)); golem_document_freshness *states=malloc(n*sizeof(*states));
    CHECK(large && links && ids && states);
    for(size_t i=0;i<n;++i) {
        (void)snprintf(ids[i],32,"doc-%zu",i); links[i]=i?i-1:0;
        large[i]=(golem_dependency_node){"work",ids[i],1,digest,i?&links[i]:NULL,i?1:0};
    }
    CHECK(golem_document_graph_evaluate(large,n,NULL,states,n,NULL)==GOLEM_OK);
    CHECK(states[n-1]==GOLEM_DOCUMENT_CURRENT);
    large[n-1].document_id=ids[0]; large[n-1].revision=2; large[n-1].parent_count=0;
    CHECK(golem_document_graph_evaluate(large,n,NULL,states,n,NULL)==GOLEM_OK);
    CHECK(states[n-2]==GOLEM_DOCUMENT_STALE && states[0]==GOLEM_DOCUMENT_SUPERSEDED);
    size_t dense[GOLEM_DOCUMENT_MAX_PARENTS];
    for(size_t i=0;i<GOLEM_DOCUMENT_MAX_PARENTS;++i) dense[i]=i;
    for(size_t i=0;i<n;++i) {
        large[i].document_id=ids[i]; large[i].revision=1;
        large[i].parents=dense;
        large[i].parent_count=i>=64 && i<320?64:0;
    }
    CHECK(golem_document_graph_evaluate(large,n,NULL,states,n,NULL)==GOLEM_OK);
    large[320].parent_count=1;
    CHECK(golem_document_graph_evaluate(large,n,NULL,states,n,NULL)==GOLEM_ERR_BUDGET_EXHAUSTED);
    CHECK(states[320]==GOLEM_DOCUMENT_CURRENT);
    free(large); free(links); free(ids); free(states);
    return 0;
}
