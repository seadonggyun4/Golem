#ifndef GOLEM_ADMISSION_INTERNAL_H
#define GOLEM_ADMISSION_INTERNAL_H
#include "golem/admission.h"
#include "events_internal.h"
#include <sys/types.h>

#define GA_FRAME_SIZE 512
typedef enum ga_operation {
    GA_INIT = 1,
    GA_BOOT,
    GA_ENQUEUE,
    GA_GRANT,
    GA_BIND,
    GA_START,
    GA_RUN,
    GA_CANCEL,
    GA_SETTLE,
    GA_RELEASE,
    GA_RESIZE
} ga_operation;
typedef struct ga_event {
    ga_operation operation;
    uint64_t ticket, epoch;
    golem_admission_request request;
    golem_digest proof;
    golem_digest boot;
    uint8_t nonce[16];
} ga_event;
typedef struct ga_model {
    golem_digest namespace_id;
    golem_digest boot;
    golem_admission_limits limits;
    uint64_t epoch, count, bypasses;
    uint8_t instance[16];
    golem_admission_ticket tickets[GOLEM_ADMISSION_MAX_TICKETS];
} ga_model;
struct golem_admission {
    golem_allocator allocator;
    int directory, leader;
    pid_t owner;
    bool poisoned, busy;
    golem_admission_checkpoint checkpoint;
    ga_model model, scratch;
    ge_ring events;
};
bool ga_nonzero(const void *bytes, size_t size);
bool ga_live(golem_admission_state state);
bool ga_children(const ga_model *model, uint64_t parent);
bool ga_request_equal(const golem_admission_request *a, const golem_admission_request *b);
uint64_t ga_pick(const ga_model *model);
/* Pure bounded transition function. Caller uses a scratch copy on rejection. */
golem_status ga_apply(ga_model *model, const ga_event *event);
golem_status ga_commit(golem_admission *admission, const ga_event *event);
void ga_observe(golem_admission *admission, const ga_event *event);
golem_status ga_load(golem_admission *admission, const golem_admission_checkpoint *expected);
golem_status ga_encode(const ga_event *event, golem_admission_checkpoint previous,
                       uint8_t frame[GA_FRAME_SIZE]);
golem_status ga_decode(const uint8_t frame[GA_FRAME_SIZE], golem_admission_checkpoint previous,
                       ga_event *event);
#endif
