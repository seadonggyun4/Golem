#ifndef GOLEM_INTENT_SCHEMA_INTERNAL_H
#define GOLEM_INTENT_SCHEMA_INTERNAL_H

#include "golem/evidence.h"

/* P1 preparation only: private, pure validators, not an installed API or an
 * authority store. No issuer, activation, or gate verdict.
 * Borrowed immutable inputs; independent outputs change only on success.
 * Existing raw CAS SHA-256 is used solely to verify supplied source bytes. */
#define GI_CONTROL_MAX (256u * 1024u)
#define GI_SOURCE_MAX (16u * 1024u * 1024u)
#define GI_BASELINE_SOURCE_MAX (64u * 1024u * 1024u)
#define GI_REQUIREMENT_MAX 1024u
#define GI_TRACE_NODE_MAX 4096u
#define GI_TRACE_EDGE_MAX 16384u
#define GI_PARENT_MAX 64u
#define GI_OBLIGATION_MAX 256u
#define GI_OBSERVATION_MAX 256u
#define GI_DISPATCH_MAX (32u * 1024u * 1024u)

typedef struct gi_span { size_t start, end; } gi_span;
typedef enum gi_classification {
    GI_REQUIREMENT, GI_CONSTRAINT, GI_CONTEXT, GI_EXPLICIT_NON_GOAL,
    GI_NON_NORMATIVE, GI_QUESTION_REQUIRED
} gi_classification;
typedef struct gi_coverage_row {
    gi_span span;
    gi_classification classification;
} gi_coverage_row;
typedef struct gi_coverage_result {
    size_t designated_bytes;
    bool has_questions;
    bool classification_review_required;
} gi_coverage_result;
typedef struct gi_source_result {
    golem_digest body_cas;
    size_t byte_length;
    size_t designated_bytes;
} gi_source_result;
typedef struct gi_capacity {
    size_t control_bytes, source_bytes, baseline_source_bytes, requirements;
    size_t trace_nodes, trace_edges, node_parents, unresolved, observations, dispatch_bytes;
} gi_capacity;

golem_status gi_capacity_validate(const gi_capacity *capacity, golem_diagnostic *diagnostic);
golem_status gi_text_validate(golem_bytes text, golem_diagnostic *diagnostic);
golem_status gi_span_validate(golem_bytes text, gi_span span, golem_diagnostic *diagnostic);
/* Counts every supplied source, including repeated bodies. The caller still
 * owns manifest completeness/membership; this is not a baseline validator. */
golem_status gi_source_set_validate(const golem_bytes *sources, size_t count,
    size_t *total_bytes, golem_diagnostic *diagnostic);
/* Rows may overlap and arrive unordered. Every row must be inside the union of
 * designated ranges, and their union must cover it exactly. This checks neither
 * classification truth nor rationale/reviewer provenance. Never returns PASS. */
golem_status gi_coverage_validate(golem_bytes text, const gi_span *designated, size_t count,
    const gi_coverage_row *rows, size_t row_count, gi_coverage_result *out,
    golem_diagnostic *diagnostic);
/* Closed source shape from the supplied design. Unknown/duplicate members and a
 * root baseline_digest are rejected. Assertion/decision refs remain UNVERIFIED.
 * Metadata is never reserialized or assigned an authoritative object identity. */
golem_status gi_source_validate(golem_bytes control, golem_bytes text,
    gi_source_result *out, golem_diagnostic *diagnostic);
/* Approved ADR-D08 primitive. Explicit source.v1 and quota-preparation.v1 registry.
 * SHA256(schema ASCII + NUL || uint64_le(exact JSON length) || exact JSON).
 * This checks JSON/scalar validity and registered schema, not its full shape or
 * provenance. A digest is byte identity, never a receipt or acceptance verdict. */
golem_status gi_domain_digest(golem_bytes control, golem_digest *out, golem_diagnostic *diagnostic);
/* Convenience binding: validate exact source metadata/body before identity.
 * Still no trusted adoption/issuer decision. No side effects or CAS publication. */
golem_status gi_source_identity(golem_bytes control, golem_bytes text,
    golem_digest *out, golem_diagnostic *diagnostic);

#endif
