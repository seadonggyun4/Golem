#include "golem/error.h"
#include <string.h>

golem_status golem_diagnostic_clear(golem_diagnostic *diagnostic)
{
    if (diagnostic == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *diagnostic = (golem_diagnostic){0};
    diagnostic->offset = GOLEM_DIAGNOSTIC_NO_OFFSET;
    return GOLEM_OK;
}
golem_status golem_diagnostic_set(golem_diagnostic *diagnostic,
                                         golem_status status, size_t offset, const char *message)
{
    if (diagnostic == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    const char *text = message == NULL ? golem_status_string(status) : message;
    golem_diagnostic next = {0};
    next.status = status;
    next.offset = offset;
    size_t i = 0;
    /* Bounded scan works even while reporting allocation failure.
     * Build a local value so message may borrow the current diagnostic. */
    while (i + 1 < sizeof(next.message) && text[i] != '\0') {
        next.message[i] = text[i];
        ++i;
    }
    next.message[i] = '\0';
    next.truncated = text[i] != '\0';
    *diagnostic = next;
    return GOLEM_OK;
}
