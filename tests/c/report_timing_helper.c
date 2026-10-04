#define _POSIX_C_SOURCE 200809L
#include "../../src/reentry/internal.h"
#include "../../src/agent_session/internal.h"
#include "test.h"
#include <string.h>
#include <errno.h>

/* Override the renderer's stream allocation only in this test translation unit.
 * Defining the store entrypoints here leaves the library's store object unused. */
static bool fail_render;
static FILE *report_stream(char **data, size_t *size)
{
    if (fail_render) { errno = ENOMEM; return NULL; }
    return open_memstream(data, size);
}
#define open_memstream report_stream
#include "../../src/reentry/store.c"
#undef open_memstream

/* Synthetic historical writer, never linked into the CLI. */
int main(int argc, char **argv)
{
    CHECK(argc == 4);
    fail_render = !strcmp(argv[1], "deferred") || !strcmp(argv[1], "failed-render");
    golem_document_store *s = NULL;
    CHECK(golem_document_store_open(argv[2], strcmp(argv[1], "read") != 0, NULL, &s, NULL) == GOLEM_OK);
    if (!strcmp(argv[1], "failed-render")) {
        golem_execution_reply out = {(uint8_t *)"unchanged", 9};
        CHECK(golem_reentry_report(s, (uint32_t)atoi(argv[3]), false, &out, NULL) == GOLEM_ERR_OUT_OF_MEMORY);
        CHECK(out.size == 9 && !memcmp(out.data, "unchanged", 9));
    } else if (!strcmp(argv[1], "deferred")) {
        struct json_object *r = json_object_from_file(argv[3]);
        CHECK(r != NULL);
        const char *text = json_object_to_json_string_ext(r, JSON_C_TO_STRING_PLAIN);
        golem_execution_reply out = {0};
        CHECK(golem_reentry_call(s, (golem_bytes){(const uint8_t *)text, strlen(text)}, &out, NULL) == GOLEM_OK);
        CHECK(fwrite(out.data, 1, out.size, stdout) == out.size);
        golem_execution_reply_free(&out);
        json_object_put(r);
        CHECK(golem_document_store_close(s) == GOLEM_OK);
        CHECK(golem_document_store_open(argv[2], false, NULL, &s, NULL) == GOLEM_OK);
    } else if (!strcmp(argv[1], "read")) {
        golem_execution_reply out = {0};
        CHECK(golem_reentry_report(s, (uint32_t)atoi(argv[3]), false, &out, NULL) == GOLEM_OK);
        CHECK(fwrite(out.data, 1, out.size, stdout) == out.size);
        golem_execution_reply_free(&out);
    } else {
        struct json_object *r = json_object_from_file(argv[3]), *d = NULL;
        CHECK(r != NULL && re_validate(r) == GOLEM_OK);
        uint64_t now;
        golem_digest boot, payload, frame;
        CHECK(as_clock_read(NULL, &now, &boot) == GOLEM_OK);
        CHECK(re_decide(s, r, now, &boot, &d) == GOLEM_OK);
        struct json_object *e = json_object_new_object();
        bool legacy = !strcmp(argv[1], "legacy");
        CHECK(ex_uint(e, "schema_version", legacy ? 1 : 2));
        CHECK(ex_text(e, "type", "reentry"));
        CHECK(dw_add(e, "request", json_object_get(r)));
        CHECK(dw_add(e, "decision", json_object_get(d)));
        if (legacy) {
            golem_execution_reply md = {0};
            golem_receipt receipt;
            CHECK(re_markdown(d, &md) == GOLEM_OK);
            CHECK(golem_evidence_put(s->cas, (golem_bytes){md.data, md.size}, &receipt, NULL) == GOLEM_OK);
            CHECK(dw_add_digest(e, "report_digest", &receipt.digest));
            golem_execution_reply_free(&md);
        } else {
            CHECK(ex_uint(e, "renderer_version", !strcmp(argv[1], "future") ? 999 : 1));
            if (!strcmp(argv[1], "tampered")) CHECK(ex_text(d, "action", "DONE"));
        }
        CHECK(dw_put_json(s, e, &payload) == GOLEM_OK);
        CHECK(dw_event_write(s, &payload, &frame) == GOLEM_OK);
        json_object_put(e);
        json_object_put(d);
        json_object_put(r);
    }
    CHECK(golem_document_store_close(s) == GOLEM_OK);
    return 0;
}
