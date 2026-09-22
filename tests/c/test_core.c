#include "golem/core.h"
#include "test.h"
#include <string.h>

static golem_status make_capsule(const golem_graph_spec *graph_spec,
                                     golem_autonomy mode, golem_work_capsule **out)
{
    golem_stage_graph *graph = NULL;
    golem_status status = golem_stage_graph_create(graph_spec, &graph);
    if (status != GOLEM_OK) {
        return status;
    }
    const char *scope[] = {"src"};
    const char *acceptance[] = {"tests pass"};
    const char *artifacts[] = {"patch"};
    const char *gates[] = {"review"};
    golem_capsule_spec spec = {0};
    spec.id = "capsule-1";
    spec.goal = "Complete work";
    spec.scope = (golem_string_list){scope, 1};
    spec.acceptance = (golem_string_list){acceptance, 1};
    spec.expected_artifacts = (golem_string_list){artifacts, 1};
    spec.required_gates = (golem_string_list){gates, 1};
    spec.graph = graph;
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) {
        spec.permissions[i] = mode;
    }
    status = golem_work_capsule_create(&spec, out);
    golem_stage_graph_free(graph);
    return status;
}

static golem_status make_run(const golem_graph_spec *spec, golem_autonomy mode,
                                 uint32_t limit, golem_work_run **out)
{
    golem_work_capsule *capsule = NULL;
    golem_status status = make_capsule(spec, mode, &capsule);
    if (status == GOLEM_OK) {
        status = golem_work_run_create("run-1", capsule, limit, out);
    }
    golem_work_capsule_free(capsule);
    return status;
}

static int pass_stages(golem_work_run *run, size_t count)
{
    for (size_t i = 0; i < count; ++i) {
        golem_stage_snapshot stage;
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED,
                                       GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    }
    return EXIT_SUCCESS;
}

