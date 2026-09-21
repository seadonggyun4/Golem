#ifndef GOLEM_REPLAY_INTERNAL_H
#define GOLEM_REPLAY_INTERNAL_H
#include "golem/replay.h"

golem_status golem_replay_apply(golem_work_run *run,
    const golem_journal_event *event);
void golem_replay_report_fill(const golem_work_run *run,
    uint64_t records, uint64_t bytes, golem_replay_report *out);
#endif
