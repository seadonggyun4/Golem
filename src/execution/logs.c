#include "internal.h"
#include <openssl/evp.h>
#include <string.h>

golem_status ex_retention(struct json_object *p)
{
    const char *keys[] = {"mode", "max_bytes", "redactor", "require_complete"};
    if (!dw_keys(p, keys, 4) ||
        !json_object_is_type(dw_get(p, "max_bytes"), json_type_int) ||
        !json_object_is_type(dw_get(p, "require_complete"), json_type_boolean))
        return GOLEM_ERR_PARSE;
    bool keep = !strcmp(dw_text(p, "mode"), "REDACTED_CAPTURE");
    uint64_t cap = dw_uint(p, "max_bytes");
    if (keep)
        return cap > 0 && cap <= GOLEM_SUPERVISOR_OUTPUT_MAX &&
                       !strcmp(dw_text(p, "redactor"), "mask-bytes-v1")
                   ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED;
    return !strcmp(dw_text(p, "mode"), "DISCARD") && cap == 0 &&
                   !strcmp(dw_text(p, "redactor"), "none") &&
                   !json_object_get_boolean(dw_get(p, "require_complete"))
               ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED;
}

void ex_logs_close(ex_log_capture *c)
{
    for (unsigned i = 0; i < 2; ++i) {
        EVP_MD_CTX_free(c->hash[i]);
        dw_scratch_free(c->store, c->retained[i]);
    }
    *c = (ex_log_capture){0};
}

golem_status ex_logs_open(golem_document_store *s, struct json_object *p, ex_log_capture *out)
{
    golem_status st = ex_retention(p);
    ex_log_capture c = {.store = s, .cap = (size_t)dw_uint(p, "max_bytes"),
                       .keep = !strcmp(dw_text(p, "mode"), "REDACTED_CAPTURE")};
    for (unsigned i = 0; st == GOLEM_OK && i < 2; ++i) {
        c.hash[i] = EVP_MD_CTX_new();
        if (!c.hash[i])
            st = GOLEM_ERR_OUT_OF_MEMORY;
        else if (EVP_DigestInit_ex(c.hash[i], EVP_sha256(), NULL) != 1)
            st = GOLEM_ERR_IO;
        if (st == GOLEM_OK && c.keep)
            st = dw_scratch(s, c.cap, &c.retained[i]);
    }
    if (st == GOLEM_OK)
        *out = c;
    else
        ex_logs_close(&c);
    return st;
}

golem_status ex_logs_write(void *context, unsigned stream, golem_bytes chunk)
{
    ex_log_capture *c = context;
    if (!c || stream > 1 || (!chunk.data && chunk.size))
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (chunk.size > UINT64_MAX - c->observed[stream])
        return GOLEM_ERR_OVERFLOW;
    if (EVP_DigestUpdate(c->hash[stream], chunk.data, chunk.size) != 1)
        return GOLEM_ERR_IO;
    c->observed[stream] += chunk.size;
    size_t take = chunk.size;
    if (take > c->cap - c->size[stream])
        take = c->cap - c->size[stream];
    /* Conservative versioned redaction: no raw byte, partial UTF-8 codepoint,
     * binary control sequence or cross-chunk secret can reach persistent storage.
     * Length is deliberately retained; this is not a diagnostic text sanitizer. */
    if (take)
        memset(c->retained[stream] + c->size[stream], '*', take);
    c->size[stream] += take;
    return GOLEM_OK;
}

