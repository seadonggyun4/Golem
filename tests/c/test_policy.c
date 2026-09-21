#include "golem/policy.h"
#include "golem/journal.h"
#include "test.h"
#include <string.h>

static int capsule(const golem_policy_spec *permissions, const golem_graph_spec *override,
    golem_work_capsule **out)
{
    golem_graph_spec spec;
    CHECK(golem_stage_graph_default_spec(&spec) == GOLEM_OK);
    if (override != NULL) spec = *override;
    golem_stage_graph *graph = NULL;
    CHECK(golem_stage_graph_create(&spec, &graph) == GOLEM_OK);
    const char *scope[] = {"local"}, *acceptance[] = {"verified"};
    golem_capsule_spec c = {0};
    c.id = "policy-capsule"; c.goal = "Enforce stage permissions";
    c.scope = (golem_string_list){scope, 1}; c.acceptance = (golem_string_list){acceptance, 1}; c.graph = graph;
    memcpy(c.permissions, permissions->permissions, sizeof(c.permissions));
    CHECK(golem_work_capsule_create(&c, out) == GOLEM_OK);
    golem_stage_graph_free(graph); return 0;
}
static golem_policy_spec uniform(golem_autonomy mode)
{
    golem_policy_spec spec = {GOLEM_POLICY_VERSION, {0}};
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) spec.permissions[i] = mode;
    return spec;
}
static int make_run(const char *id, const golem_policy_spec *spec, const golem_graph_spec *override,
    const golem_allocator *allocator, golem_work_run **out)
{
    golem_work_capsule *c = NULL; CHECK(capsule(spec, override, &c) == 0);
    CHECK(golem_work_run_create_with_allocator(id, c, 3, allocator, out, NULL) == GOLEM_OK);
    golem_work_capsule_free(c); return 0;
}
static golem_policy_verdict expected(golem_autonomy mode, golem_effect effect, golem_authorization authorization)
{
    if (mode == GOLEM_AUTONOMY_DENY || effect == GOLEM_EFFECT_UNKNOWN || authorization == GOLEM_AUTHORIZATION_REJECTED)
        return GOLEM_POLICY_DENY;
    if (authorization == GOLEM_AUTHORIZATION_NONE &&
        (effect == GOLEM_EFFECT_EXTERNAL || mode == GOLEM_AUTONOMY_ASK_ALWAYS)) return GOLEM_POLICY_ASK;
    return GOLEM_POLICY_ALLOW;
}
static int matrix(void)
{
    for (int mode = GOLEM_AUTONOMY_DENY; mode <= GOLEM_AUTONOMY_ASK_ALWAYS; ++mode) {
        golem_policy_spec spec = uniform((golem_autonomy)mode);
        golem_policy *policy = NULL;
        CHECK(golem_policy_create(&spec, NULL, &policy, NULL) == GOLEM_OK);
        for (int stage = 0; stage < GOLEM_STAGE_COUNT; ++stage) {
            for (int effect = GOLEM_EFFECT_UNKNOWN; effect <= GOLEM_EFFECT_EXTERNAL; ++effect) {
                for (int auth = GOLEM_AUTHORIZATION_NONE; auth <= GOLEM_AUTHORIZATION_REJECTED; ++auth) {
                    golem_policy_request request = {(golem_stage)stage, (golem_effect)effect, (golem_authorization)auth};
                    golem_policy_decision decision, primitive;
                    CHECK(golem_policy_evaluate(policy, &request, &decision) == GOLEM_OK);
                    CHECK(golem_autonomy_evaluate((golem_autonomy)mode, &request, &primitive) == GOLEM_OK);
                    CHECK(decision.verdict == expected((golem_autonomy)mode, request.effect, request.authorization));
                    CHECK(decision.verdict == primitive.verdict && decision.reason == primitive.reason);
                    CHECK(decision.version == GOLEM_POLICY_VERSION && decision.mode == (golem_autonomy)mode);
                    CHECK(decision.request.stage == request.stage && decision.request.effect == request.effect && decision.request.authorization == request.authorization);
                    CHECK(strcmp(golem_policy_verdict_name(decision.verdict), "unknown") != 0);
                    CHECK(strcmp(golem_policy_reason_name(decision.reason), "unknown") != 0);
                    if (mode == GOLEM_AUTONOMY_DENY) CHECK(decision.reason == GOLEM_POLICY_STAGE_DENIED);
                    else if (effect == GOLEM_EFFECT_UNKNOWN) CHECK(decision.reason == GOLEM_POLICY_EFFECT_UNKNOWN);
                    else if (auth == GOLEM_AUTHORIZATION_REJECTED) CHECK(decision.reason == GOLEM_POLICY_AUTHORIZATION_REJECTED);
                    else if (decision.verdict == GOLEM_POLICY_ASK)
                        CHECK(decision.reason == (mode == GOLEM_AUTONOMY_ASK_ALWAYS ? GOLEM_POLICY_ALWAYS_ASK : GOLEM_POLICY_EXTERNAL_ASK));
                    else CHECK(decision.reason == ((mode == GOLEM_AUTONOMY_ASK_ALWAYS || effect == GOLEM_EFFECT_EXTERNAL) ?
                        GOLEM_POLICY_APPROVED : GOLEM_POLICY_LOCAL_ALLOWED));
                }
            }
        }
        golem_policy_free(policy);
    }
    return 0;
}

