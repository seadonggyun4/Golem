/* Crash during repair itself, after one durable appended byte. Test binary only. */
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "../../src/daemon/internal.h"
#include <signal.h>
#include <stdlib.h>
#include <unistd.h>
static ssize_t crash_write_byte(int fd, const void *data, size_t size);
#define gd_intent_write test_intent_write
#define gd_intents_check test_intents_check
#define gd_checkpoint test_checkpoint
#define gd_recover_queue test_recover_queue
#define golem_daemon_recover test_daemon_recover
#define write crash_write_byte
#include "../../src/daemon/recovery.c"
#undef write
#undef gd_intent_write
#undef gd_intents_check
#undef gd_checkpoint
#undef gd_recover_queue
#undef golem_daemon_recover
static ssize_t crash_write_byte(int fd, const void *data, size_t size)
{
    if (size == 0) return 0;
    ssize_t n = write(fd, data, 1);
    if (n == 1 && fsync(fd) == 0) { (void)kill(getpid(), SIGKILL); _Exit(90); }
    return -1;
}
int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    golem_daemon_recovery_report report;
    return test_daemon_recover(argv[1], &report) == GOLEM_OK ? 0 : 1;
}
