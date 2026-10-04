#ifndef GOLEM_CLI_ERROR_H
#define GOLEM_CLI_ERROR_H
#include "golem/error.h"
/* Process-local CLI boundary, not a library last-error API. Arguments are
 * borrowed; diagnostic is copied. Only capture errno at the failing syscall. */
void cli_error_begin(void);
void cli_error_command(const char *command);
void cli_error_note(golem_status status, const char *phase, const golem_diagnostic *diagnostic);
void cli_error_errno(golem_status status, const char *phase, int saved_errno);
int cli_error_finish(int exit_code);
#endif
