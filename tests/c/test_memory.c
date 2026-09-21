#include "golem/allocator.h"
#include "golem/arena.h"
#include "golem/core.h"
#include "golem/types.h"
#include "test.h"
#include <string.h>
#include <stdint.h>

typedef struct tracker {
    size_t calls;
    size_t fail_at;
    size_t live;
    size_t bad_frees;
} tracker;
typedef union allocation_header {
    max_align_t alignment;
    struct { tracker *owner; } metadata;
} allocation_header;

static void *tracked_allocate(void *context, size_t size)
{
    tracker *state = context;
    ++state->calls;
    if ((state->fail_at != 0 && state->calls >= state->fail_at) ||
        size > SIZE_MAX - sizeof(allocation_header)) {
        return NULL;
    }
    allocation_header *header = malloc(sizeof(*header) + size);
    if (header == NULL) {
        return NULL;
    }
    header->metadata.owner = state;
    ++state->live;
    void *memory = header + 1;
    memset(memory, 0xa5, size);
    return memory;
}
static void tracked_deallocate(void *context, void *pointer)
{
    tracker *state = context;
    allocation_header *header = (allocation_header *)pointer - 1;
    if (header->metadata.owner != state || state->live == 0) {
        ++state->bad_frees;
        return;
    }
    --state->live;
    free(header);
}
static golem_allocator allocator_for(tracker *state)
{
    return (golem_allocator){state, tracked_allocate, tracked_deallocate};
}

