#include "internal.h"
#include "golem/lineage.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

static int usage(void)
{
    fputs("Usage:\n  golem lineage verify STORE GRAPH_SHA256\n"
        "  golem lineage trace STORE GRAPH_SHA256 STAGE_SEQUENCE [--direct]\n", stderr);
    return 2;
}
static bool sequence_parse(const char *text, uint64_t *out)
{
    if (*text == '\0') return false;
    uint64_t value = 0;
    for (; *text != '\0'; ++text) {
        if (*text < '0' || *text > '9') return false;
        unsigned int digit = (unsigned int)(*text - '0');
        if (value > (UINT64_MAX - digit) / 10) return false;
        value = value * 10 + digit;
    }
    if (value == 0) return false;
    *out = value; return true;
}

int golem_cli_lineage(int argc, char **argv)
{
    if (argc < 3) return usage();
    bool trace = strcmp(argv[2], "trace") == 0;
    bool verify = strcmp(argv[2], "verify") == 0;
    bool direct = argc == 7 && strcmp(argv[6], "--direct") == 0;
    if ((!trace && !verify) || (verify && argc != 5) || (trace && argc != 6 && !(argc == 7 && direct))) return usage();
    uint64_t sequence = 0;
    if (trace && !sequence_parse(argv[5], &sequence)) return usage();
    golem_digest key;
    golem_status status = golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])}, &key);
    golem_evidence_store *store = NULL;
    golem_lineage *g = NULL;
    golem_lineage_id *ids = NULL;
    if (status == GOLEM_OK) status = golem_evidence_open(argv[3], false, NULL, &store, NULL);
    if (status == GOLEM_OK) status = golem_lineage_load(store, &key, NULL, &g, NULL);
    golem_status closed = golem_evidence_close(store);
    if (status == GOLEM_OK) status = closed;
    size_t count = 0;
    if (status == GOLEM_OK && trace) {
        status = golem_lineage_predecessors(g, sequence, !direct, NULL, 0, &count);
        if (status == GOLEM_ERR_BUFFER_TOO_SMALL) {
            void *memory = NULL;
            status = golem_allocator_alloc(NULL, count * sizeof(*ids), &memory);
            ids = memory;
            if (status == GOLEM_OK) status = golem_lineage_predecessors(g, sequence, !direct, ids, count, &count);
        }
    }
    if (status != GOLEM_OK) {
        fprintf(stderr, "golem: %s\n", golem_status_string(status));
        golem_lineage_free(g); (void)golem_allocator_free(NULL, ids); return 1;
    }
    golem_lineage_stats stats;
    (void)golem_lineage_stats_get(g, &stats);
    printf("{\"schema_version\":1,\"graph_digest\":\"%s\",\"verified\":true,\"stages\":%" PRIu32
        ",\"nodes\":%" PRIu32 ",\"edges\":%" PRIu32, argv[4], stats.stages, stats.nodes, stats.edges);
    if (trace) {
        printf(",\"stage_sequence\":%" PRIu64 ",\"transitive\":%s,\"predecessors\":[", sequence, direct ? "false" : "true");
        for (size_t i = 0; i < count; ++i) {
            golem_lineage_node node; golem_lineage_stage stage;
            (void)golem_lineage_node_get(g, ids[i], &node);
            (void)golem_lineage_stage_get(g, node.stage_sequence, &stage);
            char hex[65]; size_t required;
            (void)golem_digest_format(&node.content.digest, hex, sizeof(hex), &required);
            printf("%s{\"node_id\":%" PRIu32 ",\"stage\":\"%s\",\"sequence\":%" PRIu64
                ",\"attempt\":%" PRIu32 ",\"digest\":\"%s\",\"size\":%" PRIu64 "}", i == 0 ? "" : ",",
                ids[i], golem_stage_name(stage.execution.stage), node.stage_sequence, stage.execution.attempt, hex, node.content.size);
        }
        putchar(']');
    }
    puts("}");
    golem_lineage_free(g); (void)golem_allocator_free(NULL, ids);
    return fflush(stdout) == 0 && !ferror(stdout) ? 0 : 1;
}
