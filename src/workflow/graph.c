#include "golem/workflow.h"
#include "../document/internal.h"
#include <stdlib.h>
#include <string.h>
typedef struct order { const char *id; uint32_t revision; size_t index; } order;
static int compare(const void *a,const void *b)
{
    const order *x=a,*y=b; int c=strcmp(x->id,y->id);
    if(c) return c;
    return x->revision<y->revision?-1:x->revision>y->revision?1:0;
}
golem_status golem_document_graph_evaluate(const golem_dependency_node *nodes,size_t n,
    const golem_allocator *allocator,golem_document_freshness *states,size_t capacity,golem_diagnostic *d)
{
    if(!nodes || !n || !states || n>GOLEM_DOCUMENT_MAX_REVISIONS || capacity<n ||
       golem_allocator_validate(allocator)!=GOLEM_OK) return dw_report(d,GOLEM_ERR_INVALID_ARGUMENT,NULL);
    size_t edges=0;
    for(size_t i=0;i<n;++i) {
        const golem_dependency_node *v=&nodes[i];
        bool has_digest=false;
        for(size_t j=0;j<GOLEM_DIGEST_SIZE;++j) has_digest|=v->manifest_digest.bytes[j]!=0;
        if(!dw_id(v->work_id) || !dw_id(v->document_id) || !v->revision || v->revision>GOLEM_DOCUMENT_MAX_REVISIONS ||
            !has_digest || v->parent_count>GOLEM_DOCUMENT_MAX_PARENTS || (v->parent_count && !v->parents)) return dw_report(d,GOLEM_ERR_INVALID_GRAPH,NULL);
        if(strcmp(v->work_id,nodes[0].work_id)!=0) return dw_report(d,GOLEM_ERR_IDENTITY_MISMATCH,NULL);
        if(v->parent_count>GOLEM_DOCUMENT_MAX_EDGES-edges) return dw_report(d,GOLEM_ERR_BUDGET_EXHAUSTED,NULL);
        edges+=v->parent_count;
        for(size_t j=0;j<v->parent_count;++j) {
            if(v->parents[j]>=n || v->parents[j]==i) return dw_report(d,GOLEM_ERR_INVALID_GRAPH,NULL);
            for(size_t k=0;k<j;++k) if(v->parents[k]==v->parents[j]) return dw_report(d,GOLEM_ERR_INVALID_GRAPH,NULL);
        }
    }
    /* One allocation: sorted identity index, adjacency and Kahn work queue. */
    size_t bytes=n*sizeof(order)+(3*n+2*edges)*sizeof(size_t)+n*sizeof(golem_document_freshness);
    void *memory=NULL; golem_status st=golem_allocator_alloc(allocator,bytes,&memory);
    if(st!=GOLEM_OK) return dw_report(d,st,NULL);
    order *sorted=memory;
    size_t *degree=(size_t *)(sorted+n),*head=degree+n,*queue=head+n,*next=queue+n,*child=next+edges;
    golem_document_freshness *result=(golem_document_freshness *)(child+edges);
    for(size_t i=0;i<n;++i) {
        sorted[i]=(order){nodes[i].document_id,nodes[i].revision,i};
        degree[i]=nodes[i].parent_count; head[i]=SIZE_MAX; result[i]=GOLEM_DOCUMENT_CURRENT;
    }
    qsort(sorted,n,sizeof(*sorted),compare);
    for(size_t i=1;i<n;++i) if(strcmp(sorted[i-1].id,sorted[i].id)==0) {
        if(sorted[i-1].revision==sorted[i].revision) { st=GOLEM_ERR_INVALID_GRAPH; break; }
        result[sorted[i-1].index]=GOLEM_DOCUMENT_SUPERSEDED;
    }
    size_t edge=0,read=0,write=0;
    for(size_t i=0;st==GOLEM_OK && i<n;++i) {
        if(!degree[i]) queue[write++]=i;
        for(size_t j=0;j<nodes[i].parent_count;++j) {
            size_t p=nodes[i].parents[j]; child[edge]=i; next[edge]=head[p]; head[p]=edge++;
        }
    }
    while(st==GOLEM_OK && read<write) {
        size_t i=queue[read++];
        for(size_t e=head[i];e!=SIZE_MAX;e=next[e]) {
            size_t c=child[e];
            if(result[i]!=GOLEM_DOCUMENT_CURRENT && result[c]!=GOLEM_DOCUMENT_SUPERSEDED) result[c]=GOLEM_DOCUMENT_STALE;
            if(--degree[c]==0) queue[write++]=c;
        }
    }
    if(st==GOLEM_OK && read!=n) st=GOLEM_ERR_INVALID_GRAPH;
    if(st==GOLEM_OK) memcpy(states,result,n*sizeof(*states));
    (void)golem_allocator_free(allocator,memory);
    return dw_report(d,st,st==GOLEM_OK?"dependency freshness only; semantic acceptance not verified":NULL);
}
