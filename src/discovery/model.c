#include "internal.h"
#include <ctype.h>
#include <string.h>

bool ds_array(struct json_object *a, size_t min, size_t max)
{
    return json_object_is_type(a, json_type_array) && json_object_array_length(a) >= min &&
           json_object_array_length(a) <= max;
}
bool ds_prose(struct json_object *o, const char *key)
{
    const char *s = dw_text(o, key);
    size_t n = 0;
    for (; *s; ++s)
        if ((unsigned char)*s > 32)
            ++n;
    return n >= 4 && n <= 8192;
}
bool ds_path(const char *p)
{
    if (!p || !*p || *p == '/' || strlen(p) > 512)
        return false;
    const char *deny[] = {".git",    ".golem",      ".ssh",         ".aws",        ".env",
                          "build",   "dist",        "node_modules", "__pycache__", ".cache",
                          "secrets", "credentials", "project-docs", ".envrc",      ".netrc",
                          ".npmrc",  ".pypirc",     "id_rsa",       "id_ed25519",  "id_ecdsa",
                          "target",  ".venv",       "venv",         ".next",       "coverage"};
    while (*p) {
        const char *q = strchr(p, '/');
        size_t n = q ? (size_t)(q - p) : strlen(p);
        if (!n || n > 255 || (n == 1 && *p == '.') || (n == 2 && memcmp(p, "..", 2) == 0))
            return false;
        for (size_t i = 0; i < n; ++i)
            if ((unsigned char)p[i] < 32 || p[i] == '\\' || p[i] == 127)
                return false;
        for (size_t i = 0; i < sizeof(deny) / sizeof(*deny); ++i) {
            size_t z = strlen(deny[i]);
            if (n >= z) {
                bool match = true;
                for (size_t j = 0; j < z; ++j)
                    if (tolower((unsigned char)p[j]) != deny[i][j])
                        match = false;
                if (match && (n == z || p[z] == '.'))
                    return false;
            }
        }
        if (n >= 4 && p[n - 4] == '.') {
            char ext[4] = {(char)tolower((unsigned char)p[n - 3]),
                           (char)tolower((unsigned char)p[n - 2]),
                           (char)tolower((unsigned char)p[n - 1]), 0};
            if (strcmp(ext, "pem") == 0 || strcmp(ext, "key") == 0 || strcmp(ext, "p12") == 0 ||
                strcmp(ext, "pfx") == 0)
                return false;
        }
        if (!q)
            return true;
        p = q + 1;
        if (!*p)
            return false;
    }
    return false;
}
static bool choice(const char *s, const char *a, const char *b, const char *c)
{
    return strcmp(s, a) == 0 || strcmp(s, b) == 0 || strcmp(s, c) == 0;
}
static struct json_object *find(struct json_object *a, const char *id)
{
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        struct json_object *v = json_object_array_get_idx(a, i);
        if (strcmp(dw_text(v, "id"), id) == 0)
            return v;
    }
    return NULL;
}
static bool ids(struct json_object *a)
{
    for (size_t i = 0; i < json_object_array_length(a); ++i) {
        const char *id = dw_text(json_object_array_get_idx(a, i), "id");
        if (!dw_id(id))
            return false;
        for (size_t j = 0; j < i; ++j)
            if (strcmp(id, dw_text(json_object_array_get_idx(a, j), "id")) == 0)
                return false;
    }
    return true;
}
static bool hex(const char *s, size_t n)
{
    if (strlen(s) != n)
        return false;
    for (size_t i = 0; i < n; ++i)
        if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f')))
            return false;
    return true;
}
static bool boolean(struct json_object *o, const char *key)
{
    return json_object_is_type(dw_get(o, key), json_type_boolean);
}
static bool date(const char *s)
{
    if (strlen(s) != 10 || s[4] != '-' || s[7] != '-')
        return false;
    for (size_t i = 0; i < 10; ++i)
        if (i != 4 && i != 7 && (s[i] < '0' || s[i] > '9'))
            return false;
    unsigned y = (unsigned)(s[0] - '0') * 1000 + (unsigned)(s[1] - '0') * 100 +
                 (unsigned)(s[2] - '0') * 10 + (unsigned)(s[3] - '0');
    unsigned m = (unsigned)(s[5] - '0') * 10 + (unsigned)(s[6] - '0'),
             d = (unsigned)(s[8] - '0') * 10 + (unsigned)(s[9] - '0');
    unsigned days[] = {0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (!y || !m || m > 12)
        return false;
    if (m == 2 && y % 4 == 0 && (y % 100 != 0 || y % 400 == 0))
        ++days[2];
    return d > 0 && d <= days[m];
}
static bool url(const char *s)
{
    if (strncmp(s, "https://", 8) != 0 || !s[8] || strlen(s) > 2048)
        return false;
    for (const char *p = s + 8; *p; ++p)
        if ((unsigned char)*p <= 32 || *p == '@' || *p == '\\' || *p == 127)
            return false;
    return s[8] != '/' && s[8] != '?' && s[8] != '#';
}
static bool snapshot(struct json_object *s)
{
    const char *keys[] = {"schema_version", "capture", "repositories"};
    struct json_object *repos = dw_get(s, "repositories");
    if (!dw_keys(s, keys, 3) || dw_uint(s, "schema_version") != 1 ||
        strcmp(dw_text(s, "capture"), "allowlist-read-only") != 0 ||
        !ds_array(repos, 1, GOLEM_DISCOVERY_MAX_REPOSITORIES) || !ids(repos))
        return false;
    uint64_t bytes = 0;
    for (size_t i = 0; i < json_object_array_length(repos); ++i) {
        struct json_object *r = json_object_array_get_idx(repos, i), *files = dw_get(r, "files");
        const char *rk[] = {"id",        "root_identity",     "head", "index_digest", "files",
                            "toolchain", "test_configuration"};
        golem_digest d;
        if (!dw_keys(r, rk, 7) || !dw_digest(r, "root_identity", &d) ||
            !dw_digest(r, "index_digest", &d) ||
            !(hex(dw_text(r, "head"), 40) || hex(dw_text(r, "head"), 64)) ||
            !ds_prose(r, "toolchain") || !ds_prose(r, "test_configuration") ||
            !ds_array(files, 1, 64))
            return false;
        for (size_t j = 0; j < json_object_array_length(files); ++j) {
            struct json_object *f = json_object_array_get_idx(files, j);
            const char *fk[] = {"path", "digest", "size", "tracked", "dirty"};
            if (!dw_keys(f, fk, 5) || !ds_path(dw_text(f, "path")) || !dw_digest(f, "digest", &d) ||
                dw_uint(f, "size") > GOLEM_DISCOVERY_MAX_FILE_BYTES || !boolean(f, "tracked") ||
                !boolean(f, "dirty"))
                return false;
            bytes += dw_uint(f, "size");
            for (size_t k = 0; k < j; ++k)
                if (strcmp(dw_text(f, "path"),
                           dw_text(json_object_array_get_idx(files, k), "path")) == 0)
                    return false;
        }
    }
    return bytes <= GOLEM_DISCOVERY_MAX_TOTAL_BYTES;
}
golem_status ds_validate(struct json_object *o, golem_discovery_result *out)
{
    const char *keys[] = {"schema_version", "work_id",  "snapshot",   "questions",
                          "references",     "findings", "selections", "permission",
                          "scope_revision", "non_goals"};
    if (!dw_keys(o, keys, 10))
        return GOLEM_ERR_PARSE;
    if (dw_uint(o, "schema_version") != 1 || dw_uint(o, "scope_revision") != 1)
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    struct json_object *qs = dw_get(o, "questions"), *refs = dw_get(o, "references"),
                       *fs = dw_get(o, "findings"), *ss = dw_get(o, "selections");
    if (!dw_id(dw_text(o, "work_id")) || !snapshot(dw_get(o, "snapshot")) ||
        !ds_prose(o, "non_goals") || !choice(dw_text(o, "permission"), "ALLOW", "ASK", "DENY") ||
        !ds_array(qs, 1, 64) || !ds_array(refs, 0, 64) || !ds_array(fs, 1, 64) ||
        !ds_array(ss, 1, 64) || !ids(qs) || !ids(refs) || !ids(fs) ||
        json_object_array_length(fs) != json_object_array_length(ss))
        return GOLEM_ERR_PARSE;
    golem_discovery_result result = {0};
    bool answered = true;
    for (size_t i = 0; i < json_object_array_length(qs); ++i) {
        struct json_object *q = json_object_array_get_idx(qs, i);
        const char *qk[] = {"id",
                            "question",
                            "requirement_id",
                            "source_budget",
                            "seconds_budget",
                            "elapsed_seconds",
                            "status",
                            "conclusion",
                            "search_strategy",
                            "omissions",
                            "eligibility"};
        const char *status = dw_text(q, "status");
        if (!dw_keys(q, qk, 11) || !ds_prose(q, "question") || !ds_prose(q, "eligibility") ||
            !dw_id(dw_text(q, "requirement_id")) || dw_uint(q, "source_budget") < 1 ||
            dw_uint(q, "source_budget") > 64 || dw_uint(q, "seconds_budget") < 1 ||
            dw_uint(q, "seconds_budget") > 86400 || dw_uint(q, "elapsed_seconds") > 86400 ||
            !ds_prose(q, "conclusion") || !ds_prose(q, "search_strategy") ||
            !ds_prose(q, "omissions") ||
            !(choice(status, "ANSWERED", "BUDGET_EXHAUSTED", "OFFLINE") ||
              strcmp(status, "OPEN") == 0))
            return GOLEM_ERR_PARSE;
        size_t count = 0, adopted = 0;
        for (size_t j = 0; j < json_object_array_length(refs); ++j) {
            struct json_object *r = json_object_array_get_idx(refs, j);
            if (strcmp(dw_text(r, "question_id"), dw_text(q, "id")) == 0) {
                ++count;
                if (strcmp(dw_text(r, "decision"), "ADOPT") == 0)
                    ++adopted;
            }
        }
        if (count > dw_uint(q, "source_budget"))
            return GOLEM_ERR_BUDGET_EXHAUSTED;
        if (strcmp(status, "ANSWERED") == 0 &&
            (!adopted || dw_uint(q, "elapsed_seconds") > dw_uint(q, "seconds_budget")))
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        if (strcmp(status, "BUDGET_EXHAUSTED") == 0 && count < dw_uint(q, "source_budget") &&
            dw_uint(q, "elapsed_seconds") < dw_uint(q, "seconds_budget"))
            return GOLEM_ERR_PARSE;
        if (strcmp(status, "ANSWERED") != 0)
            answered = false;
    }
    for (size_t i = 0; i < json_object_array_length(refs); ++i) {
        struct json_object *r = json_object_array_get_idx(refs, i);
        const char *rk[] = {
            "id",          "question_id",    "url",         "title",           "authors",
            "version",     "published",      "accessed",    "read_scope",      "locator",
            "claim",       "applicability",  "limitations", "counterevidence", "decision",
            "source_type", "decision_reason"};
        const char *read = dw_text(r, "read_scope");
        const char *type = dw_text(r, "source_type");
        if (!dw_keys(r, rk, 17) || !ds_prose(r, "decision_reason") ||
            !(choice(type, "STANDARD", "OFFICIAL_DOC", "PAPER") || strcmp(type, "BOOK") == 0 ||
              strcmp(type, "OTHER") == 0) ||
            !find(qs, dw_text(r, "question_id")) || !url(dw_text(r, "url")) ||
            !ds_prose(r, "title") || !ds_prose(r, "authors") || !*dw_text(r, "version") ||
            !(date(dw_text(r, "published")) || strcmp(dw_text(r, "published"), "unknown") == 0) ||
            !date(dw_text(r, "accessed")) || !ds_prose(r, "locator") || !ds_prose(r, "claim") ||
            !ds_prose(r, "applicability") || !ds_prose(r, "limitations") ||
            !ds_prose(r, "counterevidence") ||
            !(choice(read, "UNREAD", "ABSTRACT", "EXCERPT") || strcmp(read, "FULL_TEXT") == 0) ||
            !choice(dw_text(r, "decision"), "ADOPT", "REJECT", "DEFER"))
            return GOLEM_ERR_PARSE;
        if (strcmp(read, "UNREAD") == 0 && strcmp(dw_text(r, "decision"), "ADOPT") == 0)
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        for (size_t j = 0; j < i; ++j) {
            struct json_object *prior = json_object_array_get_idx(refs, j);
            if (strcmp(dw_text(prior, "url"), dw_text(r, "url")) == 0 &&
                strcmp(dw_text(prior, "version"), dw_text(r, "version")) == 0 &&
                strcmp(dw_text(prior, "question_id"), dw_text(r, "question_id")) == 0)
                return GOLEM_ERR_PARSE;
        }
        if (strcmp(read, "FULL_TEXT") == 0)
            ++result.full_text_references;
    }
    for (size_t i = 0; i < json_object_array_length(fs); ++i) {
        struct json_object *f = json_object_array_get_idx(fs, i),
                           *repro = dw_get(f, "reproduction"), *rr = dw_get(f, "reference_ids");
        const char *fk[] = {"id",           "status",        "observation", "hypothesis",
                            "uncertainty",  "repository_id", "path",        "requirement_id",
                            "reproduction", "reference_ids", "rationale"};
        const char *pk[] = {"command", "expected", "actual", "result", "evidence_digest"};
        struct json_object *repo =
            find(dw_get(dw_get(o, "snapshot"), "repositories"), dw_text(f, "repository_id"));
        if (!dw_keys(f, fk, 11) ||
            !choice(dw_text(f, "status"), "CONFIRMED", "UNCONFIRMED", "NOT_APPLICABLE") ||
            !ds_prose(f, "observation") || !ds_prose(f, "hypothesis") ||
            !ds_prose(f, "uncertainty") || !ds_prose(f, "rationale") || !repo ||
            !ds_path(dw_text(f, "path")) || !dw_id(dw_text(f, "requirement_id")) ||
            !dw_keys(repro, pk, 5) || !ds_prose(repro, "command") || !ds_prose(repro, "expected") ||
            !ds_prose(repro, "actual") ||
            !choice(dw_text(repro, "result"), "REPRODUCED", "ENVIRONMENT_FAILURE", "NOT_RUN") ||
            !ds_array(rr, 0, 64))
            return GOLEM_ERR_PARSE;
        bool located = false;
        struct json_object *files = dw_get(repo, "files");
        for (size_t j = 0; j < json_object_array_length(files); ++j)
            if (strcmp(dw_text(f, "path"), dw_text(json_object_array_get_idx(files, j), "path")) ==
                0)
                located = true;
        if (!located)
            return GOLEM_ERR_NOT_FOUND;
        golem_digest d;
        bool reproduced = strcmp(dw_text(repro, "result"), "REPRODUCED") == 0;
        if (reproduced ? !dw_digest(repro, "evidence_digest", &d)
                       : strcmp(dw_text(repro, "evidence_digest"), "") != 0)
            return GOLEM_ERR_PARSE;
        if (strcmp(dw_text(f, "status"), "CONFIRMED") == 0 && !reproduced)
            return GOLEM_ERR_REQUIREMENTS_UNMET;
        for (size_t j = 0; j < json_object_array_length(rr); ++j) {
            struct json_object *v = json_object_array_get_idx(rr, j);
            if (!json_object_is_type(v, json_type_string))
                return GOLEM_ERR_PARSE;
            struct json_object *r = find(refs, json_object_get_string(v));
            if (!r)
                return GOLEM_ERR_NOT_FOUND;
            struct json_object *q = find(qs, dw_text(r, "question_id"));
            if (strcmp(dw_text(q, "requirement_id"), dw_text(f, "requirement_id")) != 0)
                return GOLEM_ERR_REQUIREMENTS_UNMET;
            for (size_t k = 0; k < j; ++k)
                if (strcmp(json_object_get_string(v),
                           json_object_get_string(json_object_array_get_idx(rr, k))) == 0)
                    return GOLEM_ERR_PARSE;
        }
    }
    for (size_t i = 0; i < json_object_array_length(ss); ++i) {
        struct json_object *s = json_object_array_get_idx(ss, i);
        const char *sk[] = {"finding_id", "decision", "reason",          "size",
                            "acceptance", "needs_ux", "needs_publishing"};
        struct json_object *f = find(fs, dw_text(s, "finding_id"));
        if (!dw_keys(s, sk, 7) || !f ||
            !choice(dw_text(s, "decision"), "INCLUDE", "DEFER", "EXCLUDE") ||
            !ds_prose(s, "reason") || !choice(dw_text(s, "size"), "SMALL", "MEDIUM", "LARGE") ||
            !ds_prose(s, "acceptance") || !boolean(s, "needs_ux") ||
            !boolean(s, "needs_publishing"))
            return GOLEM_ERR_PARSE;
        for (size_t j = 0; j < i; ++j)
            if (strcmp(dw_text(s, "finding_id"),
                       dw_text(json_object_array_get_idx(ss, j), "finding_id")) == 0)
                return GOLEM_ERR_PARSE;
        if (strcmp(dw_text(s, "decision"), "INCLUDE") == 0) {
            if (strcmp(dw_text(f, "status"), "CONFIRMED") != 0)
                return GOLEM_ERR_REQUIREMENTS_UNMET;
            ++result.selected;
        }
    }
    result.findings = (uint32_t)json_object_array_length(fs);
    result.questions = (uint32_t)json_object_array_length(qs);
    result.references = (uint32_t)json_object_array_length(refs);
    result.scope_ready =
        result.selected > 0 && answered && strcmp(dw_text(o, "permission"), "ALLOW") == 0;
    const char *encoded =
        json_object_to_json_string_ext(dw_get(o, "snapshot"), JSON_C_TO_STRING_PLAIN);
    if (!encoded)
        return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = golem_digest_bytes((golem_bytes){(const uint8_t *)encoded, strlen(encoded)},
                                         &result.snapshot_digest);
    if (st == GOLEM_OK && out)
        *out = result;
    return st;
}
golem_status golem_discovery_validate(golem_bytes b, golem_discovery_result *out,
                                      golem_diagnostic *d)
{
    if (!out)
        return dw_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    struct json_object *o = NULL;
    golem_status st = golem_json_parse(b, GOLEM_DOCUMENT_MAX_JSON, &o);
    if (st == GOLEM_OK)
        st = ds_validate(o, out);
    json_object_put(o);
    return dw_report(d, st,
                     st == GOLEM_OK
                         ? "consistent agent claims; not verified execution or research quality"
                         : "invalid discovery relationships, budget, evidence or schema");
}
golem_status ds_metadata(struct json_object *m)
{
    struct json_object *o = dw_get(m, "assessment");
    golem_discovery_result result;
    golem_digest digest;
    golem_status st = ds_validate(o, &result);
    if (st != GOLEM_OK)
        return st;
    if (strcmp(dw_text(o, "work_id"), dw_text(m, "work_id")) != 0 ||
        !dw_digest(m, "source_snapshot", &digest) || !dw_equal(&digest, &result.snapshot_digest))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    const char *lists[] = {"questions", "findings"};
    for (size_t k = 0; k < 2; ++k) {
        struct json_object *a = dw_get(o, lists[k]), *req = dw_get(m, "requirement_ids");
        for (size_t i = 0; i < json_object_array_length(a); ++i) {
            bool found = false;
            for (size_t j = 0; j < json_object_array_length(req); ++j)
                if (strcmp(dw_text(json_object_array_get_idx(a, i), "requirement_id"),
                           json_object_get_string(json_object_array_get_idx(req, j))) == 0)
                    found = true;
            if (!found)
                return GOLEM_ERR_REQUIREMENTS_UNMET;
        }
    }
    return GOLEM_OK;
}
golem_status ds_evidence(golem_document_store *s, struct json_object *m)
{
    if (dw_uint(m, "schema_version") != 2)
        return GOLEM_OK;
    struct json_object *fs = dw_get(dw_get(m, "assessment"), "findings");
    for (size_t i = 0; i < json_object_array_length(fs); ++i) {
        struct json_object *r = dw_get(json_object_array_get_idx(fs, i), "reproduction");
        if (strcmp(dw_text(r, "result"), "REPRODUCED") != 0)
            continue;
        golem_digest digest;
        uint64_t size;
        if (!dw_digest(r, "evidence_digest", &digest))
            return GOLEM_ERR_PARSE;
        golem_status st = golem_evidence_verify(s->cas, &digest, &size, NULL);
        if (st != GOLEM_OK)
            return st;
        if (!size)
            return GOLEM_ERR_REQUIREMENTS_UNMET;
    }
    return GOLEM_OK;
}