static int gates(void)
{
    for (int mode = GOLEM_AUTONOMY_DENY; mode <= GOLEM_AUTONOMY_ASK_ALWAYS; ++mode) {
        golem_policy_spec spec = uniform((golem_autonomy)mode);
        for (int stage = 0; stage < GOLEM_STAGE_COUNT; ++stage) {
            golem_graph_spec graph = {0}; graph.count = 1; graph.order[0] = (golem_stage)stage;
            for (size_t i = 0; i < GOLEM_FAILURE_COUNT; ++i) graph.reentry[i] = GOLEM_STAGE_NONE;
            for (int effect = GOLEM_EFFECT_UNKNOWN; effect <= GOLEM_EFFECT_EXTERNAL; ++effect) {
                for (int auth = GOLEM_AUTHORIZATION_NONE; auth <= GOLEM_AUTHORIZATION_REJECTED; ++auth) {
                    golem_work_run *run = NULL; CHECK(make_run("gate", &spec, &graph, NULL, &run) == 0);
                    golem_stage_permission_request request;
                    CHECK(golem_work_run_permission_request(run, (golem_effect)effect, &request, NULL) == GOLEM_OK);
                    CHECK(request.stage == (golem_stage)stage && request.sequence == 1 && request.attempt == 1);
                    CHECK(request.authorization == GOLEM_AUTHORIZATION_NONE && strcmp(request.run_id, "gate") == 0);
                    request.authorization = (golem_authorization)auth;
                    golem_stage_snapshot snapshot = {GOLEM_STAGE_NONE, GOLEM_STAGE_PENDING, GOLEM_FAILURE_NONE, 999, 999};
                    golem_policy_decision decision; golem_diagnostic d;
                    golem_policy_verdict verdict = expected((golem_autonomy)mode, request.effect, request.authorization);
                    golem_status want = verdict == GOLEM_POLICY_ALLOW ? GOLEM_OK :
                        verdict == GOLEM_POLICY_ASK ? GOLEM_ERR_APPROVAL_REQUIRED : GOLEM_ERR_POLICY_DENIED;
                    CHECK(golem_work_run_begin_authorized(run, &request, &snapshot, &decision, &d) == want);
                    CHECK(d.status == want && decision.verdict == verdict);
                    uint32_t attempts; golem_work_snapshot work;
                    CHECK(golem_work_run_attempts_get(run, (golem_stage)stage, &attempts) == GOLEM_OK);
                    CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK);
                    if (verdict == GOLEM_POLICY_ALLOW) {
                        CHECK(snapshot.stage == (golem_stage)stage && snapshot.attempt == 1 && snapshot.sequence == 1);
                        CHECK(attempts == 1 && work.status == GOLEM_WORK_RUNNING);
                    } else {
                        CHECK(snapshot.attempt == 999 && snapshot.sequence == 999 && snapshot.stage == GOLEM_STAGE_NONE);
                        CHECK(attempts == 0 && work.status == GOLEM_WORK_READY && golem_work_run_stage_borrow(run) == NULL);
                        CHECK(golem_work_run_begin_authorized(run, &request, &snapshot, &decision, NULL) == want);
                    }
                    golem_work_run_free(run);
                    if (effect != GOLEM_EFFECT_UNKNOWN && auth != GOLEM_AUTHORIZATION_REJECTED) {
                        CHECK(make_run("legacy", &spec, &graph, NULL, &run) == 0);
                        CHECK(golem_work_run_begin(run, effect == GOLEM_EFFECT_EXTERNAL,
                            auth == GOLEM_AUTHORIZATION_GRANTED, &snapshot) ==
                            (verdict == GOLEM_POLICY_ALLOW ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED));
                        golem_work_run_free(run);
                    }
                }
            }
        }
    }
    return 0;
}

