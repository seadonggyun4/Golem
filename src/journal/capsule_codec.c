#include "internal.h"
#include "golem/arena.h"
#include <string.h>

typedef struct sink { uint8_t *data; size_t offset; bool valid; } sink;
static void put_bytes(sink *s, const void *data, size_t size)
{
    if (!s->valid || size > GOLEM_JOURNAL_MAX_PAYLOAD - s->offset) {
        s->valid = false;
        return;
    }
    if (s->data != NULL && size != 0) memcpy(s->data + s->offset, data, size);
    s->offset += size;
}
static void put32(sink *s, uint32_t value)
{
    uint8_t bytes[4];
    golem_journal_put32(bytes, value);
    put_bytes(s, bytes, sizeof(bytes));
}
static void put_string(sink *s, const char *text)
{
    size_t length = strlen(text);
    if (length == 0 || length > GOLEM_JOURNAL_MAX_PAYLOAD) {
        s->valid = false;
        return;
    }
    put32(s, (uint32_t)length);
    put_bytes(s, text, length);
}
static void put_capsule(sink *s, const char *id, const golem_capsule_spec *spec,
                         const golem_graph_spec *graph, uint32_t max_attempts)
{
    put32(s, max_attempts);
    put32(s, (uint32_t)graph->count);
    for (size_t i = 0; i < graph->count; ++i) put32(s, (uint32_t)graph->order[i]);
    for (size_t i = 0; i < GOLEM_FAILURE_COUNT; ++i) put32(s, (uint32_t)graph->reentry[i]);
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) put32(s, (uint32_t)spec->permissions[i]);
    put_string(s, id);
    put_string(s, spec->id);
    put_string(s, spec->goal);
    const golem_string_list lists[] = {spec->scope, spec->acceptance, spec->expected_artifacts, spec->required_gates};
    for (size_t i = 0; i < 4; ++i) {
        if (lists[i].count > GOLEM_JOURNAL_MAX_LIST_ITEMS) {
            s->valid = false;
            return;
        }
        put32(s, (uint32_t)lists[i].count);
        for (size_t j = 0; j < lists[i].count; ++j) put_string(s, lists[i].items[j]);
    }
}
golem_status golem_journal_created_encode(const char *run_id,
    const golem_work_capsule *capsule, uint32_t max_attempts,
    void *destination, size_t capacity, size_t *required, golem_diagnostic *d)
{
    if (run_id == NULL || run_id[0] == '\0' || capsule == NULL || max_attempts == 0 ||
        required == NULL || (destination == NULL && capacity != 0))
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, NULL);
    golem_capsule_spec spec;
    golem_graph_spec graph;
    (void)golem_work_capsule_spec_borrow(capsule, &spec);
    (void)golem_stage_graph_spec_get(spec.graph, &graph);
    sink measure = {NULL, 0, true};
    put_capsule(&measure, run_id, &spec, &graph, max_attempts);
    if (!measure.valid)
        return golem_journal_report(d, GOLEM_ERR_INVALID_ARGUMENT, 0, "capsule exceeds journal schema limits");
    if (capacity < measure.offset) {
        *required = measure.offset;
        return golem_journal_report(d, GOLEM_ERR_BUFFER_TOO_SMALL, 0, NULL);
    }
    sink writer = {destination, 0, true};
    put_capsule(&writer, run_id, &spec, &graph, max_attempts);
    *required = writer.offset;
    return golem_journal_report(d, GOLEM_OK, 0, NULL);
}

