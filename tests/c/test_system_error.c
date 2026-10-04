#include "golem/system_error.h"
#include "test.h"
#include <errno.h>
#include <pthread.h>
#include <string.h>

static void *worker(void *arg)
{
    golem_system_error_scope *scope = arg;
    if (golem_system_error_begin(scope) != GOLEM_OK) return arg;
    (void)golem_system_error_note(GOLEM_ERR_IO, "thread", "read", EBADF);
    return golem_system_error_end(scope) == GOLEM_OK ? NULL : arg;
}
int main(void)
{
    golem_system_error_scope outer, inner, other;
    errno = EACCES;
    CHECK(golem_system_error_note(GOLEM_ERR_IO, "off", "read", EIO) == GOLEM_ERR_IO);
    CHECK(errno == EACCES);
    CHECK(golem_system_error_begin(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_system_error_begin(&outer) == GOLEM_OK);
    CHECK(golem_system_error_begin(&outer) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_system_error_note(GOLEM_OK, "ignore", "read", EIO) == GOLEM_OK);
    CHECK(outer.count == 0);
    CHECK(golem_system_error_note(GOLEM_ERR_IO, "first", "read", ENOSPC) == GOLEM_ERR_IO);
    CHECK(errno == EACCES);
    CHECK(golem_system_error_begin(&inner) == GOLEM_OK);
    CHECK(golem_system_error_end(&outer) == GOLEM_ERR_INVALID_STATE);
    (void)golem_system_error_note(GOLEM_ERR_IO, "inner", "file_shape", 0);
    CHECK(inner.count == 1 && inner.entries[0].error_number == 0 && outer.count == 1);
    CHECK(golem_system_error_end(&inner) == GOLEM_OK);
    pthread_t t; void *result;
    CHECK(pthread_create(&t, NULL, worker, &other) == 0);
    CHECK(pthread_join(t, &result) == 0 && result == NULL);
    CHECK(other.count == 1 && other.entries[0].error_number == EBADF && outer.count == 1);
    char label[100]; memset(label, 'x', sizeof(label)); label[99] = 0;
    for (int i = 0; i < 10; ++i)
        (void)golem_system_error_note(GOLEM_ERR_IO, label, "quote\"\nline", EIO);
    CHECK(outer.count == 8 && outer.omitted == 3);
    CHECK(!strcmp(outer.entries[0].component, "first"));
    CHECK(outer.entries[7].truncated && !strcmp(outer.entries[7].operation, "quote__line"));
    outer.omitted = SIZE_MAX;
    (void)golem_system_error_note(GOLEM_ERR_IO, "last", "write", 99999);
    CHECK(outer.omitted == SIZE_MAX && !strcmp(outer.entries[7].component, "last"));
    CHECK(golem_system_error_end(&outer) == GOLEM_OK);
    CHECK(golem_system_error_end(&outer) == GOLEM_ERR_INVALID_STATE);
    CHECK(!strcmp(golem_system_error_name(99999), "UNKNOWN_ERRNO"));
    CHECK(!strcmp(golem_system_error_name(ENOSPC), "ENOSPC"));
    CHECK(!strcmp(golem_system_error_name(ECHILD), "ECHILD"));
    CHECK(!strcmp(golem_system_error_name(ESRCH), "ESRCH"));
    CHECK(!strcmp(golem_system_error_name(ENOEXEC), "ENOEXEC"));
    CHECK(strstr(golem_system_error_action(ECHILD), "reused process identifier") != NULL);
    CHECK(strstr(golem_system_error_action(E2BIG), "argument budget") != NULL);
    CHECK(golem_system_error_begin(&outer) == GOLEM_OK && outer.count == 0 && outer.omitted == 0);
    CHECK(golem_system_error_end(&outer) == GOLEM_OK);
    return 0;
}