static int immutable(void)
{
    golem_policy_spec spec;
    CHECK(golem_policy_spec_init(&spec) == GOLEM_OK);
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) CHECK(spec.permissions[i] == GOLEM_AUTONOMY_DENY);
    spec.permissions[GOLEM_STAGE_DEVELOPMENT] = GOLEM_AUTONOMY_AUTO_LOCAL;
    spec.permissions[GOLEM_STAGE_UX] = GOLEM_AUTONOMY_ASK_ALWAYS;
    spec.permissions[GOLEM_STAGE_PUBLISHING] = GOLEM_AUTONOMY_ASK_ON_EXTERNAL_EFFECT;
    golem_policy *policy = NULL;
    CHECK(golem_policy_create(&spec, NULL, &policy, NULL) == GOLEM_OK);
    golem_graph_spec graph = {0}; graph.count = 4;
    graph.order[0] = GOLEM_STAGE_DEVELOPMENT; graph.order[1] = GOLEM_STAGE_UX;
    graph.order[2] = GOLEM_STAGE_PUBLISHING; graph.order[3] = GOLEM_STAGE_QA;
    for (size_t i = 0; i < GOLEM_FAILURE_COUNT; ++i) graph.reentry[i] = GOLEM_STAGE_NONE;
    golem_work_run *run = NULL; CHECK(make_run("mixed", &spec, &graph, NULL, &run) == 0);
    spec = uniform(GOLEM_AUTONOMY_AUTO_LOCAL);
    golem_policy_spec copy;
    CHECK(golem_policy_spec_get(policy, &copy) == GOLEM_OK && copy.permissions[GOLEM_STAGE_QA] == GOLEM_AUTONOMY_DENY);
    copy.permissions[GOLEM_STAGE_QA] = GOLEM_AUTONOMY_AUTO_LOCAL;
    golem_policy_request check = {GOLEM_STAGE_QA, GOLEM_EFFECT_LOCAL, GOLEM_AUTHORIZATION_GRANTED};
    golem_policy_decision decision;
    CHECK(golem_policy_evaluate(policy, &check, &decision) == GOLEM_OK && decision.verdict == GOLEM_POLICY_DENY);
    golem_policy_free(policy);
    for (size_t i = 0; i < graph.count; ++i) {
        golem_stage_permission_request r;
        CHECK(golem_work_run_permission_request(run, GOLEM_EFFECT_LOCAL, &r, NULL) == GOLEM_OK);
        CHECK(r.stage == graph.order[i]);
        golem_stage_snapshot snapshot;
        golem_status status = golem_work_run_begin_authorized(run, &r, &snapshot, &decision, NULL);
        if (i == 1) {
            CHECK(status == GOLEM_ERR_APPROVAL_REQUIRED);
            r.authorization = GOLEM_AUTHORIZATION_GRANTED;
            status = golem_work_run_begin_authorized(run, &r, &snapshot, &decision, NULL);
        }
        if (i == 3) {
            CHECK(status == GOLEM_ERR_POLICY_DENIED && decision.mode == GOLEM_AUTONOMY_DENY);
            CHECK(golem_work_run_begin(run, false, true, &snapshot) == GOLEM_ERR_POLICY_DENIED);
        } else {
            CHECK(status == GOLEM_OK);
            CHECK(golem_work_run_finish(run, snapshot.sequence, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_OK);
        }
    }
    CHECK(golem_work_run_cancel(run) == GOLEM_OK); golem_work_run_free(run); return 0;
}

