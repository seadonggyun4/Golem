#include "internal.h"
#include "golem/types.h"

golem_status golem_core_report(golem_diagnostic *diagnostic,
                                      golem_status status, const char *message)
{
    if (diagnostic != NULL) {
        if (status == GOLEM_OK) {
            (void)golem_diagnostic_clear(diagnostic);
        } else {
            (void)golem_diagnostic_set(diagnostic, status, GOLEM_DIAGNOSTIC_NO_OFFSET, message);
        }
    }
    return status;
}
char *golem_core_string_clone(const char *source, const golem_allocator *allocator)
{
    golem_string_view view;
    char *copy = NULL;
    if (golem_string_view_from_cstr(source, &view) == GOLEM_OK) {
        (void)golem_string_clone(view, allocator, &copy);
    }
    return copy;
}
