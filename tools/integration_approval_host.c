#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "golem/approval.h"
#include <fcntl.h>
#include <inttypes.h>
#include <json-c/json.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Owner-controlled, same-UID cooperative adapter, not an authentication server.
 * Every callback re-reads the separately reviewed decision and admission pins. */
typedef struct authority {
    const char *decision_path;
    golem_digest decision_digest;
    const char *guard_path;
    golem_digest guard_digest;
} authority;

static golem_status digest(const char *text, golem_digest *out)
{
    return text ? golem_digest_parse((golem_string_view){text, strlen(text)}, out)
                : GOLEM_ERR_POLICY_DENIED;
}

static const char *text(struct json_object *object, const char *key)
{
    struct json_object *value = NULL;
    if (!json_object_object_get_ex(object, key, &value) ||
        !json_object_is_type(value, json_type_string))
        return NULL;
    return json_object_get_string(value);
}

static bool equal(const golem_digest *a, const golem_digest *b)
{
    return memcmp(a->bytes, b->bytes, GOLEM_DIGEST_SIZE) == 0;
}

static golem_status private_bytes(const char *path, size_t limit, const golem_digest *pin,
                                   uint8_t **out, size_t *size)
{
    golem_receipt receipt;
    golem_status st = golem_digest_file(path, &receipt, NULL);
    if (st != GOLEM_OK || (pin && !equal(&receipt.digest, pin)))
        return GOLEM_ERR_POLICY_DENIED;
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK);
    struct stat before, after;
    uint8_t *data = NULL;
    if (fd < 0 || fstat(fd, &before) || !S_ISREG(before.st_mode) || before.st_nlink != 1 ||
        before.st_uid != getuid() || (before.st_mode & 077) || before.st_size < 0 ||
        (uint64_t)before.st_size > limit) {
        if (fd >= 0)
            close(fd);
        return GOLEM_ERR_POLICY_DENIED;
    }
    size_t n = (size_t)before.st_size, used = 0;
    data = malloc(n + 1);
    if (!data) {
        close(fd);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    while (used < n) {
        ssize_t got = read(fd, data + used, n - used);
        if (got <= 0)
            break;
        used += (size_t)got;
    }
    golem_digest actual;
    if (used != n || fstat(fd, &after) || before.st_dev != after.st_dev ||
        before.st_ino != after.st_ino || before.st_size != after.st_size ||
        before.st_mode != after.st_mode || before.st_uid != after.st_uid || after.st_nlink != 1 ||
        before.st_mtime != after.st_mtime || before.st_ctime != after.st_ctime ||
        golem_digest_bytes((golem_bytes){data, n}, &actual) != GOLEM_OK ||
        !equal(&actual, &receipt.digest))
        st = GOLEM_ERR_POLICY_DENIED;
    close(fd);
    if (st != GOLEM_OK) {
        free(data);
        return st;
    }
    data[n] = 0;
    *out = data;
    *size = n;
    return GOLEM_OK;
}

static golem_status object(const char *path, const golem_digest *pin, struct json_object **out)
{
    uint8_t *data = NULL;
    size_t size = 0;
    golem_status st = private_bytes(path, 16384, pin, &data, &size);
    struct json_tokener *parser = json_tokener_new_ex(12);
    if (st == GOLEM_OK && parser) {
        json_tokener_set_flags(parser, JSON_TOKENER_STRICT | JSON_TOKENER_VALIDATE_UTF8);
        *out = json_tokener_parse_ex(parser, (const char *)data, (int)size);
        if (json_tokener_get_error(parser) != json_tokener_success ||
            json_tokener_get_parse_end(parser) != size || !json_object_is_type(*out, json_type_object))
            st = GOLEM_ERR_POLICY_DENIED;
    } else if (st == GOLEM_OK)
        st = GOLEM_ERR_OUT_OF_MEMORY;
    json_tokener_free(parser);
    free(data);
    return st;
}

static golem_status guards(authority *a)
{
    if (!a->guard_path)
        return GOLEM_OK;
    struct json_object *root = NULL, *pins = NULL;
    golem_status st = object(a->guard_path, &a->guard_digest, &root);
    if (st == GOLEM_OK && (json_object_object_length(root) != 1 ||
        !json_object_object_get_ex(root, "pins", &pins) || !json_object_is_type(pins, json_type_array) ||
        json_object_array_length(pins) < 3 || json_object_array_length(pins) > 16))
        st = GOLEM_ERR_POLICY_DENIED;
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(pins); ++i) {
        struct json_object *p = json_object_array_get_idx(pins, i);
        golem_digest pin;
        uint8_t *data = NULL;
        size_t n = 0;
        if (!json_object_is_type(p, json_type_object) || json_object_object_length(p) != 2 ||
            !text(p, "path") || digest(text(p, "sha256"), &pin) != GOLEM_OK)
            st = GOLEM_ERR_POLICY_DENIED;
        else
            st = private_bytes(text(p, "path"), GOLEM_DOCUMENT_MAX_JSON, &pin, &data, &n);
        free(data);
    }
    json_object_put(root);
    return st;
}

