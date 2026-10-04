#ifndef GOLEM_RECORD_INTERNAL_H
#define GOLEM_RECORD_INTERNAL_H
#include "golem/record.h"
#include <errno.h>

golem_status gr_api_begin(const char *operation, golem_record **record, golem_diagnostic *d);
golem_status gr_api_finish(const char *name, golem_record *record, golem_status operation, golem_diagnostic *d);
golem_status gr_api_rejected(const char *operation);
golem_status gr_api_finish_required(const char *name, golem_record *record,
    golem_status started, golem_status operation);
/* Owned immutable snapshot for a Golem-created worker. Never share active scopes.
 * Capture on the coordinator, attach on a fresh worker, detach before dispose. */
typedef struct gr_context {
    char *root, *source;
    char parent[33];
} gr_context;
golem_status gr_context_capture(gr_context *out);
void gr_context_dispose(gr_context *context);
golem_status gr_context_attach(const gr_context *context);
golem_status gr_context_detach(const gr_context *context);

/* One declaration owns the public signature and private implementation. Every
 * body return passes through finalization, including rejected requests. Keep
 * recorder/CAS primitives outside this boundary to avoid self-instrumentation.
 * Inputs are borrowed and are NOT serialized. No GNU cleanup extensions. */
#define GOLEM_RECORDED_API(name, parameters, arguments, diagnostic) \
    static golem_status name##_recorded_body parameters; \
    golem_status name parameters \
    { \
        int gr_errno = errno; \
        golem_record *gr_scope = NULL; \
        golem_status gr_status = gr_api_begin(#name, &gr_scope, diagnostic); \
        errno = gr_errno; \
        if (gr_status != GOLEM_OK) return gr_status; \
        gr_status = name##_recorded_body arguments; \
        gr_errno = errno; \
        gr_status = gr_api_finish(#name, gr_scope, gr_status, diagnostic); \
        errno = gr_errno; \
        return gr_status; \
    } \
    static golem_status name##_recorded_body parameters

/* Cancellation, lease maintenance and release must not depend on audit storage.
 * Still expose recording failure separately, even if intent could not persist. */
#define GOLEM_RECORDED_REQUIRED_API(name, parameters, arguments) \
    static golem_status name##_recorded_body parameters; \
    golem_status name parameters \
    { \
        int gr_errno = errno; \
        golem_record *gr_scope = NULL; \
        golem_status gr_started = gr_api_begin(#name, &gr_scope, NULL); \
        errno = gr_errno; \
        golem_status gr_status = name##_recorded_body arguments; \
        gr_errno = errno; \
        gr_status = gr_api_finish_required(#name, gr_scope, gr_started, gr_status); \
        errno = gr_errno; \
        return gr_status; \
    } \
    static golem_status name##_recorded_body parameters
/* A void destructor has no status channel. Always release; expose audit failure
 * through the same thread-local outcome accessor as required operations. */
#define GOLEM_RECORDED_RELEASE_API(name, parameters, arguments) \
    static void name##_recorded_body parameters; \
    void name parameters \
    { \
        int gr_errno = errno; \
        golem_record *gr_scope = NULL; \
        golem_status gr_started = gr_api_begin(#name, &gr_scope, NULL); \
        errno = gr_errno; \
        name##_recorded_body arguments; \
        gr_errno = errno; \
        (void)gr_api_finish_required(#name, gr_scope, gr_started, GOLEM_OK); \
        errno = gr_errno; \
    } \
    static void name##_recorded_body parameters
#endif
