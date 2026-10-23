#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#include "journal.h"
#include "fragment.h"
#include "inventory.h"
#include "object_inventory.h"
#include "object_graph.h"
#include "schema.h"
#include "../common/json.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

#define PREP_SIZE 160u
#define FRAME_SIZE 80u
#define RECORDS 6208u
#define QUARANTINE_HEADER 320u
static const char *const file_kinds[] = {"prep", "payload", "event"};
typedef struct record {
    uint8_t prep[PREP_SIZE];
    size_t prep_size;
    golem_digest prep_digest;
    golem_digest event;
    bool committed;
    bool payload_ready, staging;
} record;
struct gi_journal { int root; pid_t owner; bool poisoned, busy; };
typedef struct replay {
    gi_journal_status status;
    record records[RECORDS];
    size_t count;
} replay;

static uint64_t number(const uint8_t *p)
{
    uint64_t n = 0;
    for (unsigned i = 0; i < 8; ++i) n |= (uint64_t)p[i] << (8 * i);
    return n;
}
static void encode(uint8_t *p, uint64_t n)
{
    for (unsigned i = 0; i < 8; ++i) p[i] = (uint8_t)(n >> (8 * i));
}
static void name(char *out, size_t cap, size_t sequence, const char *suffix)
{
    (void)snprintf(out, cap, "%08zu.%s", sequence, suffix);
}
static const char *const prep_keys[] = {"schema", "lane", "sequence", "payload_bytes",
    "operation_id", "request_digest", "previous_event_digest", "payload_digest"};
static golem_status prep_decode(golem_bytes wire, record *rec)
{
    struct json_object *o = NULL, *v = NULL;
    golem_status st = golem_json_parse(wire, GI_CONTROL_MAX, &o);
    if (st != GOLEM_OK) return st;
    bool valid = json_object_object_length(o) == 8;
    for (unsigned i = 0; valid && i < 8; ++i) valid = json_object_object_get_ex(o, prep_keys[i], &v);
    if (valid) {
        (void)json_object_object_get_ex(o, "schema", &v);
        valid = json_object_is_type(v, json_type_string) &&
            !strcmp(json_object_get_string(v), "golem.intent.quota-preparation.v1");
    }
    memset(rec->prep, 0, PREP_SIZE); memcpy(rec->prep, "GIQPRE01", 8);
    const uint64_t caps[] = {GI_QUOTA_LANES - 1, RECORDS, GI_CONTROL_MAX};
    for (unsigned i = 1; valid && i <= 3; ++i) {
        (void)json_object_object_get_ex(o, prep_keys[i], &v);
        valid = json_object_is_type(v, json_type_int) && json_object_get_int64(v) >= 0 &&
            json_object_get_uint64(v) <= caps[i - 1];
        if (valid) encode(rec->prep + 8 * i, json_object_get_uint64(v));
    }
    for (unsigned i = 4; valid && i < 8; ++i) {
        (void)json_object_object_get_ex(o, prep_keys[i], &v);
        valid = json_object_is_type(v, json_type_string) && json_object_get_string_len(v) == 64;
        if (valid) {
            golem_digest digest;
            valid = golem_digest_parse((golem_string_view){json_object_get_string(v), 64}, &digest) == GOLEM_OK;
            if (valid) memcpy(rec->prep + 32 + (i - 4) * 32, digest.bytes, 32);
        }
    }
    json_object_put(o);
    if (!valid) return GOLEM_ERR_PARSE;
    st = gi_domain_digest(wire, &rec->prep_digest, NULL);
    if (st == GOLEM_OK) rec->prep_size = wire.size;
    return st;
}
static golem_status prep_encode(const uint8_t *prep, uint8_t **wire, size_t *size)
{
    struct json_object *o = json_object_new_object();
    if (!o) return GOLEM_ERR_OUT_OF_MEMORY;
    for (unsigned i = 0; i < 8; ++i) {
        struct json_object *v;
        if (i == 0) v = json_object_new_string("golem.intent.quota-preparation.v1");
        else if (i <= 3) v = json_object_new_uint64(number(prep + i * 8));
        else {
            char hex[65]; const char alphabet[] = "0123456789abcdef";
            for (unsigned j = 0; j < 32; ++j) {
                unsigned b = prep[32 + (i - 4) * 32 + j];
                hex[j * 2] = alphabet[b >> 4]; hex[j * 2 + 1] = alphabet[b & 15];
            }
            hex[64] = 0; v = json_object_new_string(hex);
        }
        if (!v) { json_object_put(o); return GOLEM_ERR_OUT_OF_MEMORY; }
        if (json_object_object_add(o, prep_keys[i], v) < 0) {
            json_object_put(v); json_object_put(o); return GOLEM_ERR_OUT_OF_MEMORY;
        }
    }
    const char *text = json_object_to_json_string_ext(o, JSON_C_TO_STRING_PLAIN);
    if (!text) { json_object_put(o); return GOLEM_ERR_OUT_OF_MEMORY; }
    size_t n = strlen(text); uint8_t *copy = malloc(n);
    if (!copy) { json_object_put(o); return GOLEM_ERR_OUT_OF_MEMORY; }
    memcpy(copy, text, n); json_object_put(o); *wire = copy; *size = n; return GOLEM_OK;
}
static bool same_file(const struct stat *a, const struct stat *b)
{
#ifdef __APPLE__
    if (a->st_mtimespec.tv_nsec != b->st_mtimespec.tv_nsec ||
        a->st_ctimespec.tv_nsec != b->st_ctimespec.tv_nsec) return false;
#else
    if (a->st_mtim.tv_nsec != b->st_mtim.tv_nsec ||
        a->st_ctim.tv_nsec != b->st_ctim.tv_nsec) return false;
#endif
    return a->st_dev == b->st_dev && a->st_ino == b->st_ino && a->st_uid == b->st_uid &&
        a->st_mode == b->st_mode && a->st_nlink == b->st_nlink && a->st_size == b->st_size &&
        a->st_mtime == b->st_mtime && a->st_ctime == b->st_ctime;
}
static golem_status read_file(int root, const char *path, size_t limit,
                             uint8_t **out, size_t *size, bool *exists)
{
    int fd = openat(root, path, O_RDONLY | O_NOFOLLOW | O_CLOEXEC | O_NONBLOCK);
    if (fd < 0) {
        if (errno == ENOENT) { *exists = false; return GOLEM_OK; }
        return GOLEM_ERR_IO;
    }
    struct stat before, after, named;
    golem_status st = GOLEM_OK;
    if (fstat(fd, &before) < 0) st = GOLEM_ERR_IO;
    else if (!S_ISREG(before.st_mode) || before.st_uid != geteuid() ||
             (before.st_mode & 0077) || before.st_size < 0 ||
             (uint64_t)before.st_size > limit) st = GOLEM_ERR_INVALID_STATE;
    uint8_t *data = NULL;
    size_t used = 0;
    if (st == GOLEM_OK) {
        data = malloc((size_t)before.st_size + 1);
        if (!data) st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    while (st == GOLEM_OK && used <= (size_t)before.st_size) {
        ssize_t n = read(fd, data + used, (size_t)before.st_size + 1 - used);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) { st = GOLEM_ERR_IO; break; }
        if (!n) break;
        used += (size_t)n;
    }
    if (st == GOLEM_OK && (used != (size_t)before.st_size || fstat(fd, &after) < 0 ||
        fstatat(root, path, &named, AT_SYMLINK_NOFOLLOW) < 0 ||
        !same_file(&before, &after) || !same_file(&before, &named))) st = GOLEM_ERR_INVALID_STATE;
    if (close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK) { *out = data; *size = used; *exists = true; }
    else free(data);
    return st;
}

typedef struct quarantine_layout {
    bool final_present, pending_present;
    uint64_t device, inode, bytes;
    golem_digest digest;
} quarantine_layout;

/* Recovery mode accepts complete owned publication names only. It never repairs
 * truncated data, accepts an independent duplicate, or changes the source. */
static golem_status quarantine_read_mode(gi_journal *j, size_t seq, unsigned kind, const record *rec,
    uint8_t **wire, size_t *size, bool *exists, bool recovery, quarantine_layout *layout)
{
    quarantine_layout observed = {0};
    if (layout) *layout = observed;
    int fd = openat(j->root, "quarantine", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) {
        if (errno == ENOENT) { *exists = false; return GOLEM_OK; }
        return GOLEM_ERR_IO;
    }
    struct stat root, directory, file;
    golem_status st = GOLEM_OK;
    if (fstat(j->root, &root) < 0 || fstat(fd, &directory) < 0) st = GOLEM_ERR_IO;
    else if (directory.st_uid != geteuid() || (directory.st_mode & 0077) ||
             directory.st_dev != root.st_dev) st = GOLEM_ERR_POLICY_DENIED;
    char path[64], pending_path[80], original[64]; name(path, sizeof(path), seq, file_kinds[kind]);
    (void)snprintf(pending_path, sizeof(pending_path), "%s.pending", path);
    struct stat final, pending;
    if (st == GOLEM_OK) {
        observed.final_present = fstatat(fd, path, &final, AT_SYMLINK_NOFOLLOW) == 0;
        if (!observed.final_present && errno != ENOENT) st = GOLEM_ERR_IO;
        observed.pending_present = fstatat(fd, pending_path, &pending, AT_SYMLINK_NOFOLLOW) == 0;
        if (!observed.pending_present && errno != ENOENT) st = GOLEM_ERR_IO;
        if (observed.pending_present && !recovery) st = GOLEM_ERR_INVALID_STATE;
        if (observed.final_present && observed.pending_present && !same_file(&final, &pending))
            st = GOLEM_ERR_INVALID_STATE;
    }
    const char *selected = observed.final_present ? path : pending_path;
    name(original, sizeof(original), seq, kind == 0 ? "prep.pending" : kind == 1 ? "payload.pending" : "event.pending");
    uint8_t *data = NULL; size_t n = 0; bool found = false;
    if (st == GOLEM_OK && (observed.final_present || observed.pending_present))
        st = read_file(fd, selected, GI_CONTROL_MAX + QUARANTINE_HEADER, &data, &n, &found);
    if (st == GOLEM_OK && found != (observed.final_present || observed.pending_present)) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && found) {
        golem_digest raw, envelope, stored;
        if (fstatat(fd, selected, &file, AT_SYMLINK_NOFOLLOW) < 0) st = GOLEM_ERR_IO;
        else if (!same_file(&file, observed.final_present ? &final : &pending) ||
            file.st_nlink != (observed.final_present && observed.pending_present ? 2 : 1) ||
            (file.st_mode & 0777) != 0400 || n < QUARANTINE_HEADER ||
            memcmp(data, "GIQUA001", 8) || number(data + 8) != seq || number(data + 16) != GI_QUOTA_INTAKE ||
            number(rec->prep + 8) != GI_QUOTA_INTAKE || number(data + 24) != kind ||
            number(data + 48) != n - QUARANTINE_HEADER ||
            memcmp(data + 64, rec->prep_digest.bytes, 32) || memcmp(data + 96, rec->prep + 32, 64) ||
            memcmp(data + 224, original, strlen(original) + 1)) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){data + QUARANTINE_HEADER, n - QUARANTINE_HEADER}, &raw);
        if (st == GOLEM_OK && memcmp(raw.bytes, data + 160, 32)) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK && number(data + 56)) st = GOLEM_ERR_INVALID_STATE;
        for (size_t i = 224 + strlen(original) + 1; st == GOLEM_OK && i < 288; ++i)
            if (data[i]) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) {
            memcpy(stored.bytes, data + 288, 32); memset(data + 288, 0, 32);
            st = golem_digest_bytes((golem_bytes){data, n}, &envelope);
            memcpy(data + 288, stored.bytes, 32);
            if (st == GOLEM_OK && memcmp(stored.bytes, envelope.bytes, 32)) st = GOLEM_ERR_INVALID_STATE;
        }
        if (st == GOLEM_OK) {
            observed.device = (uint64_t)file.st_dev; observed.inode = (uint64_t)file.st_ino; observed.bytes = n;
            st = golem_digest_bytes((golem_bytes){data, n}, &observed.digest);
        }
    }
    if (close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK) { *wire = data; *size = n; *exists = found; if (layout) *layout = observed; }
    else free(data);
    return st;
}

/* Fragment objects have their own exact namespace; all bytes remain charged.
 * Recovery reads never classify unknown files or incomplete objects as valid. */
