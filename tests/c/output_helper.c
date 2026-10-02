#include "../../src/cli/work.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    if (cli_output_options(&argc, argv) || argc != 3 || strcmp(argv[1], "emit")) return 2;
    cli_blob input = {0};
    golem_status st = cli_read(argv[2], CLI_BUNDLE_MAX, &input);
    if (st == GOLEM_OK) st = cli_output_write((golem_bytes){input.data, input.size});
    if (st == GOLEM_OK && (fputc('\n', stdout) == EOF || fflush(stdout))) st = GOLEM_ERR_IO;
    free(input.data);
    return st == GOLEM_OK ? 0 : 1;
}