static int test_graph(void)
{
    golem_graph_spec spec;
    CHECK(golem_stage_graph_default_spec(&spec) == GOLEM_OK);
    golem_stage_graph *graph = NULL;
    CHECK(golem_stage_graph_create(&spec, &graph) == GOLEM_OK);
    for (int from = 0; from < GOLEM_STAGE_COUNT; ++from) {
        for (int to = 0; to <= GOLEM_STAGE_COUNT; ++to) {
            golem_status expected = to == from + 1 ? GOLEM_OK : GOLEM_ERR_INVALID_STATE;
            CHECK(golem_stage_graph_validate_transition(graph, (golem_stage)from,
                                                           (golem_stage)to) == expected);
        }
    }
    CHECK(strcmp(golem_stage_name(GOLEM_STAGE_PUBLISHING), "publishing") == 0);
    CHECK(strcmp(golem_stage_name((golem_stage)-1), "unknown") == 0);
    golem_stage target = GOLEM_STAGE_AUDIT;
    CHECK(golem_stage_graph_next(graph, GOLEM_STAGE_NONE, &target) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(target == GOLEM_STAGE_AUDIT);
    CHECK(golem_stage_graph_reentry(graph, GOLEM_STAGE_PLANNING,
        GOLEM_FAILURE_IMPLEMENTATION_DEFECT, &target) == GOLEM_ERR_NO_REENTRY);
    CHECK(target == GOLEM_STAGE_AUDIT);
    golem_graph_spec copy;
    CHECK(golem_stage_graph_spec_get(graph, &copy) == GOLEM_OK);
    CHECK(copy.count == 6 && copy.order[5] == GOLEM_STAGE_AUDIT);
    golem_stage_graph *unchanged = graph;
    spec.count = 0;
    CHECK(golem_stage_graph_create(&spec, &unchanged) == GOLEM_ERR_INVALID_GRAPH);
    CHECK(unchanged == graph);
    spec.count = GOLEM_STAGE_COUNT + 1;
    CHECK(golem_stage_graph_create(&spec, &unchanged) == GOLEM_ERR_INVALID_GRAPH);
    spec.count = GOLEM_STAGE_COUNT;
    spec.order[1] = spec.order[0];
    CHECK(golem_stage_graph_create(&spec, &unchanged) == GOLEM_ERR_INVALID_GRAPH);
    spec.order[1] = (golem_stage)-1;
    CHECK(golem_stage_graph_create(&spec, &unchanged) == GOLEM_ERR_INVALID_GRAPH);
    spec.order[1] = GOLEM_STAGE_UX;
    spec.reentry[GOLEM_FAILURE_UNKNOWN] = (golem_stage)99;
    CHECK(golem_stage_graph_create(&spec, &unchanged) == GOLEM_ERR_INVALID_GRAPH);
    golem_stage_graph_free(graph);
    return EXIT_SUCCESS;
}

static int test_transitions(void)
{
    const bool allowed[6][6] = {
        {false, true, false, false, true, true},
        {false, false, true, true, true, true},
        {false, false, false, false, false, false},
        {false, false, false, false, false, false},
        {false, false, false, false, false, false},
        {false, false, false, false, false, false}
    };
    for (int from = 0; from < 6; ++from) {
        for (int to = 0; to < 6; ++to) {
            CHECK(golem_stage_transition_validate((golem_stage_status)from,
                (golem_stage_status)to) == (allowed[from][to] ? GOLEM_OK : GOLEM_ERR_INVALID_STATE));
        }
    }
    CHECK(golem_stage_transition_validate((golem_stage_status)-1,
        GOLEM_STAGE_RUNNING) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_stage_transition_validate(GOLEM_STAGE_PENDING,
        (golem_stage_status)99) == GOLEM_ERR_INVALID_ARGUMENT);
    return EXIT_SUCCESS;
}

static int test_capsule(void)
{
    golem_graph_spec spec;
    CHECK(golem_stage_graph_default_spec(&spec) == GOLEM_OK);
    golem_work_capsule *capsule = NULL;
    CHECK(make_capsule(&spec, GOLEM_AUTONOMY_AUTO_LOCAL, &capsule) == GOLEM_OK);
    golem_capsule_spec borrowed;
    CHECK(golem_work_capsule_spec_borrow(capsule, &borrowed) == GOLEM_OK);
    CHECK(strcmp(borrowed.scope.items[0], "src") == 0);
    CHECK(strcmp(borrowed.acceptance.items[0], "tests pass") == 0);
    CHECK(strcmp(borrowed.expected_artifacts.items[0], "patch") == 0);
    CHECK(strcmp(borrowed.required_gates.items[0], "review") == 0);
    char goal[] = "mutable goal";
    borrowed.goal = goal;
    golem_work_capsule *copy = NULL;
    CHECK(golem_work_capsule_create(&borrowed, &copy) == GOLEM_OK);
    goal[0] = 'X';
    golem_work_capsule_free(capsule);
    CHECK(golem_work_capsule_spec_borrow(copy, &borrowed) == GOLEM_OK);
    CHECK(strcmp(borrowed.goal, "mutable goal") == 0);
    CHECK(strcmp(borrowed.scope.items[0], "src") == 0);
    golem_work_capsule *unchanged = copy;
    golem_capsule_spec invalid = borrowed;
    invalid.goal = " \n\t";
    CHECK(golem_work_capsule_create(&invalid, &unchanged) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(unchanged == copy);
    invalid = borrowed;
    invalid.scope.count = 0;
    CHECK(golem_work_capsule_create(&invalid, &unchanged) == GOLEM_ERR_INVALID_ARGUMENT);
    invalid = borrowed;
    invalid.acceptance.items = NULL;
    CHECK(golem_work_capsule_create(&invalid, &unchanged) == GOLEM_ERR_INVALID_ARGUMENT);
    const char *duplicate[] = {"same", "same"};
    invalid = borrowed;
    invalid.required_gates = (golem_string_list){duplicate, 2};
    CHECK(golem_work_capsule_create(&invalid, &unchanged) == GOLEM_ERR_INVALID_ARGUMENT);
    invalid = borrowed;
    invalid.expected_artifacts.count = SIZE_MAX;
    CHECK(golem_work_capsule_create(&invalid, &unchanged) == GOLEM_ERR_INVALID_ARGUMENT);
    invalid = borrowed;
    invalid.permissions[0] = (golem_autonomy)99;
    CHECK(golem_work_capsule_create(&invalid, &unchanged) == GOLEM_ERR_INVALID_ARGUMENT);
    golem_work_run *run = NULL;
    CHECK(golem_work_run_create("run-owned", copy, 2, &run) == GOLEM_OK);
    golem_work_capsule_free(copy);
    CHECK(strcmp(golem_work_run_id_borrow(run), "run-owned") == 0);
    CHECK(pass_stages(run, 6) == EXIT_SUCCESS);
    golem_work_run_free(run);
    return EXIT_SUCCESS;
}

static int test_lifecycle(void)
{
    golem_graph_spec spec;
    CHECK(golem_stage_graph_default_spec(&spec) == GOLEM_OK);
    golem_work_run *run = NULL;
    CHECK(make_run(&spec, GOLEM_AUTONOMY_AUTO_LOCAL, 3, &run) == GOLEM_OK);
    CHECK(golem_work_run_stage_borrow(run) == NULL);
    CHECK(golem_work_run_reenter(run) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_work_run_finish(run, 0, GOLEM_STAGE_PASSED,
        GOLEM_FAILURE_NONE, true) == GOLEM_ERR_INVALID_STATE);
    for (size_t i = 0; i < spec.count; ++i) {
        golem_work_snapshot work;
        CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK);
        CHECK(work.status == GOLEM_WORK_READY && work.current_stage == spec.order[i]);
        CHECK(work.passed_count == i && work.stage_count == 6);
        golem_stage_snapshot stage;
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
        CHECK(stage.stage == spec.order[i] && stage.attempt == 1 && stage.sequence == i + 1);
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_ERR_INVALID_STATE);
        CHECK(golem_work_run_finish(run, stage.sequence + 1, GOLEM_STAGE_PASSED,
            GOLEM_FAILURE_NONE, true) == GOLEM_ERR_STALE_RESULT);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED,
            GOLEM_FAILURE_NONE, false) == GOLEM_ERR_REQUIREMENTS_UNMET);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_FAILED,
            GOLEM_FAILURE_NONE, false) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED,
            GOLEM_FAILURE_UNKNOWN, true) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_CANCELLED,
            GOLEM_FAILURE_NONE, false) == GOLEM_ERR_INVALID_ARGUMENT);
        golem_stage_snapshot latest;
        CHECK(golem_stage_run_snapshot_get(golem_work_run_stage_borrow(run), &latest) == GOLEM_OK);
        CHECK(latest.status == GOLEM_STAGE_RUNNING && latest.sequence == stage.sequence);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED,
            GOLEM_FAILURE_NONE, true) == GOLEM_OK);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED,
            GOLEM_FAILURE_NONE, true) == GOLEM_ERR_INVALID_STATE);
    }
    golem_work_snapshot work;
    CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK);
    CHECK(work.status == GOLEM_WORK_SUCCEEDED && work.current_stage == GOLEM_STAGE_NONE);
    CHECK(work.passed_count == 6);
    golem_stage_snapshot stage;
    CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_work_run_reenter(run) == GOLEM_ERR_INVALID_STATE);
    CHECK(golem_work_run_cancel(run) == GOLEM_ERR_INVALID_STATE);
    golem_work_run_free(run);
    return EXIT_SUCCESS;
}

