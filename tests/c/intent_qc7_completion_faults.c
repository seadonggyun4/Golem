/* Test-only substitution of storage boundaries; native completion remains intact. */
#define _POSIX_C_SOURCE 200809L
#include "../../src/document/internal.h"
#include <string.h>
#include <unistd.h>
static const char *selected_fault="";
void qc7_completion_fault(const char *name){selected_fault=name;}
static void stop_at(const char *name){if(!strcmp(selected_fault,name))_exit(77);}
static golem_status prepare_fault(golem_document_store *s,struct json_object *e,size_t limit,golem_digest *p)
{
    stop_at("before-completion-payload");
    if(!strcmp(selected_fault,"completion-payload-io"))return GOLEM_ERR_IO;
    golem_status st=dw_record_prepare(s,e,limit,p);
    if(st==GOLEM_OK)stop_at("after-completion-payload");
    return st;
}
static golem_status publish_fault(golem_document_store *s,const golem_digest *p,golem_digest *f,
                                  golem_status (*guard)(void *),void *context)
{
    stop_at("before-completion-event");
    if(!strcmp(selected_fault,"completion-event-io"))return GOLEM_ERR_IO;
    golem_status st=dw_event_write_guarded(s,p,f,guard,context);
    if(st==GOLEM_OK)stop_at("after-completion-event");
    return st;
}
#define dw_record_prepare prepare_fault
#define dw_event_write_guarded publish_fault
#include "../../src/completion/store.c"
#undef dw_record_prepare
#undef dw_event_write_guarded
