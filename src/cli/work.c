#define _POSIX_C_SOURCE 200809L
#include "work.h"
#include "../evidence/internal.h"
#include "golem/inventory.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static golem_status replay_checked(const char *path, const golem_replay_options *options,
                                   const golem_digest *head, golem_work_run **out,
                                   golem_replay_report *report)
{
    cli_blob b = {0};
    golem_replay *replay = NULL;
    golem_status s = cli_read(path, CLI_BUNDLE_MAX, &b);
    if (s == GOLEM_OK)
        s = golem_replay_create(options, NULL, &replay, NULL);
    if (s == GOLEM_OK && head) {
        golem_journal_inspection inspection;
        s = golem_journal_inspect((golem_bytes){b.data, b.size}, &inspection);
        if (s == GOLEM_OK)
            s = inspection.stream_status;
        golem_journal_checkpoint checkpoint = {0};
        if (s == GOLEM_OK) {
            checkpoint = (golem_journal_checkpoint){inspection.records, b.size, *head};
            s = golem_replay_expect_checkpoint(replay, &checkpoint);
        }
    }
    if (s == GOLEM_OK)
        s = golem_replay_feed(replay, (golem_bytes){b.data, b.size}, NULL);
    if (s == GOLEM_OK)
        s = golem_replay_finish(replay, out, report, NULL);
    golem_replay_free(replay);
    free(b.data);
    return s;
}
golem_status cli_replay_file(const char *path, const golem_replay_options *options,
                             golem_work_run **out, golem_replay_report *report)
{
    return replay_checked(path, options, NULL, out, report);
}
static int usage(void)
{
    fputs("Usage: golem init DIRECTORY | capsule validate FILE | run --noop CAPSULE --output "
          "RUN_DIR | replay RUN_DIR_OR_JOURNAL [--require-terminal] | cost report RUN_DIR\n",
          stderr);
    return 2;
}
int golem_cli_work(int argc, char **argv)
{
    if (argc >= 3 && !strcmp(argv[1], "inventory")) {
        bool validate = argc == 4 && !strcmp(argv[2], "validate");
        bool capture = argc == 5 && !strcmp(argv[2], "capture");
        bool compare = argc == 6 && !strcmp(argv[2], "compare");
        if (!validate && !capture && !compare)
            return usage();
        cli_blob policy = {0}, baseline = {0}, current = {0};
        golem_inventory_reply reply = {0};
        golem_status status = cli_read(argv[validate ? 3 : capture ? 4 : 5],
                                       GOLEM_INVENTORY_MAX_JSON, &policy);
        if (status == GOLEM_OK && validate)
            status = golem_inventory_policy_validate((golem_bytes){policy.data, policy.size}, NULL);
        if (status == GOLEM_OK && capture)
            status = golem_inventory_capture(argv[3], (golem_bytes){policy.data, policy.size}, &reply, NULL);
        if (status == GOLEM_OK && compare)
            status = cli_read(argv[3], GOLEM_INVENTORY_MAX_JSON, &baseline);
        if (status == GOLEM_OK && compare)
            status = cli_read(argv[4], GOLEM_INVENTORY_MAX_JSON, &current);
        if (status == GOLEM_OK && compare)
            status = golem_inventory_compare((golem_bytes){baseline.data, baseline.size},
                                             (golem_bytes){current.data, current.size},
                                             (golem_bytes){policy.data, policy.size}, &reply, NULL);
        struct json_object *out = NULL;
        if (status == GOLEM_OK && validate) {
            out = json_object_new_object();
            if (!out || !cli_json_add(out, "valid", json_object_new_boolean(true)))
                status = GOLEM_ERR_OUT_OF_MEMORY;
        } else if (status == GOLEM_OK)
            status = cli_json_parse((golem_bytes){reply.data, reply.size}, &out);
        golem_inventory_reply_free(&reply);
        free(policy.data);
        free(baseline.data);
        free(current.data);
        return cli_emit(status, out);
    }

    if (argc == 7 && !strcmp(argv[1], "cost") && !strcmp(argv[2], "inbox") && !strcmp(argv[6], "1")) {
        /* Disposable first-stage accounting only: no agent, Work store, journal,
         * stage PASS, settlement or persisted live-run authority is created. */
        cli_blob input = {0};
        golem_work_capsule *capsule = NULL;
        golem_work_run *run = NULL;
        golem_status status = cli_read(argv[3], CLI_CAPSULE_MAX, &input);
        if (status == GOLEM_OK)
            status = cli_capsule_decode((golem_bytes){input.data, input.size}, &capsule);
        if (status == GOLEM_OK)
            status = golem_work_run_create(argv[4], capsule, 1, &run);
        golem_cost_options options = {.version = GOLEM_COST_VERSION, .currency = "USD", .entry_capacity = 1, .report_capacity = 256};
        if (status == GOLEM_OK)
            status = golem_work_run_cost_enable(run, &options);
        if (status == GOLEM_OK)
            status = golem_work_run_cost_inbox_enable(run, argv[5], false);
        golem_stage_snapshot stage;
        if (status == GOLEM_OK)
            status = golem_work_run_begin(run, false, false, &stage);
        if (status == GOLEM_OK)
            status = golem_work_run_cost_inbox_sync(run, 1, true);
        golem_status inbox_status = GOLEM_ERR_COST_INCOMPLETE;
        if (status == GOLEM_OK)
            status = golem_work_run_cost_inbox_status(run, &inbox_status);
        const golem_cost_ledger *ledger = golem_work_run_cost_borrow(run);
        golem_cost_entry entry;
        golem_cost_totals totals, stage_totals;
        if (status == GOLEM_OK)
            status = golem_cost_ledger_entry_get(ledger, 1, &entry);
        if (status == GOLEM_OK)
            status = golem_cost_ledger_totals_get(ledger, &totals);
        if (status == GOLEM_OK)
            status = golem_cost_ledger_stage_totals_get(ledger, stage.stage, &stage_totals);
        if (status == GOLEM_OK)
            status = golem_cost_ledger_options_get(ledger, &options);
        struct json_object *out = json_object_new_object(), *reports = json_object_new_array();
        if (!out || !reports)
            status = GOLEM_ERR_OUT_OF_MEMORY;
        for (size_t i = 0; status == GOLEM_OK && i < entry.report_count; ++i) {
            golem_provider_usage report;
            status = golem_cost_ledger_report_get(ledger, 1, i, &report);
            struct json_object *row = json_object_new_object();
            if (status == GOLEM_OK && (!cli_json_add(row, "provider", json_object_new_string(report.provider)) ||
                !cli_json_add(row, "model", json_object_new_string(report.model)) ||
                !cli_json_add(row, "request_id", json_object_new_string(report.request_id)) ||
                !cli_json_add(row, "usage_known", json_object_new_boolean(report.actual.usage_known)) ||
                !cli_json_add(row, "cost_known", json_object_new_boolean(report.actual.cost_known)) ||
                (report.actual.cost_known ? !cli_json_add(row, "nano_cost", cli_json_u64(report.actual.nano_cost)) : json_object_object_add(row, "nano_cost", NULL) != 0) ||
                !cli_json_append(reports, row)))
                status = GOLEM_ERR_OUT_OF_MEMORY;
        }
        if (status == GOLEM_OK && (!cli_json_add(out, "schema", json_object_new_string("golem.accounting-reconstruction.v1")) ||
            !cli_json_add(out, "live_run_updated", json_object_new_boolean(false)) ||
            !cli_json_add(out, "acceptance_verified", json_object_new_boolean(false)) ||
            !cli_json_add(out, "unsettled", cli_json_u64(totals.unsettled)) ||
            !cli_json_add(out, "stage_reports", cli_json_u64(stage_totals.reports)) ||
            !cli_json_add(out, "inbox_status", json_object_new_string(golem_status_string(inbox_status))) ||
            !cli_json_add(out, "currency", json_object_new_string(options.currency)) ||
            !cli_json_add(out, "reports", json_object_get(reports))))
            status = GOLEM_ERR_OUT_OF_MEMORY;
        json_object_put(reports);
        golem_work_run_free(run);
        golem_work_capsule_free(capsule);
        free(input.data);
        return cli_emit(status, out);
    }

    golem_status s = GOLEM_OK;
    struct json_object *out = NULL;
    if (strcmp(argv[1], "init") == 0) {
        if (argc != 3)
            return usage();
        struct json_object *capsule = cli_capsule_template();
        int dir = -1;
        s = capsule == NULL ? GOLEM_ERR_OUT_OF_MEMORY : cli_mkdir_new(argv[2], &dir);
        if (s == GOLEM_OK)
            s = cli_json_write(dir, "capsule.json", capsule);
        if (dir >= 0 && close(dir) != 0 && s == GOLEM_OK)
            s = GOLEM_ERR_IO;
        json_object_put(capsule);
        out = json_object_new_object();
        if (!cli_json_add(out, "initialized", json_object_new_boolean(true)))
            s = GOLEM_ERR_OUT_OF_MEMORY;
    } else if (strcmp(argv[1], "capsule") == 0) {
        if (argc != 4 || strcmp(argv[2], "validate") != 0)
            return usage();
        cli_blob b = {0};
        golem_work_capsule *capsule = NULL;
        s = cli_read(argv[3], CLI_CAPSULE_MAX, &b);
        if (s == GOLEM_OK)
            s = cli_capsule_decode((golem_bytes){b.data, b.size}, &capsule);
        golem_work_capsule_free(capsule);
        free(b.data);
        out = json_object_new_object();
        if (!cli_json_add(out, "valid", json_object_new_boolean(true)))
            s = GOLEM_ERR_OUT_OF_MEMORY;
    } else if (strcmp(argv[1], "run") == 0) {
        if (argc != 6 || strcmp(argv[2], "--noop") != 0 || strcmp(argv[4], "--output") != 0)
            return usage();
        s = cli_noop_run(argv[3], argv[5], &out);
    } else if (strcmp(argv[1], "cost") == 0) {
        if (argc != 4 || strcmp(argv[2], "report") != 0)
            return usage();
        struct json_object *summary = NULL;
        s = cli_bundle_verify(argv[3], &summary, &out);
        json_object_put(summary);
    } else if (strcmp(argv[1], "replay") == 0) {
        bool terminal = false, anchored = false;
        golem_digest head;
        for (int i = 3; i < argc; ++i) {
            if (!strcmp(argv[i], "--require-terminal") && !terminal)
                terminal = true;
            else if (!strcmp(argv[i], "--expect-chain") && !anchored && i + 1 < argc) {
                ++i;
                s = golem_digest_parse((golem_string_view){argv[i], strlen(argv[i])}, &head);
                if (s != GOLEM_OK)
                    return cli_emit(s, NULL);
                anchored = true;
            } else
                return usage();
        }
        if (argc < 3)
            return usage();
        int dir = golem_evidence_path_open(argv[2], true);
        char path[CLI_PATH_MAX];
        const char *journal = argv[2];
        bool complete = false;
        if (dir >= 0) {
            struct stat st;
            s = cli_path(argv[2], "complete.json", path);
            if (s == GOLEM_OK && lstat(path, &st) == 0)
                complete = true;
            if (complete) {
                struct json_object *cost = NULL;
                s = cli_bundle_verify(argv[2], &out, &cost);
                json_object_put(cost);
            } else {
                s = cli_path(argv[2], "journal.bin", path);
                journal = path;
            }
            if (close(dir) != 0 && s == GOLEM_OK)
                s = GOLEM_ERR_IO;
        }
        if (!complete && s == GOLEM_OK) {
            golem_work_run *run = NULL;
            golem_replay_report report;
            golem_replay_options options = {.require_terminal = terminal};
            s = replay_checked(journal, &options, anchored ? &head : NULL, &run, &report);
            if (s == GOLEM_OK) {
                out = cli_run_projection(run, &report, false);
                if (out == NULL)
                    s = GOLEM_ERR_OUT_OF_MEMORY;
            }
            golem_work_run_free(run);
        }
        if (complete && anchored && s == GOLEM_OK) {
            golem_work_run *run = NULL;
            golem_replay_options options = {.require_terminal = true};
            s = cli_path(argv[2], "journal.bin", path);
            if (s == GOLEM_OK)
                s = replay_checked(path, &options, &head, &run, NULL);
            golem_work_run_free(run);
        }
    } else
        return usage();
    return cli_emit(s, out);
}
