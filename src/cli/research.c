#include "work.h"
#include "golem/research.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int golem_cli_research_bundle(int argc, char **argv);

static int observability(int argc, char **argv)
{
    if (argc != 10 || strcmp(argv[4], "--case") || strcmp(argv[6], "--format") ||
        strcmp(argv[8], "--redact") || (strcmp(argv[7], "otlp") && strcmp(argv[7], "prov"))) {
        fputs("usage: golem research observability WORK --case CASE_ID --format otlp|prov --redact POLICY.json\n", stderr);
        return 2;
    }
    cli_blob policy = {0}; golem_document_store *store = NULL; golem_execution_reply reply = {0};
    golem_status st = cli_read(argv[9], GOLEM_RESEARCH_REDACTION_MAX_JSON, &policy);
    if (st == GOLEM_OK) st = golem_document_store_open(argv[3], false, NULL, &store, NULL);
    if (st == GOLEM_OK) st = golem_research_observability(store, argv[5],
        (golem_bytes){policy.data, policy.size}, !strcmp(argv[7], "otlp")
            ? GOLEM_RESEARCH_EXPORT_OTLP_LOGS : GOLEM_RESEARCH_EXPORT_PROV_JSON, &reply, NULL);
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK) st = closed;
    if (st == GOLEM_OK && (fwrite(reply.data, 1, reply.size, stdout) != reply.size ||
        fputc('\n', stdout) == EOF || fflush(stdout) == EOF)) st = GOLEM_ERR_IO;
    free(policy.data); golem_execution_reply_free(&reply);
    if (st != GOLEM_OK) fprintf(stderr, "research observability: %s\n", golem_status_string(st));
    return st == GOLEM_OK ? 0 : 1;
}
int golem_cli_research(int argc, char **argv)
{
    if (argc > 2 && !strcmp(argv[2], "observability")) return observability(argc, argv);
    if (argc > 2 && (!strcmp(argv[2], "export") || !strcmp(argv[2], "bundle-verify")))
        return golem_cli_research_bundle(argc, argv);
    bool metrics = argc >= 4 && !strcmp(argv[2], "metrics"), markdown = false;
    const char *case_id = NULL; bool format_seen = false;
    if (metrics) for (int i = 4; i < argc; i += 2) {
        if (i + 1 >= argc) return 2;
        if (!strcmp(argv[i], "--case") && !case_id) case_id = argv[i+1];
        else if (!strcmp(argv[i], "--format") && !format_seen &&
            (!strcmp(argv[i+1], "json") || !strcmp(argv[i+1], "markdown"))) {
            format_seen = true; markdown = !strcmp(argv[i+1], "markdown");
        } else return 2;
    }
    bool validate = argc == 4 && !strcmp(argv[2], "validate");
    bool call = argc == 5 && !strcmp(argv[2], "call");
    bool status = argc == 4 && !strcmp(argv[2], "status");
    bool inspect = argc == 5 && !strcmp(argv[2], "inspect");
    bool report = argc == 5 && !strcmp(argv[2], "report");
    bool create = argc == 7 && !strcmp(argv[2], "case") && !strcmp(argv[3], "create");
    bool plan = argc == 7 && !strcmp(argv[2], "attempt") && !strcmp(argv[3], "plan");
    bool record = argc == 7 && !strcmp(argv[2], "attempt") && !strcmp(argv[3], "record");
    bool enroll = argc == 7 && !strcmp(argv[2], "outcome") && !strcmp(argv[3], "enroll");
    bool adjudicate = argc == 7 && !strcmp(argv[2], "outcome") && !strcmp(argv[3], "adjudicate");
    bool cohort = argc == 7 && !strcmp(argv[2], "cohort") && !strcmp(argv[3], "create");
    bool observe = argc == 7 && !strcmp(argv[2], "cohort") && !strcmp(argv[3], "observe");
    bool compare = argc == 5 && !strcmp(argv[2], "compare");
    bool wrapped = create || plan || record || enroll || adjudicate || cohort || observe;
    bool write = call || wrapped;
    if (!validate && !write && !status && !inspect && !report && !metrics && !compare) {
        fputs("usage: golem research validate REQUEST.json\n"
              "       golem research call WORK REQUEST.json\n"
              "       golem research case create WORK CASE.json KEY\n"
              "       golem research attempt plan|record WORK ATTEMPT.json KEY\n"
              "       golem research outcome enroll|adjudicate WORK RECORD.json KEY\n"
              "       golem research status WORK\n"
              "       golem research export WORK --case CASE_ID --output NEW_DIR --redact POLICY.json\n"
              "       golem research bundle-verify DIR\n"
              "       golem research observability WORK --case CASE_ID --format otlp|prov --redact POLICY.json\n"
              "       golem research cohort create|observe WORK RECORD.json KEY\n"
              "       golem research compare WORK COHORT_ID\n"
              "       golem research metrics WORK [--case CASE_ID] [--format json|markdown]\n"
              "       golem research inspect|report WORK SEQUENCE\n", stderr);
        return 2;
    }
    cli_blob input = {0}; golem_execution_reply reply = {0};
    golem_document_store *store = NULL; struct json_object *request = NULL, *body = NULL;
    golem_status st = GOLEM_OK;
    if (validate || write) st = cli_read(argv[validate ? 3 : call ? 4 : 5], GOLEM_RESEARCH_MAX_JSON, &input);
    golem_bytes bytes = {input.data, input.size};
    if (st == GOLEM_OK && wrapped) {
        st = cli_json_parse(bytes, &body);
        if (st == GOLEM_OK) {
            request = json_object_new_object();
            if (!cli_json_add(request, "schema_version", json_object_new_int(1)) ||
                !cli_json_add(request, "operation", json_object_new_string(create ? "case-create" : plan ? "attempt-plan" :
                    enroll ? "outcome-enroll" : adjudicate ? "adjudicate" : cohort ? "cohort-create" :
                    observe ? "cohort-observe" : "attempt-record")) ||
                !cli_json_add(request, "key", json_object_new_string(argv[6])) ||
                !cli_json_add(request, "record", json_object_get(body))) st = GOLEM_ERR_OUT_OF_MEMORY;
            if (st == GOLEM_OK) {
                const char *encoded = json_object_to_json_string_ext(request, JSON_C_TO_STRING_PLAIN);
                if (!encoded) st = GOLEM_ERR_OUT_OF_MEMORY;
                else bytes = (golem_bytes){(const uint8_t *)encoded, strlen(encoded)};
            }
        }
    }
    if (st == GOLEM_OK && (validate || write)) st = golem_research_validate(bytes, NULL);
    if (st == GOLEM_OK && !validate)
        st = golem_document_store_open(argv[wrapped ? 4 : 3], write, NULL, &store, NULL);
    if (st == GOLEM_OK && write) st = golem_research_call(store, bytes, &reply, NULL);
    if (st == GOLEM_OK && status) st = golem_research_status(store, &reply, NULL);
    if (st == GOLEM_OK && compare) st = golem_research_compare(store, argv[4], &reply, NULL);
    if (st == GOLEM_OK && metrics) st = markdown
        ? golem_research_metrics_report(store, case_id, &reply, NULL)
        : golem_research_metrics(store, case_id, &reply, NULL);
    if (st == GOLEM_OK && (inspect || report)) {
        char *end = NULL; errno = 0;
        unsigned long seq = strtoul(argv[4], &end, 10);
        if (errno || !*argv[4] || *end || seq == 0 || seq > GOLEM_RESEARCH_MAX_EVENTS) st = GOLEM_ERR_INVALID_ARGUMENT;
        else st = report ? golem_research_report(store, (uint32_t)seq, &reply, NULL)
                         : golem_research_inspect(store, (uint32_t)seq, &reply, NULL);
    }
    if (st == GOLEM_OK && reply.size && fwrite(reply.data, 1, reply.size, stdout) != reply.size) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && !report && !markdown && fputc('\n', stdout) == EOF) st = GOLEM_ERR_IO;
    free(input.data); json_object_put(body); json_object_put(request); golem_execution_reply_free(&reply);
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK) st = closed;
    if (st != GOLEM_OK) fprintf(stderr, "research: %s\n", golem_status_string(st));
    return st == GOLEM_OK ? 0 : 1;
}
