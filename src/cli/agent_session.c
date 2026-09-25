#include "work.h"
#include "golem/agent_session.h"
#include "golem/session_binding.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

int golem_cli_agent_session(int argc, char **argv)
{
    if (argc != 5 || strcmp(argv[2], "call") != 0) {
        fputs("usage: golem session call WORK REQUEST.json\n", stderr);
        return 2;
    }
    cli_blob input = {0};
    struct json_object *request = NULL;
    golem_status st = cli_read(argv[4], GOLEM_DOCUMENT_MAX_JSON, &input);
    if (st == GOLEM_OK)
        st = cli_json_parse((golem_bytes){input.data, input.size}, &request);
    struct json_object *op = NULL;
    if (request)
        (void)json_object_object_get_ex(request, "operation", &op);
    const char *name = op ? json_object_get_string(op) : "";
    bool readonly = name && (strcmp(name, "status") == 0 || strcmp(name, "next") == 0 ||
                             strcmp(name, "context") == 0);
    golem_document_store *store = NULL;
    golem_agent_reply reply = {0};
    if (st == GOLEM_OK)
        st = golem_document_store_open(argv[3], !readonly, NULL, &store, NULL);
    if (st == GOLEM_OK)
        st = golem_agent_session_call(store, (golem_bytes){input.data, input.size}, NULL, &reply,
                                      NULL);
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK) {
        if (fwrite(reply.data, 1, reply.size, stdout) != reply.size || fputc('\n', stdout) == EOF)
            st = GOLEM_ERR_IO;
    }
    golem_agent_reply_free(&reply);
    json_object_put(request);
    free(input.data);
    return st == GOLEM_OK ? 0 : cli_emit(st, NULL);
}

int golem_cli_session_binding(int argc, char **argv)
{
    bool history = argc == 5 && !strcmp(argv[1], "work") && !strcmp(argv[2], "history");
    bool binding = argc == 6 && !strcmp(argv[1], "agent") && !strcmp(argv[2], "binding") &&
                   (!strcmp(argv[3], "attach") || !strcmp(argv[3], "inspect"));
    if (!history && !binding) {
        fputs("usage: golem agent binding attach|inspect WORK REQUEST.json\n"
              "       golem work history WORK REQUEST.json\n",
              stderr);
        return 2;
    }
    cli_blob input = {0};
    struct json_object *r = NULL;
    golem_document_store *store = NULL;
    golem_agent_reply reply = {0};
    golem_status st = cli_read(argv[history ? 4 : 5], GOLEM_SESSION_BINDING_MAX_BYTES, &input);
    if (st == GOLEM_OK)
        st = cli_json_parse((golem_bytes){input.data, input.size}, &r);
    const char *op = r ? cli_json_text(json_object_object_get(r, "operation")) : "";
    if (st == GOLEM_OK && binding && strcmp(op, argv[3]))
        st = GOLEM_ERR_INVALID_ARGUMENT;
    if (st == GOLEM_OK)
        st = golem_document_store_open(argv[history ? 3 : 4], binding && !strcmp(argv[3], "attach"),
                                       NULL, &store, NULL);
    if (st == GOLEM_OK)
        st = history
                 ? golem_work_history(store, (golem_bytes){input.data, input.size}, &reply, NULL)
                 : golem_session_binding_call(store, (golem_bytes){input.data, input.size}, NULL,
                                              NULL, &reply, NULL);
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK && (fwrite(reply.data, 1, reply.size, stdout) != reply.size ||
                           fputc('\n', stdout) == EOF || fflush(stdout)))
        st = GOLEM_ERR_IO;
    golem_agent_reply_free(&reply);
    free(input.data);
    json_object_put(r);
    return st == GOLEM_OK ? 0 : cli_emit(st, NULL);
}
