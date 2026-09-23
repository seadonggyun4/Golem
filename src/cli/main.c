#include "golem/evidence.h"
#include "internal.h"
#include "golem/version.h"
int golem_cli_work(int argc, char **argv);
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static int usage(void)
{
    fputs("Usage:\n"
        "  golem init DIRECTORY\n"
        "  golem work start NEW_WORK_DIR SPEC_JSON\n"
        "  golem session call WORK_DIR REQUEST_JSON\n"
        "  golem execution validate CONTRACT_JSON\n"
        "  golem execution call WORK_DIR REQUEST_JSON [--approve-contract SHA256]\n"
        "  golem execution render WORK_DIR METADATA_JSON\n"
        "  golem research case create WORK_DIR CASE_JSON KEY\n"
        "  golem research attempt plan|record WORK_DIR ATTEMPT_JSON KEY\n"
        "  golem research validate REQUEST_JSON\n"
        "  golem research call WORK_DIR REQUEST_JSON\n"
        "  golem research status WORK_DIR\n"
        "  golem research observability WORK --case CASE_ID --format otlp|prov --redact POLICY.json\n"
        "  golem research inspect|report WORK_DIR SEQUENCE\n"
        "  golem completion validate REQUEST_JSON\n"
        "  golem completion call WORK_DIR REQUEST_JSON\n"
        "  golem completion report WORK_DIR SEQUENCE\n"
        "  golem reentry validate REQUEST_JSON\n"
        "  golem reentry call WORK_DIR REQUEST_JSON\n"
        "  golem reentry report WORK_DIR SEQUENCE\n"
        "  golem discovery snapshot PLAN_JSON\n"
        "  golem discovery validate ASSESSMENT_JSON\n"
        "  golem discovery report ASSESSMENT_JSON discovery|research|scope\n"
        "  golem workflow select WORK_DIR SCOPE_ID REVISION development|documents\n"
        "  golem workflow inputs WORK_DIR SELECTION_ID TARGET_KIND SOURCE_SHA256 BYTE_BUDGET\n"
        "  golem workflow trace WORK_DIR DOCUMENT_ID REVISION\n"
        "  golem workflow next WORK_DIR SELECTION_ID\n"
        "  golem document validate META_JSON BODY_MD\n"
        "  golem document submit WORK_DIR META_JSON BODY_MD IDEMPOTENCY_KEY\n"
        "  golem document inspect WORK_DIR DOCUMENT_ID REVISION\n"
        "  golem document project WORK_DIR DOCUMENT_ID REVISION\n"
        "  golem capsule validate FILE\n"
        "  golem run --noop CAPSULE --output RUN_DIR\n"
        "  golem replay RUN_DIR_OR_JOURNAL [--require-terminal]\n"
        "  golem journal inspect FILE [--expect-chain SHA256]\n"
        "  golem journal salvage FILE NEW_DIRECTORY --expect-source SHA256 --accept-truncated-tail\n"
        "  golem cost report RUN_DIR\n"
        "  golem daemon init ROOT | submit ROOT CAPSULE | status ROOT\n"
        "  golem daemon recover ROOT\n"
        "  golem daemon run ROOT --worker /absolute/path/golem [--once|--drain]\n"
        "  golem evidence hash FILE\n"
        "  golem evidence put STORE FILE\n"
        "  golem evidence verify STORE SHA256\n"
        "  golem evidence verify-receipt STORE RECEIPT_SHA256\n"
        "  golem lineage verify STORE GRAPH_SHA256\n"
        "  golem lineage trace STORE GRAPH_SHA256 STAGE_SEQUENCE [--direct]\n"
        "  golem adapter noop probe [--format json|msgpack]\n"
        "  golem adapter noop run STORE [--format json|msgpack] < envelope\n"
        "  golem adapter convert json|msgpack json|msgpack < envelope\n"
        "STORE must be an existing directory; put initializes its CAS layout.\n", stderr);
    return 2;
}