static golem_status fragment_read(gi_journal *j, size_t seq, unsigned kind, const record *rec,
    bool recovery, gi_journal_fragment_plan *out, uint8_t **source_out, size_t *source_size,
    uint8_t **truncated_out)
{
    gi_journal_fragment_plan p = {0}; gi_fragment_binding b = {0};
    char base[64], path[96], object[96], pending[112];
    name(base, sizeof(base), seq, file_kinds[kind]);
    (void)snprintf(object, sizeof(object), "%s.fragment", base);
    (void)snprintf(pending, sizeof(pending), "%s.pending", object);
    int fd = openat(j->root, "quarantine", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return GOLEM_ERR_INVALID_STATE;
    uint8_t *stored = NULL, *truncated = NULL, *source = NULL, *full = NULL;
    size_t stored_size = 0, n = 0, raw_size = 0, full_size = 0; bool exists = false;
    struct stat f = {0}, q = {0}, t = {0}, s = {0};
    golem_status st = GOLEM_OK;
    p.final_present = fstatat(fd, object, &f, AT_SYMLINK_NOFOLLOW) == 0;
    if (!p.final_present && errno != ENOENT) st = GOLEM_ERR_IO;
    p.pending_present = fstatat(fd, pending, &q, AT_SYMLINK_NOFOLLOW) == 0;
    if (!p.pending_present && errno != ENOENT) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && p.pending_present && !recovery) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && p.final_present && p.pending_present && !same_file(&f, &q)) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && (p.final_present || p.pending_present)) {
        const struct stat *selected = p.final_present ? &f : &q;
        st = read_file(fd, p.final_present ? object : pending, GI_CONTROL_MAX + 640,
                       &stored, &stored_size, &exists);
        struct stat checked;
        if (st == GOLEM_OK && (fstatat(fd, p.final_present ? object : pending, &checked, AT_SYMLINK_NOFOLLOW) < 0 ||
            !same_file(selected, &checked))) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK && (!exists || stored_size < 640 || memcmp(stored, "GIQFR001", 8) ||
            selected->st_nlink != (unsigned)p.final_present + (unsigned)p.pending_present ||
            (selected->st_mode & 0777) != 0400)) st = GOLEM_ERR_INVALID_STATE;
        p.object_device = (uint64_t)selected->st_dev; p.object_inode = (uint64_t)selected->st_ino;
        p.object_bytes = stored_size;
        if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){stored, stored_size}, &p.object_digest);
    }
    (void)snprintf(path, sizeof(path), "%s.pending", base);
    if (st == GOLEM_OK) st = read_file(fd, path, GI_CONTROL_MAX + 320, &truncated, &n, &p.truncated_present);
    if (st == GOLEM_OK && p.truncated_present) {
        struct stat unexpected;
        if (fstatat(fd, base, &unexpected, AT_SYMLINK_NOFOLLOW) == 0 || errno != ENOENT)
            st = GOLEM_ERR_INVALID_STATE;
        if (fstatat(fd, path, &t, AT_SYMLINK_NOFOLLOW) < 0 || t.st_nlink != 1 || (t.st_mode & 0077))
            st = GOLEM_ERR_INVALID_STATE;
        p.device = (uint64_t)t.st_dev; p.inode = (uint64_t)t.st_ino; p.bytes = n;
        if (!recovery) st = GOLEM_ERR_INVALID_STATE;
    }
    if (st == GOLEM_OK && !p.truncated_present) {
        if (!stored) st = GOLEM_ERR_INVALID_STATE;
        else {
            n = stored_size - 320; truncated = malloc(n);
            if (!truncated) st = GOLEM_ERR_OUT_OF_MEMORY;
            else memcpy(truncated, stored + 320, n);
            p.device = number(stored + 32); p.inode = number(stored + 40); p.bytes = n;
        }
    }
    if (st == GOLEM_OK && (n < 320 || memcmp(truncated, "GIQUA001", 8) ||
        number(rec->prep + 8) != GI_QUOTA_INTAKE)) st = GOLEM_ERR_INVALID_STATE;
    (void)snprintf(path, sizeof(path), "%s.pending", base);
    if (st == GOLEM_OK) st = read_file(j->root, path, GI_CONTROL_MAX, &source, &raw_size, &exists);
    if (st == GOLEM_OK && exists) {
        if (fstatat(j->root, path, &s, AT_SYMLINK_NOFOLLOW) < 0 || s.st_nlink != 1 ||
            (uint64_t)s.st_dev != number(truncated + 32) || (uint64_t)s.st_ino != number(truncated + 40))
            st = GOLEM_ERR_INVALID_STATE;
    } else if (st == GOLEM_OK) {
        bool found = false;
        st = quarantine_read_mode(j, seq, kind, rec, &full, &full_size, &found, false, NULL);
        if (st == GOLEM_OK && (!found || !p.final_present || p.truncated_present)) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) {
            raw_size = full_size - 320; source = malloc(raw_size ? raw_size : 1);
            if (!source) st = GOLEM_ERR_OUT_OF_MEMORY;
            else memcpy(source, full + 320, raw_size);
        }
    }
    if (st == GOLEM_OK) {
        gi_journal_alias_plan *a = &b.original.source;
        a->sequence = seq; a->kind = kind; a->present = true;
        a->device = number(truncated + 32); a->inode = number(truncated + 40); a->bytes = raw_size;
        a->preparation = rec->prep_digest;
        memcpy(a->operation.bytes, rec->prep + 32, 32); memcpy(a->request.bytes, rec->prep + 64, 32);
        memcpy(a->payload.bytes, rec->prep + 128, 32);
        st = golem_digest_bytes((golem_bytes){source, raw_size}, &a->final_digest);
        memcpy(b.original_approval.bytes, truncated + 192, 32);
        b.envelope_device = p.device; b.envelope_inode = p.inode;
        if (stored) memcpy(b.preservation_approval.bytes, stored + 128, 32);
        uint8_t *expected_object = NULL; size_t expected_size = 0;
        if (st == GOLEM_OK) st = gi_fragment_encode(&b, (golem_bytes){source, raw_size},
            (golem_bytes){truncated, n}, &expected_object, &expected_size);
        if (st == GOLEM_OK && stored && (stored_size != expected_size || memcmp(stored, expected_object, stored_size)))
            st = GOLEM_ERR_INVALID_STATE;
        free(expected_object);
        p.original = b.original; p.original.source.present = exists;
        p.original.approval = b.original_approval; p.original.payload_bytes = number(rec->prep + 24);
        p.original.payload_ready = rec->payload_ready; p.original.directory_present = true;
        p.preservation_approval = b.preservation_approval;
        if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){truncated, n}, &p.digest);
    }
    free(stored); free(full);
    if (close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK) { *out = p; *source_out = source; *source_size = raw_size; *truncated_out = truncated; }
    else { free(source); free(truncated); }
    return st;
}

/* Terminal damage recovery never accepts a damaged GIQFD001, or reconstructs
 * missing ancestors. Even receipt-only reentry requires the original sources. */
static golem_status damage_read(gi_journal *j, size_t seq, unsigned kind, const record *rec,
    bool recovery, gi_journal_fragment_plan *out, uint8_t **source_out, size_t *source_size,
    uint8_t **truncated_out)
{
    if (!recovery || number(rec->prep + 8) != GI_QUOTA_INTAKE) return GOLEM_ERR_INVALID_STATE;
    gi_journal_fragment_plan p = {0};
    char base[64], path[112], final[112], pending[128];
    name(base, sizeof(base), seq, file_kinds[kind]);
    int fd = openat(j->root, "quarantine", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return GOLEM_ERR_IO;
    uint8_t *stored = NULL, *cut = NULL, *env = NULL, *raw = NULL, *expected = NULL;
    size_t stored_n = 0, cut_n = 0, env_n = 0, raw_n = 0, expected_n = 0;
    bool exists = false; struct stat f = {0}, q = {0}, t = {0}, e = {0}, s = {0}, check;
    (void)snprintf(final, sizeof(final), "%s.fragment.damage", base);
    (void)snprintf(pending, sizeof(pending), "%s.pending", final);
    golem_status st = GOLEM_OK;
    p.final_present = fstatat(fd, final, &f, AT_SYMLINK_NOFOLLOW) == 0;
    if (!p.final_present && errno != ENOENT) st = GOLEM_ERR_IO;
    p.pending_present = fstatat(fd, pending, &q, AT_SYMLINK_NOFOLLOW) == 0;
    if (!p.pending_present && errno != ENOENT) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && p.final_present && p.pending_present && !same_file(&f, &q)) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && (p.final_present || p.pending_present)) {
        const struct stat *selected = p.final_present ? &f : &q;
        const char *selected_path = p.final_present ? final : pending;
        st = read_file(fd, selected_path, GI_CONTROL_MAX + 1024, &stored, &stored_n, &exists);
        if (st == GOLEM_OK && (!exists || stored_n < 704 || memcmp(stored, "GIQFD001", 8) ||
            fstatat(fd, selected_path, &check, AT_SYMLINK_NOFOLLOW) < 0 || !same_file(selected, &check) ||
            selected->st_nlink != (unsigned)p.final_present + (unsigned)p.pending_present ||
            (selected->st_mode & 0777) != 0400)) st = GOLEM_ERR_INVALID_STATE;
        p.object_device = selected->st_dev; p.object_inode = selected->st_ino; p.object_bytes = stored_n;
        if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){stored, stored_n}, &p.object_digest);
    }
    /* Both ancestors must still be present, with no competing final names. */
    (void)snprintf(path, sizeof(path), "%s.fragment", base);
    if (st == GOLEM_OK && (fstatat(fd, path, &check, AT_SYMLINK_NOFOLLOW) == 0 || errno != ENOENT)) st = GOLEM_ERR_INVALID_STATE;
    (void)snprintf(path, sizeof(path), "%s.fragment.pending", base);
    if (st == GOLEM_OK) st = read_file(fd, path, GI_CONTROL_MAX + 640, &cut, &cut_n, &p.truncated_present);
    if (st == GOLEM_OK && p.truncated_present) {
        if (fstatat(fd, path, &t, AT_SYMLINK_NOFOLLOW) < 0 || t.st_nlink != 1 || (t.st_mode & 0077)) st = GOLEM_ERR_INVALID_STATE;
        p.device = t.st_dev; p.inode = t.st_ino; p.bytes = cut_n;
    } else if (st == GOLEM_OK) {
        if (!p.final_present || p.pending_present) st = GOLEM_ERR_INVALID_STATE;
        else {
            cut_n = stored_n - 384; cut = malloc(cut_n);
            if (!cut) st = GOLEM_ERR_OUT_OF_MEMORY;
            else memcpy(cut, stored + 384, cut_n);
            p.device = number(stored + 32); p.inode = number(stored + 40); p.bytes = cut_n;
        }
    }
    if (st == GOLEM_OK && (cut_n < 320 || memcmp(cut, "GIQFR001", 8))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && (fstatat(fd, base, &check, AT_SYMLINK_NOFOLLOW) == 0 || errno != ENOENT)) st = GOLEM_ERR_INVALID_STATE;
    (void)snprintf(path, sizeof(path), "%s.pending", base);
    if (st == GOLEM_OK) st = read_file(fd, path, GI_CONTROL_MAX + 320, &env, &env_n, &exists);
    if (st == GOLEM_OK && (!exists || env_n < 320 || memcmp(env, "GIQUA001", 8) ||
        fstatat(fd, path, &e, AT_SYMLINK_NOFOLLOW) < 0 || e.st_nlink != 1 || (e.st_mode & 0077))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) st = read_file(j->root, path, GI_CONTROL_MAX, &raw, &raw_n, &exists);
    if (st == GOLEM_OK && (!exists || fstatat(j->root, path, &s, AT_SYMLINK_NOFOLLOW) < 0 ||
        s.st_nlink != 1 || (s.st_mode & 0077) || (uint64_t)s.st_dev != number(env + 32) ||
        (uint64_t)s.st_ino != number(env + 40))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) {
        gi_fragment_damage_binding b = {0};
        gi_journal_alias_plan *a = &b.fragment.original.source;
        a->sequence = seq; a->kind = kind; a->present = true;
        a->device = s.st_dev; a->inode = s.st_ino; a->bytes = raw_n; a->preparation = rec->prep_digest;
        memcpy(a->operation.bytes, rec->prep + 32, 32); memcpy(a->request.bytes, rec->prep + 64, 32);
        memcpy(a->payload.bytes, rec->prep + 128, 32);
        st = golem_digest_bytes((golem_bytes){raw, raw_n}, &a->final_digest);
        memcpy(b.fragment.original_approval.bytes, env + 192, 32);
        memcpy(b.fragment.preservation_approval.bytes, cut + 128, 32);
        b.fragment.envelope_device = e.st_dev; b.fragment.envelope_inode = e.st_ino;
        b.device = p.device; b.inode = p.inode;
        if (stored) memcpy(b.approval.bytes, stored + 160, 32);
        if (st == GOLEM_OK) st = gi_fragment_damage_encode(&b, (golem_bytes){raw, raw_n},
            (golem_bytes){env, env_n}, (golem_bytes){cut, cut_n}, &expected, &expected_n);
        if (st == GOLEM_OK && stored && (stored_n != expected_n || memcmp(stored, expected, stored_n))) st = GOLEM_ERR_INVALID_STATE;
        p.original = b.fragment.original; p.original.approval = b.fragment.original_approval;
        p.original.payload_bytes = number(rec->prep + 24); p.original.payload_ready = rec->payload_ready;
        p.original.directory_present = true; p.preservation_approval = b.approval;
        p.fragment_approval = b.fragment.preservation_approval;
        p.envelope_device = e.st_dev; p.envelope_inode = e.st_ino; p.envelope_bytes = env_n;
        if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){env, env_n}, &p.envelope_digest);
        if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){cut, cut_n}, &p.digest);
    }
    free(stored); free(env); free(expected);
    if (close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK) { *out = p; *source_out = raw; *source_size = raw_n; *truncated_out = cut; }
    else { free(raw); free(cut); }
    return st;
}

/* Read-only restoration of object publication history and a prepared tail.
 * Committed graphs are verified before use; only inspection/the live publisher
 * may observe a prepared tail. It is never a D01 pending-event recovery target. */
