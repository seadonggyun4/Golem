#ifndef GOLEM_WORKFLOW_TEMPLATE_H
#define GOLEM_WORKFLOW_TEMPLATE_H
#include "golem/execution.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Pure bounded data codec; no expression evaluation, shell, I/O or authority.
 * Inputs borrowed; owned replies freed with golem_execution_reply_free. Output
 * unchanged on failure. JSON dependency allocations follow json-c ownership.
 * Custom v1 templates retain the six-stage chain and mandatory role floors. */
golem_status golem_workflow_template_validate(golem_bytes input, golem_digest *digest);
golem_status golem_workflow_template_builtin(const char *name, golem_execution_reply *out);
golem_status golem_workflow_template_expand(golem_bytes input, golem_bytes selection,
                                            golem_execution_reply *out);
/* Read-only proposal using the current validated scope. Does not register,
 * enroll roles, grant permissions, execute work or claim acceptance. Register
 * the returned selection using the ordinary immutable document revision API.
 * Store lifetime lock and serialization rules are the same as workflow.h. */
golem_status golem_workflow_template_instantiate(golem_document_store *store, const char *scope_id,
                                                 uint32_t revision, golem_bytes input,
                                                 golem_execution_reply *out);
#ifdef __cplusplus
}
#endif
#endif
