#include "golem/error.h"

const char *golem_status_string(golem_status status)
{
    switch (status) {
    case GOLEM_OK: return "ok";
    case GOLEM_ERR_INVALID_ARGUMENT: return "invalid argument";
    case GOLEM_ERR_OUT_OF_MEMORY: return "out of memory";
    case GOLEM_ERR_PARSE: return "parse error";
    case GOLEM_ERR_POLICY_DENIED: return "policy denied";
    case GOLEM_ERR_IO: return "I/O error";
    case GOLEM_ERR_CORRUPT_JOURNAL: return "corrupt journal";
    case GOLEM_ERR_INVALID_STATE: return "invalid state transition";
    case GOLEM_ERR_INVALID_GRAPH: return "invalid stage graph";
    case GOLEM_ERR_NO_REENTRY: return "no valid reentry";
    case GOLEM_ERR_ATTEMPT_LIMIT: return "attempt limit reached";
    case GOLEM_ERR_STALE_RESULT: return "stale stage result";
    case GOLEM_ERR_REQUIREMENTS_UNMET: return "stage requirements unmet";
    case GOLEM_ERR_BUFFER_TOO_SMALL: return "buffer too small";
    case GOLEM_ERR_OVERFLOW: return "size overflow";
    case GOLEM_ERR_UNSUPPORTED_VERSION: return "unsupported schema version";
    case GOLEM_ERR_TRUNCATED_JOURNAL: return "truncated journal";
    case GOLEM_ERR_JOURNAL_BUSY: return "journal writer busy";
    case GOLEM_ERR_MISSING_RECORD: return "missing journal record";
    case GOLEM_ERR_REPLAY_MISMATCH: return "replay identity or endpoint mismatch";
    case GOLEM_ERR_INCOMPLETE_WORK: return "incomplete work";
    case GOLEM_ERR_NOT_FOUND: return "not found";
    case GOLEM_ERR_DIGEST_MISMATCH: return "digest mismatch";
    case GOLEM_ERR_SIZE_MISMATCH: return "size mismatch";
    case GOLEM_ERR_CRYPTO: return "cryptographic backend failure";
    case GOLEM_ERR_IDENTITY_MISMATCH: return "run identity mismatch";
    case GOLEM_ERR_APPROVAL_REQUIRED: return "approval required";
    case GOLEM_ERR_BUDGET_EXHAUSTED: return "budget exhausted";
    case GOLEM_ERR_COST_INCOMPLETE: return "cost accounting incomplete";
    case GOLEM_ERR_COST_CAPACITY: return "cost ledger capacity exhausted";
    case GOLEM_ERR_OPTIMIZATION_REJECTED: return "optimization rejected";
    case GOLEM_ERR_STALE_LEASE: return "stale lease";
    case GOLEM_ERR_LEASE_BUSY: return "lease busy";
    default: return "unknown status";
    }
}
