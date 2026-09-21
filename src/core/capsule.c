#include "internal.h"
#include <string.h>
static bool text_valid(const char *text)
{
    if (text == NULL) {
        return false;
    }
    for (; *text != '\0'; ++text) {
        if (*text != ' ' && *text != '\t' && *text != '\n' && *text != '\r') {
            return true;
        }
    }
    return false;
}
static bool list_valid(golem_string_list list, bool required)
{
    if ((required && list.count == 0) || list.count > SIZE_MAX / sizeof(char *) ||
        (list.count != 0 && list.items == NULL)) {
        return false;
    }
    for (size_t i = 0; i < list.count; ++i) {
        if (!text_valid(list.items[i])) {
            return false;
        }
        for (size_t j = 0; j < i; ++j) {
            if (strcmp(list.items[i], list.items[j]) == 0) {
                return false;
            }
        }
    }
    return true;
}
void golem_work_capsule_free(golem_work_capsule *capsule)
{
    if (capsule == NULL) {
        return;
    }
    const size_t counts[] = {capsule->spec.scope.count, capsule->spec.acceptance.count,
        capsule->spec.expected_artifacts.count, capsule->spec.required_gates.count};
    for (size_t i = 0; i < 4; ++i) {
        if (capsule->lists[i] != NULL) {
            for (size_t j = 0; j < counts[i]; ++j) {
                (void)golem_allocator_free(&capsule->allocator, capsule->lists[i][j]);
            }
            (void)golem_allocator_free(&capsule->allocator, capsule->lists[i]);
        }
    }
    (void)golem_allocator_free(&capsule->allocator, capsule->id);
    (void)golem_allocator_free(&capsule->allocator, capsule->goal);
    (void)golem_allocator_free(&capsule->allocator, capsule);
}
static golem_status capsule_create(const golem_capsule_spec *spec,
    const golem_allocator *allocator, golem_work_capsule **out)
{
    if (spec == NULL || out == NULL || spec->graph == NULL ||
        !text_valid(spec->id) || !text_valid(spec->goal) ||
        !list_valid(spec->scope, true) || !list_valid(spec->acceptance, true) ||
        !list_valid(spec->expected_artifacts, false) || !list_valid(spec->required_gates, false)) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    for (size_t i = 0; i < GOLEM_STAGE_COUNT; ++i) {
        if (spec->permissions[i] < GOLEM_AUTONOMY_DENY || spec->permissions[i] > GOLEM_AUTONOMY_ASK_ALWAYS) {
            return GOLEM_ERR_INVALID_ARGUMENT;
        }
    }
    void *memory;
    golem_status status = golem_allocator_alloc(allocator, sizeof(golem_work_capsule), &memory);
    if (status != GOLEM_OK) {
        return status;
    }
    golem_work_capsule *capsule = memory;
    *capsule = (golem_work_capsule){0};
    capsule->allocator = allocator == NULL ? golem_allocator_default() : *allocator;
    capsule->spec = *spec;
    capsule->graph = *spec->graph;
    capsule->graph.allocator = capsule->allocator;
    capsule->spec.graph = &capsule->graph;
    capsule->id = golem_core_string_clone(spec->id, &capsule->allocator);
    capsule->goal = golem_core_string_clone(spec->goal, &capsule->allocator);
    if (capsule->id == NULL || capsule->goal == NULL) {
        golem_work_capsule_free(capsule);
        return GOLEM_ERR_OUT_OF_MEMORY;
    }
    capsule->spec.id = capsule->id;
    capsule->spec.goal = capsule->goal;
    const golem_string_list inputs[] = {spec->scope, spec->acceptance, spec->expected_artifacts, spec->required_gates};
    golem_string_list *outputs[] = {&capsule->spec.scope, &capsule->spec.acceptance,
        &capsule->spec.expected_artifacts, &capsule->spec.required_gates};
    for (size_t i = 0; i < 4; ++i) {
        outputs[i]->items = NULL;
        if (inputs[i].count == 0) {
            continue;
        }
        status = golem_allocator_alloc(&capsule->allocator, inputs[i].count * sizeof(char *), &memory);
        if (status != GOLEM_OK) {
            golem_work_capsule_free(capsule);
            return status;
        }
        capsule->lists[i] = memory;
        for (size_t j = 0; j < inputs[i].count; ++j) {
            capsule->lists[i][j] = NULL;
        }
        for (size_t j = 0; j < inputs[i].count; ++j) {
            capsule->lists[i][j] = golem_core_string_clone(inputs[i].items[j], &capsule->allocator);
            if (capsule->lists[i][j] == NULL) {
                golem_work_capsule_free(capsule);
                return GOLEM_ERR_OUT_OF_MEMORY;
            }
        }
        outputs[i]->items = (const char *const *)capsule->lists[i];
    }
    *out = capsule;
    return GOLEM_OK;
}
golem_status golem_work_capsule_create_with_allocator(const golem_capsule_spec *spec,
    const golem_allocator *allocator, golem_work_capsule **out, golem_diagnostic *diagnostic)
{
    golem_status status = golem_allocator_validate(allocator);
    if (status == GOLEM_OK) {
        status = capsule_create(spec, allocator, out);
    }
    return golem_core_report(diagnostic, status, "work capsule creation failed");
}
golem_status golem_work_capsule_create(const golem_capsule_spec *spec, golem_work_capsule **out)
{
    return golem_work_capsule_create_with_allocator(spec, NULL, out, NULL);
}
golem_status golem_work_capsule_spec_borrow(const golem_work_capsule *capsule, golem_capsule_spec *out)
{
    if (capsule == NULL || out == NULL) {
        return GOLEM_ERR_INVALID_ARGUMENT;
    }
    *out = capsule->spec;
    return GOLEM_OK;
}
