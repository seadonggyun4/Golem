#include "golem/optimization.h"

golem_status golem_cache_break_even(const golem_cache_model *m, golem_cache_result *out)
{
    if (m == NULL || out == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if ((m->uncached_read_nano != 0 && m->expected_reads > UINT64_MAX / m->uncached_read_nano) ||
        (m->cached_read_nano != 0 && m->expected_reads > (UINT64_MAX - m->setup_nano) / m->cached_read_nano))
        return GOLEM_ERR_OVERFLOW;
    golem_cache_result r = {0};
    r.uncached_nano = m->expected_reads * m->uncached_read_nano;
    r.cached_nano = m->setup_nano + m->expected_reads * m->cached_read_nano;
    if (m->uncached_read_nano > m->cached_read_nano) {
        uint64_t quotient = m->setup_nano / (m->uncached_read_nano - m->cached_read_nano);
        if (quotient != UINT64_MAX) r.break_even_reads = quotient + 1;
    }
    r.profitable = r.uncached_nano > r.cached_nano;
    if (r.profitable) r.savings_nano = r.uncached_nano - r.cached_nano;
    *out = r; return GOLEM_OK;
}
