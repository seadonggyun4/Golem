#ifndef GOLEM_WORKPACK_INTERNAL_H
#define GOLEM_WORKPACK_INTERNAL_H
#include "golem/workpack.h"
golem_status golem_workpack_read_limit(const char *path, uint8_t *buffer, size_t capacity,
                                      size_t limit, size_t *size, golem_diagnostic *diagnostic);
#endif
