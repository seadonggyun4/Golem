#define _POSIX_C_SOURCE 200809L
#define _XOPEN_SOURCE 700
#define _DARWIN_C_SOURCE
#include "golem/event_reader.h"
#include "golem/admission.h"
#include "test.h"
#include <dirent.h>
#include <string.h>
#include <unistd.h>

static int codec(void)
{
    golem_runtime_event e = {.version = 1,
                             .kind = GOLEM_EVENT_QUEUED,
                             .origin = GOLEM_EVENT_ADMISSION_JOURNAL,
                             .cursor = {.sequence = 1},
                             .subject = UINT64_MAX};
    char frame[1024], tiny = 'x';
    size_t n;
    CHECK(golem_runtime_event_sse(&e, &tiny, 1, &n) == GOLEM_ERR_BUFFER_TOO_SMALL && tiny == 'x');
    CHECK(golem_runtime_event_sse(&e, frame, sizeof(frame) - 1, &n) == GOLEM_OK);
    frame[n] = 0;
    CHECK(strstr(frame, "\nevent: queued\ndata: {") && strstr(frame, "\"18446744073709551615\""));
    CHECK(n > 2 && frame[n - 1] == '\n' && frame[n - 2] == '\n');
    e.kind = (golem_runtime_event_kind)999;
    CHECK(golem_runtime_event_sse(&e, &tiny, 1, &n) == GOLEM_ERR_INVALID_ARGUMENT && tiny == 'x');
    return 0;
}
int main(void)
{
    CHECK(codec() == 0);
    char path[] = "/tmp/golem-event-reader-XXXXXX", real[4096];
    CHECK(mkdtemp(path) && realpath(path, real));
    golem_admission_options o = {
        .size = sizeof(o), .version = 1, .create = true, .limits = {1, 1000, 1024, 0}};
    golem_admission *a = NULL;
    CHECK(golem_admission_open(real, &o, &a) == GOLEM_OK);
    golem_event_reader *r = NULL;
    CHECK(golem_event_reader_open(real, NULL, &r) == GOLEM_OK);
    golem_runtime_event e[64];
    golem_runtime_event_page page;
    CHECK(golem_event_reader_read(r, NULL, e, 64, &page) == GOLEM_OK && page.count == 2);
    golem_runtime_cursor cursor = page.next;
    CHECK(golem_admission_resize(a, (golem_admission_limits){1, 1000, 1024, 0}) == GOLEM_OK);
    CHECK(golem_event_reader_read(r, &cursor, e, 64, &page) == GOLEM_OK && !page.count);
    CHECK(golem_event_reader_refresh(r) == GOLEM_OK);
    CHECK(golem_event_reader_read(r, &cursor, e, 64, &page) == GOLEM_OK && page.count == 1);
    cursor = page.next;
    CHECK(golem_admission_close(a) == GOLEM_OK);
    golem_event_reader_close(r);
    CHECK(golem_event_reader_open(real, NULL, &r) == GOLEM_OK);
    CHECK(golem_event_reader_read(r, &cursor, e, 64, &page) == GOLEM_OK && !page.count);
    char file[4200];
    snprintf(file, sizeof(file), "%s/%020d", real, 3);
    CHECK(unlink(file) == 0);
    CHECK(golem_event_reader_refresh(r) == GOLEM_ERR_REPLAY_MISMATCH);
    CHECK(golem_event_reader_read(r, NULL, e, 64, &page) == GOLEM_ERR_INVALID_STATE);
    golem_event_reader_close(r);
    DIR *dir = opendir(real);
    CHECK(dir);
    struct dirent *entry;
    while ((entry = readdir(dir))) {
        if (!strcmp(entry->d_name, ".") || !strcmp(entry->d_name, ".."))
            continue;
        CHECK(unlinkat(dirfd(dir), entry->d_name, 0) == 0);
    }
    CHECK(closedir(dir) == 0 && rmdir(real) == 0);
    return 0;
}
