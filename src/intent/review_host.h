#ifndef GOLEM_INTENT_REVIEW_HOST_H
#define GOLEM_INTENT_REVIEW_HOST_H
#include "review.h"

/* Owner-only exact-file adapter, LOCAL_COOPERATIVE. The host supplies pins
 * selected outside model input. No credential issuance or generic MCP action.
 * observe must revalidate D01 registration/revocation, owner-private file pins,
 * and clock on each call. It observes current state; it does not decide grants. */
typedef golem_status (*gi_review_host_observe)(void *, golem_digest *registration,
                                               golem_digest *policy, golem_digest *bundle,
                                               uint64_t *unix_seconds);
typedef struct gi_review_host gi_review_host;
golem_status gi_review_host_open(golem_bytes policy, const golem_digest *policy_pin,
                                 golem_bytes bundle, const golem_digest *bundle_pin,
                                 golem_bytes control, const golem_digest *registration_pin,
                                 gi_review_host_observe, void *, gi_review_host **);
void gi_review_host_close(gi_review_host *);
/* Concrete callbacks for gi_review_publish/apply. All permission/role/purpose/
 * scope/evidence comparisons are native. Context is an opened host, not JSON. */
golem_status gi_review_host_guard(void *);
golem_status gi_review_host_authorize(void *, gi_review_purpose, const golem_digest *,
                                      const golem_digest *, const char *, const char *,
                                      const char *, const char *);
/* Exact selected command is retained by the host, not replaced by caller. */
golem_status gi_review_host_publish(gi_review_host *, gi_journal *,
                                    const golem_digest *baseline_operation,
                                    const golem_digest *baseline_request,
                                    const golem_digest *baseline, const golem_bytes *definitions,
                                    size_t count, const golem_digest *operation, uint64_t sequence,
                                    const golem_digest *head, gi_journal_receipt *);
/* Concrete POSIX observer. Borrowed directory descriptor must remain open under
 * the existing trusted D01 owner lock throughout use. File names are single
 * components, opened afresh without symlink following at every observation.
 * d01_guard must revalidate the selected registration/revocation/current root;
 * it may not grant review rights. No file creation or approval issuance. */
typedef struct gi_review_host_files {
    int directory_fd;
    const char *policy_name, *bundle_name;
    golem_digest registration;
    gi_journal_guard d01_guard;
    void *d01_context;
} gi_review_host_files;
golem_status gi_review_host_observe_files(void *, golem_digest *, golem_digest *, golem_digest *,
                                          uint64_t *);
/* Read-only checks of owner-selected evidence for QC2/QC3, not new actions. */
golem_status gi_review_host_subject(gi_review_host *, const golem_digest *evidence,
                                    const golem_digest *subject, bool owner);
golem_status gi_review_host_stage(gi_review_host *, const golem_digest *evidence, const char *stage,
                                  const char *producer, const char *reviewer,
                                  const golem_digest *input, const golem_digest *definitions);
golem_status gi_review_host_selected(gi_review_host *, golem_bytes control);
golem_status gi_review_host_binding(gi_review_host *, const golem_digest *registration,
                                    const golem_digest *baseline, const golem_digest *policy);
golem_status gi_review_host_activation(gi_review_host *, const golem_digest *decision);
golem_status gi_review_host_qa_result(gi_review_host *, const golem_digest *evidence,
                                      const golem_digest *subject, char status[16]);
#endif
