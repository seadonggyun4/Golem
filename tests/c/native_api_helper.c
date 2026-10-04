#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "../../src/common/record_internal.h"
#include "golem/agent_session.h"
#include "golem/admission.h"
#include "golem/approval.h"
#include "golem/candidate.h"
#include "golem/completion.h"
#include "golem/context.h"
#include "golem/proof.h"
#include "golem/reentry.h"
#include "golem/research.h"
#include "golem/role_contract.h"
#include "golem/runtime_profile.h"
#include "golem/session_binding.h"
#include "golem/supervisor.h"
#include "golem/workspace.h"
#include "golem/worker.h"
#include "golem/daemon.h"
#include "golem/resource.h"
#include "golem/inventory.h"
#include "golem/runtime_event.h"
#include "golem/runtime.h"
#include "golem/adapter_descriptor.h"
#include "test.h"
#include <dirent.h>
#include <fcntl.h>
#include <pthread.h>
#include <json-c/json.h>
#include <string.h>
#include <unistd.h>

static unsigned effects;
static void *published_output;
static golem_status sabotage(const char *root)
{
    DIR *dir = opendir(root);
    if (!dir) return GOLEM_ERR_IO;
    struct dirent *e;
    golem_status st = GOLEM_OK;
    while ((e = readdir(dir))) if (strlen(e->d_name) == 32) {
        int scope = openat(dirfd(dir), e->d_name, O_RDONLY | O_DIRECTORY);
        if (scope < 0) { st = GOLEM_ERR_IO; break; }
        int started = openat(scope, "started.json", O_RDONLY);
        struct json_object *intent = started < 0 ? NULL : json_object_from_fd(started);
        if (started >= 0) close(started);
        struct json_object *operation = NULL;
        bool selected = intent && json_object_object_get_ex(intent, "operation", &operation) &&
            !strcmp(json_object_get_string(operation), "fixture");
        json_object_put(intent);
        if (!selected) { close(scope); continue; }
        int fd = openat(scope, ".pending", O_CREAT | O_EXCL | O_WRONLY, 0600);
        close(scope);
        if (fd < 0) { st = GOLEM_ERR_IO; break; }
        close(fd);
    }
    closedir(dir);
    return st;
}
GOLEM_RECORDED_API(fixture, (const char *root, bool fail, golem_diagnostic *d), (root, fail, d), d)
{
    ++effects;
    published_output = malloc(1);
    if (!published_output) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = sabotage(root);
    if (st == GOLEM_OK && fail)
        (void)golem_diagnostic_set(d, GOLEM_ERR_POLICY_DENIED,
            GOLEM_DIAGNOSTIC_NO_OFFSET, "fixture.operation_failure");
    return st == GOLEM_OK && fail ? GOLEM_ERR_POLICY_DENIED : st;
}
static int rejected(void)
{
    golem_bytes bytes = {(const uint8_t *)"private-request-body", 20};
    golem_execution_reply reply = {(uint8_t *)"sentinel", 8};
    golem_agent_reply agent = {0};
    golem_digest key = {{0}};
    golem_diagnostic d;
#define REJECT(call) CHECK((call) == GOLEM_ERR_INVALID_ARGUMENT)
    REJECT(golem_document_store_create(NULL, bytes, NULL, NULL, &d));
    REJECT(golem_document_submit(NULL, bytes, bytes, "private-key", NULL, &d));
    REJECT(golem_agent_session_call(NULL, bytes, NULL, &agent, &d));
    REJECT(golem_session_binding_call(NULL, bytes, NULL, NULL, &agent, &d));
    REJECT(golem_approval_call(NULL, bytes, NULL, NULL, &reply, &d));
    REJECT(golem_execution_call_receipted(NULL, bytes, &key, NULL, NULL, &reply, &d));
    REJECT(golem_execution_call(NULL, bytes, &key, &reply, &d));
    REJECT(golem_execution_call_authorized(NULL, bytes, NULL, &reply, &d));
    REJECT(golem_role_call(NULL, bytes, &key, &reply, &d));
    REJECT(golem_research_call(NULL, bytes, &reply, &d));
    REJECT(golem_completion_call(NULL, bytes, &reply, &d));
    REJECT(golem_reentry_call(NULL, bytes, &reply, &d));
    REJECT(golem_workspace_call(NULL, NULL, 0, NULL, NULL, NULL, NULL, &d));
    REJECT(golem_candidate_call(NULL, NULL, NULL, bytes, &reply, &d));
    REJECT(golem_runtime_profile_register(NULL, NULL, NULL, &key, &d));
    REJECT(golem_runtime_link_run(NULL, NULL, bytes, NULL, NULL, &key, &d));
    REJECT(golem_context_publish(NULL, bytes, NULL, NULL, &d));
    REJECT(golem_proof_publish(bytes, NULL, &key, &d));
    REJECT(golem_admission_publish_work(NULL, NULL, NULL, &key));
    CHECK(reply.size == 8 && !strcmp((char *)reply.data, "sentinel"));
    return 0;
}
static int extended(void)
{
    golem_admission_token token = {0};
    REJECT(golem_admission_open(NULL, NULL, NULL));
    REJECT(golem_admission_open_diagnostic(NULL, NULL, NULL, NULL));
    REJECT(golem_admission_identity(NULL, NULL, NULL));
    REJECT(golem_admission_enqueue(NULL, NULL, NULL));
    REJECT(golem_admission_lookup(NULL, NULL, NULL));
    REJECT(golem_admission_grant(NULL, NULL));
    REJECT(golem_admission_resize(NULL, (golem_admission_limits){0}));
    REJECT(golem_admission_begin(NULL, token, NULL, NULL, NULL));
    REJECT(golem_admission_dispatch(NULL, token, NULL, NULL));
    REJECT(golem_admission_cancel(NULL, token));
    REJECT(golem_admission_settle(NULL, token, (golem_digest){0}));
    REJECT(golem_admission_release(NULL, token));
    CHECK(golem_admission_close(NULL) == GOLEM_OK);
    REJECT(golem_worker_open(NULL, NULL));
    REJECT(golem_worker_submit(NULL, NULL, NULL));
    REJECT(golem_worker_start(NULL, 0, NULL, NULL, NULL, NULL));
    REJECT(golem_worker_events(NULL, NULL, NULL, 0, NULL));
    REJECT(golem_worker_inspect(NULL, 0, NULL));
    REJECT(golem_worker_cancel(NULL, 0));
    REJECT(golem_worker_heartbeat(NULL, 0, 0));
    REJECT(golem_worker_acknowledge(NULL, 0, NULL, NULL));
    CHECK(golem_worker_close(NULL) == GOLEM_OK);
    REJECT(golem_daemon_open(NULL, NULL, NULL, NULL));
    REJECT(golem_daemon_tick(NULL, NULL));
    CHECK(golem_daemon_init(NULL) != GOLEM_OK);
    REJECT(golem_daemon_inspect(NULL, NULL, 0, NULL));
    REJECT(golem_daemon_submit(NULL, NULL, NULL, NULL, NULL));
    REJECT(golem_daemon_recover(NULL, NULL));
    CHECK(golem_daemon_close(NULL) == GOLEM_OK);
    REJECT(golem_inventory_capture(NULL, (golem_bytes){0}, NULL, NULL));
    REJECT(golem_harness_probe(NULL, NULL));
    REJECT(golem_resource_run(-1, NULL, NULL, NULL, NULL, NULL, NULL,
        (golem_bytes){0}, 0, NULL, NULL, NULL, NULL));
    return 0;
}

