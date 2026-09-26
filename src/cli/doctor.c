#define _POSIX_C_SOURCE 200809L
#include "golem/admission.h"
#include "golem/document.h"
#include "../agent_session/internal.h"
#include <errno.h>
#include <stdio.h>
#include <string.h>

/* Admission mode is explicitly mutating: caller supplies a disposable directory.
 * It exercises the real writer, not a weaker imitation of its requirements. */
int golem_cli_doctor(int argc, char **argv)
{
    golem_status status;
    golem_diagnostic diagnostic;
    (void)golem_diagnostic_clear(&diagnostic);
    if (argc == 3 && !strcmp(argv[2], "clock")) {
        uint64_t now;
        golem_digest boot;
        errno = 0;
        status = as_clock_read(NULL, &now, &boot);
        int saved = errno;
        if (status != GOLEM_OK) {
            char message[96];
            (void)snprintf(message, sizeof(message), "session.boot_identity_clock errno=%d", saved);
            (void)golem_diagnostic_set(&diagnostic, status, GOLEM_DIAGNOSTIC_NO_OFFSET, message);
        }
    } else if (argc == 4 && !strcmp(argv[2], "work")) {
        golem_document_store *store = NULL;
        status = golem_document_store_open(argv[3], false, NULL, &store, NULL);
        golem_status closed = golem_document_store_close(store);
        if (status == GOLEM_OK) status = closed;
        if (status != GOLEM_OK)
            (void)golem_diagnostic_set(&diagnostic, status, GOLEM_DIAGNOSTIC_NO_OFFSET,
                                       "work.open_replay_close");
    } else if (argc == 4 && !strcmp(argv[2], "admission")) {
        golem_admission_options options = {.size = sizeof(options),
            .version = GOLEM_ADMISSION_VERSION, .create = true,
            .limits = {1, 1000, 4096, 0}};
        golem_admission *admission = NULL;
        status = golem_admission_open_diagnostic(argv[3], &options, &admission, &diagnostic);
        if (status == GOLEM_OK) {
            status = golem_admission_close(admission);
            if (status != GOLEM_OK)
                (void)golem_diagnostic_set(&diagnostic, status,
                    GOLEM_DIAGNOSTIC_NO_OFFSET, "admission.close");
        }
    } else {
        fputs("Usage: golem doctor clock | work WORK | admission ABSOLUTE_DISPOSABLE_DIRECTORY\n", stderr);
        return 2;
    }
    /* Messages above contain only fixed ASCII operation names and decimal errno. */
    printf("{\"schema\":\"golem.doctor.v1\",\"status\":\"%s\","
           "\"code\":%d,\"diagnostic\":\"%s\"}\n",
           status == GOLEM_OK ? "PASS" : "FAIL", (int)status, diagnostic.message);
    return status == GOLEM_OK ? 0 : 1;
}
