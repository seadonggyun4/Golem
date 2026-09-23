#include "work.h"
#include "golem/runtime_event.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int golem_cli_events(int argc, char **argv)
{
    if (argc != 4 && argc != 6)
        return 2;
    golem_runtime_event_format format;
    if (!strcmp(argv[3], "--jsonl"))
        format = GOLEM_RUNTIME_EVENTS_JSONL;
    else if (!strcmp(argv[3], "--otlp"))
        format = GOLEM_RUNTIME_EVENTS_OTLP;
    else if (!strcmp(argv[3], "--prov"))
        format = GOLEM_RUNTIME_EVENTS_PROV;
    else
        return 2;
    golem_runtime_cursor cursor, *after = NULL;
    if (argc == 6) {
        if (strcmp(argv[4], "--after") ||
            golem_runtime_cursor_parse((golem_string_view){argv[5], strlen(argv[5])}, &cursor) !=
                GOLEM_OK)
            return 2;
        after = &cursor;
    }
    golem_runtime_event records[GOLEM_RUNTIME_EVENT_PAGE_MAX];
    golem_runtime_event_page page;
    golem_status st = golem_runtime_events_snapshot(argv[2], NULL, after, records,
                                                    GOLEM_RUNTIME_EVENT_PAGE_MAX, &page);
    if (st == GOLEM_ERR_STALE_RESULT) {
        fprintf(stderr,
                "golem: stale event cursor; missed=%llu oldest=%llu newest=%llu; explicitly "
                "restart without --after\n",
                (unsigned long long)page.missed, (unsigned long long)page.oldest,
                (unsigned long long)page.newest);
        return 1;
    }
    size_t n = 0;
    uint8_t *bytes = NULL;
    if (st == GOLEM_OK) {
        st = golem_runtime_events_export(records, &page, format, NULL, 0, &n);
        if (st == GOLEM_ERR_BUFFER_TOO_SMALL) {
            bytes = malloc(n);
            st = bytes ? golem_runtime_events_export(records, &page, format, bytes, n, &n)
                       : GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    if (st == GOLEM_OK && (fwrite(bytes, 1, n, stdout) != n || fflush(stdout)))
        st = GOLEM_ERR_IO;
    free(bytes);
    if (st != GOLEM_OK)
        fprintf(stderr, "golem: %s\n", golem_status_string(st));
    return st == GOLEM_OK ? 0 : 1;
}