static int scope(void)
{
    golem_policy_spec spec = uniform(GOLEM_AUTONOMY_ASK_ALWAYS);
    golem_work_run *run = NULL; CHECK(make_run("scope", &spec, NULL, NULL, &run) == 0);
    golem_stage_permission_request r;
    CHECK(golem_work_run_permission_request(run, GOLEM_EFFECT_EXTERNAL, &r, NULL) == GOLEM_OK);
    r.authorization = GOLEM_AUTHORIZATION_GRANTED;
    golem_policy_decision decision = {0}; decision.version = 999;
    golem_stage_snapshot snapshot = {0}; snapshot.sequence = 999;
    for (size_t i = 0; i < 4; ++i) {
        golem_stage_permission_request wrong = r;
        if (i == 0) wrong.run_id = "other";
        if (i == 1) wrong.stage = GOLEM_STAGE_UX;
        if (i == 2) wrong.sequence = 2;
        if (i == 3) wrong.attempt = 2;
        CHECK(golem_work_run_begin_authorized(run, &wrong, &snapshot, &decision, NULL) ==
            (i == 0 ? GOLEM_ERR_IDENTITY_MISMATCH : GOLEM_ERR_STALE_RESULT));
        CHECK(snapshot.sequence == 999 && decision.version == 999);
    }
    CHECK(golem_work_run_begin_authorized(run, &r, &snapshot, &decision, NULL) == GOLEM_OK);
    CHECK(snapshot.sequence == 1 && snapshot.attempt == 1 && decision.verdict == GOLEM_POLICY_ALLOW);
    CHECK(golem_work_run_begin_authorized(run, &r, &snapshot, &decision, NULL) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_work_run_finish(run, 1, GOLEM_STAGE_FAILED, GOLEM_FAILURE_TIMEOUT, false) == GOLEM_OK);
    CHECK(golem_work_run_reenter(run) == GOLEM_OK);
    CHECK(golem_work_run_begin_authorized(run, &r, &snapshot, &decision, NULL) == GOLEM_ERR_STALE_RESULT);
    CHECK(golem_work_run_permission_request(run, GOLEM_EFFECT_EXTERNAL, &r, NULL) == GOLEM_OK);
    CHECK(r.sequence == 2 && r.attempt == 2 && r.authorization == GOLEM_AUTHORIZATION_NONE);
    CHECK(golem_work_run_begin_authorized(run, &r, &snapshot, &decision, NULL) == GOLEM_ERR_APPROVAL_REQUIRED);
    CHECK(snapshot.sequence == 1 && decision.verdict == GOLEM_POLICY_ASK);
    r.authorization = GOLEM_AUTHORIZATION_REJECTED;
    CHECK(golem_work_run_begin_authorized(run, &r, &snapshot, &decision, NULL) == GOLEM_ERR_POLICY_DENIED);
    r.authorization = GOLEM_AUTHORIZATION_GRANTED;
    CHECK(golem_work_run_begin_authorized(run, &r, &snapshot, &decision, NULL) == GOLEM_OK && snapshot.attempt == 2);
    CHECK(golem_work_run_cancel(run) == GOLEM_OK);
    CHECK(golem_work_run_permission_request(run, GOLEM_EFFECT_LOCAL, &r, NULL) == GOLEM_ERR_INVALID_STATE);
    golem_work_run_free(run); return 0;
}