static int test_reentry(void)
{
    const golem_failure failures[] = {
        GOLEM_FAILURE_PLANNING_GAP, GOLEM_FAILURE_UX_MISMATCH,
        GOLEM_FAILURE_PUBLISHING_GAP, GOLEM_FAILURE_IMPLEMENTATION_DEFECT,
        GOLEM_FAILURE_QA_FLAKE, GOLEM_FAILURE_AUDIT_GAP, GOLEM_FAILURE_TIMEOUT
    };
    const golem_stage targets[] = {GOLEM_STAGE_PLANNING, GOLEM_STAGE_UX,
        GOLEM_STAGE_PUBLISHING, GOLEM_STAGE_DEVELOPMENT, GOLEM_STAGE_QA,
        GOLEM_STAGE_PLANNING, GOLEM_STAGE_AUDIT};
    golem_graph_spec spec;
    CHECK(golem_stage_graph_default_spec(&spec) == GOLEM_OK);
    for (size_t i = 0; i < sizeof(failures) / sizeof(failures[0]); ++i) {
        golem_work_run *run = NULL;
        CHECK(make_run(&spec, GOLEM_AUTONOMY_AUTO_LOCAL, 3, &run) == GOLEM_OK);
        CHECK(pass_stages(run, 5) == EXIT_SUCCESS);
        golem_stage_snapshot stage;
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
        uint64_t old_sequence = stage.sequence;
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_FAILED,
            failures[i], false) == GOLEM_OK);
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_ERR_INVALID_STATE);
        CHECK(golem_work_run_reenter(run) == GOLEM_OK);
        golem_work_snapshot work;
        CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK);
        CHECK(work.current_stage == targets[i] && work.passed_count == (size_t)targets[i]);
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
        CHECK(stage.attempt == 2 && stage.sequence > old_sequence);
        CHECK(golem_work_run_finish(run, old_sequence, GOLEM_STAGE_PASSED,
            GOLEM_FAILURE_NONE, true) == GOLEM_ERR_STALE_RESULT);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED,
            GOLEM_FAILURE_NONE, true) == GOLEM_OK);
        CHECK(pass_stages(run, 5 - (size_t)targets[i]) == EXIT_SUCCESS);
        CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK);
        CHECK(work.status == GOLEM_WORK_SUCCEEDED && work.passed_count == 6);
        golem_work_run_free(run);
    }
    golem_work_run *run = NULL;
    CHECK(make_run(&spec, GOLEM_AUTONOMY_AUTO_LOCAL, 2, &run) == GOLEM_OK);
    for (unsigned attempt = 1; attempt <= 2; ++attempt) {
        golem_stage_snapshot stage;
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
        CHECK(stage.attempt == attempt);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_FAILED,
            GOLEM_FAILURE_TIMEOUT, false) == GOLEM_OK);
        CHECK(golem_work_run_reenter(run) ==
            (attempt == 1 ? GOLEM_OK : GOLEM_ERR_ATTEMPT_LIMIT));
    }
    golem_work_snapshot work;
    CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK);
    CHECK(work.status == GOLEM_WORK_FAILED);
    uint32_t attempts = 0;
    CHECK(golem_work_run_attempts_get(run, GOLEM_STAGE_PLANNING, &attempts) == GOLEM_OK);
    CHECK(attempts == 2);
    CHECK(golem_work_run_cancel(run) == GOLEM_OK);
    golem_work_run_free(run);
    /* A depleted downstream stage prevents a partial recovery, atomically. */
    CHECK(make_run(&spec, GOLEM_AUTONOMY_AUTO_LOCAL, 2, &run) == GOLEM_OK);
    CHECK(pass_stages(run, 5) == EXIT_SUCCESS);
    for (unsigned i = 0; i < 2; ++i) {
        golem_stage_snapshot stage;
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_FAILED,
            i == 0 ? GOLEM_FAILURE_TIMEOUT : GOLEM_FAILURE_PLANNING_GAP, false) == GOLEM_OK);
        CHECK(golem_work_run_reenter(run) == (i == 0 ? GOLEM_OK : GOLEM_ERR_ATTEMPT_LIMIT));
    }
    CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK);
    CHECK(work.status == GOLEM_WORK_FAILED && work.passed_count == 5);
    CHECK(work.current_stage == GOLEM_STAGE_AUDIT);
    golem_work_run_free(run);
    return EXIT_SUCCESS;
}

