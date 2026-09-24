#include "candidate_host.h"
#include "work.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static golem_status load(const char *path, struct json_object **out)
{
    cli_blob bytes = {0};
    golem_status st = cli_read(path, GOLEM_DOCUMENT_MAX_JSON, &bytes);
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){bytes.data, bytes.size}, GOLEM_DOCUMENT_MAX_JSON, out);
    free(bytes.data);
    return st;
}
static bool matches(const char *value, const golem_digest *digest)
{
    golem_digest parsed;
    return golem_digest_parse((golem_string_view){value, strlen(value)}, &parsed) == GOLEM_OK &&
           dw_equal(&parsed, digest);
}

int golem_cli_candidate_host(int argc, char **argv)
{
    const char *op = argv[2];
    bool validate = !strcmp(op, "host-validate"), digest_only = !strcmp(op, "request-digest"),
         serve = !strcmp(op, "serve"), call = !strcmp(op, "call");
    if (((validate || digest_only) && argc != 4) ||
        (serve && (argc != 7 || strcmp(argv[5], "--approve-config"))) ||
        (call && (argc < 5 || argc > 9 || !(argc % 2))) ||
        (!validate && !digest_only && !serve && !call)) {
        fputs("usage: golem candidate host-validate CONFIG.json\n"
              "       golem candidate request-digest REQUEST.json\n"
              "       golem candidate serve CONFIG.json SOCKET --approve-config SHA256\n"
              "       golem candidate call SOCKET REQUEST.json [--approve-request SHA256]\n"
              "             [--attest-termination REQUEST_SHA256]\n",
              stderr);
        return 2;
    }
    struct json_object *object = NULL, *reply = NULL, *envelope = NULL;
    golem_status st = load(call ? argv[4] : argv[3], &object);
    if (st == GOLEM_OK && (validate || serve))
        st = ch_validate(object);
    golem_digest digest;
    if (st == GOLEM_OK)
        st = ex_hash(object, &digest);
    if (st == GOLEM_OK && serve && !matches(argv[6], &digest))
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    if (st == GOLEM_OK && serve)
        st = ch_serve(object, argv[4]);
    if (st == GOLEM_OK && call) {
        const char *approval = "", *attestation = "";
        for (int i = 5; st == GOLEM_OK && i < argc; i += 2) {
            const char **field = !strcmp(argv[i], "--approve-request")      ? &approval
                                 : !strcmp(argv[i], "--attest-termination") ? &attestation
                                                                            : NULL;
            if (!field || **field || !matches(argv[i + 1], &digest))
                st = GOLEM_ERR_APPROVAL_REQUIRED;
            else
                *field = argv[i + 1];
        }
        envelope = json_object_new_object();
        if (st == GOLEM_OK && (!envelope || !ex_uint(envelope, "schema_version", 1) ||
                               !dw_add(envelope, "request", json_object_get(object)) ||
                               !ex_text(envelope, "approval", approval) ||
                               !ex_text(envelope, "termination_attestation", attestation)))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK)
            st = ch_client(argv[3], envelope, &reply);
        const char *keys[] = {"status", "result"};
        if (st == GOLEM_OK && (!dw_keys(reply, keys, 2) ||
                               !json_object_is_type(dw_get(reply, "status"), json_type_int)))
            st = GOLEM_ERR_PARSE;
        if (st == GOLEM_OK)
            st = (golem_status)dw_uint(reply, "status");
    }
    if (st == GOLEM_OK && (validate || digest_only)) {
        char hex[65];
        size_t needed;
        st = golem_digest_format(&digest, hex, sizeof(hex), &needed);
        if (st == GOLEM_OK && puts(hex) < 0)
            st = GOLEM_ERR_IO;
    } else if (st == GOLEM_OK && call) {
        const char *text =
            json_object_to_json_string_ext(dw_get(reply, "result"), JSON_C_TO_STRING_PLAIN);
        if (!text || puts(text) < 0)
            st = GOLEM_ERR_IO;
    }
    json_object_put(envelope);
    json_object_put(reply);
    json_object_put(object);
    return st == GOLEM_OK ? 0 : cli_emit(st, NULL);
}