static int replay(void)
{
    for (int mode = GOLEM_AUTONOMY_DENY; mode <= GOLEM_AUTONOMY_ASK_ALWAYS; ++mode) {
        golem_policy_spec spec = uniform((golem_autonomy)mode);
        golem_work_capsule *c = NULL; CHECK(capsule(&spec, NULL, &c) == 0);
        uint8_t payload[2048], log[4096]; size_t length, first, second;
        CHECK(golem_journal_created_encode("replay-policy", c, 3, payload, sizeof(payload), &length, NULL) == GOLEM_OK);
        CHECK(golem_journal_record_encode(GOLEM_JOURNAL_CREATED, 1, (golem_bytes){payload, length}, log, sizeof(log), &first, NULL) == GOLEM_OK);
        golem_work_capsule_free(c);
        for (int external = 0; external <= 1; ++external) {
            for (int authorized = 0; authorized <= 1; ++authorized) {
                golem_journal_event event = {0};
                event.type = GOLEM_JOURNAL_STARTED; event.stage = GOLEM_STAGE_PLANNING;
                event.attempt = 1; event.attempt_sequence = 1; event.outcome = GOLEM_STAGE_RUNNING;
                event.external_effect = external != 0; event.authorized = authorized != 0;
                CHECK(golem_journal_event_encode(&event, payload, sizeof(payload), &length, NULL) == GOLEM_OK);
                CHECK(golem_journal_record_encode(event.type, 2, (golem_bytes){payload, length}, log + first,
                    sizeof(log) - first, &second, NULL) == GOLEM_OK);
                golem_work_run *restored = NULL;
                golem_policy_verdict verdict = expected((golem_autonomy)mode,
                    external ? GOLEM_EFFECT_EXTERNAL : GOLEM_EFFECT_LOCAL,
                    authorized ? GOLEM_AUTHORIZATION_GRANTED : GOLEM_AUTHORIZATION_NONE);
                CHECK(golem_journal_replay((golem_bytes){log, first + second}, NULL, &restored, NULL) ==
                    (verdict == GOLEM_POLICY_ALLOW ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED));
                if (verdict != GOLEM_POLICY_ALLOW) CHECK(restored == NULL);
                golem_work_run_free(restored);
            }
        }
        golem_work_run *restored = NULL;
        CHECK(golem_journal_replay((golem_bytes){log, first}, NULL, &restored, NULL) == GOLEM_OK);
        golem_stage_permission_request r; golem_stage_snapshot stage; golem_policy_decision decision;
        CHECK(golem_work_run_permission_request(restored, GOLEM_EFFECT_EXTERNAL, &r, NULL) == GOLEM_OK);
        CHECK(golem_work_run_begin_authorized(restored, &r, &stage, &decision, NULL) ==
            (mode == GOLEM_AUTONOMY_DENY ? GOLEM_ERR_POLICY_DENIED : GOLEM_ERR_APPROVAL_REQUIRED));
        CHECK(decision.mode == (golem_autonomy)mode); golem_work_run_free(restored);
    }
    return 0;
}

typedef struct tracker { bool fail; size_t calls, live; } tracker;
static void *allocate(void *context, size_t size)
{
    tracker *t = context; ++t->calls;
    if (t->fail) return NULL;
    void *p = malloc(size); if (p != NULL) ++t->live; return p;
}
static void deallocate(void *context, void *p) { tracker *t = context; --t->live; free(p); }
static int ownership(void)
{
    tracker t = {true, 0, 0}; golem_allocator a = {&t, allocate, deallocate};
    golem_policy_spec spec = uniform(GOLEM_AUTONOMY_AUTO_LOCAL); golem_policy *policy = NULL;
    CHECK(golem_policy_create(&spec, &a, &policy, NULL) == GOLEM_ERR_OUT_OF_MEMORY && policy == NULL && t.live == 0);
    t.fail = false;
    CHECK(golem_policy_create(&spec, &a, &policy, NULL) == GOLEM_OK && t.live == 1);
    golem_work_run *run = NULL; CHECK(make_run("memory", &spec, NULL, &a, &run) == 0);
    size_t calls = t.calls;
    t.fail = true; a.allocate = NULL;
    golem_policy_request r = {GOLEM_STAGE_PLANNING, GOLEM_EFFECT_LOCAL, GOLEM_AUTHORIZATION_NONE};
    golem_policy_decision decision;
    CHECK(golem_policy_evaluate(policy, &r, &decision) == GOLEM_OK && decision.verdict == GOLEM_POLICY_ALLOW);
    golem_stage_permission_request request; golem_stage_snapshot snapshot;
    CHECK(golem_work_run_permission_request(run, GOLEM_EFFECT_LOCAL, &request, NULL) == GOLEM_OK);
    CHECK(golem_work_run_begin_authorized(run, &request, &snapshot, &decision, NULL) == GOLEM_OK);
    CHECK(t.calls == calls);
    golem_policy_free(policy); golem_work_run_free(run); CHECK(t.live == 0);
    golem_policy_free(NULL); return 0;
}

