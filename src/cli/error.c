#include "error.h"
#include "golem/system_error.h"
#include <errno.h>
#include <json-c/json.h>
#include <stdio.h>
#include <string.h>

typedef struct error_rule { golem_status status; const char *code, *category, *action; } error_rule;
#define INPUT "Inspect command syntax, request schema and declared limits before a new invocation."
#define EVIDENCE "Preserve original evidence; inspect identity, integrity and current state before recovery."
#define STATE "Inspect current Work state and prerequisites; reconcile prior effects before another mutation."
#define AUTH "Obtain the required scoped decision from the trusted host; do not self-approve or bypass policy."
#define RESOURCE "Inspect capacity, owners and limits; do not evict records or repeat effects automatically."
#define RULE(name, category, action) {name, #name, category, action}
static const error_rule rules[] = {
    RULE(GOLEM_ERR_INVALID_ARGUMENT, "input", INPUT),
    RULE(GOLEM_ERR_OUT_OF_MEMORY, "resource", RESOURCE),
    RULE(GOLEM_ERR_PARSE, "input", INPUT),
    RULE(GOLEM_ERR_POLICY_DENIED, "authorization", AUTH),
    RULE(GOLEM_ERR_IO, "io", "Inspect original diagnostics, storage and environment; effects may already exist."),
    RULE(GOLEM_ERR_CORRUPT_JOURNAL, "integrity", EVIDENCE),
    RULE(GOLEM_ERR_INVALID_STATE, "state", STATE),
    RULE(GOLEM_ERR_INVALID_GRAPH, "input", INPUT),
    RULE(GOLEM_ERR_NO_REENTRY, "state", STATE),
    RULE(GOLEM_ERR_ATTEMPT_LIMIT, "resource", RESOURCE),
    RULE(GOLEM_ERR_STALE_RESULT, "state", STATE),
    RULE(GOLEM_ERR_REQUIREMENTS_UNMET, "state", STATE),
    RULE(GOLEM_ERR_BUFFER_TOO_SMALL, "input", INPUT),
    RULE(GOLEM_ERR_OVERFLOW, "input", INPUT),
    RULE(GOLEM_ERR_UNSUPPORTED_VERSION, "input", INPUT),
    RULE(GOLEM_ERR_TRUNCATED_JOURNAL, "integrity", EVIDENCE),
    RULE(GOLEM_ERR_JOURNAL_BUSY, "resource", RESOURCE),
    RULE(GOLEM_ERR_MISSING_RECORD, "integrity", EVIDENCE),
    RULE(GOLEM_ERR_REPLAY_MISMATCH, "integrity", EVIDENCE),
    RULE(GOLEM_ERR_INCOMPLETE_WORK, "state", STATE),
    RULE(GOLEM_ERR_NOT_FOUND, "input", "Check the requested resource exists in the intended store; do not recreate state blindly."),
    RULE(GOLEM_ERR_DIGEST_MISMATCH, "integrity", EVIDENCE),
    RULE(GOLEM_ERR_SIZE_MISMATCH, "integrity", EVIDENCE),
    RULE(GOLEM_ERR_CRYPTO, "integrity", EVIDENCE),
    RULE(GOLEM_ERR_IDENTITY_MISMATCH, "integrity", EVIDENCE),
    RULE(GOLEM_ERR_APPROVAL_REQUIRED, "authorization", AUTH),
    RULE(GOLEM_ERR_BUDGET_EXHAUSTED, "resource", RESOURCE),
    RULE(GOLEM_ERR_COST_INCOMPLETE, "state", STATE),
    RULE(GOLEM_ERR_COST_CAPACITY, "resource", RESOURCE),
    RULE(GOLEM_ERR_OPTIMIZATION_REJECTED, "state", STATE),
    RULE(GOLEM_ERR_STALE_LEASE, "state", STATE),
    RULE(GOLEM_ERR_LEASE_BUSY, "resource", RESOURCE),
    RULE(GOLEM_ERR_QUEUE_FULL, "resource", RESOURCE),
};
static struct {
    golem_status status;
    const char *command, *phase;
    int os_error;
    bool has_diagnostic;
    golem_diagnostic diagnostic;
} context;
static golem_system_error_scope system_errors;
static bool collecting;

void cli_error_begin(void)
{
    if (collecting) (void)golem_system_error_end(&system_errors);
    collecting = golem_system_error_begin(&system_errors) == GOLEM_OK;
    memset(&context, 0, sizeof(context));
    context.command = "cli";
    context.phase = "command";
}
void cli_error_command(const char *command)
{
    /* Never reflect arbitrary argv, paths, requests or environment into labels. */
    static const char *const known[] = {"output", "doctor", "approval", "agent", "work", "role",
        "journal", "workflow", "context", "events", "session", "profile", "execution", "proof",
        "candidate", "reentry", "research", "completion", "discovery", "document", "init",
        "capsule", "run", "replay", "cost", "adapter", "daemon", "lineage", "evidence"};
    context.command = "unknown";
    for (size_t i = 0; i < sizeof(known) / sizeof(known[0]); ++i)
        if (command && !strcmp(command, known[i])) { context.command = known[i]; break; }
}
void cli_error_note(golem_status status, const char *phase, const golem_diagnostic *diagnostic)
{
    if (status == GOLEM_OK) return;
    /* A terminal status-only emitter must not erase the same failure's earlier
     * syscall context. A changed status cannot inherit unrelated errno. */
    if (context.status != status) {
        context.phase = "command";
        context.os_error = 0;
        context.has_diagnostic = false;
    }
    context.status = status;
    if (phase && (!context.phase || !strcmp(context.phase, "command"))) context.phase = phase;
    if (diagnostic && diagnostic->status == status) {
        context.diagnostic = *diagnostic;
        context.diagnostic.message[GOLEM_DIAGNOSTIC_MESSAGE_CAPACITY - 1] = '\0';
        context.has_diagnostic = true;
    }
}
void cli_error_errno(golem_status status, const char *phase, int saved_errno)
{
    (void)golem_system_error_note(status, "cli", phase, saved_errno);
    cli_error_note(status, phase, NULL);
    context.phase = phase;
    context.os_error = saved_errno;
}
#define ADD(key, value) do { struct json_object *v = (value); \
    if (!v) ok = false; \
    else if (!o || json_object_object_add(o, key, v)) { json_object_put(v); ok = false; } } while (0)