static golem_status decision(authority *a, const golem_digest *action,
                              golem_digest *issuer, uint64_t *epoch)
{
    struct json_object *root = NULL, *e = NULL;
    golem_digest expected;
    golem_status st = guards(a);
    if (st == GOLEM_OK)
        st = object(a->decision_path, &a->decision_digest, &root);
    if (st == GOLEM_OK && (json_object_object_length(root) != 5 ||
        !text(root, "schema") || strcmp(text(root, "schema"), "golem.integration-local-decision.v1") ||
        !text(root, "operation") || strcmp(text(root, "operation"), "approve") ||
        digest(text(root, "action_digest"), &expected) != GOLEM_OK || !equal(action, &expected) ||
        digest(text(root, "issuer"), issuer) != GOLEM_OK ||
        !json_object_object_get_ex(root, "policy_epoch", &e) || !json_object_is_type(e, json_type_int) ||
        json_object_get_int64(e) < 1 || json_object_get_uint64(e) > UINT64_C(9007199254740991)))
        st = GOLEM_ERR_POLICY_DENIED;
    if (st == GOLEM_OK) {
        *epoch = json_object_get_uint64(e);
        char canonical[512];
        int count = snprintf(canonical, sizeof(canonical),
            "{\"action_digest\":\"%s\",\"issuer\":\"%s\",\"operation\":\"approve\","
            "\"policy_epoch\":%" PRIu64 ",\"schema\":\"golem.integration-local-decision.v1\"}\n",
            text(root, "action_digest"), text(root, "issuer"), *epoch);
        uint8_t *data = NULL;
        size_t n = 0;
        st = private_bytes(a->decision_path, 16384, &a->decision_digest, &data, &n);
        if (st == GOLEM_OK && (count < 0 || (size_t)count >= sizeof(canonical) || n != (size_t)count ||
                               memcmp(data, canonical, n)))
            st = GOLEM_ERR_POLICY_DENIED;
        free(data);
    }
    json_object_put(root);
    return st;
}

static golem_status decide(void *context, const golem_digest *action, const char *operation,
                            golem_digest *issuer, uint64_t *epoch)
{
    return strcmp(operation, "approve") ? GOLEM_ERR_POLICY_DENIED
                                         : decision(context, action, issuer, epoch);
}

static golem_status recheck(void *context, const golem_digest *action,
                             const golem_digest *issuer, uint64_t epoch)
{
    golem_digest current;
    uint64_t observed = 0;
    golem_status st = decision(context, action, &current, &observed);
    return st == GOLEM_OK && equal(&current, issuer) && epoch == observed ? GOLEM_OK
                                                                        : GOLEM_ERR_POLICY_DENIED;
}

int main(int argc, char **argv)
{
    if (argc != 11 || (strcmp(argv[1], "approve") && strcmp(argv[1], "execute"))) {
        fputs("usage: golem-integration-host approve|execute WORK REQUEST DECISION DECISION_SHA RECEIPT CONTRACT SHELL GUARD GUARD_SHA\n", stderr);
        return 2;
    }
    bool execute = !strcmp(argv[1], "execute");
    authority a = {.decision_path = argv[4]};
    golem_status st = digest(argv[5], &a.decision_digest);
    if (st == GOLEM_OK && execute) {
        a.guard_path = argv[9];
        st = digest(argv[10], &a.guard_digest);
    }
    uint8_t *request = NULL;
    size_t n = 0;
    if (st == GOLEM_OK)
        st = private_bytes(argv[3], GOLEM_DOCUMENT_MAX_JSON, NULL, &request, &n);
    if (st == GOLEM_OK && !execute) {
        st = golem_approval_request_validate((golem_bytes){request, n});
        if (st == GOLEM_OK) {
            struct json_object *approved_request = json_tokener_parse((const char *)request);
            const char *operation = approved_request ? text(approved_request, "operation") : NULL;
            if (!operation || strcmp(operation, "approve"))
                st = GOLEM_ERR_POLICY_DENIED;
            json_object_put(approved_request);
        }
    }
    golem_digest receipt, contract, shell;
    golem_execution_approval approval = {.struct_size = sizeof(approval), .version = 1};
    if (st == GOLEM_OK && execute) {
        st = digest(argv[6], &receipt);
        if (st == GOLEM_OK)
            st = digest(argv[7], &contract);
        approval.contract = &contract;
        if (strcmp(argv[8], "-")) {
            if (st == GOLEM_OK)
                st = digest(argv[8], &shell);
            approval.shell_contract = &shell;
        }
    }
    golem_approval_host host = {sizeof(host), 1, decide, recheck, &a};
    golem_execution_reply out = {0};
    golem_document_store *store = NULL;
    golem_diagnostic diagnostic;
    (void)golem_diagnostic_clear(&diagnostic);
    if (st == GOLEM_OK)
        st = golem_document_store_open(argv[2], true, NULL, &store, &diagnostic);
    if (st == GOLEM_OK)
        st = execute ? golem_execution_call_receipted(store, (golem_bytes){request, n}, &receipt,
                        &host, &approval, &out, &diagnostic)
                     : golem_approval_call(store, (golem_bytes){request, n}, &host, NULL, &out, &diagnostic);
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK)
        st = closed;
    if (st == GOLEM_OK && (fwrite(out.data, 1, out.size, stdout) != out.size || fputc('\n', stdout) == EOF))
        st = GOLEM_ERR_IO;
    if (st != GOLEM_OK) {
        struct json_object *error = json_object_new_object();
        if (error) {
            json_object_object_add(error, "schema", json_object_new_string("golem.integration-host-error.v1"));
            json_object_object_add(error, "code", json_object_new_int((int)st));
            json_object_object_add(error, "diagnostic", json_object_new_string(diagnostic.message));
            fprintf(stderr, "%s\n", json_object_to_json_string_ext(error, JSON_C_TO_STRING_PLAIN));
            json_object_put(error);
        }
    }
    golem_execution_reply_free(&out);
    free(request);
    return st == GOLEM_OK ? 0 : 1;
}
