#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#include "../../src/intent/inventory.h"
#include "test.h"
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>

int main(void)
{
    char path[] = "/tmp/golem-intent-inventory-XXXXXX";
    CHECK(mkdtemp(path) != NULL);
    int root = open(path, O_RDONLY | O_DIRECTORY); CHECK(root >= 0);
    gi_inventory out, sentinel; memset(&sentinel, 0xa5, sizeof(sentinel));
    CHECK(gi_inventory_scan(root, 0, 8, &out) == GOLEM_OK);
    CHECK(out.files == 0 && out.logical_bytes == 0);
    CHECK(mkdirat(root, "cas", 0700) == 0);
    int dir = openat(root, "cas", O_RDONLY | O_DIRECTORY); CHECK(dir >= 0);
    int file = openat(dir, ".pending-object", O_CREAT | O_EXCL | O_WRONLY, 0600);
    CHECK(file >= 0); CHECK(write(file, "abc", 3) == 3); CHECK(close(file) == 0);
    CHECK(linkat(dir, ".pending-object", root, "orphan", 0) == 0);
    for (unsigned i = 0; i < 2; ++i) {
        CHECK(gi_inventory_scan(root, 3, 8, &out) == GOLEM_OK);
        CHECK(out.files == 2 && out.directories == 1 && out.logical_bytes == 6);
    }
    out = sentinel;
    CHECK(gi_inventory_scan(root, 2, 8, &out) == GOLEM_ERR_OVERFLOW);
    CHECK(memcmp(&out, &sentinel, sizeof(out)) == 0);
    CHECK(symlinkat("cas", root, "link") == 0);
    CHECK(gi_inventory_scan(root, 100, 8, &out) == GOLEM_ERR_INVALID_STATE);
    CHECK(memcmp(&out, &sentinel, sizeof(out)) == 0);
    CHECK(unlinkat(root, "link", 0) == 0);
    CHECK(mkfifoat(root, "fifo", 0600) == 0);
    CHECK(gi_inventory_scan(root, 100, 8, &out) == GOLEM_ERR_INVALID_STATE);
    CHECK(unlinkat(root, "fifo", 0) == 0);
    CHECK(mkdirat(dir, "nested", 0700) == 0);
    CHECK(gi_inventory_scan(root, 100, 1, &out) == GOLEM_ERR_OVERFLOW);
    CHECK(gi_inventory_scan(root, 100, 2, &out) == GOLEM_OK);
    CHECK(out.files == 2 && out.logical_bytes == 6 && out.directories == 2);
    CHECK(gi_inventory_scan(root, 100, 0, &out) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_inventory_scan(root, 100, 65, &out) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(gi_inventory_scan(root, 100, 8, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(unlinkat(dir, "nested", AT_REMOVEDIR) == 0);
    CHECK(unlinkat(dir, ".pending-object", 0) == 0); CHECK(close(dir) == 0);
    CHECK(unlinkat(root, "orphan", 0) == 0);
    CHECK(unlinkat(root, "cas", AT_REMOVEDIR) == 0); CHECK(close(root) == 0);
    CHECK(rmdir(path) == 0);
    return 0;
}
