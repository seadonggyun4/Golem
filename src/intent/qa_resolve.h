#ifndef GOLEM_INTENT_QA_RESOLVE_H
#define GOLEM_INTENT_QA_RESOLVE_H
#include "qa_paths.h"
#include "review_host.h"
/* Explicit local referents only; no path lookup/network/reference expansion.
 * Every provided object is bounded and used; hashes alone never resolve refs. */
golem_status gi_qa_paths_resolve(const gi_qa_paths_inputs *,const golem_bytes *,size_t,
    gi_review_host *,gi_qa_paths_result *,golem_diagnostic *);
#endif
