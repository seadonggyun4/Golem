/* Private syscall-injected backend; no fault switches in the production API. */
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include "test.h"
#include "../../src/daemon/admission_internal.h"

static unsigned mode, syncs, writes;
static int injected_sync(int fd)
{
    ++syncs;
    if ((mode == 1 && syncs == 1) || (mode == 2 && syncs == 2)) {
        errno = EIO;
        return -1;
    }
    return fsync(fd);
}
static ssize_t injected_write(int fd, const void *data, size_t size)
{
    ++writes;
    if (mode == 3 && writes > 1) {
        errno = EIO;
        return -1;
    }
    if (mode == 4 && writes == 1) {
        errno = EINTR;
        return -1;
    }
    return write(fd, data, size > 7 ? 7 : size);
}
#define gd_path fault_gd_path
#define gd_job_path fault_gd_job_path
#define gd_lock fault_gd_lock
#define gd_read fault_gd_read
#define gd_write fault_gd_write
#define gd_root fault_gd_root
#define gd_list fault_gd_list
#define fsync injected_sync
#define write injected_write
#include "../../src/daemon/storage.c"
#undef fsync
#undef write
#define ga_encode fault_ga_encode
#define ga_decode fault_ga_decode
#define ga_load fault_ga_load
#define ga_commit fault_ga_commit
#include "../../src/daemon/admission_storage.c"

int main(void)
{
    for (mode = 1; mode <= 4; ++mode) {
        char root[] = "/tmp/golem-admission-fault-XXXXXX";
        CHECK(mkdtemp(root));
        char real[4096];
        CHECK(realpath(root, real));
        golem_admission_options o = {.size = sizeof(o),
                                     .version = GOLEM_ADMISSION_VERSION,
                                     .create = true,
                                     .limits = {1, 1000, 1024, 0}};
        golem_admission *a = NULL;
        CHECK(golem_admission_open(real, &o, &a) == GOLEM_OK);
        ga_event event = {.operation = GA_ENQUEUE,
                          .ticket = 1,
                          .request = {.operation = "fault-1",
                                      .work = "work",
                                      .session = "session",
                                      .runtime_binding = {{1}},
                                      .cpu_millis = 1000,
                                      .memory_bytes = 1024}};
        syncs = writes = 0;
        uint64_t event_sequence = a->events.sequence;
        golem_status s = fault_ga_commit(a, &event);
        if (mode != 4) {
            CHECK(s == GOLEM_ERR_IO && a->poisoned && a->model.count == 0);
            CHECK(a->events.sequence == event_sequence);
            uint64_t output = 99;
            CHECK(golem_admission_enqueue(a, &event.request, &output) == GOLEM_ERR_INVALID_STATE);
            CHECK(output == 99);
        } else {
            CHECK(s == GOLEM_OK && a->model.count == 1);
            CHECK(a->events.sequence == event_sequence + 1);
        }
        CHECK(golem_admission_close(a) == GOLEM_OK);
        CHECK(golem_admission_open(real, &o, &a) == GOLEM_OK);
        golem_admission_ticket t;
        s = golem_admission_lookup(a, "fault-1", &t);
        if (mode == 2 || mode == 4)
            CHECK(s == GOLEM_OK && t.state == GOLEM_ADMISSION_QUEUED);
        else
            CHECK(s == GOLEM_ERR_NOT_FOUND);
        CHECK(golem_admission_close(a) == GOLEM_OK);
        DIR *dir = opendir(real);
        CHECK(dir);
        struct dirent *entry;
        while ((entry = readdir(dir))) {
            if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, ".."))
                continue;
            CHECK(unlinkat(dirfd(dir), entry->d_name, 0) == 0);
        }
        CHECK(closedir(dir) == 0 && rmdir(real) == 0);
    }
    return 0;
}