static golem_status restore_object_reservation(gi_journal *j, replay *r,
    uint64_t *known_files, uint64_t *known_bytes, uint64_t *known_directories, bool allow_pending)
{
    gi_object_manifest_input *inputs = calloc(RECORDS + 1, sizeof(*inputs));
    if (!inputs) return GOLEM_ERR_OUT_OF_MEMORY;
    size_t count = 0; golem_status st = GOLEM_OK;
    for (size_t seq = 1; st == GOLEM_OK && seq <= r->count + 1; ++seq) {
        char path[64]; uint8_t *data = NULL, *actual = NULL;
        size_t size = 0, actual_size = 0; bool exists = false, found = false;
        record *rec = seq <= r->count ? &r->records[seq - 1] : NULL;
        name(path, sizeof(path), seq, "objects-prep");
        st = read_file(j->root, path, GI_CONTROL_MAX, &data, &size, &exists);
        struct stat sb;
        if (st == GOLEM_OK && exists && (seq > RECORDS || fstatat(j->root, path, &sb, AT_SYMLINK_NOFOLLOW) < 0 ||
            sb.st_nlink != 1 || (sb.st_mode & 07777) != 0400)) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK && rec && rec->payload_ready) {
            name(path, sizeof(path), seq, "payload");
            st = read_file(j->root, path, GI_CONTROL_MAX, &actual, &actual_size, &found);
            if (st == GOLEM_OK && !found) st = GOLEM_ERR_INVALID_STATE;
        }
        if (st == GOLEM_OK && !exists && actual) {
            struct json_object *o = NULL, *schema = NULL;
            if (golem_json_parse((golem_bytes){actual, actual_size}, GI_CONTROL_MAX, &o) == GOLEM_OK &&
                json_object_object_get_ex(o, "schema", &schema) && json_object_is_type(schema, json_type_string) &&
                !strcmp(json_object_get_string(schema), "golem.intent.object-publication.v1")) st = GOLEM_ERR_INVALID_STATE;
            json_object_put(o);
        }
        if (st != GOLEM_OK || !exists) { free(data); free(actual); continue; }
        if ((!rec || !rec->committed || rec->staging) && !allow_pending) {
            free(data); free(actual); st = GOLEM_ERR_INVALID_STATE; break;
        }
        gi_object_preparation_result manifest;
        st = gi_object_preparation_validate((golem_bytes){data, size}, &manifest, NULL);
        const uint8_t *head = rec ? rec->prep + 96 : r->status.head.bytes;
        if (st == GOLEM_OK && (manifest.reservation.sequence != seq ||
            memcmp(manifest.reservation.head.bytes, head, 32) || (!rec && r->status.pending))) st = GOLEM_ERR_INVALID_STATE;
        char payload[GI_OBJECT_PUBLICATION_CAPACITY]; size_t length = 0;
        if (st == GOLEM_OK) st = gi_object_publication_encode(&manifest.reservation.publication, payload, sizeof(payload), &length);
        for (size_t i = 0; st == GOLEM_OK && i < r->count; ++i)
            if (i + 1 != seq && !memcmp(r->records[i].prep + 32, manifest.reservation.publication.operation.bytes, 32))
                st = GOLEM_ERR_INVALID_STATE;
        gi_object_journal_binding binding = {0};
        if (st == GOLEM_OK && rec) {
            golem_digest digest; st = golem_digest_bytes((golem_bytes){(uint8_t *)payload, length}, &digest);
            if (st == GOLEM_OK && (number(rec->prep + 8) != GI_QUOTA_INTAKE || number(rec->prep + 24) != length ||
                memcmp(rec->prep + 128, digest.bytes, 32) || memcmp(rec->prep + 32, manifest.reservation.publication.operation.bytes, 32) ||
                memcmp(rec->prep + 64, manifest.reservation.publication.request.bytes, 32) ||
                (actual && (actual_size != length || memcmp(actual, payload, length))))) st = GOLEM_ERR_INVALID_STATE;
            binding = (gi_object_journal_binding){GI_QUOTA_INTAKE, seq, manifest.reservation.head, {(uint8_t *)payload, length}};
        }
        free(actual);
        gi_quota_state projected;
        if (st == GOLEM_OK) st = gi_object_reservation_project(&r->status.usage, &manifest.reservation, rec ? &binding : NULL, &projected);
        if (st == GOLEM_OK) {
            inputs[count++] = (gi_object_manifest_input){{data, size}, rec && rec->committed};
            r->status.usage = projected;
            r->status.usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_BYTES] += size;
            ++r->status.usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_ENTRIES];
            gi_quota_usage zero = {{0}}; gi_quota_state checked;
            st = gi_quota_project(&r->status.usage, GI_QUOTA_INTAKE, &zero, &zero, &checked);
            if (!rec || !rec->committed) r->status.pending = true;
            ++*known_files; *known_bytes += size;
        } else free(data);
    }
    gi_object_inventory objects;
    if (st == GOLEM_OK && count) st = gi_object_inventory_scan(j->root, inputs, count, &objects);
    for (size_t i = 0; st == GOLEM_OK && i < count; ++i) if (inputs[i].committed) {
        gi_baseline_coverage_result coverage;
        st = gi_object_graph_validate(j->root, inputs[i].bytes, &coverage);
    }
    if (st == GOLEM_OK && count) {
        r->status.usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_BYTES] += objects.actual.logical_bytes;
        r->status.usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_ENTRIES] += objects.actual.files + objects.actual.directories;
        *known_files += objects.actual.files; *known_bytes += objects.actual.logical_bytes;
        *known_directories += objects.actual.directories;
    }
    for (size_t i = 0; i < count; ++i) free((void *)inputs[i].bytes.data);
    free(inputs);
    return st;
}

static golem_status restore_mode(gi_journal *j, replay *r, int recovery_kind)
{
    memset(r, 0, sizeof(*r));
    struct stat root;
    if (fstat(j->root, &root) < 0) return GOLEM_ERR_IO;
    if (root.st_uid != geteuid() || (root.st_mode & 0077)) return GOLEM_ERR_POLICY_DENIED;
    gi_inventory inventory;
    golem_status st = gi_inventory_scan(j->root, 33792, 4, &inventory);
    if (st != GOLEM_OK) return st;
    struct stat quarantine_dir;
    bool has_quarantine = fstatat(j->root, "quarantine", &quarantine_dir, AT_SYMLINK_NOFOLLOW) == 0;
    if (!has_quarantine && errno != ENOENT) return GOLEM_ERR_IO;
    if ((has_quarantine && (!S_ISDIR(quarantine_dir.st_mode) || quarantine_dir.st_uid != geteuid() ||
         (quarantine_dir.st_mode & 0077)))) return GOLEM_ERR_INVALID_STATE;
    if (has_quarantine) ++r->status.usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_ENTRIES];
    uint64_t known_files = 0, known_bytes = 0;
    uint64_t known_directories = has_quarantine ? 1u : 0u;
    for (size_t seq = 1; seq <= RECORDS; ++seq) {
        char path[64]; uint8_t *data = NULL; size_t size = 0; bool exists = false;
        name(path, sizeof(path), seq, "prep");
        st = read_file(j->root, path, GI_CONTROL_MAX, &data, &size, &exists);
        if (st != GOLEM_OK) return st;
        if (!exists) break;
        record *rec = &r->records[r->count];
        st = prep_decode((golem_bytes){data, size}, rec);
        free(data); data = NULL;
        if (st != GOLEM_OK) return st;
        if (r->status.pending || number(rec->prep + 16) != seq ||
            memcmp(rec->prep + 96, r->status.head.bytes, 32)) {
            free(data); return GOLEM_ERR_INVALID_STATE;
        }
        /* An operation cannot acquire a second lane or a second request. */
        for (size_t i = 0; i < r->count; ++i)
            if (!memcmp(rec->prep + 32, r->records[i].prep + 32, 32)) {
                free(data); return GOLEM_ERR_INVALID_STATE;
            }
        ++r->count;
        gi_quota_usage *usage = &r->status.usage.lane[number(rec->prep + 8)];
        ++usage->value[GI_QUOTA_EVENTS]; /* Includes prepared/reserved slots. */
        usage->value[GI_QUOTA_PAYLOAD] += number(rec->prep + 24);
        usage->value[GI_QUOTA_BYTES] += rec->prep_size;
        ++usage->value[GI_QUOTA_ENTRIES]; ++known_files; known_bytes += rec->prep_size;
        bool payload_exists = false, event_exists = false, pending = false;
        const char *suffixes[] = {"prep.pending", "payload", "payload.pending", "event", "event.pending"};
        for (unsigned k = 0; k < 5; ++k) {
            size_t limit = k < 3 ? GI_CONTROL_MAX : FRAME_SIZE;
            name(path, sizeof(path), seq, suffixes[k]);
            st = read_file(j->root, path, limit, &data, &size, &exists);
            if (st != GOLEM_OK) return st;
            if (!exists) continue;
            ++known_files; known_bytes += size;
            ++usage->value[GI_QUOTA_ENTRIES]; usage->value[GI_QUOTA_BYTES] += size;
            if (k == 1) {
                golem_digest digest;
                st = golem_digest_bytes((golem_bytes){data, size}, &digest);
                if (st == GOLEM_OK && (size != number(rec->prep + 24) ||
                    memcmp(digest.bytes, rec->prep + 128, 32))) st = GOLEM_ERR_INVALID_STATE;
                payload_exists = true;
            } else if (k == 3) {
                if (st == GOLEM_OK && (!payload_exists || size != FRAME_SIZE ||
                    memcmp(data, "GIQEV001", 8) || number(data + 8) != seq ||
                    memcmp(data + 16, r->status.head.bytes, 32) ||
                    memcmp(data + 48, rec->prep_digest.bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
                if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){data, size}, &rec->event);
                event_exists = true;
            } else {
                pending = true;
                /* Partial owned staging remains charged, never auto-repaired. */
                if (k == 0) {
                    uint8_t *original = NULL; size_t n = 0; bool found = false;
                    char original_path[64]; name(original_path, sizeof(original_path), seq, "prep");
                    st = read_file(j->root, original_path, GI_CONTROL_MAX, &original, &n, &found);
                    if (st == GOLEM_OK && (!found || size > n || memcmp(original, data, size)))
                        st = GOLEM_ERR_INVALID_STATE;
                    free(original);
                }
                if (k == 2 && size > number(rec->prep + 24)) st = GOLEM_ERR_INVALID_STATE;
            }
            free(data); data = NULL;
            if (st != GOLEM_OK) return st;
        }
        rec->committed = event_exists;
        rec->payload_ready = payload_exists;
        rec->staging = pending;
        for (unsigned kind = 0; kind < 3; ++kind) {
            char fragment_path[96]; struct stat fragment_file;
            (void)snprintf(fragment_path, sizeof(fragment_path), "quarantine/%08zu.%s.fragment", seq, file_kinds[kind]);
            bool fragment = fstatat(j->root, fragment_path, &fragment_file, AT_SYMLINK_NOFOLLOW) == 0;
            char next_path[64]; struct stat next_file;
            name(next_path, sizeof(next_path), seq + 1, "prep");
            bool last = fstatat(j->root, next_path, &next_file, AT_SYMLINK_NOFOLLOW) < 0 && errno == ENOENT;
            bool recovering_fragment = last && recovery_kind == (int)kind + 3;
            bool recovering_damage = last && recovery_kind == (int)kind + 6;
            if (recovering_damage) {
                gi_journal_fragment_plan fp; uint8_t *raw = NULL, *cut = NULL; size_t raw_size = 0;
                st = damage_read(j, seq, kind, rec, true, &fp, &raw, &raw_size, &cut);
                free(raw); free(cut);
                if (st != GOLEM_OK) return st;
                unsigned names = (unsigned)fp.final_present + (unsigned)fp.pending_present;
                uint64_t files = names + 1 + (unsigned)fp.truncated_present;
                uint64_t bytes = names * fp.object_bytes + fp.envelope_bytes + (fp.truncated_present ? fp.bytes : 0);
                known_files += files; known_bytes += bytes;
                usage->value[GI_QUOTA_ENTRIES] += files; usage->value[GI_QUOTA_BYTES] += bytes;
                pending = true;
                continue;
            }
            if (fragment || recovering_fragment) {
                gi_journal_fragment_plan fp; uint8_t *raw = NULL, *cut = NULL; size_t raw_size = 0;
                st = fragment_read(j, seq, kind, rec, recovering_fragment, &fp, &raw, &raw_size, &cut);
                free(raw); free(cut);
                if (st != GOLEM_OK) return st;
                unsigned names = (unsigned)fp.final_present + (unsigned)fp.pending_present;
                known_files += names; known_bytes += names * fp.object_bytes;
                usage->value[GI_QUOTA_ENTRIES] += names; usage->value[GI_QUOTA_BYTES] += names * fp.object_bytes;
                if (fp.truncated_present) {
                    ++known_files; known_bytes += fp.bytes;
                    ++usage->value[GI_QUOTA_ENTRIES]; usage->value[GI_QUOTA_BYTES] += fp.bytes;
                }
                if (fp.truncated_present || fp.pending_present) pending = true;
                if (fp.truncated_present) continue;
            }
            quarantine_layout layout;
            st = quarantine_read_mode(j, seq, kind, rec, &data, &size, &exists,
                                      recovery_kind == (int)kind, &layout);
            if (st != GOLEM_OK) return st;
            if (exists) {
                unsigned names = (unsigned)layout.final_present + (unsigned)layout.pending_present;
                known_files += names; known_bytes += size * names;
                usage->value[GI_QUOTA_ENTRIES] += names; usage->value[GI_QUOTA_BYTES] += size * names;
                if (layout.pending_present) pending = true;
            }
            free(data); data = NULL;
        }
        rec->staging = pending;
        if (event_exists) { ++r->status.committed; r->status.head = rec->event; }
        r->status.pending = pending || !event_exists;
    }
    st = restore_object_reservation(j, r, &known_files, &known_bytes, &known_directories, recovery_kind == -2);
    if (st != GOLEM_OK) return st;
    if ((has_quarantine && !r->count) || known_files != inventory.files || known_bytes != inventory.logical_bytes ||
        known_directories != inventory.directories)
        return GOLEM_ERR_INVALID_STATE; /* Unattributed file, gap or partial prep. */
    gi_quota_usage zero = {{0}}; gi_quota_state checked;
    return gi_quota_project(&r->status.usage, GI_QUOTA_INTAKE, &zero, &zero, &checked);
}

static golem_status restore(gi_journal *j, replay *r) { return restore_mode(j, r, -1); }

