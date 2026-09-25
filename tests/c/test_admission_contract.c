#include "../../src/daemon/admission_internal.h"
#include "test.h"
#include <string.h>

/* Independent specification table, not derived from ga_apply/ga_live.
 * Columns: bind, start, run, cancel, settle, release. Zero means rejection.
 * A binding and a nonzero termination proof are supplied in this matrix. */
static const unsigned transitions[9][6] = {
    {0, 0, 0, 9, 0, 0},
    {2, 3, 0, 9, 0, 0},
    {0, 0, 4, 5, 7, 0},
    {0, 0, 0, 5, 7, 0},
    {0, 0, 0, 5, 7, 0},
    {0, 0, 0, 0, 7, 0},
    {0, 0, 0, 0, 7, 8},
    {0, 0, 0, 0, 8, 8},
    {0, 0, 0, 9, 0, 0},
};

int main(void)
{
    ga_model *m = calloc(1, sizeof(*m)), *before = calloc(1, sizeof(*before));
    CHECK(m && before);
    size_t cases = 0;
    for (unsigned state = 1; state <= 9; ++state) {
        for (unsigned column = 0; column < 6; ++column) {
            /* Current token, wrong epoch, wrong instance, wrong boot. */
            for (unsigned fence = 0; fence < 4; ++fence) {
                memset(m, 0, sizeof(*m));
                m->namespace_id.bytes[0] = 1;
                m->epoch = 1;
                m->instance[0] = 1;
                m->boot.bytes[0] = 1;
                m->count = 1;
                m->tickets[0].state = (golem_admission_state)state;
                m->tickets[0].binding_receipt.bytes[0] = 2;
                if (state == 7 || state == 8)
                    m->tickets[0].termination_receipt.bytes[0] = 2;
                ga_event e = {.operation = (ga_operation)(GA_BIND + column),
                              .ticket = 1, .epoch = 1, .nonce = {1},
                              .boot = {{1}}, .proof = {{2}}};
                if (fence == 1) ++e.epoch;
                if (fence == 2) ++e.nonce[0];
                if (fence == 3) ++e.boot.bytes[0];
                *before = *m;
                golem_status st = ga_apply(m, &e);
                unsigned expected = fence ? 0 : transitions[state - 1][column];
                CHECK((st == GOLEM_OK) == (expected != 0));
                if (expected)
                    CHECK(m->tickets[0].state == (golem_admission_state)expected);
                else
                    CHECK(!memcmp(m, before, sizeof(*m)));
                if (fence)
                    CHECK(st == GOLEM_ERR_STALE_LEASE);
                ++cases;
            }
        }
    }
    CHECK(cases == 216);
    free(before);
    free(m);
    return 0;
}
