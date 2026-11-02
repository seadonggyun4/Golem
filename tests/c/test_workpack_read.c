#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "golem/workpack.h"
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1); } } while(0)
static const char *target;
static int change;
static ssize_t controlled_read(int fd, void *buffer, size_t size)
{
    ssize_t n=read(fd,buffer,size);
    if(n>0 && change) {
        int mode=change;change=0;
        if(mode==2) CHECK(unlink(target)==0);
        int out=open(target,O_WRONLY|O_CREAT|O_TRUNC,0600);CHECK(out>=0);
        CHECK(write(out,"xyz",3)==3);CHECK(close(out)==0);
    }
    return n;
}
#define read controlled_read
#include "../../src/workpack/read.c"
#undef read
int main(void)
{
    char dir[]="/tmp/golem-pack-read-XXXXXX";CHECK(mkdtemp(dir));
    char resolved[4096];CHECK(realpath(dir,resolved));char path[4200];CHECK(snprintf(path,sizeof(path),"%s/input",resolved)>0);target=path;
    uint8_t bytes[GOLEM_WORKPACK_MAX_JSON];size_t n=99;golem_diagnostic d;
    for(int mode=0;mode<3;mode++) {
        int fd=open(path,O_WRONLY|O_CREAT|O_TRUNC,0600);CHECK(fd>=0);CHECK(write(fd,"abc",3)==3);CHECK(close(fd)==0);
        memset(bytes,0xa5,sizeof(bytes));n=99;change=mode;
        golem_status s=golem_workpack_read(path,bytes,sizeof(bytes),&n,&d);
        if(!mode) {CHECK(s==GOLEM_OK && n==3 && !memcmp(bytes,"abc",3));}
        else {CHECK(s==GOLEM_ERR_STALE_RESULT);CHECK(n==99);for(size_t i=0;i<sizeof(bytes);i++)CHECK(bytes[i]==0xa5);}
    }
    CHECK(golem_workpack_read(path,bytes,1,&n,&d)==GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(golem_workpack_read(NULL,bytes,sizeof(bytes),&n,&d)==GOLEM_ERR_INVALID_ARGUMENT);
    const char *catalog="{\"schema\":\"golem.workpack.catalog.v0\",\"entries\":[]}";
    int fd=open(path,O_WRONLY|O_TRUNC);CHECK(fd>=0);CHECK(write(fd,catalog,strlen(catalog))==(ssize_t)strlen(catalog));CHECK(close(fd)==0);
    size_t required=777;char output[1024];memset(output,'!',sizeof(output));
    CHECK(golem_workpack_catalog(path,(golem_string_view){NULL,0},NULL,0,&required,&d)==GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(required>1 && required<sizeof(output));
    CHECK(golem_workpack_catalog(path,(golem_string_view){NULL,0},output,sizeof(output),&required,&d)==GOLEM_OK);
    CHECK(strstr(output,"LISTED"));
    required=777;memset(output,'!',sizeof(output));
    CHECK(golem_workpack_catalog(path,(golem_string_view){"\xff",1},output,sizeof(output),&required,&d)!=GOLEM_OK);
    CHECK(required==777 && output[0]=='!');
    change=1;
    CHECK(golem_workpack_catalog(path,(golem_string_view){NULL,0},output,sizeof(output),&required,&d)==GOLEM_ERR_STALE_RESULT);
    CHECK(required==777 && output[0]=='!');
    CHECK(unlink(path)==0);CHECK(rmdir(dir)==0);return 0;
}
