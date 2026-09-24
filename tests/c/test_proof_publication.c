#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "test.h"
#include "../../src/execution/proof_internal.h"
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static unsigned mode, nth, writes, syncs, closes, links;
static ssize_t fault_write(int fd, const void *data, size_t size)
{
    ++writes;
    if (mode == 1 && writes == nth) {
        errno = EIO;
        return -1;
    }
    if (mode == 5 && writes == 1) {
        errno = EINTR;
        return -1;
    }
    return write(fd, data, mode == 5 && size > 3 ? 3 : size);
}
static int fault_sync(int fd)
{
    if (++syncs == nth && mode == 2) {
        errno = EIO;
        return -1;
    }
    return fsync(fd);
}
static int fault_close(int fd)
{
    int result = close(fd);
    if (++closes == nth && mode == 3) {
        errno = EIO;
        return -1;
    }
    return result;
}
static int fault_link(int from, const char *old, int to, const char *name, int flags)
{
    if (++links == nth && mode == 4) {
        errno = EIO;
        return -1;
    }
    int result = linkat(from, old, to, name, flags);
    if (mode == 6 && links == nth && result == 0)
        _exit(71);
    return result;
}

/* Exercise the production storage and pack publication code with syscall
 * fault injection, without adding production fault controls or replacing CAS. */
#define dw_scratch fault_dw_scratch
#define dw_scratch_free fault_dw_scratch_free
#define dw_dir fault_dw_dir
#define dw_read_at fault_dw_read_at
#define dw_publish fault_dw_publish
#define dw_event_write fault_dw_event_write
#define dw_cas_json fault_dw_cas_json
#define dw_put_json fault_dw_put_json
#define dw_replay fault_dw_replay
#define dw_project fault_dw_project
#define write fault_write
#define fsync fault_sync
#define close fault_close
#define linkat fault_link
#include "../../src/document/storage.c"
#define golem_proof_publish fault_proof_publish
#define golem_proof_verify_directory fault_proof_verify_directory
#include "../../src/execution/proof_store.c"
#undef golem_proof_publish
#undef golem_proof_verify_directory
#undef write
#undef fsync
#undef close
#undef linkat

static int cleanup(const char *root, const golem_digest *digest)
{
    char hex[65], folder[256];
    size_t needed;
    CHECK(golem_digest_format(digest, hex, sizeof(hex), &needed) == GOLEM_OK);
    CHECK(snprintf(folder, sizeof(folder), "%s/%s", root, hex) > 0);
    DIR *dir = opendir(folder);
    if (dir) {
        struct dirent *e;
        while ((e = readdir(dir)))
            if (strcmp(e->d_name, ".") && strcmp(e->d_name, ".."))
                CHECK(unlinkat(dirfd(dir), e->d_name, 0) == 0);
        CHECK(closedir(dir) == 0);
        CHECK(rmdir(folder) == 0);
    }
    CHECK(rmdir(root) == 0);
    return 0;
}

int main(void)
{
    struct json_object *files = json_object_new_object(), *policy = json_object_new_object(),
                       *pack = NULL;
    CHECK(ex_uint(policy, "schema_version", 1));
    CHECK(ex_text(policy, "profile", "MINIMAL"));
    CHECK(dw_add(policy, "acknowledge_linkability", json_object_new_boolean(false)));
    for (size_t i = 0; i < PROOF_PAYLOADS; ++i)
        CHECK(ex_text(files, proof_names[i], "fixture\n"));
    CHECK(proof_seal(files, policy, &pack) == GOLEM_OK);
    golem_execution_reply reply = {0};
    CHECK(ex_emit(pack, &reply) == GOLEM_OK);
    golem_bytes bytes = {reply.data, reply.size};
    golem_digest digest;
    struct json_object *parsed = NULL;
    CHECK(proof_parse(bytes, NULL, &parsed, &digest) == GOLEM_OK);
    json_object_put(parsed);
    unsigned limits[] = {0, 6, 14, 8, 6, 1, 6};
    for (unsigned kind = 1; kind <= 6; ++kind) {
        for (unsigned point = 1; point <= limits[kind]; ++point) {
            char root[] = "/private/tmp/golem-proof-fault-XXXXXX";
#ifndef __APPLE__
            memcpy(root, "/tmp/golem-proof-fault-XXXXXX", sizeof("/tmp/golem-proof-fault-XXXXXX"));
#endif
            CHECK(mkdtemp(root) != NULL);
            mode = kind;
            nth = point;
            writes = syncs = closes = links = 0;
            golem_digest output;
            memset(&output, 0x7a, sizeof(output));
            golem_digest sentinel = output;
            if (kind == 6) {
                pid_t child = fork();
                CHECK(child >= 0);
                if (child == 0) {
                    (void)fault_proof_publish(bytes, root, &output, NULL);
                    _exit(72);
                }
                int status;
                CHECK(waitpid(child, &status, 0) == child);
                CHECK(WIFEXITED(status) && WEXITSTATUS(status) == 71);
            } else {
                golem_status st = fault_proof_publish(bytes, root, &output, NULL);
                CHECK(st == (kind == 5 ? GOLEM_OK : GOLEM_ERR_IO));
                if (st != GOLEM_OK)
                    CHECK(memcmp(&output, &sentinel, sizeof(output)) == 0);
            }
            mode = 0;
            golem_status verified = golem_proof_verify_directory(root, &digest, NULL);
            /* Final commit link, last dirsync or directory close can fail after
             * a complete pack is visible. Earlier failures never authorize it. */
            bool visible = kind == 5 || (kind == 2 && point == 14) || (kind == 3 && point == 8) ||
                           (kind == 6 && point == 6);
            CHECK((verified == GOLEM_OK) == visible);
            CHECK(golem_proof_publish(bytes, root, &output, NULL) == GOLEM_OK);
            CHECK(golem_proof_verify_directory(root, &digest, NULL) == GOLEM_OK);
            CHECK(cleanup(root, &digest) == 0);
        }
    }
    golem_execution_reply_free(&reply);
    json_object_put(pack);
    json_object_put(policy);
    json_object_put(files);
    return EXIT_SUCCESS;
}
