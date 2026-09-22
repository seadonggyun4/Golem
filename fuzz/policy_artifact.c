#include "golem/policy.h"
#include "check.h"

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    golem_policy_artifact a;
    memset(&a, 0xa5, sizeof(a));
    unsigned char saved[sizeof(a)]; memcpy(saved, &a, sizeof(a));
    golem_status s = golem_policy_artifact_decode((golem_bytes){data, size}, &a);
    if (s != GOLEM_OK) { REQUIRE(memcmp(saved, &a, sizeof(a)) == 0); return 0; }
    uint8_t wire[GOLEM_POLICY_ARTIFACT_SIZE]; size_t n;
    REQUIRE(golem_policy_artifact_encode(&a, wire, sizeof(wire), &n) == GOLEM_OK);
    REQUIRE(n == size && memcmp(wire, data, n) == 0);
    for (int stage = 0; stage < GOLEM_STAGE_COUNT; ++stage) {
        for (int effect = GOLEM_EFFECT_UNKNOWN; effect <= GOLEM_EFFECT_EXTERNAL; ++effect) {
            for (int auth = GOLEM_AUTHORIZATION_NONE; auth <= GOLEM_AUTHORIZATION_REJECTED; ++auth) {
                golem_policy_request r = {(golem_stage)stage, (golem_effect)effect, (golem_authorization)auth};
                golem_policy_decision d;
                REQUIRE(golem_autonomy_evaluate(a.policy.permissions[stage], &r, &d) == GOLEM_OK);
                if (a.policy.permissions[stage] == GOLEM_AUTONOMY_DENY || effect == GOLEM_EFFECT_UNKNOWN ||
                    auth == GOLEM_AUTHORIZATION_REJECTED) REQUIRE(d.verdict == GOLEM_POLICY_DENY);
                if (auth == GOLEM_AUTHORIZATION_NONE && effect == GOLEM_EFFECT_EXTERNAL)
                    REQUIRE(d.verdict != GOLEM_POLICY_ALLOW);
            }
        }
    }
    return 0;
}