golem_status gi_journal_open(int root, gi_journal **out)
{
    if (root < 0 || !out) return GOLEM_ERR_INVALID_ARGUMENT;
    int fd = openat(root, ".", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return GOLEM_ERR_IO;
    struct stat sb;
    if (fstat(fd, &sb) < 0 || sb.st_uid != geteuid() || (sb.st_mode & 0077)) {
        close(fd); return GOLEM_ERR_POLICY_DENIED;
    }
    if (flock(fd, LOCK_EX | LOCK_NB) < 0) { close(fd); return GOLEM_ERR_INVALID_STATE; }
    gi_journal *j = calloc(1, sizeof(*j));
    if (!j) { close(fd); return GOLEM_ERR_OUT_OF_MEMORY; }
    j->root = fd; j->owner = getpid(); *out = j; return GOLEM_OK;
}
void gi_journal_close(gi_journal *j)
{
    if (j) { close(j->root); free(j); }
}
golem_status gi_journal_inspect(gi_journal *j, gi_journal_status *out)
{
    if (!j || !out) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = restore_mode(j, r, -2);
    if (st == GOLEM_OK) *out = r->status;
    free(r); return st;
}
static golem_status visit_mode(gi_journal *j, gi_journal_visitor visitor, void *context, int recovery_kind)
{
    if (!j || !visitor) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = restore_mode(j, r, recovery_kind);
    j->busy = true;
    for (size_t i = 0; st == GOLEM_OK && i < r->count; ++i) {
        record *rec = &r->records[i];
        golem_digest operation, request;
        memcpy(operation.bytes, rec->prep + 32, 32);
        memcpy(request.bytes, rec->prep + 64, 32);
        gi_journal_operation item = {(gi_quota_lane)number(rec->prep + 8), i + 1,
            rec->committed, rec->staging || !rec->committed, rec->event};
        st = visitor(context, &operation, &request, &item);
    }
    j->busy = false;
    free(r);
    return st;
}

golem_status gi_journal_visit(gi_journal *j, gi_journal_visitor visitor, void *context)
{
    return visit_mode(j, visitor, context, -1);
}

golem_status gi_journal_envelope_visit(gi_journal *j, unsigned kind, gi_journal_visitor visitor, void *context)
{
    if (kind > 2) return GOLEM_ERR_INVALID_ARGUMENT;
    return visit_mode(j, visitor, context, (int)kind);
}

golem_status gi_journal_fragment_visit(gi_journal *j, unsigned kind, gi_journal_visitor visitor, void *context)
{
    if (kind > 2) return GOLEM_ERR_INVALID_ARGUMENT;
    return visit_mode(j, visitor, context, (int)kind + 3);
}

golem_status gi_journal_lookup(gi_journal *j, const golem_digest *operation,
    const golem_digest *request, gi_journal_operation *out)
{
    if (!j || !operation || !request || !out) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = restore(j, r);
    if (st == GOLEM_OK) {
        st = GOLEM_ERR_NOT_FOUND;
        for (size_t i = 0; i < r->count; ++i) {
            record *rec = &r->records[i];
            if (memcmp(rec->prep + 32, operation->bytes, 32)) continue;
            st = memcmp(rec->prep + 64, request->bytes, 32) ? GOLEM_ERR_INVALID_STATE : GOLEM_OK;
            if (st == GOLEM_OK) *out = (gi_journal_operation){
                (gi_quota_lane)number(rec->prep + 8), i + 1, rec->committed,
                rec->staging || !rec->committed, rec->event};
            break;
        }
    }
    free(r); return st;
}

static golem_status publish_name(int root, const char *final, golem_bytes bytes)
{
    char pending[256];
    (void)snprintf(pending, sizeof(pending), "%s.pending", final);
    int fd = openat(root, pending, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) return GOLEM_ERR_IO;
    golem_status st = GOLEM_OK; size_t used = 0;
    while (used < bytes.size) {
        ssize_t n = write(fd, bytes.data + used, bytes.size - used);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) { st = GOLEM_ERR_IO; break; }
        used += (size_t)n;
    }
    if (st == GOLEM_OK && (fchmod(fd, 0400) < 0 || fsync(fd) < 0)) st = GOLEM_ERR_IO;
    if (close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (st == GOLEM_OK && (linkat(root, pending, root, final, 0) < 0 || fsync(root) < 0))
        st = GOLEM_ERR_IO;
    /* Only this successful live publication removes its own staging name. */
    if (st == GOLEM_OK && (unlinkat(root, pending, 0) < 0 || fsync(root) < 0)) st = GOLEM_ERR_IO;
    return st;
}
static golem_status publish(gi_journal *j, size_t seq, const char *suffix, golem_bytes bytes)
{
    char final[64]; name(final, sizeof(final), seq, suffix);
    return publish_name(j->root, final, bytes);
}

static golem_status alias_plan(gi_journal *j, unsigned kind, replay *r, gi_journal_alias_plan *out)
{
    if (kind > 2 || !r->count) return GOLEM_ERR_INVALID_STATE;
    record *rec = &r->records[r->count - 1];
    if (number(rec->prep + 8) != GI_QUOTA_INTAKE) return GOLEM_ERR_INVALID_STATE;
    const char *suffix[] = {"prep", "payload", "event"};
    for (unsigned i = 0; i < 3; ++i) {
        char original[64], alias[80]; struct stat source, staging;
        name(original, sizeof(original), r->count, suffix[i]);
        (void)snprintf(alias, sizeof(alias), "%s.pending", original);
        if (fstatat(j->root, alias, &staging, AT_SYMLINK_NOFOLLOW) < 0) {
            if (errno == ENOENT) continue;
            return GOLEM_ERR_IO;
        }
        if (fstatat(j->root, original, &source, AT_SYMLINK_NOFOLLOW) < 0 ||
            !S_ISREG(source.st_mode) || !S_ISREG(staging.st_mode) || source.st_uid != geteuid() ||
            (source.st_mode & 0077) || source.st_nlink != 2 || staging.st_nlink != 2 ||
            source.st_dev != staging.st_dev || source.st_ino != staging.st_ino) return GOLEM_ERR_INVALID_STATE;
    }
    char final[64], pending[80]; name(final, sizeof(final), r->count, suffix[kind]);
    (void)snprintf(pending, sizeof(pending), "%s.pending", final);
    struct stat f, p;
    if (fstatat(j->root, final, &f, AT_SYMLINK_NOFOLLOW) < 0) return GOLEM_ERR_INVALID_STATE;
    bool present = fstatat(j->root, pending, &p, AT_SYMLINK_NOFOLLOW) == 0;
    if (!present && errno != ENOENT) return GOLEM_ERR_IO;
    if (!S_ISREG(f.st_mode) || f.st_uid != geteuid() || (f.st_mode & 0077) ||
        f.st_nlink != (present ? 2 : 1) || (present && (!S_ISREG(p.st_mode) ||
        p.st_dev != f.st_dev || p.st_ino != f.st_ino || p.st_nlink != 2))) return GOLEM_ERR_INVALID_STATE;
    uint8_t *data = NULL; size_t size = 0; bool exists = false;
    golem_status st = read_file(j->root, final, GI_CONTROL_MAX, &data, &size, &exists);
    gi_journal_alias_plan a = {0};
    if (st == GOLEM_OK && !exists) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){data, size}, &a.final_digest);
    free(data);
    if (st != GOLEM_OK) return st;
    a.sequence = r->count; a.kind = kind; a.device = (uint64_t)f.st_dev;
    a.inode = (uint64_t)f.st_ino; a.bytes = size; a.present = present;
    a.state = r->status; a.preparation = rec->prep_digest;
    memcpy(a.operation.bytes, rec->prep + 32, 32); memcpy(a.request.bytes, rec->prep + 64, 32);
    memcpy(a.payload.bytes, rec->prep + 128, 32);
    uint8_t wire[360] = {0}; size_t used = 0;
    memcpy(wire, "GIALS001", 8); used = 8;
    uint64_t numbers[] = {a.sequence, a.kind, a.device, a.inode, a.bytes, a.present,
                          a.state.committed, a.state.pending};
    for (unsigned i = 0; i < 8; ++i) { encode(wire + used, numbers[i]); used += 8; }
    const golem_digest *digests[] = {&a.operation, &a.request, &a.preparation, &a.payload, &a.final_digest, &a.state.head};
    for (unsigned i = 0; i < 6; ++i) { memcpy(wire + used, digests[i]->bytes, 32); used += 32; }
    for (unsigned lane = 0; lane < GI_QUOTA_LANES; ++lane)
        for (unsigned axis = 0; axis < GI_QUOTA_AXES; ++axis) {
            encode(wire + used, a.state.usage.lane[lane].value[axis]); used += 8;
        }
    st = golem_digest_bytes((golem_bytes){wire, used}, &a.snapshot);
    if (st == GOLEM_OK) *out = a;
    return st;
}

golem_status gi_journal_alias_observe(gi_journal *j, unsigned kind, gi_journal_alias_plan *out)
{
    if (!j || !out || kind > 2) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = restore(j, r);
    if (st == GOLEM_OK) st = alias_plan(j, kind, r, out);
    free(r); return st;
}

golem_status gi_journal_alias_remove(gi_journal *j, unsigned kind, const golem_digest *snapshot,
    gi_journal_guard guard, void *context, gi_journal_alias_plan *out)
{
    if (!j || !snapshot || !guard || !out || kind > 2) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->poisoned || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    j->busy = true;
    gi_journal_alias_plan before, after;
    golem_status st = GOLEM_OK;
    for (unsigned pass = 0; pass < 2 && st == GOLEM_OK; ++pass) {
        st = guard(context);
        if (st == GOLEM_OK) st = restore(j, r);
        if (st == GOLEM_OK) st = alias_plan(j, kind, r, &before);
        if (st == GOLEM_OK && (!before.present || memcmp(before.snapshot.bytes, snapshot->bytes, 32)))
            st = GOLEM_ERR_INVALID_STATE;
    }
    if (st == GOLEM_OK) {
        const char *suffix[] = {"prep.pending", "payload.pending", "event.pending"};
        char path[64]; name(path, sizeof(path), before.sequence, suffix[kind]);
        if (unlinkat(j->root, path, 0) < 0 || fsync(j->root) < 0) st = GOLEM_ERR_IO;
        if (st == GOLEM_OK) st = restore(j, r);
        if (st == GOLEM_OK) st = alias_plan(j, kind, r, &after);
        gi_quota_state expected = before.state.usage;
        expected.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_BYTES] -= before.bytes;
        --expected.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_ENTRIES];
        if (st == GOLEM_OK && (after.present || before.device != after.device || before.inode != after.inode ||
            before.bytes != after.bytes || memcmp(before.final_digest.bytes, after.final_digest.bytes, 32) ||
            before.state.committed != after.state.committed || memcmp(before.state.head.bytes, after.state.head.bytes, 32) ||
            memcmp(&expected, &after.state.usage, sizeof(expected)))) st = GOLEM_ERR_INVALID_STATE;
        if (st != GOLEM_OK) j->poisoned = true;
    }
    if (st == GOLEM_OK) *out = after;
    j->busy = false; free(r); return st;
}

static golem_status partial_plan_mode(gi_journal *j, unsigned kind, replay *r, gi_journal_partial_plan *out,
                                     bool recovery, quarantine_layout *layout)
{
    if (kind > 2 || !r->count) return GOLEM_ERR_INVALID_STATE;
    record *rec = &r->records[r->count - 1];
    if (number(rec->prep + 8) != GI_QUOTA_INTAKE) return GOLEM_ERR_INVALID_STATE;
    gi_journal_partial_plan p = {0};
    char preparation_path[64]; struct stat preparation_file;
    name(preparation_path, sizeof(preparation_path), r->count, "prep");
    if (fstatat(j->root, preparation_path, &preparation_file, AT_SYMLINK_NOFOLLOW) < 0 ||
        preparation_file.st_nlink != 1 || (preparation_file.st_mode & 0777) != 0400)
        return GOLEM_ERR_INVALID_STATE;
    struct stat directory;
    p.directory_present = fstatat(j->root, "quarantine", &directory, AT_SYMLINK_NOFOLLOW) == 0;
    if (!p.directory_present && errno != ENOENT) return GOLEM_ERR_IO;
    gi_journal_alias_plan *a = &p.source;
    a->sequence = r->count; a->kind = kind; a->state = r->status; a->preparation = rec->prep_digest;
    memcpy(a->operation.bytes, rec->prep + 32, 32); memcpy(a->request.bytes, rec->prep + 64, 32);
    memcpy(a->payload.bytes, rec->prep + 128, 32);
    p.payload_bytes = number(rec->prep + 24); p.payload_ready = rec->payload_ready;
    uint8_t *archived = NULL; size_t archived_size = 0;
    golem_status st = quarantine_read_mode(j, r->count, kind, rec, &archived, &archived_size, &p.archived,
                                           recovery, layout);
    char path[64]; uint8_t *data = NULL; size_t n = 0;
    for (unsigned i = 0; st == GOLEM_OK && i < 3; ++i) {
        (void)snprintf(path, sizeof(path), "%08zu.%s.pending", r->count, file_kinds[i]);
        struct stat file;
        if (fstatat(j->root, path, &file, AT_SYMLINK_NOFOLLOW) < 0) {
            if (errno != ENOENT) st = GOLEM_ERR_IO;
            continue;
        }
        if (i != kind || !S_ISREG(file.st_mode) || file.st_nlink != 1 ||
            file.st_uid != geteuid() || (file.st_mode & 0077)) { st = GOLEM_ERR_INVALID_STATE; break; }
        st = read_file(j->root, path, GI_CONTROL_MAX, &data, &n, &a->present);
        struct stat checked;
        if (st == GOLEM_OK && (fstatat(j->root, path, &checked, AT_SYMLINK_NOFOLLOW) < 0 ||
            !same_file(&file, &checked))) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK && !a->present) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){data, n}, &a->final_digest);
        a->device = (uint64_t)file.st_dev; a->inode = (uint64_t)file.st_ino; a->bytes = n;
        if (st == GOLEM_OK && p.archived && (number(archived + 32) != a->device ||
            number(archived + 40) != a->inode || number(archived + 48) != a->bytes ||
            memcmp(archived + 160, a->final_digest.bytes, 32) ||
            memcmp(archived + QUARANTINE_HEADER, data, n))) st = GOLEM_ERR_INVALID_STATE;
        free(data); data = NULL;
    }
    if (st == GOLEM_OK && p.archived) {
        a->device = number(archived + 32); a->inode = number(archived + 40); a->bytes = number(archived + 48);
        memcpy(a->final_digest.bytes, archived + 160, 32); memcpy(p.approval.bytes, archived + 192, 32);
    }
    free(archived);
    if (st == GOLEM_OK && !a->present && !p.archived) st = GOLEM_ERR_INVALID_STATE;
    uint8_t wire[440] = {0}; size_t used = 8;
    memcpy(wire, "GIPAR001", 8);
    uint64_t values[] = {a->sequence, kind, a->device, a->inode, a->bytes, a->present,
        p.archived, p.payload_ready, p.payload_bytes, a->state.committed, a->state.pending, p.directory_present};
    for (unsigned i = 0; i < 12; ++i) { encode(wire + used, values[i]); used += 8; }
    const golem_digest *digests[] = {&a->operation, &a->request, &a->preparation, &a->payload,
        &a->final_digest, &p.approval, &a->state.head};
    for (unsigned i = 0; i < 7; ++i) { memcpy(wire + used, digests[i]->bytes, 32); used += 32; }
    for (unsigned lane = 0; lane < GI_QUOTA_LANES; ++lane)
        for (unsigned axis = 0; axis < GI_QUOTA_AXES; ++axis) {
            encode(wire + used, a->state.usage.lane[lane].value[axis]); used += 8;
        }
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){wire, used}, &a->snapshot);
    if (st == GOLEM_OK) *out = p;
    return st;
}