golem_status ex_logs_finish(ex_log_capture *c, const golem_supervisor_capture *observed,
                           struct json_object **out, bool *complete)
{
    struct json_object *logs = json_object_new_array();
    golem_status st = logs ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
    bool all = true;
    for (unsigned i = 0; st == GOLEM_OK && i < 2; ++i) {
        golem_digest hash;
        unsigned n = 0;
        if (observed->observed_bytes[i] != c->observed[i]) {
            st = GOLEM_ERR_INCOMPLETE_WORK;
            break;
        }
        if (EVP_DigestFinal_ex(c->hash[i], hash.bytes, &n) != 1 || n != sizeof(hash.bytes)) {
            st = GOLEM_ERR_IO;
            break;
        }
        bool full = observed->spawned && observed->eof[i] && c->size[i] == c->observed[i];
        all = all && full && c->keep;
        struct json_object *o = json_object_new_object();
        if (!ex_text(o, "stream", i == 0 ? "stdout" : "stderr") ||
            !ex_text(o, "state", !c->keep ? "DISCARDED" : full ? "COMPLETE" : "TRUNCATED") ||
            !dw_add_digest(o, "observed_digest", &hash) ||
            !ex_uint(o, "observed_bytes", c->observed[i]) ||
            !ex_uint(o, "retained_bytes", c->size[i]) || !ex_uint(o, "offset", 0) ||
            !ex_uint(o, "cap_bytes", c->cap) ||
            !ex_uint(o, "dropped_observed_bytes", c->observed[i] - c->size[i]) ||
            !dw_add(o, "eof", json_object_new_boolean(observed->eof[i])) ||
            !dw_add(o, "total_bytes_known", json_object_new_boolean(observed->spawned && observed->eof[i])) ||
            !ex_text(o, "redactor", c->keep ? "mask-bytes-v1" : "none"))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        golem_receipt retained;
        golem_digest receipt;
        if (st == GOLEM_OK && c->keep)
            st = golem_evidence_put(c->store->cas,
                (golem_bytes){c->retained[i], c->size[i]}, &retained, NULL);
        if (st == GOLEM_OK && c->keep)
            st = golem_evidence_receipt_store(c->store->cas, &retained, &receipt, NULL);
        if (st == GOLEM_OK && c->keep && !dw_add_digest(o, "retained_receipt", &receipt))
            st = GOLEM_ERR_OUT_OF_MEMORY;
        if (st == GOLEM_OK) {
            if (!wf_append(logs, o))
                st = GOLEM_ERR_OUT_OF_MEMORY;
        } else
            json_object_put(o);
    }
    if (st == GOLEM_OK) {
        *out = logs;
        *complete = all;
    } else
        json_object_put(logs);
    return st;
}

golem_status ex_logs_verify(golem_document_store *s, struct json_object *gate,
                           struct json_object *policy)
{
    golem_status st = ex_retention(policy);
    struct json_object *logs = dw_get(gate, "logs");
    bool keep = !strcmp(dw_text(policy, "mode"), "REDACTED_CAPTURE");
    bool required = json_object_get_boolean(dw_get(policy, "require_complete"));
    if (st != GOLEM_OK || !ds_array(logs, 2, 2))
        return GOLEM_ERR_PARSE;
    for (unsigned i = 0; i < 2; ++i) {
        struct json_object *o = json_object_array_get_idx(logs, i);
        const char *keys[] = {"stream", "state", "observed_digest", "observed_bytes",
            "retained_bytes", "offset", "cap_bytes", "dropped_observed_bytes", "eof",
            "total_bytes_known", "redactor", "retained_receipt"};
        golem_digest hash;
        uint64_t seen = dw_uint(o, "observed_bytes"), size = dw_uint(o, "retained_bytes");
        bool eof = json_object_get_boolean(dw_get(o, "eof"));
        bool known = json_object_get_boolean(dw_get(o, "total_bytes_known"));
        bool full = known && eof && size == seen;
        if (!dw_keys(o, keys, keep ? 12 : 11) ||
            !json_object_is_type(dw_get(o, "eof"), json_type_boolean) ||
            !json_object_is_type(dw_get(o, "total_bytes_known"), json_type_boolean) ||
            strcmp(dw_text(o, "stream"), i ? "stderr" : "stdout") ||
            !dw_digest(o, "observed_digest", &hash) || size > seen ||
            dw_uint(o, "offset") != 0 || dw_uint(o, "cap_bytes") != dw_uint(policy, "max_bytes") ||
            size > dw_uint(policy, "max_bytes") || (!keep && size) ||
            dw_uint(o, "dropped_observed_bytes") != seen - size ||
            known != (eof && json_object_get_boolean(dw_get(gate, "spawned"))) ||
            strcmp(dw_text(o, "redactor"), dw_text(policy, "redactor")) ||
            strcmp(dw_text(o, "state"), !keep ? "DISCARDED" : full ? "COMPLETE" : "TRUNCATED"))
            return GOLEM_ERR_CORRUPT_JOURNAL;
        if (required && !full && !strcmp(dw_text(gate, "status"), "PASS"))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        if (keep) {
            golem_receipt receipt;
            if (!dw_digest(o, "retained_receipt", &hash))
                return GOLEM_ERR_PARSE;
            st = golem_evidence_receipt_verify(s->cas, &hash, &receipt, NULL);
            if (st != GOLEM_OK)
                return st;
            if (receipt.size != size)
                return GOLEM_ERR_DIGEST_MISMATCH;
        }
    }
    return GOLEM_OK;
}