static int lifecycle(void)
{
    REJECT(golem_runtime_create(NULL, NULL, NULL, NULL, NULL, NULL, NULL));
    REJECT(golem_runtime_recover(NULL, NULL, NULL, NULL, NULL, NULL));
    REJECT(golem_runtime_step(NULL));
    REJECT(golem_runtime_drive(NULL));
    REJECT(golem_runtime_cancel(NULL));
    REJECT(golem_runtime_report_get(NULL, NULL));
    REJECT(golem_runtime_lease_bind(NULL, NULL, NULL));
    REJECT(golem_runtime_checkpoint(NULL));
    REJECT(golem_runtime_heartbeat(NULL, 0, NULL));
    golem_runtime_free(NULL);
    REJECT(golem_journal_open(NULL, NULL, NULL, NULL));
    REJECT(golem_journal_append(NULL, GOLEM_JOURNAL_CREATED, (golem_bytes){0}, NULL, NULL));
    REJECT(golem_journal_checkpoint_get(NULL, NULL));
    REJECT(golem_journal_recover(NULL, NULL, NULL, NULL, NULL));
    CHECK(golem_journal_close(NULL, NULL) == GOLEM_OK);
    REJECT(golem_document_store_open(NULL, false, NULL, NULL, NULL));
    CHECK(golem_document_store_close(NULL) == GOLEM_OK);
    return 0;
}

