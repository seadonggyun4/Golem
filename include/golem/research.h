#ifndef GOLEM_RESEARCH_H
#define GOLEM_RESEARCH_H
#include "golem/execution.h"
#ifdef __cplusplus
extern "C" {
#endif
#define GOLEM_RESEARCH_VERSION 1u
#define GOLEM_RESEARCH_MAX_JSON 65536u
#define GOLEM_RESEARCH_MAX_EVENTS 256u
#define GOLEM_RESEARCH_MAX_REFS 32u
#define GOLEM_RESEARCH_BUNDLE_MAX_JSON 4194304u
#define GOLEM_RESEARCH_REDACTION_MAX_JSON 4096u

/* Schema-1 requests: declarations and optional outcome enrollment/adjudication.
 * Inputs/diagnostic borrowed for the call. Replies own malloc storage; release
 * with golem_execution_reply_free. Outputs unchanged on failure. Serialize calls
 * on the existing Work handle. See docs/research.md for the exact JSON contract.
 * validate is structural only. call requires a writable Work and its permission.
 * Keys are unique within the Work's research namespace; parsed JSON equality
 * (member order/whitespace independent) returns the original receipt on retry.
 * IDs are immutable. All referenced evidence must exist in this Work's CAS.
 * Actor/timestamps/counts/classification are declared observations, not verified
 * identity, trusted time, derived metrics or independently adjudicated outcomes.
 * An uncertain commit poisons the handle; close/reopen and retry the SAME key.
 * No provider dispatch, lease grants, QA, network, redaction or export occurs. */
/* outcome-enroll adds an immutable Work completion obligation. adjudicate derives
 * a bounded predicate from declared observations and a runtime QA receipt; it
 * never establishes independent review or DONE. See docs/outcome.md. New
 * outcome journal events use version 2; old version-1 records remain readable. */
golem_status golem_research_validate(golem_bytes request, golem_diagnostic *diagnostic);
golem_status golem_research_call(golem_document_store *store, golem_bytes request,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
/* Read-only replay views. sequence is the research ordinal (1..256), not the
 * global Work event sequence. Missing sequences return NOT_FOUND. report is
 * escaped Markdown, private by default; no filesystem projection is created. */
golem_status golem_research_inspect(golem_document_store *store, uint32_t sequence,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
golem_status golem_research_report(golem_document_store *store, uint32_t sequence,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
golem_status golem_research_status(golem_document_store *store,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
/* Read-only derived metrics over this handle's fully replayed Work prefix.
 * case_id is borrowed, NULL selects all cases; an empty/invalid ID is rejected
 * and an unknown ID returns NOT_FOUND. No live source probes or journal writes.
 * JSON and Markdown own reply storage; free with golem_execution_reply_free.
 * Outputs remain unchanged on failure. A metric is NOT completion authority.
 * Unknown observations are not zeros. See docs/metrics.md for denominators,
 * declared-input limitations and the versioned deterministic projection rule. */
golem_status golem_research_metrics(golem_document_store *store, const char *case_id,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
golem_status golem_research_metrics_report(golem_document_store *store, const char *case_id,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
/* Cohort IDs and all inputs borrowed. Read-only deterministic JSON comparison;
 * the reply owns malloc storage, freed with golem_execution_reply_free.
 * Output unchanged on failure. NOT completion or causal-effect authority.
 * cohort-create/cohort-observe use research_call and schema-2 journal events.
 * See docs/cohort.md for arm definitions and declared-measurement limitations. */
golem_status golem_research_compare(golem_document_store *store, const char *cohort_id,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
/* Read-only case-scoped derived export, never raw CAS/document copying.
 * Inputs borrowed. Output owns malloc memory, freed by golem_execution_reply_free;
 * unchanged on failure. Policy is strict schema-1 MINIMAL or explicit LINKABLE.
 * Returned JSON contains a fixed map of UTF-8 filenames to content strings.
 * No filesystem writes/network/publication. Serialize access to the Work handle.
 * All bundles require human privacy review, even when source hashes are withheld.
 * verify checks file inventory/checksums, NOT authenticity, privacy or acceptance.
 * See docs/bundle.md for disclosure scope, resource bounds and omissions. */
golem_status golem_research_redaction_validate(golem_bytes policy, golem_diagnostic *diagnostic);
golem_status golem_research_bundle(golem_document_store *store, const char *case_id,
    golem_bytes policy, golem_execution_reply *out, golem_diagnostic *diagnostic);
golem_status golem_research_bundle_verify(golem_bytes bundle, golem_diagnostic *diagnostic);
typedef enum golem_research_export_format {
    GOLEM_RESEARCH_EXPORT_OTLP_LOGS = 1,
    GOLEM_RESEARCH_EXPORT_PROV_JSON = 2
} golem_research_export_format;
/* Read-only schema-1 derived observability export over the 29E redacted bundle.
 * Inputs borrowed; output owns malloc storage, free with execution_reply_free.
 * Output unchanged on error. Same policy, limits and handle serialization as
 * bundle. No network, filesystem writes, timestamps, span identity or completion
 * authority. OTLP is an ExportLogsServiceRequest JSON snapshot, not live spans.
 * PROV-JSON describes derivation, not authenticated actors or causal effects.
 * See docs/observability.md; all output requires private disclosure review. */
golem_status golem_research_observability(golem_document_store *store, const char *case_id,
    golem_bytes policy, golem_research_export_format format,
    golem_execution_reply *out, golem_diagnostic *diagnostic);
#ifdef __cplusplus
}
#endif
#endif
