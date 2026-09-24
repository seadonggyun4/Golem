#ifndef GOLEM_PROOF_INTERNAL_H
#define GOLEM_PROOF_INTERNAL_H
#include "internal.h"
#include "golem/proof.h"
#define PROOF_FILES 6
#define PROOF_PAYLOADS 4
extern const char *const proof_names[PROOF_FILES];
golem_status proof_parse(golem_bytes bytes, const golem_digest *expected, struct json_object **out,
                         golem_digest *manifest);
golem_status proof_seal(struct json_object *files, struct json_object *policy,
                        struct json_object **out);
#endif