static int required(void)
{
    /* Allocate with recording disabled, then make audit storage unavailable.
     * Closing must still free the actual pool, not merely accept NULL. */
    const char *configured = getenv("GOLEM_RECORD_ROOT");
    char *root = configured ? strdup(configured) : NULL;
    CHECK(root && unsetenv("GOLEM_RECORD_ROOT") == 0);
    golem_worker_options options = golem_worker_options_default();
    golem_worker_pool *pool = NULL;
    CHECK(golem_worker_open(&options, &pool) == GOLEM_OK);
    char *args[] = {"/not-executed", NULL}, *env[] = {NULL};
    golem_worker_request request = {.executable = args[0], .cwd = "/", .argv = args,
        .envp = env, .cpu_units = 1, .memory_bytes = 1, .io_slots = 1,
        .timeout_ns = 1000000000, .lease_ns = 1000000000, .resource_class = GOLEM_WORKER_QA};
    uint64_t id;
    CHECK(golem_worker_submit(pool, &request, &id) == GOLEM_OK);
    CHECK(setenv("GOLEM_RECORD_ROOT", root, 1) == 0);
    free(root);
    CHECK(golem_worker_cancel(pool, id) == GOLEM_OK);
    golem_worker_snapshot snapshot;
    CHECK(golem_worker_inspect(pool, id, &snapshot) == GOLEM_OK);
    CHECK(snapshot.state == GOLEM_WORKER_FINISHED && !snapshot.observation.spawned);
    CHECK(golem_worker_acknowledge(pool, id, NULL, NULL) == GOLEM_OK);
    errno = EDOM;
    CHECK(golem_worker_close(pool) == GOLEM_OK);
    CHECK(errno == EDOM);
    golem_record_api_outcome outcome = {.struct_size = sizeof(outcome), .version = 1};
    CHECK(golem_record_last_api_outcome(&outcome));
    CHECK(outcome.dispatched && outcome.operation_status == GOLEM_OK);
    CHECK(outcome.recording_status != GOLEM_OK);
    CHECK(!strcmp(outcome.operation, "golem_worker_close"));
    REJECT(golem_worker_cancel(NULL, 0));
    CHECK(golem_record_last_api_outcome(&outcome) && outcome.dispatched);
    CHECK(outcome.operation_status == GOLEM_ERR_INVALID_ARGUMENT && outcome.recording_status != GOLEM_OK);
    return 0;
}
static void *thread_rejected(void *unused)
{
    (void)unused;
    static int result;
    result = rejected();
    golem_record_api_outcome outcome = {.struct_size = sizeof(outcome), .version = 1};
    if (!golem_record_last_api_outcome(&outcome) || !outcome.dispatched ||
        outcome.operation_status != GOLEM_ERR_INVALID_ARGUMENT ||
        outcome.recording_status != GOLEM_OK) result = 1;
    return &result;
}
static void *thread_inherited(void *context)
{
    static int result;
    gr_context *inherited = context;
    result = gr_context_attach(inherited) != GOLEM_OK;
    if (!result) result = gr_context_attach(inherited) != GOLEM_ERR_INVALID_STATE;
    if (!result) result = rejected();
    if (gr_context_detach(inherited) != GOLEM_OK) result = 1;
    if (gr_context_detach(inherited) != GOLEM_ERR_INVALID_STATE) result = 1;
    return &result;
}
GOLEM_RECORDED_API(outer_fixture, (const char *root, golem_diagnostic *d), (root, d), d)
{
    return fixture(root, false, d);
}
int main(int argc, char **argv)
{
    CHECK(argc == 3);
    golem_record_api_outcome outcome = {.struct_size = sizeof(outcome), .version = 1};
    CHECK(!golem_record_last_api_outcome(&outcome));
    CHECK(!golem_record_last_api_outcome(NULL));
    if (!strcmp(argv[1], "extended")) return extended();
    if (!strcmp(argv[1], "lifecycle")) return lifecycle();
    if (!strcmp(argv[1], "required")) return required();
    if (!strcmp(argv[1], "handoff")) {
        golem_record_options options = {.struct_size = sizeof(options), .version = 1,
            .root = argv[2], .kind = "host", .operation = "handoff"};
        golem_record *parent = NULL;
        CHECK(golem_record_begin(&options, &parent) == GOLEM_OK);
        gr_context context;
        CHECK(gr_context_capture(&context) == GOLEM_OK);
        golem_record_result result = {.struct_size = sizeof(result), .version = 1, .exit_code = -1};
        CHECK(golem_record_finish(parent, &result) == GOLEM_OK);
        pthread_t thread;
        void *returned;
        CHECK(pthread_create(&thread, NULL, thread_inherited, &context) == 0);
        CHECK(pthread_join(thread, &returned) == 0 && *(int *)returned == 0);
        gr_context_dispose(&context);
        CHECK(context.root == NULL && context.source == NULL);
        return 0;
    }
    if (!strcmp(argv[1], "threads")) {
        pthread_t thread;
        void *result;
        CHECK(pthread_create(&thread, NULL, thread_rejected, NULL) == 0);
        CHECK(pthread_join(thread, &result) == 0 && *(int *)result == 0);
        CHECK(!golem_record_last_api_outcome(&outcome));
        return rejected();
    }
    if (!strcmp(argv[1], "nested-fail")) {
        golem_diagnostic d;
        CHECK(outer_fixture(argv[2], &d) == GOLEM_OK);
        CHECK(golem_record_last_api_outcome(&outcome));
        CHECK(!strcmp(outcome.operation, "outer_fixture"));
        CHECK(outcome.dispatched && outcome.operation_status == GOLEM_OK);
        CHECK(outcome.recording_status == GOLEM_ERR_IO && effects == 1);
        CHECK(published_output);
        free(published_output);
        return 0;
    }
    if (!strcmp(argv[1], "reject")) return rejected();
    if (!strcmp(argv[1], "nested")) {
        golem_record_options o = {.struct_size = sizeof(o), .version = 1, .root = argv[2],
            .kind = "host", .operation = "parent"};
        golem_record *r = NULL;
        CHECK(golem_record_begin(&o, &r) == GOLEM_OK);
        CHECK(rejected() == 0);
        golem_record_result result = {.struct_size = sizeof(result), .version = 1, .exit_code = -1};
        CHECK(golem_record_finish(r, &result) == GOLEM_OK);
        return 0;
    }
    if (!strcmp(argv[1], "supervisor-reject")) {
        golem_supervisor_result out;
        golem_supervisor_observation obs;
        golem_supervisor_capture capture;
        CHECK(golem_supervisor_run_at(NULL, NULL, NULL, NULL, (golem_bytes){0}, 1, NULL, NULL, &out) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(golem_supervisor_run_observed(NULL, NULL, NULL, NULL, (golem_bytes){0}, 1, NULL, NULL, &out, &obs) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(golem_supervisor_run_streamed(NULL, NULL, NULL, NULL, (golem_bytes){0}, 1, NULL, NULL, &out, NULL, &capture) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(golem_supervisor_run_bulk(NULL, NULL, NULL, NULL, (golem_bytes){0}, 1, NULL, NULL, &out, NULL, NULL, &capture) == GOLEM_ERR_INVALID_ARGUMENT);
        return 0;
    }
    if (!strcmp(argv[1], "finish-fail") || !strcmp(argv[1], "operation-fail") || !strcmp(argv[1], "begin-fail")) {
        golem_diagnostic d = {0};
        golem_system_error_scope scope;
        CHECK(golem_system_error_begin(&scope) == GOLEM_OK);
        bool fail = !strcmp(argv[1], "operation-fail");
        golem_status st = fixture(argv[2], fail, &d);
        CHECK(golem_system_error_end(&scope) == GOLEM_OK);
        bool storage_diagnostic = false;
        for (size_t i = 0; i < scope.count; ++i)
            if (!strcmp(scope.entries[i].component, "record.storage") && scope.entries[i].error_number)
                storage_diagnostic = true;
        CHECK(storage_diagnostic);
        CHECK(golem_record_last_api_outcome(&outcome));
        CHECK(!strcmp(outcome.operation, "fixture"));
        CHECK(outcome.recording_status != GOLEM_OK);
        outcome.version = 2;
        CHECK(!golem_record_last_api_outcome(&outcome) && outcome.version == 2);
        outcome.version = 1;
        outcome.struct_size = 0;
        CHECK(!golem_record_last_api_outcome(&outcome) && outcome.struct_size == 0);
        outcome.struct_size = sizeof(outcome);
        if (!strcmp(argv[1], "begin-fail")) {
            CHECK(!outcome.dispatched);
            CHECK(!published_output);
            CHECK(st != GOLEM_OK && effects == 0);
            CHECK(!strcmp(d.message, "record.begin_dispatch_not_started"));
        } else {
            CHECK(outcome.dispatched);
            CHECK(outcome.operation_status == (fail ? GOLEM_ERR_POLICY_DENIED : GOLEM_OK));
            CHECK(effects == 1 && st == (fail ? GOLEM_ERR_POLICY_DENIED : GOLEM_OK));
            CHECK(published_output);
            free(published_output);
            if (!fail) CHECK(!strcmp(d.message, "record.finish_effects_uncertain"));
            else CHECK(!strcmp(d.message, "fixture.operation_failure"));
        }
        return 0;
    }
    const char *spec = "{\"schema_version\":1,\"work_id\":\"recording\",\"request\":\"test\","
        "\"scope\":\"local\",\"non_goals\":\"none\",\"permission\":\"AUTO_LOCAL\",\"max_revisions\":4,"
        "\"acceptance\":[{\"id\":\"R1\",\"criterion\":\"record\"}],\"policy_version\":1}";
    golem_document_store *store = NULL;
    golem_diagnostic d;
    golem_status st = golem_document_store_create(argv[2], (golem_bytes){(const uint8_t *)spec, strlen(spec)}, NULL, &store, &d);
    CHECK(golem_record_last_api_outcome(&outcome));
    CHECK(!strcmp(outcome.operation, "golem_document_store_create"));
    CHECK(outcome.dispatched == (strcmp(argv[1], "blocked") != 0));
    if (!strcmp(argv[1], "blocked")) CHECK(st != GOLEM_OK && store == NULL);
    else { CHECK(st == GOLEM_OK && store); CHECK(golem_document_store_close(store) == GOLEM_OK); }
    return 0;
}
