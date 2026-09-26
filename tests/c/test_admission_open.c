/* Inject only at this test's translation-unit boundary, never through runtime env. */
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "test.h"
#include "../../src/daemon/admission_internal.h"
#include "../../src/daemon/internal.h"
#include "../../src/evidence/internal.h"
#include "../../src/agent_session/internal.h"
#include <openssl/rand.h>
#include <dirent.h>
#include <errno.h>
#include <string.h>
#include <unistd.h>

static unsigned fault, commits;
static int probe_path(const char *path, bool directory)
{
    if (fault == 1) { errno = EACCES; return -1; }
    return golem_evidence_path_open(path, directory);
}
static int probe_lock(int dir, const char *name, bool create, bool exclusive)
{
    if (fault == 2) { errno = EPERM; return -1; }
    return gd_lock(dir, name, create, exclusive);
}
static golem_status probe_load(golem_admission *a, const golem_admission_checkpoint *expected)
{
    if (fault == 3) { errno = EIO; return GOLEM_ERR_IO; }
    return ga_load(a, expected);
}
static golem_status probe_clock(const golem_agent_clock *c, uint64_t *now, golem_digest *boot)
{
    if (fault == 4) { errno = EPERM; return GOLEM_ERR_IO; }
    (void)c;
    *now = 1000;
    memset(boot, 42, sizeof(*boot));
    return GOLEM_OK;
}
static int probe_random(unsigned char *buffer, int count)
{
    if (fault == 5) return 0;
    return RAND_bytes(buffer, count);
}
static golem_status probe_commit(golem_admission *a, const ga_event *event)
{
    ++commits;
    if ((fault == 6 && commits == 1) || (fault == 7 && commits == 2)) {
        errno = EIO;
        return GOLEM_ERR_IO;
    }
    return ga_commit(a, event);
}

#define golem_evidence_path_open probe_path
#define gd_lock probe_lock
#define ga_load probe_load
#define as_clock_read probe_clock
#define RAND_bytes probe_random
#define ga_commit probe_commit
#include "../../src/daemon/admission.c"

static int initial_frames(const char *root, uint8_t frames[2][GA_FRAME_SIZE])
{
    for (unsigned i = 0; i < 2; ++i) {
        char name[8192];
        (void)snprintf(name, sizeof(name), "%s/%020u", root, i + 1);
        FILE *file = fopen(name, "rb");
        CHECK(file);
        CHECK(fread(frames[i], 1, GA_FRAME_SIZE, file) == GA_FRAME_SIZE);
        CHECK(fgetc(file) == EOF && !ferror(file));
        CHECK(fclose(file) == 0);
    }
    return 0;
}

int main(void)
{
    const char *expected[] = {"", "root_open", "owner_lock", "replay",
                              "boot_identity_clock", "random_namespace",
                              "initial_commit", "epoch_commit"};
    for (fault = 0; fault <= 7; ++fault) {
        char temporary[] = "/tmp/golem-open-XXXXXX", path[4096];
        CHECK(mkdtemp(temporary));
        CHECK(realpath(temporary, path));
        golem_admission_options options = {.size = sizeof(options), .version = 1,
            .create = true, .limits = {1, 1000, 4096, 0}};
        golem_admission *a = NULL;
        golem_diagnostic diagnostic;
        commits = 0;
        golem_status status = golem_admission_open_diagnostic(path, &options, &a, &diagnostic);
        if (fault) {
            CHECK(status != GOLEM_OK && a == NULL && diagnostic.status == status);
            CHECK(strstr(diagnostic.message, expected[fault]));
            CHECK(!strstr(diagnostic.message, path));
            if (fault == 4) CHECK(commits == 0);
        } else {
            CHECK(status == GOLEM_OK && diagnostic.status == GOLEM_OK);
            CHECK(golem_admission_close(a) == GOLEM_OK);
            uint8_t before[2][GA_FRAME_SIZE], after[2][GA_FRAME_SIZE];
            CHECK(initial_frames(path, before) == 0);
            fault = 4;
            for (unsigned retry = 0; retry < 2; ++retry) {
                a = NULL;
                commits = 0;
                CHECK(golem_admission_open_diagnostic(path, &options, &a, &diagnostic) == GOLEM_ERR_IO);
                CHECK(a == NULL && commits == 0);
                CHECK(!strcmp(diagnostic.message, "admission.boot_identity_clock errno=1"));
                CHECK(initial_frames(path, after) == 0);
                CHECK(memcmp(before, after, sizeof(before)) == 0);
            }
            fault = 0;
        }
        DIR *dir = opendir(path);
        CHECK(dir);
        struct dirent *entry;
        while ((entry = readdir(dir))) {
            if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, "..")) continue;
            if (fault == 4) CHECK(!strcmp(entry->d_name, ".owner"));
            CHECK(unlinkat(dirfd(dir), entry->d_name, 0) == 0);
        }
        CHECK(closedir(dir) == 0 && rmdir(path) == 0);
    }
    return 0;
}
