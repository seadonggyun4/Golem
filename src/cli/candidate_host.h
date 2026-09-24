#ifndef GOLEM_CLI_CANDIDATE_HOST_H
#define GOLEM_CLI_CANDIDATE_HOST_H
#include "../candidate/internal.h"
#include "../agent_session/internal.h"
#define CH_WIRE_MAX (2u * GOLEM_DOCUMENT_MAX_JSON)
typedef struct ch_host {
    struct json_object *config, *request;
    golem_digest config_digest, authorized;
    golem_document_store *parent, *target;
    golem_admission *admission;
    golem_workspace_host workspace;
    golem_candidate_current_binding bindings[GOLEM_CANDIDATE_MAX];
    golem_candidate_member target_member;
    golem_candidate_current_options options;
    golem_candidate_host capabilities;
    bool approved, attested, stop;
} ch_host;
/* CLI-private: config borrowed for open; retained until close. Per-request child
 * handles are released before returning so independent agent CLIs can proceed. */
golem_status ch_validate(struct json_object *config);
golem_status ch_open(ch_host *host, struct json_object *config);
golem_status ch_close(ch_host *host);
golem_status ch_call(ch_host *host, struct json_object *envelope, struct json_object **out);
golem_status ch_serve(struct json_object *config, const char *socket_path);
golem_status ch_client(const char *socket_path, struct json_object *envelope,
                       struct json_object **out);
int golem_cli_candidate_host(int argc, char **argv);
#endif
