#include "descriptor_internal.h"
#include <string.h>

static bool text_valid(const char *s, bool empty)
{
    if (!memchr(s, 0, GOLEM_ADAPTER_ID_CAPACITY))
        return false;
    return (empty && !*s) || golem_adapter_id_valid(s);
}
static bool tools_valid(const golem_harness_tool *tools, size_t count)
{
    if (count > GOLEM_DESCRIPTOR_MAX_TOOLS)
        return false;
    for (size_t i = 0; i < count; ++i) {
        if (!text_valid(tools[i].id, false))
            return false;
        for (size_t j = 0; j < i; ++j)
            if (!strcmp(tools[i].id, tools[j].id))
                return false;
    }
    return true;
}
golem_status golem_adapter_descriptor_validate(const golem_adapter_descriptor *d)
{
    if (!d)
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (d->version != 1 || d->protocol_version != 1)
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    if (!text_valid(d->adapter_id, false) || !text_valid(d->adapter_version, true) ||
        !text_valid(d->session_id, true) || (!d->current_agent && *d->session_id) || !d->stages ||
        (d->stages & ~GOLEM_ADAPTER_ALL_STAGES) ||
        (d->features_known & ~GOLEM_HARNESS_ALL_FEATURES) ||
        (d->features_supported & ~d->features_known) || (d->inputs_known & ~GOLEM_INPUT_ALL) ||
        (d->inputs_supported & ~d->inputs_known) || d->simulation < GOLEM_HARNESS_UNKNOWN ||
        d->simulation > GOLEM_HARNESS_YES || d->hidden_prompt_known < GOLEM_HARNESS_UNKNOWN ||
        d->hidden_prompt_known > GOLEM_HARNESS_YES || d->sandbox < GOLEM_SANDBOX_UNKNOWN ||
        d->sandbox > GOLEM_SANDBOX_VM ||
        (d->effect < GOLEM_EFFECT_UNKNOWN || d->effect > GOLEM_EFFECT_EXTERNAL) ||
        !tools_valid(d->tools, d->tool_count))
        return GOLEM_ERR_INVALID_ARGUMENT;
    return GOLEM_OK;
}
golem_status golem_adapter_descriptor_from_v1(const golem_adapter_capability *c,
                                              golem_adapter_descriptor *out)
{
    if (!out || golem_adapter_capability_valid(c) != GOLEM_OK)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_adapter_descriptor d = {0};
    d.version = d.protocol_version = 1;
    memcpy(d.adapter_id, c->adapter_id, sizeof(d.adapter_id));
    d.stages = c->stages;
    d.effect = c->effect;
    d.simulation = c->simulation ? GOLEM_HARNESS_YES : GOLEM_HARNESS_NO;
    *out = d;
    return GOLEM_OK;
}
golem_status golem_adapter_descriptor_to_v1(const golem_adapter_descriptor *d,
                                            golem_adapter_capability *out)
{
    golem_status s = golem_adapter_descriptor_validate(d);
    if (s != GOLEM_OK || !out)
        return s != GOLEM_OK ? s : GOLEM_ERR_INVALID_ARGUMENT;
    if (d->current_agent || *d->adapter_version || *d->session_id || d->features_known ||
        d->inputs_known || d->sandbox || d->hidden_prompt_known || d->tool_count ||
        d->simulation == GOLEM_HARNESS_UNKNOWN || d->effect == GOLEM_EFFECT_UNKNOWN)
        return GOLEM_ERR_INVALID_STATE;
    golem_adapter_capability c = {0};
    c.version = 1;
    memcpy(c.adapter_id, d->adapter_id, sizeof(c.adapter_id));
    c.stages = d->stages;
    c.effect = d->effect;
    c.simulation = d->simulation == GOLEM_HARNESS_YES;
    *out = c;
    return GOLEM_OK;
}
golem_status golem_adapter_descriptor_current(const char *id, const char *session,
                                              golem_adapter_descriptor *out)
{
    if (!out || !id || !session || strlen(id) >= GOLEM_ADAPTER_ID_CAPACITY ||
        strlen(session) >= GOLEM_ADAPTER_ID_CAPACITY)
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_adapter_descriptor d = {0};
    d.version = d.protocol_version = 1;
    d.current_agent = true;
    strcpy(d.adapter_id, id);
    strcpy(d.session_id, session);
    /* Stage participation describes the workflow, not verified execution support. */
    d.stages = GOLEM_ADAPTER_ALL_STAGES;
    d.effect = GOLEM_EFFECT_UNKNOWN;
    golem_status s = golem_adapter_descriptor_validate(&d);
    if (s == GOLEM_OK)
        *out = d;
    return s;
}
static bool contains_tool(const golem_adapter_descriptor *d, const golem_harness_tool *tool)
{
    for (size_t i = 0; i < d->tool_count; ++i)
        if (!strcmp(d->tools[i].id, tool->id) &&
            !memcmp(&d->tools[i].digest, &tool->digest, sizeof(tool->digest)))
            return true;
    return false;
}
golem_status golem_harness_compatible(const golem_adapter_descriptor *c,
                                      const golem_adapter_descriptor *o,
                                      const golem_harness_requirements *r)
{
    golem_status s = golem_adapter_descriptor_validate(c);
    if (s == GOLEM_OK)
        s = golem_adapter_descriptor_validate(o);
    if (s != GOLEM_OK)
        return s;
    if (!r || r->size != sizeof(*r) || r->version != 1 || !r->stages ||
        (r->stages & ~GOLEM_ADAPTER_ALL_STAGES) || (r->features & ~GOLEM_HARNESS_ALL_FEATURES) ||
        !r->inputs || (r->inputs & ~GOLEM_INPUT_ALL) || r->sandbox < GOLEM_SANDBOX_UNKNOWN ||
        r->sandbox > GOLEM_SANDBOX_VM || r->simulation < GOLEM_HARNESS_UNKNOWN ||
        r->simulation > GOLEM_HARNESS_YES ||
        (r->effect != GOLEM_EFFECT_LOCAL && r->effect != GOLEM_EFFECT_EXTERNAL) ||
        !tools_valid(r->tools, r->tool_count))
        return GOLEM_ERR_INVALID_ARGUMENT;
    if (strcmp(c->adapter_id, o->adapter_id) || strcmp(c->session_id, o->session_id) ||
        c->current_agent != o->current_agent || strcmp(c->adapter_version, o->adapter_version))
        return GOLEM_ERR_IDENTITY_MISMATCH;
    if ((r->stages & c->stages & o->stages) != r->stages ||
        (r->features & c->features_supported & o->features_supported) != r->features ||
        (r->inputs & c->inputs_supported & o->inputs_supported) != r->inputs ||
        (r->sandbox && (c->sandbox != r->sandbox || o->sandbox != r->sandbox)) ||
        (r->simulation && (c->simulation != r->simulation || o->simulation != r->simulation)) ||
        c->effect == GOLEM_EFFECT_UNKNOWN || c->effect != o->effect ||
        (r->effect == GOLEM_EFFECT_LOCAL && c->effect != GOLEM_EFFECT_LOCAL))
        return GOLEM_ERR_POLICY_DENIED;
    for (size_t i = 0; i < r->tool_count; ++i)
        if (!contains_tool(c, &r->tools[i]) || !contains_tool(o, &r->tools[i]))
            return GOLEM_ERR_POLICY_DENIED;
    return GOLEM_OK;
}
