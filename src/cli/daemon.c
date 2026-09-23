#define _POSIX_C_SOURCE 200809L
#include "internal.h"
#include "work.h"
#include "daemon_worker.h"
#include <openssl/rand.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stopped;
static void stop(int signal_number)
{
    (void)signal_number;
    stopped = 1;
}
static struct json_object *status_json(const char *root, golem_status *status)
{
    golem_daemon_job jobs[GOLEM_DAEMON_MAX_JOBS];
    size_t count;
    *status = golem_daemon_inspect(root, jobs, GOLEM_DAEMON_MAX_JOBS, &count);
    if (*status != GOLEM_OK)
        return NULL;
    struct json_object *o = json_object_new_object(), *rows = json_object_new_array();
    if (o == NULL || rows == NULL)
        goto oom;
    for (size_t n = 0; n < count; ++n) {
        static const char *const states[] = {"ready", "complete", "attention", "busy"};
        struct json_object *row = json_object_new_object();
        if (!cli_json_add(row, "ticket", cli_json_u64(jobs[n].ticket)) ||
            !cli_json_add(row, "run_id", json_object_new_string(jobs[n].run_id)) ||
            !cli_json_add(row, "state", json_object_new_string(states[jobs[n].state])) ||
            !cli_json_add(row, "reason",
                          json_object_new_string(golem_status_string(jobs[n].reason)))) {
            json_object_put(row);
            goto oom;
        }
        if (!cli_json_append(rows, row))
            goto oom;
    }
    if (!cli_json_add(o, "schema_version", json_object_new_int(1)) ||
        !cli_json_add(o, "acceptance_verified", json_object_new_boolean(false)))
        goto oom;
    if (!cli_json_add(o, "jobs", rows)) {
        rows = NULL;
        goto oom;
    }
    return o;
oom:
    json_object_put(o);
    json_object_put(rows);
    *status = GOLEM_ERR_OUT_OF_MEMORY;
    return NULL;
}
static golem_status submit(const char *root, const char *capsule_path, struct json_object **out)
{
    cli_blob b = {0};
    golem_work_capsule *capsule = NULL;
    golem_status s = cli_read(capsule_path, CLI_CAPSULE_MAX, &b);
    if (s == GOLEM_OK)
        s = cli_capsule_decode((golem_bytes){b.data, b.size}, &capsule);
    unsigned char random[16];
    char id[37] = "run-";
    if (s == GOLEM_OK && RAND_bytes(random, sizeof(random)) != 1)
        s = GOLEM_ERR_CRYPTO;
    if (s == GOLEM_OK)
        for (size_t n = 0; n < sizeof(random); ++n)
            (void)snprintf(id + 4 + 2 * n, 3, "%02x", random[n]);
    golem_runtime_options options = {GOLEM_RUNTIME_VERSION, 3, 64, UINT64_C(30000000000)};
    uint64_t ticket;
    if (s == GOLEM_OK) {
        /* BUSY is returned before publication: retry the same identity only.
         * Never retry I/O/uncertain-commit errors or create a new identity. */
        for (unsigned attempt = 0; attempt < 100; ++attempt) {
            s = golem_daemon_submit(root, id, capsule, &options, &ticket);
            if (s != GOLEM_ERR_JOURNAL_BUSY)
                break;
            struct timespec delay = {0, 10000000};
            (void)nanosleep(&delay, NULL);
        }
    }
    if (s == GOLEM_OK) {
        *out = json_object_new_object();
        if (!cli_json_add(*out, "ticket", cli_json_u64(ticket)) ||
            !cli_json_add(*out, "run_id", json_object_new_string(id)))
            s = GOLEM_ERR_OUT_OF_MEMORY;
    }
    free(b.data);
    golem_work_capsule_free(capsule);
    return s;
}
static golem_status drive(const char *root, const char *worker, const char *mode)
{
    if (worker[0] != '/')
        return GOLEM_ERR_INVALID_ARGUMENT;
    stopped = 0;
    cli_daemon_host host = {worker, &stopped};
    golem_daemon_ops ops = {cli_daemon_execute};
    golem_daemon *daemon = NULL;
    golem_status s = golem_daemon_open(root, &ops, &host, &daemon);
    if (s != GOLEM_OK)
        return s;
    struct sigaction action = {0}, old_int, old_term;
    action.sa_handler = stop;
    sigemptyset(&action.sa_mask);
    bool has_int = sigaction(SIGINT, &action, &old_int) == 0, has_term = false;
    if (has_int)
        has_term = sigaction(SIGTERM, &action, &old_term) == 0;
    if (!has_term)
        s = GOLEM_ERR_IO;
    while (s == GOLEM_OK && !stopped) {
        bool worked;
        s = golem_daemon_tick(daemon, &worked);
        if (s != GOLEM_OK || (mode != NULL && (strcmp(mode, "--once") == 0 || !worked)))
            break;
        if (!worked) {
            struct timespec delay = {0, 100000000};
            (void)nanosleep(&delay, NULL);
        }
    }
    if (has_term)
        (void)sigaction(SIGTERM, &old_term, NULL);
    if (has_int)
        (void)sigaction(SIGINT, &old_int, NULL);
    golem_status closed = golem_daemon_close(daemon);
    return s == GOLEM_OK ? closed : s;
}
int golem_cli_daemon(int argc, char **argv)
{
    golem_status s;
    struct json_object *o = NULL;
    if (argc == 4 && strcmp(argv[2], "init") == 0) {
        int dir = -1;
        s = cli_mkdir_new(argv[3], &dir);
        if (s == GOLEM_OK && close(dir) < 0)
            s = GOLEM_ERR_IO;
        if (s == GOLEM_OK)
            s = golem_daemon_init(argv[3]);
    } else if (argc == 5 && strcmp(argv[2], "submit") == 0)
        s = submit(argv[3], argv[4], &o);
    else if (argc == 4 && strcmp(argv[2], "status") == 0) {
        o = status_json(argv[3], &s);
        return cli_emit(s, o);
    } else if (argc == 4 && strcmp(argv[2], "recover") == 0) {
        golem_daemon_recovery_report r;
        s = golem_daemon_recover(argv[3], &r);
        if (s == GOLEM_OK) {
            o = status_json(argv[3], &s);
            struct json_object *report = json_object_new_object();
            if (s == GOLEM_OK && (!cli_json_add(report, "jobs", cli_json_u64(r.jobs)) ||
                                  !cli_json_add(report, "repaired", cli_json_u64(r.repaired)) ||
                                  !cli_json_add(report, "ready", cli_json_u64(r.ready)) ||
                                  !cli_json_add(report, "complete", cli_json_u64(r.complete)) ||
                                  !cli_json_add(report, "attention", cli_json_u64(r.attention)) ||
                                  !cli_json_add(report, "busy", cli_json_u64(r.busy))))
                s = GOLEM_ERR_OUT_OF_MEMORY;
            if (s == GOLEM_OK) {
                if (!cli_json_add(o, "recovery", report))
                    s = GOLEM_ERR_OUT_OF_MEMORY;
            } else
                json_object_put(report);
        }
    } else if ((argc == 6 || argc == 7) && strcmp(argv[2], "run") == 0 &&
               strcmp(argv[4], "--worker") == 0 &&
               (argc == 6 || strcmp(argv[6], "--once") == 0 || strcmp(argv[6], "--drain") == 0))
        s = drive(argv[3], argv[5], argc == 7 ? argv[6] : NULL);
    else {
        fputs("Usage: golem daemon init ROOT | submit ROOT CAPSULE | status ROOT | recover ROOT\n"
              "       golem daemon run ROOT --worker /absolute/path/golem [--once|--drain]\n",
              stderr);
        return 2;
    }
    if (s == GOLEM_OK && o == NULL)
        o = status_json(argv[3], &s);
    return cli_emit(s, o);
}
