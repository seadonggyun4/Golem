#ifndef GOLEM_CLI_OUTPUT_H
#define GOLEM_CLI_OUTPUT_H
#include "golem/types.h"
/* Process-local presentation only. No runtime/Work policy or API changes. */
int cli_output_options(int *argc, char **argv);
golem_status cli_output_write(golem_bytes bytes);
int golem_cli_output(int argc, char **argv);
#endif