typedef struct cursor { golem_bytes bytes; size_t offset; bool valid; } cursor;
static uint32_t take32(cursor *c)
{
    if (!c->valid || c->bytes.size - c->offset < 4) {
        c->valid = false;
        return 0;
    }
    uint32_t value = golem_journal_u32(c->bytes.data + c->offset);
    c->offset += 4;
    return value;
}
static const char *take_string(cursor *c, golem_arena *arena)
{
    uint32_t length = take32(c);
    if (!c->valid || length == 0 || length > c->bytes.size - c->offset ||
        memchr(c->bytes.data + c->offset, 0, length) != NULL) {
        c->valid = false;
        return NULL;
    }
    void *memory;
    if (golem_arena_alloc(arena, (size_t)length + 1, 1, &memory) != GOLEM_OK) {
        c->valid = false;
        return NULL;
    }
    char *text = memory;
    memcpy(text, c->bytes.data + c->offset, length);
    text[length] = '\0';
    c->offset += length;
    return text;
}
golem_status golem_journal_created_decode(golem_bytes payload,
    const golem_allocator *allocator, golem_work_run **out, golem_diagnostic *d)
{
    if (payload.size > GOLEM_JOURNAL_MAX_PAYLOAD)
        return golem_journal_report(d, GOLEM_ERR_CORRUPT_JOURNAL, 0, "capsule too large");
    /* Bound all temporary text and pointer arrays independently of wire lengths. */
    size_t scratch_size = payload.size + 4 * GOLEM_JOURNAL_MAX_LIST_ITEMS *
        (sizeof(char *) + 1) + 4 * _Alignof(max_align_t) + 16;
    void *scratch;
    golem_status status = golem_allocator_alloc(allocator, scratch_size, &scratch);
    if (status != GOLEM_OK) return golem_journal_report(d, status, 0, NULL);
    golem_arena arena;
    (void)golem_arena_init(&arena, scratch, scratch_size);
    cursor c = {payload, 0, true};
    golem_graph_spec graph_spec = {0};
    golem_capsule_spec spec = {0};
    golem_stage_graph *graph = NULL;
    golem_work_capsule *capsule = NULL;
    golem_work_run *run = NULL;
    uint32_t max_attempts = take32(&c);
    uint32_t count = take32(&c);
    if (max_attempts == 0 || count == 0 || count > GOLEM_STAGE_COUNT) c.valid = false;
    graph_spec.count = c.valid ? count : 0;
    for (size_t i = 0; i < graph_spec.count; ++i) {
        uint32_t stage = take32(&c);
        if (stage >= GOLEM_STAGE_COUNT) c.valid = false;
        graph_spec.order[i] = stage < GOLEM_STAGE_COUNT ? (golem_stage)stage : GOLEM_STAGE_NONE;
    }
    for (size_t i = 0; i < GOLEM_FAILURE_COUNT; ++i) {
        uint32_t stage = take32(&c);
        if (stage > GOLEM_STAGE_NONE) c.valid = false;
        graph_spec.reentry[i] = stage <= GOLEM_STAGE_NONE ? (golem_stage)stage : GOLEM_STAGE_NONE;
    }
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) {
        uint32_t mode = take32(&c);
        if (mode > GOLEM_AUTONOMY_ASK_ALWAYS) c.valid = false;
        spec.permissions[i] = mode <= GOLEM_AUTONOMY_ASK_ALWAYS ? (golem_autonomy)mode : GOLEM_AUTONOMY_DENY;
    }
    const char *id = take_string(&c, &arena);
    spec.id = take_string(&c, &arena);
    spec.goal = take_string(&c, &arena);
    golem_string_list *lists[] = {&spec.scope, &spec.acceptance, &spec.expected_artifacts, &spec.required_gates};
    for (size_t i = 0; i < 4 && c.valid; ++i) {
        count = take32(&c);
        if (!c.valid || count > GOLEM_JOURNAL_MAX_LIST_ITEMS) {
            c.valid = false;
            break;
        }
        if (count == 0) continue;
        void *memory;
        if (golem_arena_alloc(&arena, count * sizeof(char *), _Alignof(char *), &memory) != GOLEM_OK) {
            c.valid = false;
            break;
        }
        const char **items = memory;
        lists[i]->items = items;
        lists[i]->count = count;
        for (size_t j = 0; j < count; ++j) items[j] = take_string(&c, &arena);
    }
    if (!c.valid || c.offset != payload.size) {
        status = GOLEM_ERR_CORRUPT_JOURNAL;
    } else {
        status = golem_stage_graph_create_with_allocator(&graph_spec, allocator, &graph, NULL);
        spec.graph = graph;
        if (status == GOLEM_OK) status = golem_work_capsule_create_with_allocator(&spec, allocator, &capsule, NULL);
        if (status == GOLEM_OK) status = golem_work_run_create_with_allocator(id, capsule, max_attempts, allocator, &run, NULL);
        if (status != GOLEM_OK && status != GOLEM_ERR_OUT_OF_MEMORY) status = GOLEM_ERR_CORRUPT_JOURNAL;
    }
    golem_work_capsule_free(capsule);
    golem_stage_graph_free(graph);
    (void)golem_allocator_free(allocator, scratch);
    if (status != GOLEM_OK) return golem_journal_report(d, status, c.offset, "invalid or unallocatable capsule");
    *out = run;
    return golem_journal_report(d, GOLEM_OK, 0, NULL);
}
