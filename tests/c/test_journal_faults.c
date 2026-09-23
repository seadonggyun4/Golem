/* Syscall failures are injected only into this private backend translation unit. */
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include "test.h"
static unsigned mode, calls;
static ssize_t injected_write(int fd, const void *data, size_t size)
{
    ++calls;
    if (mode == 2 && calls > 1) {
        errno = EIO;
        return -1;
    }
    if (mode == 4 && calls == 1) {
        errno = EINTR;
        return -1;
    }
    return write(fd, data, (mode == 1 || mode == 2) && size > 7 ? 7 : size);
}
static int injected_sync(int fd)
{
    if (mode == 3) {
        errno = EIO;
        return -1;
    }
    return fsync(fd);
}
#define golem_journal_open fault_open
#define golem_journal_close fault_close
#define golem_journal_append fault_append
#define golem_journal_recover fault_recover
#define golem_journal_checkpoint_get fault_checkpoint
#define write injected_write
#define fsync injected_sync
#include "../../src/journal/file.c"
#undef write
#undef fsync

int main(void)
{
    for (mode = 1; mode <= 4; ++mode) {
        char path[] = "/tmp/golem-fault-XXXXXX";
        int fd = mkstemp(path);
        CHECK(fd >= 0 && close(fd) == 0);
        golem_journal *writer = NULL;
        CHECK(fault_open(path, NULL, &writer, NULL) == GOLEM_OK);
        uint64_t sequence = 99;
        calls = 0;
        golem_status status =
            fault_append(writer, GOLEM_JOURNAL_CANCELLED, (golem_bytes){NULL, 0}, &sequence, NULL);
        golem_journal_checkpoint checkpoint;
        if (mode == 2 || mode == 3) {
            CHECK(status == GOLEM_ERR_IO && sequence == 99);
            CHECK(fault_checkpoint(writer, &checkpoint) == GOLEM_ERR_INVALID_STATE);
            CHECK(fault_append(writer, GOLEM_JOURNAL_CANCELLED, (golem_bytes){NULL, 0}, &sequence,
                               NULL) == GOLEM_ERR_INVALID_STATE);
        } else {
            CHECK(status == GOLEM_OK && sequence == 1);
            CHECK(fault_checkpoint(writer, &checkpoint) == GOLEM_OK);
            CHECK(checkpoint.records == 1 && checkpoint.bytes == 32);
        }
        CHECK(fault_close(writer, NULL) == GOLEM_OK);
        fd = open(path, O_RDONLY);
        CHECK(fd >= 0);
        uint8_t data[64];
        ssize_t size = read(fd, data, sizeof(data));
        CHECK(size == (mode == 2 ? 7 : 32));
        CHECK(close(fd) == 0);
        golem_journal_inspection inspection;
        CHECK(golem_journal_inspect((golem_bytes){data, (size_t)size}, &inspection) == GOLEM_OK);
        CHECK(inspection.stream_status == (mode == 2 ? GOLEM_ERR_TRUNCATED_JOURNAL : GOLEM_OK));
        CHECK(unlink(path) == 0);
    }
    return EXIT_SUCCESS;
}
