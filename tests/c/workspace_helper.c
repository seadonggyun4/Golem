#define _POSIX_C_SOURCE 200809L
#include "golem/workspace.h"
#include "test.h"
#include <string.h>
#include <unistd.h>

static golem_status authorize(void *context, golem_workspace_operation operation,
                               const char *candidate)
{
    (void)operation;
    (void)candidate;
    unsigned *count = context;
    ++*count;
    const char *crash = getenv("WS_CRASH_AT");
    if (crash && *count == (unsigned)strtoul(crash, NULL, 10))
        _exit(77);
    return getenv("WS_DENY") ? GOLEM_ERR_POLICY_DENIED : GOLEM_OK;
}

static golem_status heartbeat(void *context)
{
    (void)context;
    return getenv("WS_EXPIRE") ? GOLEM_ERR_STALE_LEASE : GOLEM_OK;
}

int main(int argc, char **argv)
{
    CHECK(argc == 8);
    golem_document_store *store = NULL;
    golem_status st = golem_document_store_open(argv[1], true, NULL, &store, NULL);
    if (st != GOLEM_OK) {
        fprintf(stderr, "%s\n", golem_status_string(st));
        return 1;
    }
    unsigned count = 0;
    golem_workspace_host host = {.struct_size = sizeof(host), .version = 1,
        .repository_id = "fixture", .repository_root = argv[2], .worktree_root = argv[3],
        .check = authorize, .pulse = heartbeat, .context = &count};
    golem_workspace_operation operation = (golem_workspace_operation)strtol(argv[5], NULL, 10);
    golem_workspace_result out = {.state = GOLEM_WORKSPACE_ATTENTION};
    golem_workspace_result original = out;
    golem_digest evidence;
    const golem_digest *retained = NULL;
    if (operation == GOLEM_WORKSPACE_RETAIN) {
        st = golem_digest_parse((golem_string_view){argv[7], strlen(argv[7])}, &evidence);
        retained = &evidence;
    }
    if (st == GOLEM_OK)
        st = golem_workspace_call(store, &host, operation, argv[4],
            operation == GOLEM_WORKSPACE_CREATE ? argv[6] : NULL, retained, &out, NULL);
    if (st != GOLEM_OK)
        CHECK(!memcmp(&original, &out, sizeof(out)));
    golem_status closed = golem_document_store_close(store);
    if (st == GOLEM_OK)
        st = closed;
    if (st != GOLEM_OK) {
        fprintf(stderr, "%s\n", golem_status_string(st));
        return 1;
    }
    char digest[65];
    size_t n;
    CHECK(golem_digest_format(&out.receipt, digest, sizeof(digest), &n) == GOLEM_OK);
    printf("%u\n%s\n%s\n", (unsigned)out.state, out.path, digest);
    return 0;
}