static golem_status partial_plan(gi_journal *j, unsigned kind, replay *r, gi_journal_partial_plan *out)
{
    return partial_plan_mode(j, kind, r, out, false, NULL);
}

static golem_status envelope_plan(gi_journal *j, unsigned kind, replay *r, gi_journal_envelope_plan *out)
{
    gi_journal_envelope_plan p = {0}; quarantine_layout layout;
    golem_status st = partial_plan_mode(j, kind, r, &p.partial, true, &layout);
    if (st == GOLEM_OK && (!p.partial.archived || !p.partial.source.present)) st = GOLEM_ERR_INVALID_STATE;
    if (st != GOLEM_OK) return st;
    p.final_present = layout.final_present; p.pending_present = layout.pending_present;
    p.device = layout.device; p.inode = layout.inode; p.bytes = layout.bytes; p.digest = layout.digest;
    uint8_t wire[112] = {0};
    memcpy(wire, "GIQFN001", 8); memcpy(wire + 8, p.partial.source.snapshot.bytes, 32);
    encode(wire + 40, p.final_present); encode(wire + 48, p.pending_present);
    encode(wire + 56, p.device); encode(wire + 64, p.inode); encode(wire + 72, p.bytes);
    memcpy(wire + 80, p.digest.bytes, 32);
    st = golem_digest_bytes((golem_bytes){wire, sizeof(wire)}, &p.snapshot);
    if (st == GOLEM_OK) *out = p;
    return st;
}

golem_status gi_journal_envelope_observe(gi_journal *j, unsigned kind, gi_journal_envelope_plan *out)
{
    if (!j || !out || kind > 2) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = restore_mode(j, r, (int)kind);
    if (st == GOLEM_OK) st = envelope_plan(j, kind, r, out);
    free(r); return st;
}

golem_status gi_journal_envelope_check_quota(const gi_journal_envelope_plan *p)
{
    if (!p || p->bytes < QUARANTINE_HEADER || p->bytes > QUARANTINE_HEADER + GI_CONTROL_MAX ||
        !p->pending_present) return GOLEM_ERR_INVALID_ARGUMENT;
    gi_quota_usage retained = {{0}}, peak = {{0}}; gi_quota_state checked;
    if (!p->final_present) {
        peak.value[GI_QUOTA_BYTES] = p->bytes; peak.value[GI_QUOTA_ENTRIES] = 1;
    }
    return gi_quota_project(&p->partial.source.state.usage, GI_QUOTA_INTAKE, &retained, &peak, &checked);
}

static bool envelope_unchanged(const gi_journal_envelope_plan *a, const gi_journal_envelope_plan *b)
{
    const gi_journal_alias_plan *x = &a->partial.source, *y = &b->partial.source;
    return a->device == b->device && a->inode == b->inode && a->bytes == b->bytes &&
        !memcmp(a->digest.bytes, b->digest.bytes, 32) &&
        x->device == y->device && x->inode == y->inode && x->bytes == y->bytes && y->present &&
        x->sequence == y->sequence && x->kind == y->kind &&
        !memcmp(x->final_digest.bytes, y->final_digest.bytes, 32) &&
        !memcmp(x->preparation.bytes, y->preparation.bytes, 32) &&
        !memcmp(x->operation.bytes, y->operation.bytes, 32) && !memcmp(x->request.bytes, y->request.bytes, 32) &&
        !memcmp(a->partial.approval.bytes, b->partial.approval.bytes, 32) &&
        a->partial.payload_ready == b->partial.payload_ready &&
        x->state.committed == y->state.committed && !memcmp(x->state.head.bytes, y->state.head.bytes, 32);
}

