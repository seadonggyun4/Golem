#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "internal.h"
#include "../core/internal.h"
#include "../common/json.h"
#include "../evidence/internal.h"
#include "golem/system_error.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define INBOX_BYTES 1048576u
#define INBOX_REPORTS 256u
struct golem_cost_inbox { int fd; bool require_billed; golem_status last_status; };

static golem_status io_error(const char *operation)
{
    return golem_system_error_note(GOLEM_ERR_IO, "cost.inbox", operation, errno);
}
static bool private_shape(const struct stat *s)
{
    return (s->st_mode & 0077) == 0 && s->st_uid == geteuid();
}
static bool text_equal(struct json_object *o, const char *key, const char *expected)
{
    struct json_object *v = NULL;
    return json_object_object_get_ex(o, key, &v) && json_object_is_type(v, json_type_string) &&
        (size_t)json_object_get_string_len(v) == strlen(expected) &&
        strcmp(json_object_get_string(v), expected) == 0;
}
golem_status golem_work_run_cost_inbox_enable(golem_work_run *run,
    const char *directory, bool require_billed)
{
    if (run == NULL || directory == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status status = golem_core_ownership_check(run);
    if (status != GOLEM_OK) return status;
    if (run->cost == NULL || run->cost_inbox != NULL || run->sequence != 0 ||
        run->status != GOLEM_WORK_READY) return GOLEM_ERR_INVALID_STATE;
    int fd = golem_evidence_path_open(directory, true);
    if (fd < 0) return io_error("open_directory");
    struct stat s;
    if (fstat(fd, &s) < 0) status = io_error("fstat_directory");
    else if (!S_ISDIR(s.st_mode) || !private_shape(&s)) status = GOLEM_ERR_POLICY_DENIED;
    void *memory = NULL;
    if (status == GOLEM_OK) status = golem_allocator_alloc(&run->allocator, sizeof(struct golem_cost_inbox), &memory);
    if (status == GOLEM_OK) {
        run->cost_inbox = memory;
        *run->cost_inbox = (struct golem_cost_inbox){fd, require_billed, GOLEM_ERR_COST_INCOMPLETE};
    } else if (close(fd) < 0) (void)io_error("close_directory_on_error");
    return status;
}
void golem_cost_inbox_free(golem_work_run *run)
{
    if (run->cost_inbox == NULL) return;
    if (close(run->cost_inbox->fd) < 0) (void)io_error("close_directory");
    (void)golem_allocator_free(&run->allocator, run->cost_inbox);
    run->cost_inbox = NULL;
}
static golem_status read_snapshot(golem_work_run *run, uint64_t sequence, struct json_object **out)
{
    char name[32];
    (void)snprintf(name, sizeof(name), "%020" PRIu64 ".json", sequence);
    int fd = openat(run->cost_inbox->fd, name, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return errno == ENOENT ? GOLEM_ERR_COST_INCOMPLETE : io_error("open_snapshot");
    struct stat s;
    golem_status status = GOLEM_OK;
    if (fstat(fd, &s) < 0) status = io_error("fstat_snapshot");
    else if (!S_ISREG(s.st_mode) || !private_shape(&s)) status = GOLEM_ERR_POLICY_DENIED;
    else if (s.st_size <= 0 || (uintmax_t)s.st_size > INBOX_BYTES) status = GOLEM_ERR_PARSE;
    void *memory = NULL;
    if (status == GOLEM_OK) status = golem_allocator_alloc(&run->allocator, (size_t)s.st_size + 1, &memory);
    size_t used = 0;
    while (status == GOLEM_OK && used < (size_t)s.st_size + 1) {
        ssize_t n = read(fd, (uint8_t *)memory + used, (size_t)s.st_size + 1 - used);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) { status = io_error("read_snapshot"); break; }
        if (n == 0) break;
        used += (size_t)n;
    }
    if (close(fd) < 0 && status == GOLEM_OK) status = io_error("close_snapshot");
    if (status == GOLEM_OK && used != (size_t)s.st_size) status = GOLEM_ERR_PARSE;
    if (status == GOLEM_OK) status = golem_json_parse((golem_bytes){memory, used}, INBOX_BYTES, out);
    (void)golem_allocator_free(&run->allocator, memory);
    return status;
}
static golem_status sync_snapshot(golem_work_run *run, uint64_t sequence, bool require_sealed)
{
    if (run == NULL || sequence == 0) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status status;
    if (run->cost_inbox == NULL || run->cost == NULL) return GOLEM_ERR_INVALID_STATE;
    golem_cost_entry entry;
    status = golem_cost_ledger_entry_get(run->cost, sequence, &entry);
    if (status != GOLEM_OK) return status;
    struct json_object *root = NULL, *reports = NULL, *sealed = NULL;
    status = read_snapshot(run, sequence, &root);
    if (status != GOLEM_OK) return status;
    char seq[32]; (void)snprintf(seq, sizeof(seq), "%" PRIu64, sequence);
    if (!json_object_is_type(root, json_type_object) || json_object_object_length(root) != 5 ||
        !text_equal(root, "schema", "golem.native-cost-inbox.v1") ||
        !text_equal(root, "run_id", run->id) || !text_equal(root, "sequence", seq) ||
        !json_object_object_get_ex(root, "sealed", &sealed) || !json_object_is_type(sealed, json_type_boolean) ||
        !json_object_object_get_ex(root, "reports", &reports) || !json_object_is_type(reports, json_type_array)) {
        json_object_put(root); return GOLEM_ERR_PARSE;
    }
    size_t count = json_object_array_length(reports);
    if (count == 0 || (require_sealed && !json_object_get_boolean(sealed))) {
        json_object_put(root); return GOLEM_ERR_COST_INCOMPLETE;
    }
    if (count > INBOX_REPORTS || count > run->cost->options.report_capacity) {
        json_object_put(root); return GOLEM_ERR_COST_CAPACITY;
    }
    void *memory = NULL;
    status = golem_allocator_alloc(&run->allocator, count * sizeof(golem_provider_usage), &memory);
    golem_provider_usage *decoded = memory;
    bool partial[INBOX_REPORTS] = {false};
    /* Validate the complete envelope before any report affects the ledger. */
    for (size_t i = 0; status == GOLEM_OK && i < count; ++i) {
        const char *json = json_object_to_json_string_ext(json_object_array_get_idx(reports, i), JSON_C_TO_STRING_PLAIN);
        uint64_t reported_sequence = 0;
        status = golem_cost_report_decode_extended((golem_bytes){(const uint8_t *)json, strlen(json)},
            run->id, &reported_sequence, &decoded[i], &partial[i]);
        if (status == GOLEM_OK && reported_sequence != sequence) status = GOLEM_ERR_IDENTITY_MISMATCH;
        if (status == GOLEM_OK && run->cost_inbox->require_billed && !decoded[i].actual.cost_known)
            status = GOLEM_ERR_COST_INCOMPLETE;
    }
    for (size_t i = 0; status == GOLEM_OK && i < count; ++i)
        status = partial[i] ? golem_cost_report_apply(run, sequence, &decoded[i], true) :
            golem_work_run_cost_report(run, sequence, &decoded[i]);
    (void)golem_allocator_free(&run->allocator, memory);
    json_object_put(root);
    return status;
}
golem_status golem_work_run_cost_inbox_sync(golem_work_run *run, uint64_t sequence, bool require_sealed)
{
    if (run == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status ownership = golem_core_ownership_check(run);
    if (ownership != GOLEM_OK) return ownership;
    golem_status status = sync_snapshot(run, sequence, require_sealed);
    if (run != NULL && run->cost_inbox != NULL) run->cost_inbox->last_status = status;
    return status;
}
golem_status golem_work_run_cost_inbox_status(const golem_work_run *run, golem_status *out)
{
    if (run == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (run->cost_inbox == NULL) return GOLEM_ERR_INVALID_STATE;
    *out = run->cost_inbox->last_status;
    return GOLEM_OK;
}
