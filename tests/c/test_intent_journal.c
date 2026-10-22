#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "../../src/intent/journal.h"
#include "test.h"
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <dirent.h>

typedef struct guard_context { int root, calls, mode; gi_journal *j; } guard_context;
typedef struct visit_context { gi_journal *j; uint64_t count; bool fail; } visit_context;
static golem_status visitor(void *arg, const golem_digest *operation,
    const golem_digest *request, const gi_journal_operation *record)
{
    visit_context *v = arg;
    gi_journal_status state;
    if (!operation || !request || record->sequence != ++v->count ||
        gi_journal_inspect(v->j, &state) != GOLEM_ERR_INVALID_STATE ||
        gi_journal_visit(v->j, visitor, v) != GOLEM_ERR_INVALID_STATE) return GOLEM_ERR_IO;
    return v->fail ? GOLEM_ERR_POLICY_DENIED : GOLEM_OK;
}
static golem_status guard(void *arg)
{
    guard_context *g = arg;
    ++g->calls;
    gi_journal_status state;
    if (gi_journal_inspect(g->j, &state) != GOLEM_ERR_INVALID_STATE) return GOLEM_ERR_IO;
    gi_journal *other = NULL;
    if (gi_journal_open(g->root, &other) != GOLEM_ERR_INVALID_STATE) {
        gi_journal_close(other); return GOLEM_ERR_IO;
    }
    if (g->mode == 1 || ((g->mode == 2 || g->mode == 6) && g->calls == 2)) return GOLEM_ERR_POLICY_DENIED;
    if (g->mode == 3 && g->calls == 2) {
        int fd = openat(g->root, "unattributed", O_WRONLY | O_CREAT | O_EXCL, 0600);
        if (fd < 0) return GOLEM_ERR_IO;
        close(fd);
    }
    if (g->mode == 4 && g->calls == 2) {
        if (unlinkat(g->root, "00000001.payload", 0) < 0) return GOLEM_ERR_IO;
    }
    if (g->mode == 5 && g->calls == 2) _exit(77);
    if (g->mode == 7 && g->calls == 3) return GOLEM_ERR_POLICY_DENIED;
    if (g->mode == 8 && g->calls == 3) {
        int fd = openat(g->root, "00000001.payload", O_WRONLY | O_CREAT | O_EXCL, 0400);
        if (fd < 0) return GOLEM_ERR_IO;
        ssize_t written = write(fd, "payload", 7);
        if (close(fd) < 0 || written != 7) return GOLEM_ERR_IO;
    }
    return GOLEM_OK;
}
static void cleanup(int root, const char *path)
{
    int fd = openat(root, ".", O_RDONLY | O_DIRECTORY);
    DIR *dir = fdopendir(fd);
    if (dir) {
        struct dirent *e;
        while ((e = readdir(dir))) if (strcmp(e->d_name, ".") && strcmp(e->d_name, ".."))
            (void)unlinkat(root, e->d_name, 0);
        closedir(dir);
    }
    close(root); (void)rmdir(path);
}
static golem_bytes bytes(const char *s) { return (golem_bytes){(const uint8_t *)s, strlen(s)}; }
static int scenario(int mode)
{
    char path[] = "/tmp/golem-intent-journal-XXXXXX";
    CHECK(mkdtemp(path) != NULL);
    int root = open(path, O_RDONLY | O_DIRECTORY); CHECK(root >= 0);
    gi_journal *j = NULL; CHECK(gi_journal_open(root, &j) == GOLEM_OK);
    guard_context g = {root, 0, mode, j};
    golem_digest op, req, zero = {{0}};
    CHECK(golem_digest_bytes(bytes("operation"), &op) == GOLEM_OK);
    CHECK(golem_digest_bytes(bytes("request"), &req) == GOLEM_OK);
    gi_journal_receipt result, sentinel; memset(&sentinel, 0xa5, sizeof(sentinel)); result = sentinel;
    gi_journal_status state;
    if (mode == 5) {
        gi_journal_close(j);
        pid_t child = fork(); CHECK(child >= 0);
        if (!child) {
            if (gi_journal_open(root, &j) != GOLEM_OK) _exit(1);
            g.j = j;
            (void)gi_journal_append(j, GI_QUOTA_INTAKE, &op, &req, 0, &zero, bytes("payload"), guard, &g, &result);
            _exit(2);
        }
        int status; CHECK(waitpid(child, &status, 0) == child);
        CHECK(WIFEXITED(status) && WEXITSTATUS(status) == 77);
        CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j; g.mode = 0;
        CHECK(gi_journal_inspect(j, &state) == GOLEM_OK);
        CHECK(state.committed == 0 && state.pending);
        struct stat sb; CHECK(fstatat(root, "00000001.prep", &sb, 0) == 0);
        CHECK(state.usage.lane[0].value[GI_QUOTA_BYTES] == (uint64_t)sb.st_size + 7);
        CHECK(state.usage.lane[0].value[GI_QUOTA_EVENTS] == 1);
        gi_journal_operation lookup;
        CHECK(gi_journal_lookup(j, &op, &req, &lookup) == GOLEM_OK);
        CHECK(!lookup.committed && lookup.pending && lookup.lane == GI_QUOTA_INTAKE);
        CHECK(gi_journal_append(j, GI_QUOTA_INTAKE, &op, &req, 0, &zero, bytes("payload"), guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
    } else {
        golem_status st = gi_journal_append(j, GI_QUOTA_INTAKE, &op, &req, 0, &zero, bytes("payload"), guard, &g, &result);
        if (mode) {
            CHECK(st != GOLEM_OK && memcmp(&result, &sentinel, sizeof(result)) == 0);
            struct stat sb;
            CHECK(fstatat(root, "00000001.event", &sb, AT_SYMLINK_NOFOLLOW) < 0);
            if (mode == 1) {
                CHECK(gi_journal_inspect(j, &state) == GOLEM_OK);
                CHECK(state.usage.lane[0].value[GI_QUOTA_ENTRIES] == 0);
            }
            if (mode == 2) {
                /* An owned staging alias is charged, not discarded on reopen. */
                CHECK(linkat(root, "00000001.payload", root, "00000001.payload.pending", 0) == 0);
                gi_journal_close(j); CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j;
                CHECK(gi_journal_inspect(j, &state) == GOLEM_OK);
                CHECK(state.pending && state.committed == 0);
                gi_journal_pending_plan pending;
                CHECK(gi_journal_pending_plan_get(j, &pending) == GOLEM_ERR_INVALID_STATE);
                CHECK(fstatat(root, "00000001.prep", &sb, 0) == 0);
                CHECK(state.usage.lane[0].value[GI_QUOTA_BYTES] == (uint64_t)sb.st_size + 14);
                CHECK(state.usage.lane[0].value[GI_QUOTA_ENTRIES] == 3);
                g.mode = 0;
                CHECK(gi_journal_append(j, GI_QUOTA_INTAKE, &op, &req, 0, &zero, bytes("payload"), guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
                CHECK(fstatat(root, "00000001.payload.pending", &sb, AT_SYMLINK_NOFOLLOW) == 0);
            }
            if (mode == 6) {
                gi_journal_close(j); CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j;
                gi_journal_pending_plan pending;
                CHECK(gi_journal_pending_plan_get(j, &pending) == GOLEM_OK);
                CHECK(pending.sequence == 1 && pending.payload_bytes == 7);
                CHECK(gi_journal_inspect(j, &state) == GOLEM_OK);
                gi_quota_state before = state.usage;
                g.mode = 0; g.calls = 0;
                CHECK(gi_journal_pending_finish(j, &zero, guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
                g.mode = 2; g.calls = 0;
                CHECK(gi_journal_pending_finish(j, &pending.snapshot, guard, &g, &result) == GOLEM_ERR_POLICY_DENIED);
                CHECK(memcmp(&result, &sentinel, sizeof(result)) == 0);
                g.mode = 0; g.calls = 0;
                CHECK(gi_journal_pending_finish(j, &pending.snapshot, guard, &g, &result) == GOLEM_OK);
                CHECK(g.calls == 2 && result.sequence == 1 && !result.replayed);
                CHECK(gi_journal_inspect(j, &state) == GOLEM_OK && state.committed == 1 && !state.pending);
                CHECK(state.usage.lane[0].value[GI_QUOTA_EVENTS] == before.lane[0].value[GI_QUOTA_EVENTS]);
                CHECK(state.usage.lane[0].value[GI_QUOTA_PAYLOAD] == before.lane[0].value[GI_QUOTA_PAYLOAD]);
                CHECK(state.usage.lane[0].value[GI_QUOTA_BYTES] == before.lane[0].value[GI_QUOTA_BYTES] + 80);
                CHECK(state.usage.lane[0].value[GI_QUOTA_ENTRIES] == before.lane[0].value[GI_QUOTA_ENTRIES] + 1);
                CHECK(memcmp(&state.usage.lane[1], &before.lane[1], 2 * sizeof(before.lane[1])) == 0);
                CHECK(gi_journal_pending_finish(j, &pending.snapshot, guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
            }
        } else {
            CHECK(st == GOLEM_OK && result.sequence == 1 && !result.replayed && g.calls == 2);
            pid_t contender = fork(); CHECK(contender >= 0);
            if (!contender) {
                gi_journal_status inherited;
                if (gi_journal_inspect(j, &inherited) != GOLEM_ERR_INVALID_STATE) _exit(2);
                gi_journal *other = NULL;
                golem_status locked = gi_journal_open(root, &other);
                gi_journal_close(other); _exit(locked == GOLEM_ERR_INVALID_STATE ? 0 : 1);
            }
            int child_status; CHECK(waitpid(contender, &child_status, 0) == contender);
            CHECK(WIFEXITED(child_status) && WEXITSTATUS(child_status) == 0);
            CHECK(gi_journal_inspect(j, &state) == GOLEM_OK);
            CHECK(state.committed == 1 && !state.pending);
            struct stat sb; CHECK(fstatat(root, "00000001.prep", &sb, 0) == 0);
            uint64_t first_bytes = (uint64_t)sb.st_size + 7 + 80;
            CHECK(state.usage.lane[0].value[GI_QUOTA_BYTES] == first_bytes);
            CHECK(state.usage.lane[0].value[GI_QUOTA_ENTRIES] == 3);
            gi_journal_status saved = state;
            gi_journal_close(j); CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j;
            CHECK(gi_journal_inspect(j, &state) == GOLEM_OK);
            CHECK(memcmp(&saved.usage, &state.usage, sizeof(state.usage)) == 0);
            CHECK(gi_journal_append(j, GI_QUOTA_INTAKE, &op, &req, 0, &zero, bytes("payload"), guard, &g, &result) == GOLEM_OK);
            CHECK(result.replayed);
            gi_journal_operation lookup;
            CHECK(gi_journal_lookup(j, &op, &req, &lookup) == GOLEM_OK);
            CHECK(lookup.committed && !lookup.pending && lookup.sequence == 1);
            CHECK(gi_journal_lookup(j, &op, &zero, &lookup) == GOLEM_ERR_INVALID_STATE);
            CHECK(gi_journal_append(j, GI_QUOTA_RESOLUTION, &op, &req, 0, &zero, bytes("payload"), guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
            CHECK(gi_journal_append(j, GI_QUOTA_INTAKE, &op, &req, 0, &zero, bytes("changed"), guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
            CHECK(golem_digest_bytes(bytes("second"), &op) == GOLEM_OK);
            CHECK(gi_journal_append(j, GI_QUOTA_RESOLUTION, &op, &req, 0, &zero, bytes("payload"), guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
            CHECK(gi_journal_append(j, GI_QUOTA_RESOLUTION, &op, &req, 1, &state.head, bytes("payload"), guard, &g, &result) == GOLEM_OK);
            CHECK(gi_journal_inspect(j, &state) == GOLEM_OK);
            CHECK(state.committed == 2 && state.usage.lane[0].value[GI_QUOTA_BYTES] == first_bytes && state.usage.lane[1].value[GI_QUOTA_BYTES] == first_bytes);
            visit_context v = {j, 0, false};
            CHECK(gi_journal_visit(j, visitor, &v) == GOLEM_OK && v.count == 2);
            v.count = 0; v.fail = true;
            CHECK(gi_journal_visit(j, visitor, &v) == GOLEM_ERR_POLICY_DENIED && v.count == 1);
            CHECK(gi_journal_inspect(j, &state) == GOLEM_OK && state.committed == 2);
            CHECK(gi_journal_visit(j, NULL, &v) == GOLEM_ERR_INVALID_ARGUMENT);
        }
    }
    gi_journal_close(j); cleanup(root, path); return 0;
}
static int saturation(void)
{
    char path[] = "/tmp/golem-intent-journal-limit-XXXXXX";
    CHECK(mkdtemp(path) != NULL);
    int root = open(path, O_RDONLY | O_DIRECTORY); CHECK(root >= 0);
    gi_journal *j; CHECK(gi_journal_open(root, &j) == GOLEM_OK);
    guard_context g = {root, 0, 0, j};
    golem_digest head = {{0}}, op, request;
    CHECK(golem_digest_bytes(bytes("request"), &request) == GOLEM_OK);
    gi_journal_receipt receipt;
    for (uint64_t i = 0; i < 64; ++i) {
        char key[32]; (void)snprintf(key, sizeof(key), "op-%llu", (unsigned long long)i);
        CHECK(golem_digest_bytes(bytes(key), &op) == GOLEM_OK);
        CHECK(gi_journal_append(j, GI_QUOTA_RECOVERY, &op, &request, i, &head, bytes("x"), guard, &g, &receipt) == GOLEM_OK);
        head = receipt.digest;
    }
    CHECK(golem_digest_bytes(bytes("overflow"), &op) == GOLEM_OK);
    CHECK(gi_journal_append(j, GI_QUOTA_RECOVERY, &op, &request, 64, &head, bytes("x"), guard, &g, &receipt) == GOLEM_ERR_OVERFLOW);
    struct stat sb;
    CHECK(fstatat(root, "00000065.prep", &sb, AT_SYMLINK_NOFOLLOW) < 0);
    CHECK(gi_journal_append(j, GI_QUOTA_INTAKE, &op, &request, 64, &head, bytes("x"), guard, &g, &receipt) == GOLEM_OK);
    gi_journal_status state;
    CHECK(gi_journal_inspect(j, &state) == GOLEM_OK && state.committed == 65);
    CHECK(state.usage.lane[2].value[0] == 64 && state.usage.lane[0].value[0] == 1);
    /* Corrupt committed preparation cannot silently reassign its first lane. */
    CHECK(fchmodat(root, "00000001.prep", 0600, 0) == 0);
    int fd = openat(root, "00000001.prep", O_RDWR); CHECK(fd >= 0);
    char wire[1024] = {0}; CHECK(read(fd, wire, sizeof(wire) - 1) > 0);
    char *lane = strstr(wire, "\"lane\":2"); CHECK(lane != NULL);
    CHECK(pwrite(fd, "0", 1, (off_t)(lane - wire + 7)) == 1); CHECK(close(fd) == 0);
    gi_journal_status saved = state;
    CHECK(gi_journal_inspect(j, &state) == GOLEM_ERR_INVALID_STATE);
    CHECK(memcmp(&state, &saved, sizeof(state)) == 0);
    gi_journal_close(j); cleanup(root, path); return 0;
}
static int partial_preparation(void)
{
    char path[] = "/tmp/golem-intent-journal-partial-XXXXXX";
    CHECK(mkdtemp(path) != NULL);
    int root = open(path, O_RDONLY | O_DIRECTORY); CHECK(root >= 0);
    int fd = openat(root, "00000001.prep.pending", O_CREAT | O_EXCL | O_WRONLY, 0600);
    CHECK(fd >= 0 && write(fd, "GIQ", 3) == 3 && close(fd) == 0);
    gi_journal *j; CHECK(gi_journal_open(root, &j) == GOLEM_OK);
    gi_journal_status state;
    CHECK(gi_journal_inspect(j, &state) == GOLEM_ERR_INVALID_STATE);
    struct stat sb;
    CHECK(fstatat(root, "00000001.prep.pending", &sb, AT_SYMLINK_NOFOLLOW) == 0 && sb.st_size == 3);
    gi_journal_close(j); cleanup(root, path); return 0;
}
static int alias_recovery(unsigned kind)
{
    char path[] = "/tmp/golem-intent-alias-XXXXXX";
    CHECK(mkdtemp(path) != NULL);
    int root = open(path, O_RDONLY | O_DIRECTORY); CHECK(root >= 0);
    gi_journal *j; CHECK(gi_journal_open(root, &j) == GOLEM_OK);
    guard_context g = {root, 0, 0, j}; golem_digest op, req, zero = {{0}};
    CHECK(golem_digest_bytes(bytes("alias-operation"), &op) == GOLEM_OK);
    CHECK(golem_digest_bytes(bytes("alias-request"), &req) == GOLEM_OK);
    gi_journal_receipt receipt;
    CHECK(gi_journal_append(j, GI_QUOTA_INTAKE, &op, &req, 0, &zero, bytes("payload"), guard, &g, &receipt) == GOLEM_OK);
    const char *names[] = {"00000001.prep", "00000001.payload", "00000001.event"};
    char pending[64]; (void)snprintf(pending, sizeof(pending), "%s.pending", names[kind]);
    CHECK(linkat(root, names[kind], root, pending, 0) == 0);
    gi_journal_alias_plan before, after, sentinel;
    CHECK(gi_journal_alias_observe(j, kind, &before) == GOLEM_OK && before.present);
    CHECK(linkat(root, names[kind], root, "third-link", 0) == 0);
    CHECK(gi_journal_alias_observe(j, kind, &after) != GOLEM_OK);
    CHECK(unlinkat(root, "third-link", 0) == 0);
    memset(&sentinel, 0xa5, sizeof(sentinel)); after = sentinel;
    g.calls = 0;
    CHECK(gi_journal_alias_remove(j, kind, &zero, guard, &g, &after) == GOLEM_ERR_INVALID_STATE);
    CHECK(memcmp(&after, &sentinel, sizeof(after)) == 0);
    g.mode = 2; g.calls = 0;
    CHECK(gi_journal_alias_remove(j, kind, &before.snapshot, guard, &g, &after) == GOLEM_ERR_POLICY_DENIED);
    g.mode = 0; g.calls = 0;
    CHECK(gi_journal_alias_remove(j, kind, &before.snapshot, guard, &g, &after) == GOLEM_OK);
    CHECK(g.calls == 2 && !after.present && !after.state.pending && after.state.committed == 1);
    CHECK(before.inode == after.inode && memcmp(before.final_digest.bytes, after.final_digest.bytes, 32) == 0);
    CHECK(after.state.usage.lane[0].value[GI_QUOTA_BYTES] + before.bytes == before.state.usage.lane[0].value[GI_QUOTA_BYTES]);
    CHECK(after.state.usage.lane[0].value[GI_QUOTA_ENTRIES] + 1 == before.state.usage.lane[0].value[GI_QUOTA_ENTRIES]);
    CHECK(after.state.usage.lane[0].value[GI_QUOTA_EVENTS] == before.state.usage.lane[0].value[GI_QUOTA_EVENTS]);
    CHECK(after.state.usage.lane[0].value[GI_QUOTA_PAYLOAD] == before.state.usage.lane[0].value[GI_QUOTA_PAYLOAD]);
    CHECK(memcmp(&after.state.usage.lane[1], &before.state.usage.lane[1], 2 * sizeof(before.state.usage.lane[1])) == 0);
    CHECK(gi_journal_alias_remove(j, kind, &before.snapshot, guard, &g, &after) == GOLEM_ERR_INVALID_STATE);
    gi_journal_close(j); cleanup(root, path); return 0;
}

static int partial_recovery(int interruption)
{
    char path[] = "/tmp/golem-intent-partial-XXXXXX";
    CHECK(mkdtemp(path) != NULL);
    int root = open(path, O_RDONLY | O_DIRECTORY); CHECK(root >= 0);
    gi_journal *j = NULL; CHECK(gi_journal_open(root, &j) == GOLEM_OK);
    guard_context g = {root, 0, 2, j};
    golem_digest op, req, zero = {{0}};
    CHECK(golem_digest_bytes(bytes("partial-operation"), &op) == GOLEM_OK);
    CHECK(golem_digest_bytes(bytes("partial-request"), &req) == GOLEM_OK);
    gi_journal_receipt receipt;
    CHECK(gi_journal_append(j, GI_QUOTA_INTAKE, &op, &req, 0, &zero, bytes("payload"), guard, &g, &receipt) == GOLEM_ERR_POLICY_DENIED);
    gi_journal_close(j); CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j;
    CHECK(unlinkat(root, "00000001.payload", 0) == 0);
    int fd = openat(root, "00000001.payload.pending", O_WRONLY | O_CREAT | O_EXCL, 0600); CHECK(fd >= 0);
    CHECK(write(fd, "pay", 3) == 3); CHECK(close(fd) == 0);
    gi_journal_partial_plan before, after, sentinel;
    CHECK(gi_journal_partial_observe(j, 1, &before) == GOLEM_OK);
    CHECK(before.source.present && !before.archived && !before.payload_ready);
    gi_journal_partial_plan capacity = before;
    gi_quota_usage limit; CHECK(gi_quota_limit(GI_QUOTA_INTAKE, &limit) == GOLEM_OK);
    capacity.source.state.usage.lane[0].value[GI_QUOTA_BYTES] = limit.value[GI_QUOTA_BYTES] - 323;
    CHECK(gi_journal_partial_check_quota(&capacity, false) == GOLEM_ERR_OVERFLOW);
    capacity.source.state.usage.lane[0].value[GI_QUOTA_BYTES] -= 323;
    CHECK(gi_journal_partial_check_quota(&capacity, false) == GOLEM_OK);
    capacity = before;
    capacity.source.state.usage.lane[0].value[GI_QUOTA_ENTRIES] = limit.value[GI_QUOTA_ENTRIES] - 2;
    CHECK(gi_journal_partial_check_quota(&capacity, false) == GOLEM_ERR_OVERFLOW);
    --capacity.source.state.usage.lane[0].value[GI_QUOTA_ENTRIES];
    CHECK(gi_journal_partial_check_quota(&capacity, false) == GOLEM_OK);
    memset(&sentinel, 0xa5, sizeof(sentinel)); after = sentinel;
    g.mode = 0; g.calls = 0;
    CHECK(gi_journal_partial_quarantine(j, 1, &zero, &req, guard, &g, &after) == GOLEM_ERR_INVALID_STATE);
    CHECK(memcmp(&after, &sentinel, sizeof(after)) == 0);
    g.mode = 2; g.calls = 0;
    CHECK(gi_journal_partial_quarantine(j, 1, &before.source.snapshot, &req, guard, &g, &after) == GOLEM_ERR_POLICY_DENIED);
    struct stat sb; CHECK(fstatat(root, "quarantine", &sb, 0) < 0);
    /* Simulate denial/interruption after durable evidence but before separation. */
    g.mode = interruption >= 9 ? 7 : interruption; g.calls = 0;
    CHECK(gi_journal_partial_quarantine(j, 1, &before.source.snapshot, &req, guard, &g, &after) ==
          (interruption == 8 ? GOLEM_ERR_INVALID_STATE : GOLEM_ERR_POLICY_DENIED));
    CHECK(fstatat(root, "00000001.payload.pending", &sb, 0) == 0);
    if (interruption == 8) {
        gi_journal_close(j);
        int q = openat(root, "quarantine", O_RDONLY | O_DIRECTORY); CHECK(q >= 0);
        CHECK(unlinkat(q, "00000001.payload", 0) == 0); close(q);
        CHECK(unlinkat(root, "quarantine", AT_REMOVEDIR) == 0);
        cleanup(root, path); return 0;
    }
    CHECK(gi_journal_partial_quarantine(j, 1, &before.source.snapshot, &req, guard, &g, &after) == GOLEM_ERR_INVALID_STATE);
    gi_journal_close(j); CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j;
    if (interruption == 10 || interruption == 11) {
        int q = openat(root, "quarantine", O_RDONLY | O_DIRECTORY); CHECK(q >= 0);
        CHECK(renameat(q, "00000001.payload", q, "00000001.payload.pending") == 0);
        CHECK(fchmodat(q, "00000001.payload.pending", 0600, 0) == 0);
        int cut = openat(q, "00000001.payload.pending", O_WRONLY); CHECK(cut >= 0);
        CHECK(ftruncate(cut, 322) == 0 && fchmod(cut, 0400) == 0); close(cut);
        gi_journal_fragment_plan f, result, untouched;
        CHECK(gi_journal_fragment_observe(j, 1, &f) == GOLEM_OK && f.truncated_present && !f.final_present);
        gi_journal_status state;
        CHECK(gi_journal_inspect(j, &state) == GOLEM_ERR_INVALID_STATE);
        memset(&untouched, 0xa5, sizeof(untouched)); result = untouched;
        g.mode = 0; g.calls = 0;
        CHECK(gi_journal_fragment_apply(j, 1, 0, &zero, &req, &op, guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
        CHECK(memcmp(&result, &untouched, sizeof(result)) == 0);
        CHECK(gi_journal_fragment_apply(j, 1, 0, &f.snapshot, &zero, &op, guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
        g.mode = 2; g.calls = 0;
        CHECK(gi_journal_fragment_apply(j, 1, 0, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_ERR_POLICY_DENIED);
        CHECK(fstatat(q, "00000001.payload.fragment", &sb, 0) < 0);
        g.mode = 7; g.calls = 0;
        CHECK(gi_journal_fragment_apply(j, 1, 0, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_ERR_POLICY_DENIED);
        CHECK(fstatat(q, "00000001.payload.fragment", &sb, 0) == 0);
        CHECK(fstatat(q, "00000001.payload.pending", &sb, 0) == 0);
        gi_journal_close(j); CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j;
        CHECK(renameat(q, "00000001.payload.fragment", q, "00000001.payload.fragment.pending") == 0);
        if (interruption == 11) {
            CHECK(fchmodat(q, "00000001.payload.fragment.pending", 0600, 0) == 0);
            int damaged = openat(q, "00000001.payload.fragment.pending", O_WRONLY); CHECK(damaged >= 0);
            CHECK(ftruncate(damaged, 641) == 0 && fchmod(damaged, 0400) == 0); close(damaged);
            CHECK(gi_journal_fragment_observe(j, 1, &f) == GOLEM_ERR_INVALID_STATE);
            CHECK(gi_journal_damage_observe(j, 1, &f) == GOLEM_OK && f.bytes == 641 && f.envelope_bytes == 322);
            gi_journal *other = NULL;
            CHECK(gi_journal_open(root, &other) == GOLEM_ERR_INVALID_STATE);
            g.mode = 0; g.calls = 0; result = untouched;
            CHECK(gi_journal_damage_apply(j, 1, 0, &zero, &req, &op, guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
            CHECK(memcmp(&result, &untouched, sizeof(result)) == 0);
            CHECK(gi_journal_damage_apply(j, 1, 0, &f.snapshot, &zero, &op, guard, &g, &result) == GOLEM_ERR_INVALID_STATE);
            g.mode = 2; g.calls = 0;
            CHECK(gi_journal_damage_apply(j, 1, 0, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_ERR_POLICY_DENIED);
            CHECK(fstatat(q, "00000001.payload.fragment.damage", &sb, 0) < 0);
            g.mode = 7; g.calls = 0;
            CHECK(gi_journal_damage_apply(j, 1, 0, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_ERR_POLICY_DENIED);
            CHECK(memcmp(&result, &untouched, sizeof(result)) == 0);
            gi_journal_close(j); CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j;
            CHECK(gi_journal_damage_observe(j, 1, &f) == GOLEM_OK && f.final_present && f.object_bytes == 1025);
            CHECK(renameat(q, "00000001.payload.fragment.damage", q, "00000001.payload.fragment.damage.pending") == 0);
            CHECK(gi_journal_damage_observe(j, 1, &f) == GOLEM_OK && f.pending_present && !f.final_present);
            g.mode = 7; g.calls = 0;
            CHECK(gi_journal_damage_apply(j, 1, 1, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_ERR_POLICY_DENIED);
            CHECK(fstatat(q, "00000001.payload.fragment.damage", &sb, 0) == 0 && sb.st_nlink == 2);
            gi_journal_close(j); CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j;
            CHECK(gi_journal_damage_observe(j, 1, &f) == GOLEM_OK);
            g.mode = 0; g.calls = 0;
            CHECK(gi_journal_damage_apply(j, 1, 1, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_OK);
            CHECK(result.final_present && !result.pending_present && result.truncated_present);
            f = result; g.mode = 2; g.calls = 0;
            CHECK(gi_journal_damage_apply(j, 1, 2, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_ERR_POLICY_DENIED);
            CHECK(fstatat(q, "00000001.payload.fragment.pending", &sb, 0) == 0);
            g.mode = 0; g.calls = 0;
            CHECK(gi_journal_damage_apply(j, 1, 2, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_OK);
            CHECK(!result.truncated_present && result.original.source.present);
            CHECK(result.original.source.state.usage.lane[0].value[GI_QUOTA_BYTES] + 641 ==
                f.original.source.state.usage.lane[0].value[GI_QUOTA_BYTES]);
            CHECK(gi_journal_inspect(j, &state) == GOLEM_ERR_INVALID_STATE);
            CHECK(fstatat(root, "00000001.event", &sb, 0) < 0 && fstatat(root, "00000001.payload", &sb, 0) < 0);
            gi_journal_close(j);
            CHECK(unlinkat(q, "00000001.payload.fragment.damage", 0) == 0);
            CHECK(unlinkat(q, "00000001.payload.pending", 0) == 0); close(q);
            CHECK(unlinkat(root, "quarantine", AT_REMOVEDIR) == 0);
            cleanup(root, path); return 0;
        }
        CHECK(gi_journal_fragment_observe(j, 1, &f) == GOLEM_OK && f.pending_present && !f.final_present);
        g.mode = 7; g.calls = 0;
        CHECK(gi_journal_fragment_apply(j, 1, 1, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_ERR_POLICY_DENIED);
        CHECK(fstatat(q, "00000001.payload.fragment", &sb, 0) == 0 && sb.st_nlink == 2);
        gi_journal_close(j); CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j;
        CHECK(gi_journal_fragment_observe(j, 1, &f) == GOLEM_OK);
        g.mode = 0; g.calls = 0;
        CHECK(gi_journal_fragment_apply(j, 1, 1, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_OK);
        CHECK(result.truncated_present && !result.pending_present && result.final_present);
        f = result; g.mode = 2; g.calls = 0;
        CHECK(gi_journal_fragment_apply(j, 1, 2, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_ERR_POLICY_DENIED);
        CHECK(fstatat(q, "00000001.payload.pending", &sb, 0) == 0);
        g.mode = 0; g.calls = 0;
        CHECK(gi_journal_fragment_apply(j, 1, 2, &f.snapshot, &req, &op, guard, &g, &result) == GOLEM_OK);
        CHECK(!result.truncated_present && result.original.source.present);
        CHECK(result.original.source.state.usage.lane[0].value[GI_QUOTA_BYTES] + 322 == f.original.source.state.usage.lane[0].value[GI_QUOTA_BYTES]);
        CHECK(gi_journal_inspect(j, &state) == GOLEM_OK && state.pending && state.committed == 0);
        CHECK(fstatat(root, "00000001.event", &sb, 0) < 0 && fstatat(root, "00000001.payload", &sb, 0) < 0);
        gi_journal_close(j);
        CHECK(unlinkat(q, "00000001.payload.fragment", 0) == 0); close(q);
        CHECK(unlinkat(root, "quarantine", AT_REMOVEDIR) == 0);
        cleanup(root, path); return 0;
    }
    if (interruption == 9) {
        int q = openat(root, "quarantine", O_RDONLY | O_DIRECTORY); CHECK(q >= 0);
        CHECK(renameat(q, "00000001.payload", q, "00000001.payload.pending") == 0);
        gi_journal_status blocked;
        CHECK(gi_journal_inspect(j, &blocked) == GOLEM_ERR_INVALID_STATE);
        gi_journal_envelope_plan e, done, untouched;
        CHECK(gi_journal_envelope_observe(j, 1, &e) == GOLEM_OK && !e.final_present && e.pending_present);
        gi_journal_envelope_plan capacity_plan = e;
        capacity_plan.partial.source.state.usage.lane[0].value[GI_QUOTA_BYTES] =
            limit.value[GI_QUOTA_BYTES] - e.bytes + 1;
        CHECK(gi_journal_envelope_check_quota(&capacity_plan) == GOLEM_ERR_OVERFLOW);
        --capacity_plan.partial.source.state.usage.lane[0].value[GI_QUOTA_BYTES];
        CHECK(gi_journal_envelope_check_quota(&capacity_plan) == GOLEM_OK);
        capacity_plan = e;
        capacity_plan.partial.source.state.usage.lane[0].value[GI_QUOTA_ENTRIES] = limit.value[GI_QUOTA_ENTRIES];
        CHECK(gi_journal_envelope_check_quota(&capacity_plan) == GOLEM_ERR_OVERFLOW);
        memset(&untouched, 0xa5, sizeof(untouched)); done = untouched;
        g.mode = 0; g.calls = 0;
        CHECK(gi_journal_envelope_finish(j, 1, &zero, &req, guard, &g, &done) == GOLEM_ERR_INVALID_STATE);
        CHECK(memcmp(&done, &untouched, sizeof(done)) == 0);
        CHECK(gi_journal_envelope_finish(j, 1, &e.snapshot, &zero, guard, &g, &done) == GOLEM_ERR_INVALID_STATE);
        g.mode = 2; g.calls = 0;
        CHECK(gi_journal_envelope_finish(j, 1, &e.snapshot, &req, guard, &g, &done) == GOLEM_ERR_POLICY_DENIED);
        CHECK(fstatat(q, "00000001.payload", &sb, 0) < 0);
        g.mode = 7; g.calls = 0;
        CHECK(gi_journal_envelope_finish(j, 1, &e.snapshot, &req, guard, &g, &done) == GOLEM_ERR_POLICY_DENIED);
        CHECK(fstatat(q, "00000001.payload", &sb, 0) == 0 && sb.st_nlink == 2);
        CHECK(fstatat(root, "00000001.payload.pending", &sb, 0) == 0);
        gi_journal_close(j); CHECK(gi_journal_open(root, &j) == GOLEM_OK); g.j = j;
        CHECK(gi_journal_envelope_observe(j, 1, &e) == GOLEM_OK && e.final_present && e.pending_present);
        g.mode = 0; g.calls = 0;
        CHECK(gi_journal_envelope_finish(j, 1, &e.snapshot, &req, guard, &g, &done) == GOLEM_OK);
        CHECK(g.calls == 3 && done.final_present && !done.pending_present && done.partial.source.present);
        CHECK(done.inode == e.inode && memcmp(done.digest.bytes, e.digest.bytes, 32) == 0);
        CHECK(done.partial.source.state.usage.lane[0].value[GI_QUOTA_BYTES] + e.bytes ==
              e.partial.source.state.usage.lane[0].value[GI_QUOTA_BYTES]);
        CHECK(gi_journal_envelope_finish(j, 1, &done.snapshot, &req, guard, &g, &e) == GOLEM_ERR_INVALID_STATE);
        CHECK(fstatat(root, "00000001.payload", &sb, 0) < 0);
        CHECK(fstatat(root, "00000001.event", &sb, 0) < 0);
        close(q);
    }
    CHECK(gi_journal_partial_observe(j, 1, &after) == GOLEM_OK && after.archived && after.source.present);
    CHECK(after.source.state.usage.lane[0].value[GI_QUOTA_BYTES] == before.source.state.usage.lane[0].value[GI_QUOTA_BYTES] + 323);
    g.mode = 0; g.calls = 0;
    CHECK(gi_journal_partial_quarantine(j, 1, &after.source.snapshot, &zero, guard, &g, &before) == GOLEM_ERR_INVALID_STATE);
    g.calls = 0;
    CHECK(gi_journal_partial_quarantine(j, 1, &after.source.snapshot, &req, guard, &g, &before) == GOLEM_OK);
    CHECK(g.calls == 3 && before.archived && !before.source.present && !before.payload_ready);
    capacity = before;
    capacity.source.state.usage.lane[0].value[GI_QUOTA_BYTES] = limit.value[GI_QUOTA_BYTES] - 7;
    CHECK(gi_journal_partial_check_quota(&capacity, true) == GOLEM_ERR_OVERFLOW);
    capacity.source.state.usage.lane[0].value[GI_QUOTA_BYTES] -= 7;
    CHECK(gi_journal_partial_check_quota(&capacity, true) == GOLEM_OK);
    CHECK(fstatat(root, "00000001.payload.pending", &sb, 0) < 0);
    CHECK(gi_journal_payload_replace(j, &before.source.snapshot, bytes("wrong"), guard, &g, &after) == GOLEM_ERR_INVALID_STATE);
    CHECK(gi_journal_payload_replace(j, &zero, bytes("payload"), guard, &g, &after) == GOLEM_ERR_INVALID_STATE);
    g.mode = 2; g.calls = 0;
    CHECK(gi_journal_payload_replace(j, &before.source.snapshot, bytes("payload"), guard, &g, &after) == GOLEM_ERR_POLICY_DENIED);
    CHECK(fstatat(root, "00000001.payload", &sb, 0) < 0);
    g.mode = 0; g.calls = 0;
    CHECK(gi_journal_payload_replace(j, &before.source.snapshot, bytes("payload"), guard, &g, &after) == GOLEM_OK);
    CHECK(g.calls == 2 && after.payload_ready && after.source.state.pending && !after.source.state.committed);
    CHECK(fstatat(root, "00000001.event", &sb, 0) < 0);
    CHECK(after.source.state.usage.lane[0].value[GI_QUOTA_BYTES] == before.source.state.usage.lane[0].value[GI_QUOTA_BYTES] + 7);
    CHECK(after.source.state.usage.lane[0].value[GI_QUOTA_EVENTS] == 1);
    CHECK(after.source.state.usage.lane[0].value[GI_QUOTA_PAYLOAD] == 7);
    CHECK(gi_journal_payload_replace(j, &after.source.snapshot, bytes("payload"), guard, &g, &before) == GOLEM_ERR_INVALID_STATE);
    gi_journal_pending_plan pending;
    CHECK(gi_journal_pending_plan_get(j, &pending) == GOLEM_OK);
    /* Only a separate explicit call can publish an event. */
    CHECK(gi_journal_pending_finish(j, &pending.snapshot, guard, &g, &receipt) == GOLEM_OK);
    gi_journal_status state; CHECK(gi_journal_inspect(j, &state) == GOLEM_OK && state.committed == 1);
    CHECK(golem_digest_bytes(bytes("next-operation"), &op) == GOLEM_OK);
    CHECK(gi_journal_append(j, GI_QUOTA_INTAKE, &op, &req, 1, &state.head, bytes("next"), guard, &g, &receipt) == GOLEM_OK);
    CHECK(gi_journal_inspect(j, &state) == GOLEM_OK && state.committed == 2 && !state.pending);
    gi_journal_close(j);
    int q = openat(root, "quarantine", O_RDONLY | O_DIRECTORY); CHECK(q >= 0);
    CHECK(unlinkat(q, "00000001.payload", 0) == 0); close(q);
    CHECK(unlinkat(root, "quarantine", AT_REMOVEDIR) == 0);
    cleanup(root, path); return 0;
}

int main(void)
{
    for (int mode = 0; mode <= 6; ++mode) CHECK(scenario(mode) == 0);
    CHECK(saturation() == 0);
    CHECK(partial_preparation() == 0);
    for (unsigned kind = 0; kind < 3; ++kind) CHECK(alias_recovery(kind) == 0);
    CHECK(partial_recovery(7) == 0);
    CHECK(partial_recovery(8) == 0);
    CHECK(partial_recovery(9) == 0);
    CHECK(partial_recovery(10) == 0);
    CHECK(partial_recovery(11) == 0);
    return 0;
}