static int test_policy_cancel(void)
{
    golem_graph_spec spec;
    CHECK(golem_stage_graph_default_spec(&spec) == GOLEM_OK);
    for (int mode = GOLEM_AUTONOMY_DENY; mode <= GOLEM_AUTONOMY_ASK_ALWAYS; ++mode) {
        for (int external = 0; external <= 1; ++external) {
            for (int authorized = 0; authorized <= 1; ++authorized) {
                golem_work_run *run = NULL;
                CHECK(make_run(&spec, (golem_autonomy)mode, 2, &run) == GOLEM_OK);
                bool allowed = mode != GOLEM_AUTONOMY_DENY &&
                    (authorized || (!external && mode != GOLEM_AUTONOMY_ASK_ALWAYS));
                golem_stage_snapshot stage = {0};
                CHECK(golem_work_run_begin(run, external != 0, authorized != 0, &stage) ==
                    (allowed ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED));
                uint32_t attempts = 99;
                CHECK(golem_work_run_attempts_get(run, GOLEM_STAGE_PLANNING, &attempts) == GOLEM_OK);
                CHECK(attempts == (allowed ? 1u : 0u));
                CHECK(golem_work_run_cancel(run) == GOLEM_OK);
                CHECK(golem_work_run_begin(run, false, true, &stage) == GOLEM_ERR_INVALID_STATE);
                CHECK(golem_work_run_cancel(run) == GOLEM_ERR_INVALID_STATE);
                if (allowed) {
                    CHECK(golem_stage_run_snapshot_get(golem_work_run_stage_borrow(run), &stage) == GOLEM_OK);
                    CHECK(stage.status == GOLEM_STAGE_CANCELLED);
                    CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED,
                        GOLEM_FAILURE_NONE, true) == GOLEM_ERR_INVALID_STATE);
                }
                golem_work_run_free(run);
            }
        }
    }
    const golem_failure blocks[] = {GOLEM_FAILURE_POLICY_DENIED,
        GOLEM_FAILURE_STALE_LEASE, GOLEM_FAILURE_BUDGET_EXHAUSTED};
    for (size_t i = 0; i < 3; ++i) {
        golem_work_run *run = NULL;
        CHECK(make_run(&spec, GOLEM_AUTONOMY_AUTO_LOCAL, 2, &run) == GOLEM_OK);
        golem_stage_snapshot stage;
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_FAILED, blocks[i], false) == GOLEM_OK);
        golem_work_snapshot work;
        CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK);
        CHECK(work.status == GOLEM_WORK_BLOCKED);
        CHECK(golem_work_run_reenter(run) == GOLEM_ERR_INVALID_STATE);
        CHECK(golem_work_run_begin(run, false, true, &stage) == GOLEM_ERR_INVALID_STATE);
        CHECK(golem_work_run_cancel(run) == GOLEM_OK);
        golem_work_run_free(run);
    }
    return EXIT_SUCCESS;
}

