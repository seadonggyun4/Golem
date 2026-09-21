#ifndef GOLEM_JOURNAL_INTERNAL_H
#define GOLEM_JOURNAL_INTERNAL_H
#include "golem/journal.h"
uint32_t golem_journal_u32(const uint8_t *p);
uint64_t golem_journal_u64(const uint8_t *p);
void golem_journal_put32(uint8_t *p, uint32_t value);
void golem_journal_put64(uint8_t *p, uint64_t value);
golem_status golem_journal_report(golem_diagnostic *d, golem_status status,
                                         size_t offset, const char *message);
golem_status golem_journal_header_check(const uint8_t *p, size_t *frame_size,
                                               golem_diagnostic *d);
golem_status golem_journal_created_decode(golem_bytes payload,
    const golem_allocator *allocator, golem_work_run **out, golem_diagnostic *d);
#endif
