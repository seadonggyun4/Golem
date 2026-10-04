#include <json-c/json.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
/* Fault injection stays in this translation unit, not in production switches. */
static int fail_allocation;
static struct json_object *test_object(void)
{
    return fail_allocation ? NULL : json_object_new_object();
}
#define json_object_new_object test_object
#include "../../src/cli/error.c"
#undef json_object_new_object

int main(int argc, char **argv)
{
    cli_error_begin();
    cli_error_command("secret-not-a-command");
    if (argc != 2) return cli_error_finish(2);
    if (!strcmp(argv[1], "system")) {
        (void)golem_system_error_note(GOLEM_ERR_IO, "storage", "write", ENOSPC);
        (void)golem_system_error_note(GOLEM_ERR_IO, "storage", "file_shape", 0);
        errno = EBADF;
        cli_error_note(GOLEM_ERR_IO, "publish", NULL);
        return cli_error_finish(1);
    }
    if (!strcmp(argv[1], "allocation")) {
        fail_allocation = 1;
        return cli_error_finish(1);
    }
    if (!strcmp(argv[1], "reset")) {
        cli_error_errno(GOLEM_ERR_IO, "old", EACCES);
        cli_error_begin();
        return cli_error_finish(2);
    }
    if (!strcmp(argv[1], "diagnostic")) {
        golem_diagnostic d;
        golem_diagnostic_clear(&d);
        d.status = GOLEM_ERR_PARSE;
        d.offset = 17;
        d.truncated = true;
        memcpy(d.message, "quote\"\nline", sizeof("quote\"\nline"));
        cli_error_errno(GOLEM_ERR_IO, "old", EACCES);
        cli_error_note(GOLEM_ERR_PARSE, "parse", &d);
        return cli_error_finish(1);
    }
    golem_status status = (golem_status)atoi(argv[1]);
    cli_error_note(status, "injected", NULL);
    return cli_error_finish(status == GOLEM_OK ? 0 : 1);
}
