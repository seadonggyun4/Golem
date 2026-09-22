#include "golem/discovery.h"
#include "test.h"
#include <string.h>
int main(void)
{
    FILE *f=fopen(GOLEM_DISCOVERY_SAMPLE,"rb"); CHECK(f!=NULL);
    uint8_t sample[8192]; size_t n=fread(sample,1,sizeof(sample),f);
    CHECK(!ferror(f) && feof(f) && fclose(f)==0);
    golem_bytes b={sample,n}; golem_discovery_result r;
    CHECK(golem_discovery_validate(b,&r,NULL)==GOLEM_OK);
    CHECK(r.findings==1 && r.selected==0 && !r.scope_ready);
    golem_discovery_result saved=r;
    CHECK(golem_discovery_validate((golem_bytes){NULL,0},&r,NULL)!=GOLEM_OK);
    CHECK(memcmp(&r,&saved,sizeof(r))==0);
    CHECK(golem_discovery_validate(b,NULL,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    size_t required=0;
    CHECK(golem_discovery_report(b,"discovery",NULL,0,&required,NULL)==GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(required>100);
    char sentinel[4]="xyz";
    CHECK(golem_discovery_report(b,"discovery",sentinel,sizeof(sentinel),&required,NULL)==GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(strcmp(sentinel,"xyz")==0);
    uint8_t *buffer=malloc(required); CHECK(buffer!=NULL);
    CHECK(golem_discovery_report(b,"discovery",buffer,required,&required,NULL)==GOLEM_OK);
    CHECK(memcmp(buffer,"# Project discovery",19)==0);
    free(buffer);
    size_t original=required;
    CHECK(golem_discovery_report(b,"other",NULL,0,&required,NULL)==GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(required==original);
    uint8_t *output=(uint8_t *)(uintptr_t)1; size_t size=123;
    CHECK(golem_discovery_snapshot((golem_bytes){NULL,0},NULL,&output,&size,NULL)!=GOLEM_OK);
    CHECK(output==(uint8_t *)(uintptr_t)1 && size==123);
    return 0;
}