/* Enumerate all 1,956 nonempty ordered subsets of the six stages. */
static int check_orders(golem_graph_spec *spec, size_t depth, unsigned mask, size_t *checked)
{
    CHECK(depth <= GOLEM_STAGE_COUNT);
    if (depth != 0) {
        spec->count = depth;
        golem_work_run *run = NULL;
        CHECK(make_run(spec, GOLEM_AUTONOMY_AUTO_LOCAL, 2, &run) == GOLEM_OK);
        for (size_t i = 0; i < depth; ++i) {
            golem_stage_snapshot stage;
            CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
            CHECK(stage.stage == spec->order[i]);
            CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED,
                GOLEM_FAILURE_NONE, true) == GOLEM_OK);
        }
        golem_work_snapshot work;
        CHECK(golem_work_run_snapshot_get(run, &work) == GOLEM_OK);
        CHECK(work.status == GOLEM_WORK_SUCCEEDED && work.passed_count == depth);
        golem_work_run_free(run);
        ++*checked;
    }
    if (depth == GOLEM_STAGE_COUNT) return EXIT_SUCCESS;
    for (unsigned stage = 0; stage < GOLEM_STAGE_COUNT; ++stage) {
        if ((mask & (1u << stage)) == 0) {
            spec->order[depth] = (golem_stage)stage;
            CHECK(check_orders(spec, depth + 1, mask | (1u << stage), checked) == EXIT_SUCCESS);
        }
    }
    return EXIT_SUCCESS;
}