static int test_allocator(void)
{
    tracker state = {0};
    golem_allocator allocator = allocator_for(&state);
    unsigned char sentinel;
    void *memory = &sentinel;
    CHECK(golem_allocator_validate(NULL) == GOLEM_OK);
    golem_allocator invalid = {0};
    CHECK(golem_allocator_validate(&invalid) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_allocator_alloc(&invalid, 1, &memory) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_allocator_free(&invalid, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_allocator_alloc(&allocator, 0, &memory) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_allocator_alloc(&allocator, 1, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_allocator_alloc_zero(&allocator, SIZE_MAX, 2, &memory) == GOLEM_ERR_OVERFLOW);
    CHECK(golem_allocator_alloc_zero(&allocator, 0, 2, &memory) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(memory == &sentinel && state.calls == 0);
    CHECK(golem_allocator_alloc_zero(&allocator, 8, sizeof(uint64_t), &memory) == GOLEM_OK);
    CHECK((uintptr_t)memory % _Alignof(max_align_t) == 0);
    for (size_t i = 0; i < 8 * sizeof(uint64_t); ++i) {
        CHECK(((unsigned char *)memory)[i] == 0);
    }
    CHECK(golem_allocator_free(&allocator, memory) == GOLEM_OK);
    CHECK(golem_allocator_free(&allocator, NULL) == GOLEM_OK);
    CHECK(state.live == 0 && state.bad_frees == 0);
    state.fail_at = state.calls + 1;
    memory = &sentinel;
    CHECK(golem_allocator_alloc(&allocator, 12, &memory) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(memory == &sentinel);
    CHECK(golem_allocator_alloc(NULL, sizeof(max_align_t), &memory) == GOLEM_OK);
    CHECK((uintptr_t)memory % _Alignof(max_align_t) == 0);
    CHECK(golem_allocator_free(NULL, memory) == GOLEM_OK);
    return EXIT_SUCCESS;
}

static int test_arena(void)
{
    unsigned char storage[512];
    golem_arena arena;
    unsigned char sentinel;
    for (size_t offset = 0; offset < _Alignof(max_align_t); ++offset) {
        CHECK(golem_arena_init(&arena, storage + offset, sizeof(storage) - offset) == GOLEM_OK);
        for (size_t alignment = 1; alignment <= _Alignof(max_align_t); alignment *= 2) {
            void *memory;
            CHECK(golem_arena_alloc(&arena, 3, alignment, &memory) == GOLEM_OK);
            CHECK((uintptr_t)memory % alignment == 0);
            memset(memory, 0x42, 3);
        }
        size_t used;
        CHECK(golem_arena_used_get(&arena, &used) == GOLEM_OK);
        void *memory = &sentinel;
        CHECK(golem_arena_alloc(&arena, SIZE_MAX, 1, &memory) == GOLEM_ERR_OUT_OF_MEMORY);
        CHECK(golem_arena_alloc(&arena, 1, 3, &memory) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(golem_arena_alloc(&arena, 0, 1, &memory) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(golem_arena_alloc(&arena, 1, 0, &memory) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(golem_arena_alloc(&arena, 1, _Alignof(max_align_t) * 2, &memory) == GOLEM_ERR_INVALID_ARGUMENT);
        CHECK(arena.used == used && memory == &sentinel);
        size_t remaining = arena.capacity - used;
        CHECK(golem_arena_alloc(&arena, remaining, 1, &memory) == GOLEM_OK);
        CHECK(arena.used == arena.capacity);
        CHECK(golem_arena_alloc(&arena, 1, 1, &memory) == GOLEM_ERR_OUT_OF_MEMORY);
        CHECK(golem_arena_reset(&arena) == GOLEM_OK);
        CHECK(arena.used == 0);
        CHECK(golem_arena_alloc(&arena, arena.capacity, 1, &memory) == GOLEM_OK);
        CHECK(memory == storage + offset);
    }
    CHECK(golem_arena_init(&arena, NULL, 0) == GOLEM_OK);
    void *memory = &sentinel;
    CHECK(golem_arena_alloc(&arena, 1, 1, &memory) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(golem_arena_init(&arena, NULL, 1) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(arena.capacity == 0 && arena.data == NULL);
    CHECK(golem_arena_init(NULL, storage, sizeof(storage)) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_arena_alloc(NULL, 1, 1, &memory) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_arena_reset(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_arena_used_get(NULL, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    /* Insufficient alignment padding must not consume space. */
    for (size_t offset = 0; offset < _Alignof(max_align_t); ++offset) {
        CHECK(golem_arena_init(&arena, storage + offset, 1) == GOLEM_OK);
        golem_status expected = (uintptr_t)(storage + offset) % _Alignof(max_align_t) == 0
            ? GOLEM_OK : GOLEM_ERR_OUT_OF_MEMORY;
        CHECK(golem_arena_alloc(&arena, 1, _Alignof(max_align_t), &memory) == expected);
        CHECK(arena.used == (expected == GOLEM_OK ? 1u : 0u));
    }
    return EXIT_SUCCESS;
}

static int test_spans(void)
{
    char data[] = {'a', '\0', 'b'};
    golem_string_view view, slice;
    CHECK(golem_string_view_init(&view, data, sizeof(data)) == GOLEM_OK);
    CHECK(golem_string_view_slice(view, 1, 2, &slice) == GOLEM_OK);
    CHECK(slice.data == data + 1 && slice.size == 2);
    CHECK(golem_string_view_slice(view, 2, SIZE_MAX, &slice) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(slice.data == data + 1 && slice.size == 2);
    CHECK(golem_string_view_slice(view, SIZE_MAX, 0, &slice) == GOLEM_ERR_INVALID_ARGUMENT);
    char buffer[8] = "KEEP";
    size_t required = 99;
    CHECK(golem_string_view_write(view, NULL, 0, &required) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(required == 4);
    CHECK(golem_string_view_write(view, buffer, 3, &required) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(strcmp(buffer, "KEEP") == 0);
    CHECK(golem_string_view_write(view, buffer, 4, &required) == GOLEM_OK);
    CHECK(memcmp(buffer, data, 3) == 0 && buffer[3] == '\0' && required == 4);
    strcpy(buffer, "abcdef");
    CHECK(golem_string_view_init(&view, buffer, 4) == GOLEM_OK);
    CHECK(golem_string_view_write(view, buffer + 1, 5, &required) == GOLEM_OK);
    CHECK(strcmp(buffer, "aabcd") == 0);
    CHECK(golem_string_view_from_cstr(buffer + 1, &view) == GOLEM_OK);
    CHECK(golem_string_view_write(view, buffer, sizeof(buffer), &required) == GOLEM_OK);
    CHECK(strcmp(buffer, "abcd") == 0);
    golem_string_view invalid = {data, SIZE_MAX};
    required = 99;
    CHECK(golem_string_view_write(invalid, buffer, sizeof(buffer), &required) == GOLEM_ERR_OVERFLOW);
    CHECK(required == 99 && strcmp(buffer, "abcd") == 0);
    CHECK(golem_string_view_init(&view, NULL, 0) == GOLEM_OK);
    CHECK(golem_string_view_slice(view, 0, 0, &slice) == GOLEM_OK);
    CHECK(slice.data == NULL && slice.size == 0);
    CHECK(golem_string_view_write(view, buffer, 1, &required) == GOLEM_OK);
    CHECK(buffer[0] == '\0' && required == 1);
    CHECK(golem_string_view_init(&view, NULL, 1) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_string_view_from_cstr(NULL, &view) == GOLEM_ERR_INVALID_ARGUMENT);

    uint8_t bytes[] = {0, 1, 2, 3, 4};
    golem_bytes source = {bytes, sizeof(bytes)}, part;
    CHECK(golem_bytes_slice(source, 1, 3, &part) == GOLEM_OK);
    CHECK(part.data == bytes + 1 && part.size == 3);
    CHECK(golem_bytes_write(part, bytes + 2, 3, &required) == GOLEM_OK);
    CHECK(bytes[2] == 1 && bytes[3] == 2 && bytes[4] == 3);
    CHECK(golem_bytes_write(source, NULL, 0, &required) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(required == sizeof(bytes));
    uint8_t guard[] = {0xaa, 0xbb};
    CHECK(golem_bytes_write(source, guard, sizeof(guard), &required) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(guard[0] == 0xaa && guard[1] == 0xbb);
    CHECK(golem_bytes_slice(source, 4, SIZE_MAX, &part) == GOLEM_ERR_INVALID_ARGUMENT);
    required = 99;
    CHECK(golem_bytes_write(source, NULL, 1, &required) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(required == 99);
    CHECK(golem_bytes_write((golem_bytes){NULL, 0}, NULL, 0, &required) == GOLEM_OK);
    CHECK(required == 0);
    CHECK(golem_bytes_slice((golem_bytes){NULL, 0}, 0, 0, &part) == GOLEM_OK);
    CHECK(part.data == NULL && part.size == 0);

    tracker state = {0};
    golem_allocator allocator = allocator_for(&state);
    char *copy = NULL;
    CHECK(golem_string_clone((golem_string_view){data, sizeof(data)}, &allocator, &copy) == GOLEM_OK);
    CHECK(memcmp(copy, data, sizeof(data)) == 0 && copy[3] == '\0');
    CHECK(golem_allocator_free(&allocator, copy) == GOLEM_OK);
    copy = data;
    state.fail_at = state.calls + 1;
    CHECK(golem_string_clone((golem_string_view){data, 3}, &allocator, &copy) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(copy == data);
    CHECK(golem_string_clone(invalid, &allocator, &copy) == GOLEM_ERR_OVERFLOW);
    CHECK(copy == data && state.live == 0);
    CHECK(golem_string_clone((golem_string_view){NULL, 0}, NULL, &copy) == GOLEM_OK);
    CHECK(copy[0] == '\0');
    CHECK(golem_allocator_free(NULL, copy) == GOLEM_OK);
    return EXIT_SUCCESS;
}

static int test_diagnostics(void)
{
    golem_diagnostic diagnostic;
    CHECK(golem_diagnostic_clear(&diagnostic) == GOLEM_OK);
    CHECK(diagnostic.status == GOLEM_OK && diagnostic.offset == GOLEM_DIAGNOSTIC_NO_OFFSET);
    CHECK(diagnostic.message[0] == '\0' && !diagnostic.truncated);
    char message[] = "bad record";
    CHECK(golem_diagnostic_set(&diagnostic, GOLEM_ERR_PARSE, 42, message) == GOLEM_OK);
    message[0] = 'X';
    CHECK(strcmp(diagnostic.message, "bad record") == 0);
    CHECK(diagnostic.status == GOLEM_ERR_PARSE && diagnostic.offset == 42);
    CHECK(golem_diagnostic_set(&diagnostic, GOLEM_ERR_PARSE, 43, diagnostic.message + 4) == GOLEM_OK);
    CHECK(strcmp(diagnostic.message, "record") == 0);
    char long_message[GOLEM_DIAGNOSTIC_MESSAGE_CAPACITY + 10];
    memset(long_message, 'x', sizeof(long_message) - 1);
    long_message[sizeof(long_message) - 1] = '\0';
    CHECK(golem_diagnostic_set(&diagnostic, GOLEM_ERR_OUT_OF_MEMORY, 0, long_message) == GOLEM_OK);
    CHECK(diagnostic.truncated && diagnostic.status == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(strlen(diagnostic.message) == GOLEM_DIAGNOSTIC_MESSAGE_CAPACITY - 1);
    long_message[GOLEM_DIAGNOSTIC_MESSAGE_CAPACITY - 1] = '\0';
    CHECK(golem_diagnostic_set(&diagnostic, GOLEM_ERR_PARSE, 1, long_message) == GOLEM_OK);
    CHECK(!diagnostic.truncated);
    CHECK(golem_diagnostic_set(&diagnostic, (golem_status)999, 0, NULL) == GOLEM_OK);
    CHECK(diagnostic.status == (golem_status)999 && strcmp(diagnostic.message, "unknown status") == 0);
    CHECK(golem_diagnostic_clear(&diagnostic) == GOLEM_OK);
    CHECK(diagnostic.message[0] == '\0' && !diagnostic.truncated);
    CHECK(golem_diagnostic_set(NULL, GOLEM_OK, 0, NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_diagnostic_clear(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    return EXIT_SUCCESS;
}

static int test_core_oom(void)
{
    golem_graph_spec graph_spec;
    CHECK(golem_stage_graph_default_spec(&graph_spec) == GOLEM_OK);
    golem_stage_graph *graph = NULL;
    golem_stage_graph *graph_anchor = NULL;
    CHECK(golem_stage_graph_create(&graph_spec, &graph_anchor) == GOLEM_OK);
    golem_diagnostic diagnostic;
    tracker state = {0};
    golem_allocator allocator = allocator_for(&state);
    state.fail_at = 1;
    graph = graph_anchor;
    CHECK(golem_stage_graph_create_with_allocator(&graph_spec, &allocator, &graph, &diagnostic) == GOLEM_ERR_OUT_OF_MEMORY);
    CHECK(graph == graph_anchor && state.live == 0 && diagnostic.status == GOLEM_ERR_OUT_OF_MEMORY);
    golem_stage_graph_free(graph_anchor);
    graph = NULL;
    state = (tracker){0};
    CHECK(golem_stage_graph_create_with_allocator(&graph_spec, &allocator, &graph, &diagnostic) == GOLEM_OK);
    CHECK(diagnostic.status == GOLEM_OK && diagnostic.message[0] == '\0');
    const char *scope[] = {"src", "tests"};
    const char *acceptance[] = {"tests pass", "review passes"};
    const char *artifacts[] = {"patch", "receipt"};
    const char *gates[] = {"review", "test"};
    golem_capsule_spec spec = {0};
    spec.id = "capsule";
    spec.goal = "Allocator integration";
    spec.graph = graph;
    spec.scope = (golem_string_list){scope, 2};
    spec.acceptance = (golem_string_list){acceptance, 2};
    spec.expected_artifacts = (golem_string_list){artifacts, 2};
    spec.required_gates = (golem_string_list){gates, 2};
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) {
        spec.permissions[i] = GOLEM_AUTONOMY_AUTO_LOCAL;
    }
    tracker capsule_state = {0};
    golem_allocator capsule_allocator = allocator_for(&capsule_state);
    golem_work_capsule *capsule = NULL;
    CHECK(golem_work_capsule_create_with_allocator(&spec, &capsule_allocator, &capsule, &diagnostic) == GOLEM_OK);
    size_t capsule_calls = capsule_state.calls;
    CHECK(capsule_calls > 10);
    golem_work_capsule_free(capsule);
    CHECK(capsule_state.live == 0 && capsule_state.bad_frees == 0);
    golem_work_capsule *capsule_anchor = NULL;
    CHECK(golem_work_capsule_create(&spec, &capsule_anchor) == GOLEM_OK);
    for (size_t failure = 1; failure <= capsule_calls; ++failure) {
        capsule_state = (tracker){.fail_at = failure};
        capsule = capsule_anchor;
        CHECK(golem_work_capsule_create_with_allocator(&spec, &capsule_allocator, &capsule, &diagnostic) == GOLEM_ERR_OUT_OF_MEMORY);
        CHECK(capsule == capsule_anchor && capsule_state.live == 0 && capsule_state.bad_frees == 0);
        CHECK(diagnostic.status == GOLEM_ERR_OUT_OF_MEMORY && diagnostic.message[0] != '\0');
    }
    capsule = capsule_anchor;
    /* Callback table is copied, so its original variable can be discarded. */
    allocator = (golem_allocator){0};
    golem_stage_graph_free(graph);
    CHECK(state.live == 0 && state.bad_frees == 0);

    tracker run_state = {0};
    golem_allocator run_allocator = allocator_for(&run_state);
    golem_work_run *run = NULL;
    CHECK(golem_work_run_create_with_allocator("run", capsule, 2, &run_allocator, &run, &diagnostic) == GOLEM_OK);
    size_t run_calls = run_state.calls;
    golem_work_run_free(run);
    CHECK(run_state.live == 0 && run_state.bad_frees == 0);
    golem_work_run *run_anchor = NULL;
    CHECK(golem_work_run_create("anchor", capsule, 2, &run_anchor) == GOLEM_OK);
    for (size_t failure = 1; failure <= run_calls; ++failure) {
        run_state = (tracker){.fail_at = failure};
        run = run_anchor;
        CHECK(golem_work_run_create_with_allocator("run", capsule, 2, &run_allocator, &run, &diagnostic) == GOLEM_ERR_OUT_OF_MEMORY);
        CHECK(run == run_anchor && run_state.live == 0 && run_state.bad_frees == 0);
        CHECK(diagnostic.status == GOLEM_ERR_OUT_OF_MEMORY);
    }
    golem_work_run_free(run_anchor);
    run = NULL;
    run_state = (tracker){0};
    CHECK(golem_work_run_create_with_allocator("run", capsule, 2, &run_allocator, &run, &diagnostic) == GOLEM_OK);
    golem_work_capsule_free(capsule);
    run_calls = run_state.calls;
    run_state.fail_at = run_calls + 1;
    run_allocator = (golem_allocator){0};
    for (size_t i = 0; i < 6; ++i) {
        golem_stage_snapshot stage;
        CHECK(golem_work_run_begin(run, false, false, &stage) == GOLEM_OK);
        CHECK(golem_work_run_finish(run, stage.sequence, GOLEM_STAGE_PASSED,
                                       GOLEM_FAILURE_NONE, true) == GOLEM_OK);
    }
    CHECK(run_state.calls == run_calls);
    golem_work_run_free(run);
    CHECK(run_state.live == 0 && run_state.bad_frees == 0);
    graph = NULL;
    CHECK(golem_stage_graph_create_with_allocator(&graph_spec, &allocator, &graph, &diagnostic) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(graph == NULL && diagnostic.status == GOLEM_ERR_INVALID_ARGUMENT);
    return EXIT_SUCCESS;
}

int main(int argc, char **argv)
{
    const struct { const char *name; int (*run)(void); } cases[] = {
        {"allocator", test_allocator}, {"arena", test_arena}, {"spans", test_spans},
        {"diagnostics", test_diagnostics}, {"core_oom", test_core_oom}
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