static struct json_object *system_error_json(const golem_system_error *e)
{
    struct json_object *o = json_object_new_object();
    bool ok = o != NULL;
    ADD("component", json_object_new_string(e->component));
    ADD("operation", json_object_new_string(e->operation));
    ADD("status_code", json_object_new_int(e->status));
    ADD("kind", json_object_new_string(e->error_number ? "system" : "validation"));
    if (e->error_number) { ADD("errno", json_object_new_int(e->error_number)); }
    else if (o && json_object_object_add(o, "errno", NULL)) ok = false;
    ADD("errno_name", json_object_new_string(golem_system_error_name(e->error_number)));
    ADD("next_action", json_object_new_string(golem_system_error_action(e->error_number)));
    ADD("truncated", json_object_new_boolean(e->truncated));
    if (!ok) { json_object_put(o); return NULL; }
    return o;
}
int cli_error_finish(int exit_code)
{
    if (!exit_code) {
        int flushed = fflush(stdout);
        int saved = flushed ? errno : 0;
        if (flushed || ferror(stdout)) {
            cli_error_errno(GOLEM_ERR_IO, "stdout_flush", saved);
            exit_code = 1;
        }
    }
    if (exit_code == 1 && context.status == GOLEM_OK && ferror(stdout))
        cli_error_note(GOLEM_ERR_IO, "stdout_write", NULL);
    if (collecting) {
        (void)golem_system_error_end(&system_errors);
        collecting = false;
    }
    if (!exit_code) return 0;
    const error_rule *rule = NULL;
    for (size_t i = 0; i < sizeof(rules) / sizeof(rules[0]); ++i)
        if (rules[i].status == context.status) { rule = &rules[i]; break; }
    const char *code = rule ? rule->code : exit_code == 2 ? "CLI_USAGE" : "CLI_FAILED";
    struct json_object *o = json_object_new_object();
    bool ok = o != NULL;
    ADD("schema", json_object_new_string("golem.cli-error.v1"));
    ADD("code", json_object_new_string(code));
    ADD("category", json_object_new_string(rule ? rule->category : exit_code == 2 ? "usage" : "unknown"));
    ADD("exit_code", json_object_new_int(exit_code));
    if (context.status != GOLEM_OK) { ADD("status_code", json_object_new_int((int)context.status)); }
    else if (o && json_object_object_add(o, "status_code", NULL)) ok = false;
    ADD("command", json_object_new_string(context.command ? context.command : "cli"));
    ADD("phase", json_object_new_string(context.phase ? context.phase : "command"));
    ADD("message", json_object_new_string(context.status != GOLEM_OK ? golem_status_string(context.status) :
                                         exit_code == 2 ? "invalid command usage" : "command failed without a native status"));
    if (context.os_error) { ADD("errno", json_object_new_int(context.os_error)); }
    else if (o && json_object_object_add(o, "errno", NULL)) ok = false;
    if (context.has_diagnostic) {
        ADD("diagnostic", json_object_new_string(context.diagnostic.message));
        ADD("diagnostic_truncated", json_object_new_boolean(context.diagnostic.truncated));
        if (context.diagnostic.offset != GOLEM_DIAGNOSTIC_NO_OFFSET) {
            ADD("offset", json_object_new_uint64(context.diagnostic.offset));
        }
    }
    ADD("next_action", json_object_new_string(rule ? rule->action : exit_code == 2 ? INPUT : EVIDENCE));
    ADD("retry_effect", json_object_new_boolean(false));
    ADD("effects", json_object_new_string("NOT_INFERRED_FROM_EXIT_STATUS"));
    struct json_object *observations = json_object_new_array();
    if (!observations) ok = false;
    for (size_t i = 0; observations && i < system_errors.count; ++i) {
        struct json_object *entry = system_error_json(&system_errors.entries[i]);
        if (!entry) { ok = false; break; }
        if (json_object_array_add(observations, entry)) { json_object_put(entry); ok = false; break; }
    }
    ADD("system_errors", observations);
    ADD("system_errors_omitted", json_object_new_uint64(system_errors.omitted));
    ADD("system_errors_role", json_object_new_string("OBSERVATIONS_NOT_INFERRED_CAUSES"));
    ADD("execution_authorized", json_object_new_boolean(false));
    const char *text = ok ? json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN) : NULL;
    if (text) fprintf(stderr, "%s\n", text);
    else fprintf(stderr, "{\"schema\":\"golem.cli-error.v1\",\"code\":\"CLI_DIAGNOSTIC_UNAVAILABLE\","
                         "\"exit_code\":%d,\"retry_effect\":false,\"execution_authorized\":false}\n", exit_code);
    json_object_put(o);
    return exit_code;
}
#undef ADD