static int invalid(void)
{
    golem_policy_spec spec; CHECK(golem_policy_spec_init(&spec) == GOLEM_OK);
    CHECK(golem_policy_spec_init(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_policy_spec_validate(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_policy *policy = NULL;
    spec.version = 0;
    CHECK(golem_policy_create(&spec, NULL, &policy, NULL) == GOLEM_ERR_UNSUPPORTED_VERSION && policy == NULL);
    spec.version = GOLEM_POLICY_VERSION;
    spec.permissions[GOLEM_STAGE_AUDIT] = (golem_autonomy)-1;
    CHECK(golem_policy_spec_validate(&spec) == GOLEM_ERR_INVALID_ARGUMENT);
    spec.permissions[GOLEM_STAGE_AUDIT] = GOLEM_AUTONOMY_DENY;
    CHECK(golem_policy_create(&spec, NULL, &policy, NULL) == GOLEM_OK);
    golem_policy_request r = {GOLEM_STAGE_NONE, GOLEM_EFFECT_LOCAL, GOLEM_AUTHORIZATION_NONE};
    golem_policy_decision decision = {0}; decision.version = 999;
    CHECK(golem_policy_evaluate(policy, &r, &decision) == GOLEM_ERR_INVALID_ARGUMENT && decision.version == 999);
    r.stage = GOLEM_STAGE_PLANNING; r.effect = (golem_effect)99;
    CHECK(golem_policy_evaluate(policy, &r, &decision) == GOLEM_ERR_INVALID_ARGUMENT && decision.version == 999);
    r.effect = GOLEM_EFFECT_LOCAL; r.authorization = (golem_authorization)-1;
    CHECK(golem_policy_evaluate(policy, &r, &decision) == GOLEM_ERR_INVALID_ARGUMENT && decision.version == 999);
    r.authorization = GOLEM_AUTHORIZATION_NONE;
    CHECK(golem_autonomy_evaluate((golem_autonomy)99, &r, &decision) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_policy_evaluate(NULL, &r, &decision) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_policy_evaluate(policy, NULL, &decision) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_policy_evaluate(policy, &r, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_policy_spec_get(policy, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(strcmp(golem_policy_verdict_name((golem_policy_verdict)99), "unknown") == 0);
    CHECK(strcmp(golem_policy_reason_name((golem_policy_reason)-1), "unknown") == 0);
    golem_work_run *run = NULL; CHECK(make_run("invalid", &spec, NULL, NULL, &run) == 0);
    golem_stage_permission_request request;
    CHECK(golem_work_run_permission_request(run, GOLEM_EFFECT_LOCAL, &request, NULL) == GOLEM_OK);
    golem_stage_snapshot snapshot = {0}; snapshot.sequence = 999;
    request.authorization = (golem_authorization)99;
    CHECK(golem_work_run_begin_authorized(run, &request, &snapshot, &decision, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(snapshot.sequence == 999 && decision.version == 999);
    CHECK(golem_work_run_permission_request(NULL, GOLEM_EFFECT_LOCAL, &request, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_begin_authorized(run, NULL, &snapshot, &decision, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_begin_authorized(NULL, &request, &snapshot, &decision, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_begin_authorized(run, &request, NULL, &decision, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_work_run_free(run); golem_policy_free(policy); return 0;
}

int main(int argc, char **argv)
{
    CHECK(argc == 2);
    if (strcmp(argv[1], "matrix") == 0) return matrix();
    if (strcmp(argv[1], "gates") == 0) return gates();
    if (strcmp(argv[1], "immutable") == 0) return immutable();
    if (strcmp(argv[1], "scope") == 0) return scope();
    if (strcmp(argv[1], "replay") == 0) return replay();
    if (strcmp(argv[1], "ownership") == 0) return ownership();
    if (strcmp(argv[1], "invalid") == 0) return invalid();
    return EXIT_FAILURE;
}
