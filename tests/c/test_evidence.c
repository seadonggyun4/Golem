#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE
#define _DEFAULT_SOURCE
#include "golem/evidence.h"
#include "test.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

static const char empty_hex[] = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
static const char abc_hex[] = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
static const char million_hex[] = "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0";

static golem_bytes bytes(const char *text)
{
    return (golem_bytes){(const uint8_t *)text, strlen(text)};
}

static int format(const golem_digest *digest, char hex[65])
{
    size_t required;
    CHECK(golem_digest_format(digest, hex, 65, &required) == GOLEM_OK);
    CHECK(required == 65);
    return 0;
}

static int make_root(char root[128])
{
#ifdef __APPLE__
    strcpy(root, "/private/tmp/golem-evidence-XXXXXX");
#else
    strcpy(root, "/tmp/golem-evidence-XXXXXX");
#endif
    CHECK(mkdtemp(root) != NULL);
    return 0;
}

static int cleanup(const char *path)
{
    struct stat info;
    CHECK(lstat(path, &info) == 0);
    if (!S_ISDIR(info.st_mode)) { CHECK(unlink(path) == 0); return 0; }
    DIR *directory = opendir(path);
    CHECK(directory != NULL);
    struct dirent *entry;
    while ((entry = readdir(directory)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;
        char child[1024];
        CHECK(snprintf(child, sizeof(child), "%s/%s", path, entry->d_name) < (int)sizeof(child));
        CHECK(cleanup(child) == 0);
    }
    CHECK(closedir(directory) == 0);
    CHECK(rmdir(path) == 0);
    return 0;
}

static int write_file(const char *path, const void *data, size_t length)
{
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    CHECK(fd >= 0);
    size_t offset = 0;
    while (offset < length) {
        ssize_t amount = write(fd, (const uint8_t *)data + offset, length - offset);
        if (amount < 0 && errno == EINTR) continue;
        CHECK(amount > 0);
        offset += (size_t)amount;
    }
    CHECK(close(fd) == 0);
    return 0;
}

static int object_path(const char *root, const golem_digest *digest, char path[512])
{
    char hex[65];
    CHECK(format(digest, hex) == 0);
    CHECK(snprintf(path, 512, "%s/objects/sha256/%.2s/%s", root, hex, hex + 2) < 512);
    return 0;
}

static int no_temporaries(const char *root)
{
    char path[256];
    (void)snprintf(path, sizeof(path), "%s/objects/sha256", root);
    DIR *directory = opendir(path);
    CHECK(directory != NULL);
    struct dirent *entry;
    while ((entry = readdir(directory)) != NULL) CHECK(strncmp(entry->d_name, ".tmp-", 5) != 0);
    CHECK(closedir(directory) == 0);
    return 0;
}

static int digest_tests(void)
{
    golem_digest digest, parsed;
    char hex[65];
    CHECK(golem_digest_bytes((golem_bytes){NULL, 0}, &digest) == GOLEM_OK);
    CHECK(format(&digest, hex) == 0 && strcmp(hex, empty_hex) == 0);
    CHECK(golem_digest_bytes(bytes("abc"), &digest) == GOLEM_OK);
    CHECK(format(&digest, hex) == 0 && strcmp(hex, abc_hex) == 0);
    CHECK(golem_digest_parse((golem_string_view){hex, 64}, &parsed) == GOLEM_OK);
    CHECK(memcmp(parsed.bytes, digest.bytes, 32) == 0);
    size_t required = 999;
    char small[64]; memset(small, 'x', sizeof(small));
    CHECK(golem_digest_format(&digest, small, sizeof(small), &required) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(required == 65);
    for (size_t i = 0; i < sizeof(small); ++i) CHECK(small[i] == 'x');
    CHECK(golem_digest_format(&digest, NULL, 0, &required) == GOLEM_ERR_BUFFER_TOO_SMALL);
    const size_t bad_lengths[] = {0, 1, 63, 65};
    for (size_t i = 0; i < sizeof(bad_lengths) / sizeof(bad_lengths[0]); ++i)
        CHECK(golem_digest_parse((golem_string_view){hex, bad_lengths[i]}, &parsed) == GOLEM_ERR_PARSE);
    for (size_t i = 0; i < 64; ++i) {
        char save = hex[i]; hex[i] = i % 2 ? '/' : 'A';
        CHECK(golem_digest_parse((golem_string_view){hex, 64}, &parsed) == GOLEM_ERR_PARSE);
        CHECK(memcmp(parsed.bytes, digest.bytes, 32) == 0);
        hex[i] = save;
    }
    CHECK(golem_digest_bytes((golem_bytes){NULL, 1}, &digest) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_digest_bytes(bytes("abc"), NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_digest_parse((golem_string_view){NULL, 64}, &parsed) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_digest_parse((golem_string_view){NULL, 0}, &parsed) == GOLEM_ERR_PARSE);
    return 0;
}

static int receipt_tests(void)
{
    const uint8_t golden[48] = {
        0x48,0x57,0x45,0x52,0x01,0x00,0x01,0x00,0x03,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
        0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,
        0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
    golem_receipt receipt = {1, 1, 3, {{0}}}, decoded;
    CHECK(golem_digest_bytes(bytes("abc"), &receipt.digest) == GOLEM_OK);
    uint8_t encoded[49]; memset(encoded, 0xaa, sizeof(encoded));
    size_t required = 0;
    CHECK(golem_receipt_encode(&receipt, NULL, 0, &required) == GOLEM_ERR_BUFFER_TOO_SMALL && required == 48);
    CHECK(golem_receipt_encode(&receipt, encoded, 47, &required) == GOLEM_ERR_BUFFER_TOO_SMALL);
    for (size_t i = 0; i < sizeof(encoded); ++i) CHECK(encoded[i] == 0xaa);
    CHECK(golem_receipt_encode(&receipt, encoded, sizeof(encoded), &required) == GOLEM_OK);
    CHECK(memcmp(encoded, golden, 48) == 0 && encoded[48] == 0xaa);
    CHECK(golem_receipt_decode((golem_bytes){golden, 48}, &decoded) == GOLEM_OK);
    CHECK(decoded.version == 1 && decoded.algorithm == 1 && decoded.size == 3);
    CHECK(memcmp(decoded.digest.bytes, receipt.digest.bytes, 32) == 0);
    for (size_t i = 0; i < 48; ++i) {
        CHECK(golem_receipt_decode((golem_bytes){encoded, i}, &decoded) == GOLEM_ERR_PARSE);
        CHECK(decoded.size == 3);
    }
    CHECK(golem_receipt_decode((golem_bytes){encoded, 49}, &decoded) == GOLEM_ERR_PARSE);
    encoded[0] = 0;
    CHECK(golem_receipt_decode((golem_bytes){encoded, 48}, &decoded) == GOLEM_ERR_PARSE);
    encoded[0] = 'H'; encoded[4] = 2;
    CHECK(golem_receipt_decode((golem_bytes){encoded, 48}, &decoded) == GOLEM_ERR_UNSUPPORTED_VERSION);
    encoded[4] = 1; encoded[6] = 2;
    CHECK(golem_receipt_decode((golem_bytes){encoded, 48}, &decoded) == GOLEM_ERR_UNSUPPORTED_VERSION);
    encoded[6] = 1; encoded[15] = 0xff;
    CHECK(golem_receipt_decode((golem_bytes){encoded, 48}, &decoded) == GOLEM_ERR_OVERFLOW);
    receipt.version = 2; required = 999;
    CHECK(golem_receipt_encode(&receipt, encoded, sizeof(encoded), &required) == GOLEM_ERR_UNSUPPORTED_VERSION);
    CHECK(required == 999 && decoded.size == 3);
    return 0;
}

static int roundtrip_tests(void)
{
    char root[128]; CHECK(make_root(root) == 0);
    golem_evidence_store *store = NULL;
    CHECK(golem_evidence_open(root, false, NULL, &store, NULL) == GOLEM_ERR_NOT_FOUND && store == NULL);
    CHECK(golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_OK);
    golem_receipt first, second, decoded;
    CHECK(golem_evidence_put(store, bytes("abc"), &first, NULL) == GOLEM_OK);
    char path[512]; CHECK(object_path(root, &first.digest, path) == 0);
    struct stat before, after;
    CHECK(stat(path, &before) == 0 && (before.st_mode & 0777) == 0400);
    CHECK(golem_evidence_put(store, bytes("abc"), &second, NULL) == GOLEM_OK);
    CHECK(stat(path, &after) == 0 && before.st_ino == after.st_ino);
    CHECK(memcmp(first.digest.bytes, second.digest.bytes, 32) == 0 && second.size == 3);
    uint64_t size = 999;
    CHECK(golem_evidence_verify(store, &first.digest, &size, NULL) == GOLEM_OK && size == 3);
    golem_digest receipt_key;
    CHECK(golem_evidence_receipt_store(store, &first, &receipt_key, NULL) == GOLEM_OK);
    CHECK(golem_evidence_receipt_verify(store, &receipt_key, &decoded, NULL) == GOLEM_OK);
    CHECK(decoded.size == 3 && memcmp(decoded.digest.bytes, first.digest.bytes, 32) == 0);
    CHECK(golem_evidence_put(store, (golem_bytes){NULL, 0}, &second, NULL) == GOLEM_OK);
    CHECK(golem_evidence_verify(store, &second.digest, &size, NULL) == GOLEM_OK && size == 0);
    CHECK(golem_evidence_close(store) == GOLEM_OK);
    CHECK(golem_evidence_open(root, false, NULL, &store, NULL) == GOLEM_OK);
    CHECK(golem_evidence_receipt_verify(store, &receipt_key, &decoded, NULL) == GOLEM_OK);
    CHECK(golem_evidence_put(store, bytes("x"), &second, NULL) == GOLEM_ERR_POLICY_DENIED);
    CHECK(golem_evidence_import(store, path, &second, NULL) == GOLEM_ERR_POLICY_DENIED);
    CHECK(golem_evidence_close(store) == GOLEM_OK);
    CHECK(no_temporaries(root) == 0);
    return cleanup(root);
}

static int file_tests(void)
{
    char root[128], source[256]; CHECK(make_root(root) == 0);
    (void)snprintf(source, sizeof(source), "%s/artifact", root);
    uint8_t *million = malloc(1000000); CHECK(million != NULL);
    memset(million, 'a', 1000000);
    CHECK(write_file(source, million, 1000000) == 0);
    golem_digest digest;
    CHECK(golem_digest_bytes((golem_bytes){million, 1000000}, &digest) == GOLEM_OK);
    free(million);
    golem_receipt hashed, imported;
    CHECK(golem_digest_file(source, &hashed, NULL) == GOLEM_OK);
    char hex[65]; CHECK(format(&hashed.digest, hex) == 0 && strcmp(hex, million_hex) == 0);
    CHECK(memcmp(hashed.digest.bytes, digest.bytes, 32) == 0 && hashed.size == 1000000);
    golem_evidence_store *store = NULL;
    CHECK(golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_OK);
    CHECK(golem_evidence_import(store, source, &imported, NULL) == GOLEM_OK);
    CHECK(memcmp(imported.digest.bytes, digest.bytes, 32) == 0 && imported.size == 1000000);
    uint64_t size;
    CHECK(golem_evidence_verify(store, &digest, &size, NULL) == GOLEM_OK && size == 1000000);
    CHECK(write_file(source, NULL, 0) == 0);
    CHECK(golem_evidence_import(store, source, &imported, NULL) == GOLEM_OK && imported.size == 0);
    CHECK(format(&imported.digest, hex) == 0 && strcmp(hex, empty_hex) == 0);
    CHECK(golem_evidence_import(store, root, &imported, NULL) == GOLEM_ERR_IO);
    CHECK(golem_digest_file(root, &hashed, NULL) == GOLEM_ERR_IO);
    CHECK(unlink(source) == 0);
    CHECK(golem_evidence_import(store, source, &imported, NULL) == GOLEM_ERR_NOT_FOUND);
    CHECK(imported.size == 0);
    CHECK(golem_evidence_close(store) == GOLEM_OK);
    CHECK(no_temporaries(root) == 0);
    return cleanup(root);
}

static int corruption_tests(void)
{
    char root[128], path[512]; CHECK(make_root(root) == 0);
    golem_evidence_store *store = NULL;
    CHECK(golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_OK);
    golem_receipt receipt, saved, output = {1, 1, 999, {{0}}};
    CHECK(golem_evidence_put(store, bytes("abc"), &receipt, NULL) == GOLEM_OK);
    saved = receipt;
    CHECK(object_path(root, &receipt.digest, path) == 0 && chmod(path, 0600) == 0);
    const char *corrupt[] = {"abd", "ab", "abcd", ""};
    uint64_t size = 999;
    golem_diagnostic d;
    for (size_t i = 0; i < sizeof(corrupt) / sizeof(corrupt[0]); ++i) {
        CHECK(write_file(path, corrupt[i], strlen(corrupt[i])) == 0);
        CHECK(golem_evidence_verify(store, &receipt.digest, &size, &d) == GOLEM_ERR_DIGEST_MISMATCH);
        CHECK(size == 999 && d.status == GOLEM_ERR_DIGEST_MISMATCH);
        CHECK(golem_evidence_put(store, bytes("abc"), &output, NULL) == GOLEM_ERR_DIGEST_MISMATCH);
        CHECK(output.size == 999);
        struct stat info; CHECK(stat(path, &info) == 0 && info.st_size == (off_t)strlen(corrupt[i]));
    }
    CHECK(unlink(path) == 0);
    CHECK(golem_evidence_verify(store, &receipt.digest, &size, NULL) == GOLEM_ERR_NOT_FOUND && size == 999);
    golem_digest key;
    CHECK(golem_evidence_receipt_store(store, &saved, &key, NULL) == GOLEM_OK);
    CHECK(golem_evidence_receipt_verify(store, &key, &output, NULL) == GOLEM_ERR_NOT_FOUND);
    CHECK(output.size == 999);
    CHECK(golem_evidence_put(store, bytes("abc"), &receipt, NULL) == GOLEM_OK);
    saved.size = 4;
    CHECK(golem_evidence_receipt_store(store, &saved, &key, NULL) == GOLEM_OK);
    CHECK(golem_evidence_receipt_verify(store, &key, &output, NULL) == GOLEM_ERR_SIZE_MISMATCH);
    CHECK(output.size == 999);
    CHECK(object_path(root, &key, path) == 0 && chmod(path, 0600) == 0);
    uint8_t encoded[48]; size_t required;
    CHECK(golem_receipt_encode(&saved, encoded, sizeof(encoded), &required) == GOLEM_OK);
    encoded[8] = 3;
    CHECK(write_file(path, encoded, sizeof(encoded)) == 0);
    CHECK(golem_evidence_receipt_verify(store, &key, &output, NULL) == GOLEM_ERR_DIGEST_MISMATCH);
    encoded[4] = 2;
    CHECK(golem_evidence_put(store, (golem_bytes){encoded, sizeof(encoded)}, &receipt, NULL) == GOLEM_OK);
    CHECK(golem_evidence_receipt_verify(store, &receipt.digest, &output, NULL) == GOLEM_ERR_UNSUPPORTED_VERSION);
    CHECK(golem_evidence_put(store, bytes("not a receipt"), &receipt, NULL) == GOLEM_OK);
    CHECK(golem_evidence_receipt_verify(store, &receipt.digest, &output, NULL) == GOLEM_ERR_PARSE);
    CHECK(golem_evidence_close(store) == GOLEM_OK);
    CHECK(no_temporaries(root) == 0);
    return cleanup(root);
}

static int path_tests(void)
{
    char root[128], other[128], path[512], alias[256];
    CHECK(make_root(root) == 0 && make_root(other) == 0);
    golem_evidence_store *store = NULL;
    (void)snprintf(alias, sizeof(alias), "%s/link", other);
    CHECK(symlink(root, alias) == 0);
    CHECK(golem_evidence_open(alias, true, NULL, &store, NULL) == GOLEM_ERR_IO && store == NULL);
    (void)snprintf(path, sizeof(path), "%s/objects", root);
    CHECK(symlink(other, path) == 0);
    CHECK(golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_ERR_IO && store == NULL);
    CHECK(unlink(path) == 0 && mkdir(path, 0700) == 0);
    (void)snprintf(path, sizeof(path), "%s/objects/sha256", root);
    CHECK(symlink(other, path) == 0);
    CHECK(golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_ERR_IO);
    CHECK(unlink(path) == 0);
    CHECK(golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_OK);
    golem_receipt receipt;
    golem_digest key;
    CHECK(golem_digest_bytes(bytes("abc"), &key) == GOLEM_OK);
    (void)snprintf(path, sizeof(path), "%s/objects/sha256/ba", root);
    CHECK(symlink(other, path) == 0);
    CHECK(golem_evidence_put(store, bytes("abc"), &receipt, NULL) == GOLEM_ERR_IO);
    uint64_t size;
    CHECK(golem_evidence_verify(store, &key, &size, NULL) == GOLEM_ERR_IO);
    CHECK(unlink(path) == 0 && mkdir(path, 0700) == 0);
    CHECK(object_path(root, &key, path) == 0);
    (void)snprintf(alias, sizeof(alias), "%s/source", other);
    CHECK(write_file(alias, "abc", 3) == 0 && symlink(alias, path) == 0);
    CHECK(golem_evidence_verify(store, &key, &size, NULL) == GOLEM_ERR_IO);
    CHECK(golem_evidence_put(store, bytes("abc"), &receipt, NULL) == GOLEM_ERR_IO);
    CHECK(golem_evidence_import(store, path, &receipt, NULL) == GOLEM_ERR_IO);
    CHECK(golem_digest_file(path, &receipt, NULL) == GOLEM_ERR_IO);
    CHECK(unlink(path) == 0 && mkfifo(path, 0600) == 0);
    CHECK(golem_evidence_verify(store, &key, &size, NULL) == GOLEM_ERR_IO);
    CHECK(golem_evidence_import(store, path, &receipt, NULL) == GOLEM_ERR_IO);
    CHECK(unlink(path) == 0 && mkdir(path, 0700) == 0);
    CHECK(golem_evidence_verify(store, &key, &size, NULL) == GOLEM_ERR_IO);
    CHECK(rmdir(path) == 0);
    (void)snprintf(path, sizeof(path), "%s/../source", root);
    CHECK(golem_digest_file(path, &receipt, NULL) == GOLEM_ERR_IO);
    CHECK(golem_evidence_close(store) == GOLEM_OK);
    CHECK(no_temporaries(root) == 0);
    CHECK(cleanup(root) == 0);
    return cleanup(other);
}

typedef struct allocation_state { size_t calls; size_t live; bool fail; } allocation_state;
static void *allocate(void *context, size_t size)
{
    allocation_state *state = context; ++state->calls;
    if (state->fail) return NULL;
    void *result = malloc(size);
    if (result != NULL) ++state->live;
    return result;
}
static void deallocate(void *context, void *pointer)
{
    allocation_state *state = context; --state->live; free(pointer);
}
static int ownership_tests(void)
{
    char root[128]; CHECK(make_root(root) == 0);
    allocation_state state = {0, 0, true};
    golem_allocator allocator = {&state, allocate, deallocate};
    golem_evidence_store *store = NULL;
    CHECK(golem_evidence_open(root, true, &allocator, &store, NULL) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(store == NULL && state.live == 0 && state.calls == 1);
    state.fail = false;
    CHECK(golem_evidence_open(root, true, &allocator, &store, NULL) == GOLEM_OK && state.live == 1);
    allocator.allocate = NULL;
    state.fail = true;
    golem_receipt receipt;
    CHECK(golem_evidence_put(store, bytes("abc"), &receipt, NULL) == GOLEM_OK);
    uint64_t size;
    CHECK(golem_evidence_verify(store, &receipt.digest, &size, NULL) == GOLEM_OK);
    CHECK(state.calls == 2);
    CHECK(golem_evidence_close(store) == GOLEM_OK && state.live == 0);
    CHECK(golem_evidence_close(NULL) == GOLEM_OK);
    CHECK(golem_evidence_open(root, true, &allocator, &store, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_evidence_put(NULL, bytes("abc"), &receipt, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_evidence_verify(NULL, &receipt.digest, &size, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_receipt_decode((golem_bytes){NULL, 48}, &receipt) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_digest_file(NULL, &receipt, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return cleanup(root);
}

static int concurrent_tests(void)
{
    char root[128]; CHECK(make_root(root) == 0);
    uint8_t *payload = malloc(1000000); CHECK(payload != NULL);
    memset(payload, 'a', 1000000);
    pid_t children[6];
    for (size_t i = 0; i < 6; ++i) {
        children[i] = fork(); CHECK(children[i] >= 0);
        if (children[i] == 0) {
            golem_evidence_store *store = NULL;
            golem_receipt receipt;
            golem_digest key;
            bool ok = golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_OK &&
                golem_evidence_put(store, (golem_bytes){payload, 1000000}, &receipt, NULL) == GOLEM_OK &&
                golem_evidence_receipt_store(store, &receipt, &key, NULL) == GOLEM_OK;
            /* Deliberately exit without close: published evidence survives process loss. */
            _exit(ok ? 0 : 1);
        }
    }
    for (size_t i = 0; i < 6; ++i) {
        int status;
        CHECK(waitpid(children[i], &status, 0) == children[i]);
        CHECK(WIFEXITED(status) && WEXITSTATUS(status) == 0);
    }
    golem_evidence_store *store = NULL;
    CHECK(golem_evidence_open(root, false, NULL, &store, NULL) == GOLEM_OK);
    golem_receipt receipt = {1, 1, 1000000, {{0}}}, verified;
    CHECK(golem_digest_bytes((golem_bytes){payload, 1000000}, &receipt.digest) == GOLEM_OK);
    free(payload);
    uint8_t encoded[48]; size_t required;
    CHECK(golem_receipt_encode(&receipt, encoded, sizeof(encoded), &required) == GOLEM_OK);
    golem_digest key;
    CHECK(golem_digest_bytes((golem_bytes){encoded, sizeof(encoded)}, &key) == GOLEM_OK);
    CHECK(golem_evidence_receipt_verify(store, &key, &verified, NULL) == GOLEM_OK && verified.size == 1000000);
    CHECK(golem_evidence_close(store) == GOLEM_OK);
    CHECK(no_temporaries(root) == 0);
    return cleanup(root);
}

static int io_failure_tests(void)
{
    char root[128]; CHECK(make_root(root) == 0);
    const char payload[] = "this artifact exceeds the process file size limit";
    pid_t child = fork(); CHECK(child >= 0);
    if (child == 0) {
        struct rlimit limit = {8, 8};
        bool ok = signal(SIGXFSZ, SIG_IGN) != SIG_ERR && setrlimit(RLIMIT_FSIZE, &limit) == 0;
        golem_evidence_store *store = NULL;
        golem_receipt output = {1, 1, 999, {{0}}};
        ok = ok && golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_OK &&
            golem_evidence_put(store, bytes(payload), &output, NULL) == GOLEM_ERR_IO && output.size == 999;
        ok = golem_evidence_close(store) == GOLEM_OK && ok;
        _exit(ok ? 0 : 1);
    }
    int status;
    CHECK(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    CHECK(no_temporaries(root) == 0);
    golem_evidence_store *store = NULL;
    CHECK(golem_evidence_open(root, true, NULL, &store, NULL) == GOLEM_OK);
    golem_digest key;
    CHECK(golem_digest_bytes(bytes(payload), &key) == GOLEM_OK);
    uint64_t size = 999;
    CHECK(golem_evidence_verify(store, &key, &size, NULL) == GOLEM_ERR_NOT_FOUND && size == 999);
    golem_receipt output;
    CHECK(golem_evidence_put(store, bytes(payload), &output, NULL) == GOLEM_OK);
    CHECK(golem_evidence_verify(store, &key, &size, NULL) == GOLEM_OK && size == strlen(payload));
    CHECK(golem_evidence_close(store) == GOLEM_OK);
    return cleanup(root);
}

int main(int argc, char **argv)
{
    CHECK(argc == 2);
    if (strcmp(argv[1], "digest") == 0) return digest_tests();
    if (strcmp(argv[1], "receipt") == 0) return receipt_tests();
    if (strcmp(argv[1], "roundtrip") == 0) return roundtrip_tests();
    if (strcmp(argv[1], "file") == 0) return file_tests();
    if (strcmp(argv[1], "corruption") == 0) return corruption_tests();
    if (strcmp(argv[1], "paths") == 0) return path_tests();
    if (strcmp(argv[1], "ownership") == 0) return ownership_tests();
    if (strcmp(argv[1], "concurrent") == 0) return concurrent_tests();
    if (strcmp(argv[1], "io_failure") == 0) return io_failure_tests();
    return EXIT_FAILURE;
}
