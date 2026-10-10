#include "work.h"
#include "golem/agent_session.h"
#include "golem/session_binding.h"
#include "context_tokenizer.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

int golem_cli_agent_session(int argc, char **argv)
{
    bool resume = (argc == 6 || argc == 7) && !strcmp(argv[2], "resume");
    if (!resume && (argc != 5 || strcmp(argv[2], "call") != 0)) {
        fputs("usage: golem session call WORK REQUEST.json\n"
              "       golem session resume WORK RESUME.json CONTEXT.json [TOKEN_COUNT.json]\n", stderr);
        return 2;
    }
    cli_blob input = {0};
    cli_blob context = {0};
    cli_context_count count = {0};
    struct json_object *request = NULL;
    golem_status st = cli_read(argv[4], GOLEM_DOCUMENT_MAX_JSON, &input);
    if (st == GOLEM_OK && resume)
        st = cli_read(argv[5], GOLEM_CONTEXT_REQUEST_MAX, &context);
    if (st == GOLEM_OK && resume && argc == 7)
        st = cli_context_count_load(argv[6], &count);
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
    golem_diagnostic diagnostic;
    (void)golem_diagnostic_clear(&diagnostic);
    const char *phase = "request_read_parse";
    if (st == GOLEM_OK) {
        phase = "work_store_open_replay";
        st = golem_document_store_open(argv[3], !readonly, NULL, &store, &diagnostic);
    }
    if (st == GOLEM_OK) {
        phase = "session_call";
        st = resume ? golem_agent_session_resume_context(store, (golem_bytes){input.data, input.size},
                (golem_bytes){context.data, context.size}, argc == 7 ? &count.tokenizer : NULL,
                NULL, &reply, &diagnostic)
                    : golem_agent_session_call(store, (golem_bytes){input.data, input.size}, NULL, &reply,
                                               &diagnostic);
    }
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK) {
        if (cli_output_write((golem_bytes){reply.data, reply.size}) != GOLEM_OK || fputc('\n', stdout) == EOF)
            st = GOLEM_ERR_IO;
    }
    golem_agent_reply_free(&reply);
    json_object_put(request);
    free(input.data);
    free(context.data);
    cli_context_count_clear(&count);
    if (st != GOLEM_OK) {
        cli_error_note(st, phase, &diagnostic);
        struct json_object *error = json_object_new_object();
        if (error) {
            json_object_object_add(error, "schema", json_object_new_string("golem.session-error.v1"));
            json_object_object_add(error, "code", json_object_new_int((int)st));
            json_object_object_add(error, "phase", json_object_new_string(phase));
            json_object_object_add(error, "diagnostic", json_object_new_string(diagnostic.message));
            fprintf(stderr, "%s\n", json_object_to_json_string_ext(error, JSON_C_TO_STRING_PLAIN));
            json_object_put(error);
        }
    }
    return st == GOLEM_OK ? 0 : cli_emit(st, NULL);
}

int golem_cli_session_binding(int argc, char **argv)
{
    bool history = argc == 5 && !strcmp(argv[1], "work") && !strcmp(argv[2], "history");
    bool record = argc == 5 && !strcmp(argv[1], "work") && !strcmp(argv[2], "record");
    bool binding = argc == 6 && !strcmp(argv[1], "agent") && !strcmp(argv[2], "binding") &&
                   (!strcmp(argv[3], "attach") || !strcmp(argv[3], "inspect"));
    if (!history && !record && !binding) {
        fputs("usage: golem agent binding attach|inspect WORK REQUEST.json\n"
              "       golem work history|record WORK REQUEST.json\n",
              stderr);
        return 2;
    }
    cli_blob input = {0};
    struct json_object *r = NULL;
    golem_document_store *store = NULL;
    golem_agent_reply reply = {0};
    golem_diagnostic diagnostic;
    (void)golem_diagnostic_clear(&diagnostic);
    golem_status st = cli_read(argv[history || record ? 4 : 5], GOLEM_SESSION_BINDING_MAX_BYTES, &input);
    if (st == GOLEM_OK)
        st = cli_json_parse((golem_bytes){input.data, input.size}, &r);
    const char *op = r ? cli_json_text(json_object_object_get(r, "operation")) : "";
    if (st == GOLEM_OK && binding && strcmp(op, argv[3]))
        st = GOLEM_ERR_INVALID_ARGUMENT;
    if (st == GOLEM_OK)
        st = golem_document_store_open(argv[history || record ? 3 : 4], binding && !strcmp(argv[3], "attach"),
                                       NULL, &store, &diagnostic);
    if (st == GOLEM_OK)
        st = record ? golem_work_record(store, (golem_bytes){input.data, input.size}, NULL,
                                        &reply, &diagnostic)
             : history
                 ? golem_work_history(store, (golem_bytes){input.data, input.size}, &reply, NULL)
                 : golem_session_binding_call(store, (golem_bytes){input.data, input.size}, NULL,
                                              NULL, &reply, NULL);
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK && (cli_output_write((golem_bytes){reply.data, reply.size}) != GOLEM_OK ||
                           fputc('\n', stdout) == EOF || fflush(stdout)))
        st = GOLEM_ERR_IO;
    golem_agent_reply_free(&reply);
    free(input.data);
    json_object_put(r);
    cli_error_note(st, "work_or_binding", &diagnostic);
    if (record && st != GOLEM_OK) {
        struct json_object *error = json_object_new_object();
        if (error) {
            json_object_object_add(error, "schema", json_object_new_string("golem.work-record-error.v1"));
            json_object_object_add(error, "code", json_object_new_int((int)st));
            json_object_object_add(error, "diagnostic", json_object_new_string(diagnostic.message));
            json_object_object_add(error, "next_action", json_object_new_string(
                "Inspect original evidence and current heads; do not retry mutations or discard history."));
            fprintf(stderr, "%s\n", json_object_to_json_string_ext(error, JSON_C_TO_STRING_PLAIN));
            json_object_put(error);
        }
    }
    return st == GOLEM_OK ? 0 : cli_emit(st, NULL);
}