static int test_overrides(void)
{
    golem_graph_spec spec;
    CHECK(golem_stage_graph_default_spec(&spec) == GOLEM_OK);
    size_t checked = 0;
    CHECK(check_orders(&spec, 0, 0, &checked) == EXIT_SUCCESS);
    CHECK(checked == 1956);
    spec.count = 2;
    spec.order[0] = GOLEM_STAGE_DEVELOPMENT;
    spec.order[1] = GOLEM_STAGE_QA;
    golem_stage_graph *graph = NULL;
    CHECK(golem_stage_graph_create(&spec, &graph) == GOLEM_OK);
    golem_stage target = GOLEM_STAGE_NONE;
    CHECK(golem_stage_graph_reentry(graph, GOLEM_STAGE_QA,
        GOLEM_FAILURE_UX_MISMATCH, &target) == GOLEM_ERR_NO_REENTRY);
    CHECK(target == GOLEM_STAGE_NONE);
    CHECK(golem_stage_graph_reentry(graph, GOLEM_STAGE_QA,
        GOLEM_FAILURE_UNKNOWN, &target) == GOLEM_ERR_NO_REENTRY);
    golem_stage_graph_free(graph);
    spec.reentry[GOLEM_FAILURE_UNKNOWN] = GOLEM_STAGE_DEVELOPMENT;
    CHECK(golem_stage_graph_create(&spec, &graph) == GOLEM_OK);
    CHECK(golem_stage_graph_reentry(graph, GOLEM_STAGE_QA,
        GOLEM_FAILURE_UNKNOWN, &target) == GOLEM_OK);
    CHECK(target == GOLEM_STAGE_DEVELOPMENT);
    golem_stage_graph_free(graph);
    return EXIT_SUCCESS;
}

static int test_nulls(void)
{
    CHECK(golem_stage_graph_default_spec(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_stage_graph_create(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_stage_graph_spec_get(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_stage_graph_next(NULL, GOLEM_STAGE_PLANNING, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_stage_graph_reentry(NULL, GOLEM_STAGE_PLANNING, GOLEM_FAILURE_UNKNOWN, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_capsule_create(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_capsule_spec_borrow(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_create(NULL, NULL, 0, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_snapshot_get(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_attempts_get(NULL, GOLEM_STAGE_NONE, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_begin(NULL, false, false, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_finish(NULL, 0, GOLEM_STAGE_PASSED, GOLEM_FAILURE_NONE, true) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_cancel(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_reenter(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_stage_run_snapshot_get(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_work_run_id_borrow(NULL) == NULL);
    CHECK(golem_work_run_stage_borrow(NULL) == NULL);
    golem_stage_graph_free(NULL);
    golem_work_capsule_free(NULL);
    golem_work_run_free(NULL);
    return EXIT_SUCCESS;
}

int main(int argc, char **argv)
{
    const struct { const char *name; int (*run)(void); } cases[] = {
        {"graph", test_graph}, {"transitions", test_transitions}, {"capsule", test_capsule},
        {"lifecycle", test_lifecycle}, {"reentry", test_reentry},
        {"policy_cancel", test_policy_cancel}, {"overrides", test_overrides}, {"nulls", test_nulls}
    };
    if (argc != 2) {
        return EXIT_FAILURE;
    }
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        if (strcmp(argv[1], cases[i].name) == 0) {
            return cases[i].run();
        }
    }
    return EXIT_FAILURE;
}