int golem_cli_document(int argc, char **argv);
int golem_cli_discovery(int argc, char **argv);
int golem_cli_workflow(int argc, char **argv);
int golem_cli_agent_session(int argc, char **argv);
int golem_cli_execution(int argc, char **argv);
int golem_cli_reentry(int argc, char **argv);
int golem_cli_research(int argc, char **argv);
int golem_cli_completion(int argc, char **argv);
int main(int argc, char **argv)
{
    if (argc >= 2 && strcmp(argv[1], "journal") == 0) return golem_cli_journal(argc, argv);
    if(argc>=2 && strcmp(argv[1],"workflow")==0) return golem_cli_workflow(argc,argv);
    if(argc>=2 && strcmp(argv[1],"session")==0) return golem_cli_agent_session(argc,argv);
    if(argc>=2 && strcmp(argv[1],"execution")==0) return golem_cli_execution(argc,argv);
    if(argc>=2 && strcmp(argv[1],"reentry")==0) return golem_cli_reentry(argc,argv);
    if(argc>=2 && strcmp(argv[1],"research")==0) return golem_cli_research(argc,argv);
    if(argc>=2 && strcmp(argv[1],"completion")==0) return golem_cli_completion(argc,argv);
    if(argc>=2 && strcmp(argv[1],"discovery")==0) return golem_cli_discovery(argc,argv);
    if (argc >= 2 && (strcmp(argv[1], "work") == 0 || strcmp(argv[1], "document") == 0))
        return golem_cli_document(argc, argv);
    if (argc == 2 && strcmp(argv[1], "--help") == 0) { (void)usage(); return 0; }
    if (argc == 2 && strcmp(argv[1], "--version") == 0) { puts(GOLEM_VERSION_STRING); return 0; }
    if (argc >= 2 && (strcmp(argv[1], "init") == 0 || strcmp(argv[1], "capsule") == 0 ||
        strcmp(argv[1], "run") == 0 || strcmp(argv[1], "replay") == 0 || strcmp(argv[1], "cost") == 0)) return golem_cli_work(argc, argv);
    if (argc >= 2 && strcmp(argv[1], "adapter") == 0) return golem_cli_adapter(argc, argv);
    if (argc >= 2 && strcmp(argv[1], "daemon") == 0) return golem_cli_daemon(argc, argv);
    if (argc >= 2 && strcmp(argv[1], "lineage") == 0) return golem_cli_lineage(argc, argv);
    if (argc < 3 || strcmp(argv[1], "evidence") != 0) return usage();
    bool hash = strcmp(argv[2], "hash") == 0;
    bool put = strcmp(argv[2], "put") == 0;
    bool verify = strcmp(argv[2], "verify") == 0;
    bool receipt = strcmp(argv[2], "verify-receipt") == 0;
    if ((!hash && !put && !verify && !receipt) || argc != (hash ? 4 : 5)) return usage();
    golem_receipt result = {GOLEM_RECEIPT_VERSION, GOLEM_DIGEST_SHA256, 0, {{0}}};
    golem_digest receipt_key = {{0}};
    golem_status status;
    golem_evidence_store *store = NULL;
    if (hash) status = golem_digest_file(argv[3], &result, NULL);
    else {
        status = GOLEM_OK;
        golem_digest key;
        if (!put) status = golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])}, &key);
        if (status == GOLEM_OK) status = golem_evidence_open(argv[3], put, NULL, &store, NULL);
        if (status == GOLEM_OK && put) {
            status = golem_evidence_import(store, argv[4], &result, NULL);
            if (status == GOLEM_OK) status = golem_evidence_receipt_store(store, &result, &receipt_key, NULL);
        } else if (status == GOLEM_OK && receipt) {
            status = golem_evidence_receipt_verify(store, &key, &result, NULL);
        } else if (status == GOLEM_OK) {
            result.digest = key;
            status = golem_evidence_verify(store, &key, &result.size, NULL);
        }
    }
    golem_status closed = golem_evidence_close(store);
    if (status == GOLEM_OK) status = closed;
    if (status != GOLEM_OK) {
        fprintf(stderr, "golem: %s\n", golem_status_string(status));
        return 1;
    }
    char digest[GOLEM_DIGEST_HEX_CAPACITY], receipt_hex[GOLEM_DIGEST_HEX_CAPACITY];
    size_t required;
    (void)golem_digest_format(&result.digest, digest, sizeof(digest), &required);
    printf("{\"schema_version\":%u,\"algorithm\":\"sha256\",\"digest\":\"%s\",\"size\":%" PRIu64,
        (unsigned int)result.version, digest, result.size);
    if (put) {
        (void)golem_digest_format(&receipt_key, receipt_hex, sizeof(receipt_hex), &required);
        printf(",\"receipt_digest\":\"%s\"", receipt_hex);
    }
    if (verify || receipt) fputs(",\"verified\":true", stdout);
    puts("}");
    return fflush(stdout) == 0 && !ferror(stdout) ? 0 : 1;
}