golem_status gi_journal_envelope_finish(gi_journal *j, unsigned kind, const golem_digest *snapshot,
    const golem_digest *approval, gi_journal_guard guard, void *context, gi_journal_envelope_plan *out)
{
    if (!j || kind > 2 || !snapshot || !approval || !guard || !out) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->poisoned || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    j->busy = true;
    gi_journal_envelope_plan before, after; golem_status st = GOLEM_OK;
    for (unsigned pass = 0; st == GOLEM_OK && pass < 2; ++pass) {
        st = guard(context);
        if (st == GOLEM_OK) st = restore_mode(j, r, (int)kind);
        if (st == GOLEM_OK) st = envelope_plan(j, kind, r, &before);
        if (st == GOLEM_OK && (!before.pending_present || memcmp(before.snapshot.bytes, snapshot->bytes, 32) ||
            memcmp(before.partial.approval.bytes, approval->bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) st = gi_journal_envelope_check_quota(&before);
    }
    int fd = -1; bool started = false;
    char final[64], pending[80]; gi_quota_state expected_usage;
    if (st == GOLEM_OK) {
        name(final, sizeof(final), before.partial.source.sequence, file_kinds[kind]);
        (void)snprintf(pending, sizeof(pending), "%s.pending", final);
        fd = openat(j->root, "quarantine", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (fd < 0) st = GOLEM_ERR_IO;
    }
    if (st == GOLEM_OK) {
        int source = openat(fd, pending, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
        struct stat file;
        if (source < 0) st = GOLEM_ERR_IO;
        else {
            if (fstat(source, &file) < 0 || (uint64_t)file.st_dev != before.device ||
                (uint64_t)file.st_ino != before.inode || (uint64_t)file.st_size != before.bytes) st = GOLEM_ERR_INVALID_STATE;
            if (st == GOLEM_OK && fsync(source) < 0) st = GOLEM_ERR_IO;
            if (close(source) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
        }
    }
    if (st == GOLEM_OK) {
        expected_usage = before.partial.source.state.usage;
        if (!before.final_present) {
            started = true;
            if (linkat(fd, pending, fd, final, 0) < 0) st = GOLEM_ERR_IO;
            expected_usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_BYTES] += before.bytes;
            ++expected_usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_ENTRIES];
        }
        if (st == GOLEM_OK && fsync(fd) < 0) st = GOLEM_ERR_IO;
    }
    if (st == GOLEM_OK) st = guard(context);
    if (st == GOLEM_OK) st = restore_mode(j, r, (int)kind);
    if (st == GOLEM_OK) st = envelope_plan(j, kind, r, &after);
    if (st == GOLEM_OK && (!after.final_present || !after.pending_present || !envelope_unchanged(&before, &after) ||
        memcmp(&expected_usage, &after.partial.source.state.usage, sizeof(expected_usage)))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) {
        started = true;
        if (unlinkat(fd, pending, 0) < 0 || fsync(fd) < 0) st = GOLEM_ERR_IO;
        expected_usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_BYTES] -= before.bytes;
        --expected_usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_ENTRIES];
        if (st == GOLEM_OK) st = restore_mode(j, r, (int)kind);
        if (st == GOLEM_OK) st = envelope_plan(j, kind, r, &after);
        if (st == GOLEM_OK && (!after.final_present || after.pending_present || !envelope_unchanged(&before, &after) ||
            memcmp(&expected_usage, &after.partial.source.state.usage, sizeof(expected_usage)))) st = GOLEM_ERR_INVALID_STATE;
    }
    if (fd >= 0 && close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (started && st != GOLEM_OK) j->poisoned = true;
    if (st == GOLEM_OK) *out = after;
    j->busy = false; free(r); return st;
}

golem_status gi_journal_partial_observe(gi_journal *j, unsigned kind, gi_journal_partial_plan *out)
{
    if (!j || !out || kind > 2) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = restore(j, r);
    if (st == GOLEM_OK) st = partial_plan(j, kind, r, out);
    free(r); return st;
}

golem_status gi_journal_partial_check_quota(const gi_journal_partial_plan *p, bool replace)
{
    if (!p || p->source.bytes > GI_CONTROL_MAX || p->payload_bytes > GI_CONTROL_MAX)
        return GOLEM_ERR_INVALID_ARGUMENT;
    uint64_t bytes = replace ? p->payload_bytes : QUARANTINE_HEADER + p->source.bytes;
    if (!replace && p->archived) {
        gi_quota_usage zero = {{0}}; gi_quota_state checked;
        return gi_quota_project(&p->source.state.usage, GI_QUOTA_INTAKE, &zero, &zero, &checked);
    }
    uint64_t directory = p->directory_present ? 0 : 1;
    gi_quota_usage retained = {{0, 0, bytes, 1 + directory}};
    gi_quota_usage peak = {{0, 0, 2 * bytes, 2 + directory}};
    gi_quota_state projected;
    return gi_quota_project(&p->source.state.usage, GI_QUOTA_INTAKE, &retained, &peak, &projected);
}

golem_status gi_journal_partial_quarantine(gi_journal *j, unsigned kind, const golem_digest *snapshot,
    const golem_digest *approval, gi_journal_guard guard, void *context, gi_journal_partial_plan *out)
{
    if (!j || !snapshot || !approval || !guard || !out || kind > 2) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->poisoned || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    j->busy = true;
    gi_journal_partial_plan before, after; golem_status st = GOLEM_OK;
    for (unsigned pass = 0; st == GOLEM_OK && pass < 2; ++pass) {
        st = guard(context);
        if (st == GOLEM_OK) st = restore(j, r);
        if (st == GOLEM_OK) st = partial_plan(j, kind, r, &before);
        if (st == GOLEM_OK && (!before.source.present ||
            memcmp(before.source.snapshot.bytes, snapshot->bytes, 32) ||
            (before.archived && memcmp(before.approval.bytes, approval->bytes, 32)))) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) st = gi_journal_partial_check_quota(&before, false);
    }
    bool started = false;
    if (st == GOLEM_OK && !before.archived) {
        char path[64]; (void)snprintf(path, sizeof(path), "%08llu.%s.pending",
            (unsigned long long)before.source.sequence, file_kinds[kind]);
        uint8_t *raw = NULL; size_t size = 0; bool exists = false;
        st = read_file(j->root, path, GI_CONTROL_MAX, &raw, &size, &exists);
        golem_digest digest;
        if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){raw, size}, &digest);
        if (st == GOLEM_OK && (!exists || size != before.source.bytes ||
            memcmp(digest.bytes, before.source.final_digest.bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
        uint8_t *wire = NULL; size_t wire_size = 0;
        if (st == GOLEM_OK) {
            gi_fragment_binding binding = {.original = before, .original_approval = *approval};
            st = gi_quarantine_encode(&binding, (golem_bytes){raw, size}, &wire, &wire_size);
        }
        if (st == GOLEM_OK) {
            started = true;
            if (mkdirat(j->root, "quarantine", 0700) < 0 && errno != EEXIST) st = GOLEM_ERR_IO;
            if (st == GOLEM_OK && fsync(j->root) < 0) st = GOLEM_ERR_IO;
            int fd = st == GOLEM_OK ? openat(j->root, "quarantine", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC) : -1;
            if (st == GOLEM_OK && fd < 0) st = GOLEM_ERR_IO;
            if (st == GOLEM_OK) {
                gi_journal container = {.root = fd};
                st = publish(&container, before.source.sequence, file_kinds[kind],
                             (golem_bytes){wire, wire_size});
            }
            if (fd >= 0 && close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
        }
        free(raw); free(wire);
    }
    /* Durable envelope must validate against the still-present source before
     * separation. A crash leaves evidence and requires a fresh owner plan. */
    if (st == GOLEM_OK) st = guard(context);
    if (st == GOLEM_OK) st = restore(j, r);
    if (st == GOLEM_OK) st = partial_plan(j, kind, r, &after);
    gi_quota_state expected_usage;
    if (st == GOLEM_OK) {
        expected_usage = before.source.state.usage;
        if (!before.archived) {
            expected_usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_BYTES] += QUARANTINE_HEADER + before.source.bytes;
            expected_usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_ENTRIES] += 1 + !before.directory_present;
        }
    }
    if (st == GOLEM_OK && (!after.archived || !after.source.present ||
        memcmp(after.approval.bytes, approval->bytes, 32) ||
        after.source.device != before.source.device || after.source.inode != before.source.inode ||
        after.payload_ready != before.payload_ready || after.source.state.committed != before.source.state.committed ||
        memcmp(after.source.state.head.bytes, before.source.state.head.bytes, 32) ||
        memcmp(&after.source.state.usage, &expected_usage, sizeof(expected_usage)) ||
        memcmp(after.source.final_digest.bytes, before.source.final_digest.bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) {
        char path[64]; (void)snprintf(path, sizeof(path), "%08llu.%s.pending",
            (unsigned long long)before.source.sequence, file_kinds[kind]);
        started = true;
        if (unlinkat(j->root, path, 0) < 0 || fsync(j->root) < 0) st = GOLEM_ERR_IO;
        if (st == GOLEM_OK) st = restore(j, r);
        if (st == GOLEM_OK) st = partial_plan(j, kind, r, &after);
        expected_usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_BYTES] -= before.source.bytes;
        --expected_usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_ENTRIES];
        if (st == GOLEM_OK && (after.source.present || !after.archived ||
            memcmp(&after.source.state.usage, &expected_usage, sizeof(expected_usage)) ||
            after.source.state.committed != before.source.state.committed ||
            memcmp(after.source.state.head.bytes, before.source.state.head.bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
    }
    if (started && st != GOLEM_OK) j->poisoned = true;
    if (st == GOLEM_OK) *out = after;
    j->busy = false; free(r); return st;
}

golem_status gi_journal_payload_replace(gi_journal *j, const golem_digest *snapshot, golem_bytes payload,
    gi_journal_guard guard, void *context, gi_journal_partial_plan *out)
{
    if (!j || !snapshot || !guard || !out || (!payload.data && payload.size)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (payload.size > GI_CONTROL_MAX) return GOLEM_ERR_OVERFLOW;
    if (j->busy || j->poisoned || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    j->busy = true;
    golem_digest digest; golem_status st = golem_digest_bytes(payload, &digest);
    gi_journal_partial_plan before, after;
    for (unsigned pass = 0; st == GOLEM_OK && pass < 2; ++pass) {
        st = guard(context);
        if (st == GOLEM_OK) st = restore(j, r);
        if (st == GOLEM_OK) st = partial_plan(j, 1, r, &before);
        if (st == GOLEM_OK && (!before.archived || before.source.present || before.payload_ready ||
            r->status.committed + 1 != r->count || r->records[r->count - 1].staging ||
            memcmp(before.source.snapshot.bytes, snapshot->bytes, 32) || payload.size != before.payload_bytes ||
            memcmp(digest.bytes, before.source.payload.bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) st = gi_journal_partial_check_quota(&before, true);
    }
    if (st == GOLEM_OK) {
        st = publish(j, before.source.sequence, "payload", payload);
        if (st == GOLEM_OK) st = restore(j, r);
        if (st == GOLEM_OK) st = partial_plan(j, 1, r, &after);
        gi_quota_state expected_usage = before.source.state.usage;
        expected_usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_BYTES] += payload.size;
        ++expected_usage.lane[GI_QUOTA_INTAKE].value[GI_QUOTA_ENTRIES];
        if (st == GOLEM_OK && (!after.payload_ready || after.source.state.committed != before.source.state.committed ||
            memcmp(&after.source.state.usage, &expected_usage, sizeof(expected_usage)) ||
            memcmp(after.source.state.head.bytes, before.source.state.head.bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
        if (st != GOLEM_OK) j->poisoned = true;
    }
    if (st == GOLEM_OK) *out = after;
    j->busy = false; free(r); return st;
}

static golem_status pending_plan(replay *r, gi_journal_pending_plan *out)
{
    if (!r->count || r->count != r->status.committed + 1 || !r->status.pending)
        return GOLEM_ERR_INVALID_STATE;
    record *rec = &r->records[r->count - 1];
    if (rec->committed || rec->staging || !rec->payload_ready || number(rec->prep + 8) != GI_QUOTA_INTAKE)
        return GOLEM_ERR_INVALID_STATE;
    gi_journal_pending_plan p = {0};
    p.sequence = r->count; p.payload_bytes = number(rec->prep + 24);
    memcpy(p.operation.bytes, rec->prep + 32, 32);
    memcpy(p.request.bytes, rec->prep + 64, 32);
    p.head = r->status.head; p.preparation = rec->prep_digest;
    memcpy(p.payload.bytes, rec->prep + 128, 32);
    uint8_t binding[184] = {0};
    memcpy(binding, "GIRCV001", 8); encode(binding + 8, p.sequence); encode(binding + 16, p.payload_bytes);
    memcpy(binding + 24, p.operation.bytes, 32); memcpy(binding + 56, p.request.bytes, 32);
    memcpy(binding + 88, p.head.bytes, 32); memcpy(binding + 120, p.preparation.bytes, 32);
    memcpy(binding + 152, p.payload.bytes, 32);
    golem_status st = golem_digest_bytes((golem_bytes){binding, sizeof(binding)}, &p.snapshot);
    if (st == GOLEM_OK) *out = p;
    return st;
}

golem_status gi_journal_pending_plan_get(gi_journal *j, gi_journal_pending_plan *out)
{
    if (!j || !out) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = restore(j, r);
    if (st == GOLEM_OK) st = pending_plan(r, out);
    free(r); return st;
}

golem_status gi_journal_pending_finish(gi_journal *j, const golem_digest *snapshot,
    gi_journal_guard guard, void *context, gi_journal_receipt *out)
{
    if (!j || !snapshot || !guard || !out) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->poisoned || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    j->busy = true;
    gi_journal_pending_plan p;
    golem_status st = GOLEM_OK;
    for (unsigned pass = 0; pass < 2 && st == GOLEM_OK; ++pass) {
        st = guard(context);
        if (st == GOLEM_OK) st = restore(j, r);
        if (st == GOLEM_OK) st = pending_plan(r, &p);
        if (st == GOLEM_OK && memcmp(p.snapshot.bytes, snapshot->bytes, 32)) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) {
            gi_quota_usage added = {{0, 0, FRAME_SIZE, 1}}, peak = {{0, 0, 2 * FRAME_SIZE, 2}};
            gi_quota_state projected;
            st = gi_quota_project(&r->status.usage, GI_QUOTA_INTAKE, &added, &peak, &projected);
        }
    }
    uint8_t frame[FRAME_SIZE] = {0}; golem_digest digest;
    if (st == GOLEM_OK) {
        memcpy(frame, "GIQEV001", 8); encode(frame + 8, p.sequence);
        memcpy(frame + 16, p.head.bytes, 32); memcpy(frame + 48, p.preparation.bytes, 32);
        st = golem_digest_bytes((golem_bytes){frame, sizeof(frame)}, &digest);
    }
    if (st == GOLEM_OK) {
        st = publish(j, p.sequence, "event", (golem_bytes){frame, sizeof(frame)});
        if (st != GOLEM_OK) j->poisoned = true;
    }
    if (st == GOLEM_OK) *out = (gi_journal_receipt){p.sequence, digest, false};
    j->busy = false; free(r); return st;
}

static golem_status preservation_read(gi_journal *j, size_t seq, unsigned kind, const record *rec,
    bool damage, gi_journal_fragment_plan *p, uint8_t **raw, size_t *n, uint8_t **cut)
{
    return damage ? damage_read(j, seq, kind, rec, true, p, raw, n, cut) :
        fragment_read(j, seq, kind, rec, true, p, raw, n, cut);
}

static golem_status preservation_plan(gi_journal *j, unsigned kind, replay *r, bool damage, gi_journal_fragment_plan *out)
{
    if (!r->count || kind > 2) return GOLEM_ERR_INVALID_STATE;
    char path[64]; struct stat file;
    name(path, sizeof(path), r->count, "prep");
    if (fstatat(j->root, path, &file, AT_SYMLINK_NOFOLLOW) < 0 || file.st_nlink != 1 ||
        (file.st_mode & 0777) != 0400) return GOLEM_ERR_INVALID_STATE;
    for (unsigned k = 0; k < 3; ++k) {
        if (k == kind) continue;
        (void)snprintf(path, sizeof(path), "%08zu.%s.pending", r->count, file_kinds[k]);
        if (fstatat(j->root, path, &file, AT_SYMLINK_NOFOLLOW) == 0 || errno != ENOENT) return GOLEM_ERR_INVALID_STATE;
    }
    uint8_t *raw = NULL, *cut = NULL; size_t n = 0; gi_journal_fragment_plan p;
    golem_status st = preservation_read(j, r->count, kind, &r->records[r->count - 1], damage, &p, &raw, &n, &cut);
    free(raw); free(cut);
    if (st != GOLEM_OK) return st;
    if (!p.original.source.present) return GOLEM_ERR_INVALID_STATE;
    p.original.source.state = r->status;
    uint8_t wire[768] = {0}; size_t used = 8; memcpy(wire, damage ? "GIDPL001" : "GIFPL001", 8);
    uint64_t v[] = {r->count, kind, p.device, p.inode, p.bytes, p.object_device, p.object_inode,
        p.object_bytes, p.truncated_present, p.final_present, p.pending_present, p.original.source.device,
        p.original.source.inode, p.original.source.bytes, r->status.committed, r->status.pending,
        p.original.payload_ready, p.original.payload_bytes};
    for (unsigned i = 0; i < 18; ++i) { encode(wire + used, v[i]); used += 8; }
    const golem_digest *d[] = {&p.digest, &p.object_digest, &p.preservation_approval, &p.original.approval,
        &p.original.source.preparation, &p.original.source.operation, &p.original.source.request,
        &p.original.source.payload, &p.original.source.final_digest, &r->status.head};
    for (unsigned i = 0; i < 10; ++i) { memcpy(wire + used, d[i]->bytes, 32); used += 32; }
    for (unsigned l = 0; l < GI_QUOTA_LANES; ++l)
        for (unsigned a = 0; a < GI_QUOTA_AXES; ++a) { encode(wire + used, r->status.usage.lane[l].value[a]); used += 8; }
    if (damage) {
        encode(wire + used, p.envelope_device); used += 8;
        encode(wire + used, p.envelope_inode); used += 8;
        encode(wire + used, p.envelope_bytes); used += 8;
        memcpy(wire + used, p.envelope_digest.bytes, 32); used += 32;
        memcpy(wire + used, p.fragment_approval.bytes, 32); used += 32;
    }
    st = golem_digest_bytes((golem_bytes){wire, used}, &p.snapshot);
    if (st == GOLEM_OK) *out = p;
    return st;
}

golem_status gi_journal_fragment_observe(gi_journal *j, unsigned kind, gi_journal_fragment_plan *out)
{
    if (!j || !out || kind > 2) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r)); if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = restore_mode(j, r, (int)kind + 3);
    if (st == GOLEM_OK) st = preservation_plan(j, kind, r, false, out);
    free(r); return st;
}

golem_status gi_journal_damage_observe(gi_journal *j, unsigned kind, gi_journal_fragment_plan *out)
{
    if (!j || !out || kind > 2) return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r)); if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    golem_status st = restore_mode(j, r, (int)kind + 6);
    if (st == GOLEM_OK) st = preservation_plan(j, kind, r, true, out);
    free(r); return st;
}

golem_status gi_journal_damage_visit(gi_journal *j, unsigned kind, gi_journal_visitor visitor, void *context)
{
    if (kind > 2) return GOLEM_ERR_INVALID_ARGUMENT;
    return visit_mode(j, visitor, context, (int)kind + 6);
}

static bool fragment_same(const gi_journal_fragment_plan *a, const gi_journal_fragment_plan *b)
{
    const gi_journal_alias_plan *x = &a->original.source, *y = &b->original.source;
    return a->envelope_device == b->envelope_device && a->envelope_inode == b->envelope_inode &&
        a->envelope_bytes == b->envelope_bytes && !memcmp(a->envelope_digest.bytes, b->envelope_digest.bytes, 32) &&
        !memcmp(a->fragment_approval.bytes, b->fragment_approval.bytes, 32) &&
        a->device == b->device && a->inode == b->inode && a->bytes == b->bytes &&
        !memcmp(a->digest.bytes, b->digest.bytes, 32) && x->sequence == y->sequence && x->kind == y->kind &&
        x->device == y->device && x->inode == y->inode && x->bytes == y->bytes && y->present &&
        !memcmp(x->preparation.bytes, y->preparation.bytes, 32) && !memcmp(x->final_digest.bytes, y->final_digest.bytes, 32) &&
        !memcmp(a->original.approval.bytes, b->original.approval.bytes, 32) &&
        x->state.committed == y->state.committed && !memcmp(x->state.head.bytes, y->state.head.bytes, 32);
}

static golem_status preservation_apply(gi_journal *j, unsigned kind, unsigned action, bool damage,
    const golem_digest *snapshot, const golem_digest *original_approval,
    const golem_digest *preservation_approval, gi_journal_guard guard, void *context, gi_journal_fragment_plan *out)
{
    if (!j || kind > 2 || action > 2 || !snapshot || !original_approval || !preservation_approval || !guard || !out)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->busy || j->poisoned || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r)); if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    j->busy = true; gi_journal_fragment_plan before, after; golem_status st = GOLEM_OK;
    for (unsigned pass = 0; pass < 2 && st == GOLEM_OK; ++pass) {
        st = guard(context);
        if (st == GOLEM_OK) st = restore_mode(j, r, (int)kind + (damage ? 6 : 3));
        if (st == GOLEM_OK) st = preservation_plan(j, kind, r, damage, &before);
        if (st == GOLEM_OK && (!before.truncated_present || memcmp(before.snapshot.bytes, snapshot->bytes, 32) ||
            memcmp(before.original.approval.bytes, original_approval->bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK && ((action == 0 && (before.final_present || before.pending_present)) ||
            (action == 1 && !before.pending_present) || (action == 2 && (!before.final_present || before.pending_present)) ||
            (action && memcmp(before.preservation_approval.bytes, preservation_approval->bytes, 32)))) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) st = damage ?
            gi_fragment_damage_check_quota(&r->status.usage, before.bytes, before.final_present, before.pending_present) :
            gi_fragment_check_quota(&r->status.usage, before.bytes, before.final_present, before.pending_present);
    }
    int fd = -1; bool started = false; char suffix[64], final[96], pending[112], original[96];
    gi_quota_state usage;
    if (st == GOLEM_OK) {
        (void)snprintf(suffix, sizeof(suffix), damage ? "%s.fragment.damage" : "%s.fragment", file_kinds[kind]);
        name(final, sizeof(final), before.original.source.sequence, suffix);
        (void)snprintf(pending, sizeof(pending), "%s.pending", final);
        (void)snprintf(original, sizeof(original), damage ? "%08llu.%s.fragment.pending" : "%08llu.%s.pending",
            (unsigned long long)before.original.source.sequence, file_kinds[kind]);
        usage = before.original.source.state.usage;
        fd = openat(j->root, "quarantine", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (fd < 0) st = GOLEM_ERR_IO;
    }
    if (st == GOLEM_OK && action == 0) {
        uint8_t *raw = NULL, *cut = NULL, *wire = NULL; size_t raw_size = 0, n = 0; gi_journal_fragment_plan seen;
        st = preservation_read(j, r->count, kind, &r->records[r->count - 1], damage, &seen, &raw, &raw_size, &cut);
        if (st == GOLEM_OK) {
            seen.original.source.state = before.original.source.state;
            if (!fragment_same(&before, &seen)) st = GOLEM_ERR_INVALID_STATE;
        }
        gi_fragment_binding b = {.original = before.original, .original_approval = *original_approval,
            .preservation_approval = *preservation_approval, .envelope_device = before.device, .envelope_inode = before.inode};
        if (st == GOLEM_OK && damage) {
            uint8_t *env = NULL; size_t env_n = 0; bool exists = false; char env_path[96];
            (void)snprintf(env_path, sizeof(env_path), "%08llu.%s.pending",
                (unsigned long long)before.original.source.sequence, file_kinds[kind]);
            st = read_file(fd, env_path, GI_CONTROL_MAX + 320, &env, &env_n, &exists);
            if (st == GOLEM_OK && !exists) st = GOLEM_ERR_INVALID_STATE;
            b.preservation_approval = before.fragment_approval;
            b.envelope_device = before.envelope_device; b.envelope_inode = before.envelope_inode;
            gi_fragment_damage_binding db = {.fragment = b, .device = before.device,
                .inode = before.inode, .approval = *preservation_approval};
            if (st == GOLEM_OK) st = gi_fragment_damage_encode(&db, (golem_bytes){raw, raw_size},
                (golem_bytes){env, env_n}, (golem_bytes){cut, before.bytes}, &wire, &n);
            free(env);
        } else if (st == GOLEM_OK) st = gi_fragment_encode(&b, (golem_bytes){raw, raw_size}, (golem_bytes){cut, before.bytes}, &wire, &n);
        if (st == GOLEM_OK) {
            started = true; gi_journal container = {.root = fd};
            st = publish(&container, before.original.source.sequence, suffix, (golem_bytes){wire, n});
            usage.lane[0].value[GI_QUOTA_BYTES] += n; ++usage.lane[0].value[GI_QUOTA_ENTRIES];
        }
        free(raw); free(cut); free(wire);
    } else if (st == GOLEM_OK && action == 1) {
        int source = openat(fd, pending, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
        if (source < 0) st = GOLEM_ERR_IO;
        else { if (fsync(source) < 0) st = GOLEM_ERR_IO; if (close(source) < 0) st = GOLEM_ERR_IO; }
        if (st == GOLEM_OK && !before.final_present) {
            started = true;
            if (linkat(fd, pending, fd, final, 0) < 0 || fsync(fd) < 0) st = GOLEM_ERR_IO;
        }
        if (st == GOLEM_OK) st = guard(context);
        if (st == GOLEM_OK) st = restore_mode(j, r, (int)kind + (damage ? 6 : 3));
        if (st == GOLEM_OK) st = preservation_plan(j, kind, r, damage, &after);
        gi_quota_state linked_usage = usage;
        if (!before.final_present) {
            linked_usage.lane[0].value[GI_QUOTA_BYTES] += before.object_bytes;
            ++linked_usage.lane[0].value[GI_QUOTA_ENTRIES];
        }
        if (st == GOLEM_OK && (!fragment_same(&before, &after) || !after.final_present || !after.pending_present ||
            after.object_device != before.object_device || after.object_inode != before.object_inode ||
            memcmp(after.object_digest.bytes, before.object_digest.bytes, 32) ||
            memcmp(&linked_usage, &after.original.source.state.usage, sizeof(linked_usage)))) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) {
            started = true;
            if (unlinkat(fd, pending, 0) < 0 || fsync(fd) < 0) st = GOLEM_ERR_IO;
            if (before.final_present) {
                usage.lane[0].value[GI_QUOTA_BYTES] -= before.object_bytes; --usage.lane[0].value[GI_QUOTA_ENTRIES];
            }
        }
    } else if (st == GOLEM_OK) {
        started = true;
        if (unlinkat(fd, original, 0) < 0 || fsync(fd) < 0) st = GOLEM_ERR_IO;
        usage.lane[0].value[GI_QUOTA_BYTES] -= before.bytes; --usage.lane[0].value[GI_QUOTA_ENTRIES];
    }
    if (st == GOLEM_OK) st = guard(context);
    if (st == GOLEM_OK) st = restore_mode(j, r, (int)kind + (damage ? 6 : 3));
    if (st == GOLEM_OK) st = preservation_plan(j, kind, r, damage, &after);
    if (st == GOLEM_OK && (!fragment_same(&before, &after) || !after.final_present || after.pending_present ||
        after.truncated_present != (action != 2) || memcmp(after.preservation_approval.bytes, preservation_approval->bytes, 32) ||
        memcmp(&usage, &after.original.source.state.usage, sizeof(usage)))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && action && (before.object_device != after.object_device ||
        before.object_inode != after.object_inode || before.object_bytes != after.object_bytes ||
        memcmp(before.object_digest.bytes, after.object_digest.bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
    if (fd >= 0 && close(fd) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    if (started && st != GOLEM_OK) j->poisoned = true;
    if (st == GOLEM_OK) *out = after;
    j->busy = false; free(r); return st;
}

golem_status gi_journal_fragment_apply(gi_journal *j, unsigned kind, unsigned action,
    const golem_digest *snapshot, const golem_digest *original, const golem_digest *approval,
    gi_journal_guard guard, void *context, gi_journal_fragment_plan *out)
{
    return preservation_apply(j, kind, action, false, snapshot, original, approval, guard, context, out);
}

golem_status gi_journal_damage_apply(gi_journal *j, unsigned kind, unsigned action,
    const golem_digest *snapshot, const golem_digest *original, const golem_digest *approval,
    gi_journal_guard guard, void *context, gi_journal_fragment_plan *out)
{
    return preservation_apply(j, kind, action, true, snapshot, original, approval, guard, context, out);
}

golem_status gi_journal_append(gi_journal *j, gi_quota_lane lane,
    const golem_digest *operation, const golem_digest *request,
    uint64_t expected_sequence, const golem_digest *expected_head,
    golem_bytes payload, gi_journal_guard guard, void *context, gi_journal_receipt *out)
{
    gi_quota_usage limit;
    if (!j || !operation || !request || !expected_head || !out || !guard ||
        (!payload.data && payload.size) || gi_quota_limit(lane, &limit) != GOLEM_OK)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (payload.size > GI_CONTROL_MAX) return GOLEM_ERR_OVERFLOW;
    if (j->poisoned || j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    replay *r = malloc(sizeof(*r));
    if (!r) return GOLEM_ERR_OUT_OF_MEMORY;
    j->busy = true;
    golem_status st = guard(context);
    if (st == GOLEM_OK) st = restore(j, r);
    golem_digest body;
    if (st == GOLEM_OK) st = golem_digest_bytes(payload, &body);
    if (st == GOLEM_OK) {
        for (size_t i = 0; i < r->count; ++i) {
            record *rec = &r->records[i];
            if (memcmp(rec->prep + 32, operation->bytes, 32)) continue;
            if (!rec->committed || r->status.pending || number(rec->prep + 8) != (uint64_t)lane ||
                memcmp(rec->prep + 64, request->bytes, 32) || memcmp(rec->prep + 128, body.bytes, 32))
                st = GOLEM_ERR_INVALID_STATE;
            else *out = (gi_journal_receipt){i + 1, rec->event, true};
            free(r); j->busy = false; return st;
        }
        if (r->status.pending || expected_sequence != r->status.committed ||
            memcmp(expected_head->bytes, r->status.head.bytes, 32)) st = GOLEM_ERR_INVALID_STATE;
    }
    size_t seq = st == GOLEM_OK ? r->count + 1 : 0;
    uint8_t prep[PREP_SIZE] = {0}, frame[FRAME_SIZE] = {0};
    uint8_t *wire = NULL; size_t wire_size = 0;
    golem_digest prep_digest, event_digest;
    if (st == GOLEM_OK) {
        memcpy(prep, "GIQPRE01", 8); encode(prep + 8, (uint64_t)lane);
        encode(prep + 16, seq); encode(prep + 24, payload.size);
        memcpy(prep + 32, operation->bytes, 32); memcpy(prep + 64, request->bytes, 32);
        memcpy(prep + 96, expected_head->bytes, 32); memcpy(prep + 128, body.bytes, 32);
        st = prep_encode(prep, &wire, &wire_size);
    }
    if (st == GOLEM_OK) st = gi_domain_digest((golem_bytes){wire, wire_size}, &prep_digest, NULL);
    if (st == GOLEM_OK) {
        gi_quota_usage retained = {{1, payload.size, wire_size + payload.size + FRAME_SIZE, 3}};
        gi_quota_usage peak = {{1, payload.size, 2 * (wire_size + payload.size + FRAME_SIZE), 6}};
        gi_quota_state projected;
        st = gi_quota_project(&r->status.usage, lane, &retained, &peak, &projected);
    }
    bool started = false;
    if (st == GOLEM_OK) {
        started = true;
        st = publish(j, seq, "prep", (golem_bytes){wire, wire_size});
    }
    if (st == GOLEM_OK) st = publish(j, seq, "payload", payload);
    if (st == GOLEM_OK) st = guard(context);
    if (st == GOLEM_OK) st = restore(j, r); /* Same owner lock, no cached quota. */
    if (st == GOLEM_OK && (r->count != seq || r->status.committed != seq - 1 ||
        memcmp(r->records[seq - 1].prep, prep, PREP_SIZE) ||
        memcmp(r->records[seq - 1].prep_digest.bytes, prep_digest.bytes, 32) ||
        !r->records[seq - 1].payload_ready || r->records[seq - 1].staging)) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) {
        gi_quota_usage retained = {{0, 0, FRAME_SIZE, 1}}, peak = {{0, 0, 2 * FRAME_SIZE, 2}};
        gi_quota_state projected;
        st = gi_quota_project(&r->status.usage, lane, &retained, &peak, &projected);
    }
    if (st == GOLEM_OK) {
        memcpy(frame, "GIQEV001", 8); encode(frame + 8, seq);
        memcpy(frame + 16, expected_head->bytes, 32); memcpy(frame + 48, prep_digest.bytes, 32);
        st = golem_digest_bytes((golem_bytes){frame, sizeof(frame)}, &event_digest);
    }
    if (st == GOLEM_OK) st = publish(j, seq, "event", (golem_bytes){frame, sizeof(frame)});
    if (st == GOLEM_OK) *out = (gi_journal_receipt){seq, event_digest, false};
    if (started && st != GOLEM_OK) j->poisoned = true;
    free(wire); free(r); j->busy = false; return st;
}

typedef struct object_blob {
    char path[192]; gi_object_kind kind; golem_digest digest; golem_bytes bytes; bool fresh;
} object_blob;
static bool json_set(struct json_object *o, const char *key, struct json_object *value)
{
    if (!value) return false;
    if (json_object_object_add(o, key, value) == 0) return true;
    json_object_put(value); return false;
}
static golem_status blob_add(object_blob *blobs, size_t *count, gi_object_kind kind,
    const golem_digest *digest, golem_bytes bytes)
{
    object_blob b = {0}; b.kind = kind; b.digest = *digest; b.bytes = bytes;
    golem_status st = gi_object_path(kind, digest, b.path, sizeof(b.path));
    if (st != GOLEM_OK) return st;
    for (size_t i = 0; i < *count; ++i) if (!strcmp(blobs[i].path, b.path))
        return blobs[i].bytes.size == bytes.size && (!bytes.size || !memcmp(blobs[i].bytes.data, bytes.data, bytes.size)) ?
            GOLEM_OK : GOLEM_ERR_INVALID_STATE;
    blobs[(*count)++] = b; return GOLEM_OK;
}
static golem_status object_parent(int root, const char *path, int *out, char leaf[192])
{
    struct stat base; if (fstat(root, &base) < 0) return GOLEM_ERR_IO;
    char copy[192]; if (strlen(path) >= sizeof(copy)) return GOLEM_ERR_INVALID_ARGUMENT;
    strcpy(copy, path); char *part = copy, *slash;
    int parent = openat(root, ".", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (parent < 0) return GOLEM_ERR_IO;
    while ((slash = strchr(part, '/'))) {
        *slash = 0; int child = openat(parent, part, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        struct stat sb; golem_status st = GOLEM_OK;
        if (child < 0) st = GOLEM_ERR_IO;
        else if (fstat(child, &sb) < 0 || sb.st_dev != base.st_dev || sb.st_uid != geteuid() ||
            (sb.st_mode & 07777) != 0700) st = GOLEM_ERR_INVALID_STATE;
        if (close(parent) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
        if (st != GOLEM_OK) { if (child >= 0) close(child); return st; }
        parent = child; part = slash + 1;
    }
    strcpy(leaf, part); *out = parent; return GOLEM_OK;
}
static golem_status object_manifest(gi_journal *j, object_blob *blobs, size_t count,
    const golem_digest *operation, const golem_digest *request, uint64_t sequence,
    const golem_digest *head, const golem_digest *baseline, struct json_object **out)
{
    struct json_object *m = json_object_new_object(), *rows = json_object_new_array(), *dirs = json_object_new_array();
    struct json_object *seen = json_object_new_object();
    if (!m || !rows || !dirs || !seen) { json_object_put(m); json_object_put(rows); json_object_put(dirs); json_object_put(seen); return GOLEM_ERR_OUT_OF_MEMORY; }
    golem_status st = GOLEM_OK; size_t required;
    char op[65], req[65], prev[65], base[65];
    (void)golem_digest_format(operation, op, sizeof(op), &required);
    (void)golem_digest_format(request, req, sizeof(req), &required);
    (void)golem_digest_format(head, prev, sizeof(prev), &required);
    (void)golem_digest_format(baseline, base, sizeof(base), &required);
    if (!json_set(m, "schema", json_object_new_string("golem.intent.object-preparation.v1")) ||
        !json_set(m, "operation_id", json_object_new_string(op)) || !json_set(m, "request_digest", json_object_new_string(req)) ||
        !json_set(m, "lane", json_object_new_int(GI_QUOTA_INTAKE)) || !json_set(m, "expected_sequence", json_object_new_uint64(sequence)) ||
        !json_set(m, "expected_head", json_object_new_string(prev)) || !json_set(m, "baseline_digest", json_object_new_string(base))) st = GOLEM_ERR_OUT_OF_MEMORY;
    for (size_t i = 0; st == GOLEM_OK && i < count; ++i) {
        object_blob *b = &blobs[i]; struct stat sb;
        if (fstatat(j->root, b->path, &sb, AT_SYMLINK_NOFOLLOW) == 0) {
            uint8_t *existing = NULL; size_t n = 0;
            st = gi_object_load(j->root, b->kind, &b->digest, b->bytes.size, &existing, &n);
            if (st == GOLEM_OK && (n != b->bytes.size || (n && memcmp(existing, b->bytes.data, n)))) st = GOLEM_ERR_INVALID_STATE;
            free(existing);
        } else if (errno == ENOENT) b->fresh = true; else st = GOLEM_ERR_IO;
        if (st != GOLEM_OK) break;
        char hex[65]; (void)golem_digest_format(&b->digest, hex, sizeof(hex), &required);
        struct json_object *row = json_object_new_object();
        if (!row) { st = GOLEM_ERR_OUT_OF_MEMORY; break; }
        if (!json_set(row, "path", json_object_new_string(b->path)) ||
            !json_set(row, "kind", json_object_new_string(b->kind == GI_OBJECT_RAW ? "raw" : "domain")) ||
            !json_set(row, "byte_length", json_object_new_uint64(b->bytes.size)) ||
            !json_set(row, "digest", json_object_new_string(hex)) ||
            !json_set(row, "disposition", json_object_new_string(b->fresh ? "new" : "reuse")) ||
            json_object_array_add(rows, row) != 0) { json_object_put(row); st = GOLEM_ERR_OUT_OF_MEMORY; break; }
        if (!b->fresh) continue;
        char parent[192]; strcpy(parent, b->path);
        for (char *slash = strchr(parent, '/'); slash && st == GOLEM_OK; slash = strchr(slash + 1, '/')) {
            *slash = 0;
            if (!json_object_object_get_ex(seen, parent, NULL)) {
                if (fstatat(j->root, parent, &sb, AT_SYMLINK_NOFOLLOW) < 0) {
                    if (errno != ENOENT) st = GOLEM_ERR_IO;
                    else {
                        struct json_object *v = json_object_new_string(parent);
                        if (!v || json_object_array_add(dirs, v) != 0) { json_object_put(v); st = GOLEM_ERR_OUT_OF_MEMORY; }
                    }
                } else if (!S_ISDIR(sb.st_mode) || sb.st_uid != geteuid() || (sb.st_mode & 07777) != 0700) st = GOLEM_ERR_INVALID_STATE;
                if (st == GOLEM_OK && json_object_object_add(seen, parent, NULL) != 0) st = GOLEM_ERR_OUT_OF_MEMORY;
            }
            *slash = '/';
        }
    }
    if (st == GOLEM_OK && !json_set(m, "objects", json_object_get(rows))) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK && !json_set(m, "new_directories", json_object_get(dirs))) st = GOLEM_ERR_OUT_OF_MEMORY;
    json_object_put(rows); json_object_put(dirs); json_object_put(seen);
    if (st == GOLEM_OK) *out = m; else json_object_put(m);
    return st;
}

golem_status gi_journal_store_objects(gi_journal *j, const golem_digest *operation, const golem_digest *request,
    uint64_t expected_sequence, const golem_digest *expected_head, golem_bytes baseline,
    const gi_source_input *sources, size_t source_count, gi_journal_guard guard, void *context, gi_journal_receipt *out)
{
    if (!j || !operation || !request || !expected_head || !guard || !out || !sources || !source_count)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (j->poisoned || j->busy || j->owner != getpid()) return GOLEM_ERR_INVALID_STATE;
    j->busy = true; bool started = false;
    replay *r = malloc(sizeof(*r)); object_blob *blobs = NULL;
    struct json_object *manifest = NULL; uint8_t *wire = NULL; size_t wire_size = 0, count = 0;
    golem_status st = r ? guard(context) : GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) st = restore(j, r);
    gi_baseline_coverage_result coverage; golem_digest base;
    if (st == GOLEM_OK) st = gi_baseline_coverage_validate(baseline, sources, source_count, &coverage, NULL);
    if (st == GOLEM_OK) st = gi_baseline_identity(baseline, &base, NULL);
    if (st == GOLEM_OK) for (size_t i = 0; i < r->count; ++i) {
        record *rec = &r->records[i]; if (memcmp(rec->prep + 32, operation->bytes, 32)) continue;
        char path[64]; uint8_t *data = NULL; size_t n = 0; bool exists = false;
        name(path, sizeof(path), i + 1, "objects-prep");
        st = read_file(j->root, path, GI_CONTROL_MAX, &data, &n, &exists);
        gi_object_preparation_result old;
        if (st == GOLEM_OK && (!exists || !rec->committed || r->status.pending || memcmp(rec->prep + 64, request->bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
        if (st == GOLEM_OK) st = gi_object_preparation_validate((golem_bytes){data, n}, &old, NULL);
        if (st == GOLEM_OK && memcmp(&base, &old.reservation.publication.baseline, sizeof(base))) st = GOLEM_ERR_INVALID_STATE;
        free(data);
        if (st == GOLEM_OK) *out = (gi_journal_receipt){i + 1, rec->event, true};
        goto done;
    }
    if (st == GOLEM_OK && (r->status.pending || r->count == RECORDS || expected_sequence != r->status.committed ||
        memcmp(expected_head, &r->status.head, sizeof(*expected_head)))) st = GOLEM_ERR_INVALID_STATE;
    gi_journal_status before = {0}; if (st == GOLEM_OK) before = r->status;
    if (st == GOLEM_OK) { blobs = calloc(1 + 2 * source_count, sizeof(*blobs)); if (!blobs) st = GOLEM_ERR_OUT_OF_MEMORY; }
    if (st == GOLEM_OK) st = blob_add(blobs, &count, GI_OBJECT_BASELINE, &base, baseline);
    for (size_t i = 0; st == GOLEM_OK && i < source_count; ++i) {
        golem_digest digest;
        st = gi_source_identity(sources[i].control, sources[i].text, &digest, NULL);
        if (st == GOLEM_OK) st = blob_add(blobs, &count, GI_OBJECT_SOURCE, &digest, sources[i].control);
        if (st == GOLEM_OK) st = golem_digest_bytes(sources[i].text, &digest);
        if (st == GOLEM_OK) st = blob_add(blobs, &count, GI_OBJECT_RAW, &digest, sources[i].text);
    }
    if (st == GOLEM_OK) st = object_manifest(j, blobs, count, operation, request, expected_sequence, expected_head, &base, &manifest);
    const char *json = NULL; size_t json_size = 0; gi_object_preparation_result plan;
    if (st == GOLEM_OK) {
        json = json_object_to_json_string_ext(manifest, JSON_C_TO_STRING_PLAIN);
        if (!json) st = GOLEM_ERR_OUT_OF_MEMORY;
        else { json_size = strlen(json); st = gi_object_preparation_validate((golem_bytes){(const uint8_t *)json, json_size}, &plan, NULL); }
    }
    char payload[GI_OBJECT_PUBLICATION_CAPACITY]; size_t payload_size = 0;
    if (st == GOLEM_OK) st = gi_object_publication_encode(&plan.reservation.publication, payload, sizeof(payload), &payload_size);
    uint8_t prep[PREP_SIZE] = {0}, frame[FRAME_SIZE] = {0}; golem_digest payload_digest, prep_digest, event_digest;
    size_t seq = st == GOLEM_OK ? r->count + 1 : 0;
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){(uint8_t *)payload, payload_size}, &payload_digest);
    if (st == GOLEM_OK) {
        memcpy(prep, "GIQPRE01", 8); encode(prep + 8, GI_QUOTA_INTAKE); encode(prep + 16, seq); encode(prep + 24, payload_size);
        memcpy(prep + 32, operation->bytes, 32); memcpy(prep + 64, request->bytes, 32);
        memcpy(prep + 96, expected_head->bytes, 32); memcpy(prep + 128, payload_digest.bytes, 32);
        st = prep_encode(prep, &wire, &wire_size);
    }
    if (st == GOLEM_OK) st = gi_domain_digest((golem_bytes){wire, wire_size}, &prep_digest, NULL);
    if (st == GOLEM_OK) {
        uint64_t files = 4 + plan.new_objects, bytes = json_size + wire_size + payload_size + FRAME_SIZE + plan.new_object_bytes;
        gi_quota_usage retained = {{1, payload_size, bytes, files + plan.new_directories}};
        gi_quota_usage peak = {{1, payload_size, 2 * bytes, 2 * files + plan.new_directories}};
        gi_quota_state checked; st = gi_quota_project(&r->status.usage, GI_QUOTA_INTAKE, &retained, &peak, &checked);
    }
    if (st == GOLEM_OK) st = guard(context);
    if (st == GOLEM_OK) st = restore(j, r);
    if (st == GOLEM_OK && memcmp(&before, &r->status, sizeof(before))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) { started = true; st = publish(j, seq, "objects-prep", (golem_bytes){(const uint8_t *)json, json_size}); }
    struct json_object *dirs = NULL;
    if (manifest) (void)json_object_object_get_ex(manifest, "new_directories", &dirs);
    for (size_t i = 0; st == GOLEM_OK && i < json_object_array_length(dirs); ++i) {
        int parent = -1; char leaf[192];
        st = object_parent(j->root, json_object_get_string(json_object_array_get_idx(dirs, i)), &parent, leaf);
        if (st == GOLEM_OK && (mkdirat(parent, leaf, 0700) < 0 || fsync(parent) < 0)) st = GOLEM_ERR_IO;
        if (parent >= 0 && close(parent) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    }
    for (size_t i = 0; st == GOLEM_OK && i < count; ++i) if (blobs[i].fresh) {
        int parent = -1; char leaf[192]; st = object_parent(j->root, blobs[i].path, &parent, leaf);
        if (st == GOLEM_OK) st = publish_name(parent, leaf, blobs[i].bytes);
        if (parent >= 0 && close(parent) < 0 && st == GOLEM_OK) st = GOLEM_ERR_IO;
    }
    if (st == GOLEM_OK) st = guard(context);
    if (st == GOLEM_OK) st = restore_mode(j, r, -2);
    if (st == GOLEM_OK) st = gi_object_graph_validate(j->root, (golem_bytes){(const uint8_t *)json, json_size}, &coverage);
    if (st == GOLEM_OK) {
        gi_quota_usage retained = {{0, 0, wire_size + payload_size + FRAME_SIZE, 3}};
        gi_quota_usage peak = {{0, 0, 2 * (wire_size + payload_size + FRAME_SIZE), 6}};
        gi_quota_state checked; st = gi_quota_project(&r->status.usage, GI_QUOTA_INTAKE, &retained, &peak, &checked);
    }
    if (st == GOLEM_OK) st = publish(j, seq, "prep", (golem_bytes){wire, wire_size});
    if (st == GOLEM_OK) st = publish(j, seq, "payload", (golem_bytes){(uint8_t *)payload, payload_size});
    if (st == GOLEM_OK) st = guard(context);
    if (st == GOLEM_OK) st = restore_mode(j, r, -2);
    if (st == GOLEM_OK && (r->count != seq || r->status.committed != seq - 1 ||
        memcmp(r->records[seq - 1].prep, prep, PREP_SIZE) || !r->records[seq - 1].payload_ready || r->records[seq - 1].staging))
        st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) st = gi_object_graph_validate(j->root, (golem_bytes){(const uint8_t *)json, json_size}, &coverage);
    if (st == GOLEM_OK) {
        gi_quota_usage retained = {{0, 0, FRAME_SIZE, 1}}, peak = {{0, 0, 2 * FRAME_SIZE, 2}};
        gi_quota_state checked; st = gi_quota_project(&r->status.usage, GI_QUOTA_INTAKE, &retained, &peak, &checked);
    }
    if (st == GOLEM_OK) {
        memcpy(frame, "GIQEV001", 8); encode(frame + 8, seq); memcpy(frame + 16, expected_head->bytes, 32);
        memcpy(frame + 48, prep_digest.bytes, 32); st = golem_digest_bytes((golem_bytes){frame, sizeof(frame)}, &event_digest);
    }
    if (st == GOLEM_OK) st = publish(j, seq, "event", (golem_bytes){frame, sizeof(frame)});
    if (st == GOLEM_OK) st = restore(j, r);
    if (st == GOLEM_OK && (r->status.pending || r->status.committed != seq || memcmp(&r->status.head, &event_digest, sizeof(event_digest))))
        st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) *out = (gi_journal_receipt){seq, event_digest, false};
done:
    if (started && st != GOLEM_OK) j->poisoned = true;
    free(wire); free(blobs); json_object_put(manifest); free(r); j->busy = false; return st;
}
