#include "golem/adapter_descriptor.h"
#include "test.h"
#include <string.h>

static int example(golem_adapter_descriptor *out)
{
    golem_adapter_capability cap = {1, "local.noop", GOLEM_ADAPTER_ALL_STAGES, GOLEM_EFFECT_LOCAL,
                                    true};
    CHECK(golem_adapter_descriptor_from_v1(&cap, out) == GOLEM_OK);
    return 0;
}
static int codec(void)
{
    golem_adapter_descriptor d, decoded;
    CHECK(example(&d) == 0);
    const char *golden =
        "{\"adapter_id\":\"local.noop\",\"adapter_version\":\"\",\"current_agent\":0,\"domain\":"
        "\"golem.adapter-descriptor.v1\",\"effect\":1,\"features_known\":0,\"features_supported\":"
        "0,\"hidden_prompt_known\":0,\"inputs_known\":0,\"inputs_supported\":0,\"protocol_"
        "version\":1,\"sandbox\":0,\"schema_version\":1,\"session_id\":\"\",\"simulation\":2,"
        "\"stages\":63,\"tools\":[]}";
    char buf[GOLEM_DESCRIPTOR_MAX_BYTES], again[GOLEM_DESCRIPTOR_MAX_BYTES];
    size_t n, m;
    CHECK(golem_adapter_descriptor_encode(&d, NULL, 0, &n) == GOLEM_ERR_BUFFER_TOO_SMALL);
    memset(buf, 'x', sizeof(buf));
    CHECK(golem_adapter_descriptor_encode(&d, buf, n - 1, &m) == GOLEM_ERR_BUFFER_TOO_SMALL);
    CHECK(buf[0] == 'x' && n == m);
    CHECK(golem_adapter_descriptor_encode(&d, buf, sizeof(buf), &n) == GOLEM_OK);
    CHECK(n == strlen(golden) && !memcmp(buf, golden, n));
    CHECK(golem_adapter_descriptor_decode((golem_bytes){(uint8_t *)buf, n}, &decoded) == GOLEM_OK);
    CHECK(golem_adapter_descriptor_encode(&decoded, again, sizeof(again), &m) == GOLEM_OK &&
          n == m && !memcmp(buf, again, n));
    golem_digest hash, expected;
    CHECK(golem_adapter_descriptor_digest(&d, &hash) == GOLEM_OK);
    CHECK(golem_digest_bytes((golem_bytes){(const uint8_t *)golden, strlen(golden)}, &expected) ==
          GOLEM_OK);
    CHECK(!memcmp(&hash, &expected, sizeof(hash)));
    golem_adapter_capability cap;
    CHECK(golem_adapter_descriptor_to_v1(&d, &cap) == GOLEM_OK && cap.simulation &&
          cap.stages == 63);
    d.inputs_known = d.inputs_supported = GOLEM_INPUT_JSON;
    CHECK(golem_adapter_descriptor_to_v1(&d, &cap) == GOLEM_ERR_INVALID_STATE);
    d.tool_count = GOLEM_DESCRIPTOR_MAX_TOOLS;
    for (size_t i = 0; i < d.tool_count; ++i) {
        (void)snprintf(d.tools[i].id, sizeof(d.tools[i].id), "tool-%02zu", d.tool_count - i);
        d.tools[i].digest = hash;
    }
    CHECK(golem_adapter_descriptor_encode(&d, buf, sizeof(buf), &n) == GOLEM_OK);
    CHECK(golem_adapter_descriptor_decode((golem_bytes){(uint8_t *)buf, n}, &decoded) == GOLEM_OK);
    CHECK(!strcmp(decoded.tools[0].id, "tool-01") &&
          decoded.tool_count == GOLEM_DESCRIPTOR_MAX_TOOLS);
    CHECK(golem_adapter_descriptor_encode(&decoded, again, sizeof(again), &m) == GOLEM_OK &&
          n == m && !memcmp(buf, again, n));
    return 0;
}
static int invalid(void)
{
    golem_adapter_descriptor d, out;
    CHECK(example(&d) == 0);
    char buf[GOLEM_DESCRIPTOR_MAX_BYTES + 1];
    size_t n;
    CHECK(golem_adapter_descriptor_encode(&d, buf, sizeof(buf), &n) == GOLEM_OK);
    for (size_t i = 0; i < n; ++i) {
        out.version = 999;
        CHECK(golem_adapter_descriptor_decode((golem_bytes){(uint8_t *)buf, i}, &out) != GOLEM_OK &&
              out.version == 999);
    }
    buf[n] = 0;
    CHECK(golem_adapter_descriptor_decode((golem_bytes){(uint8_t *)buf, n + 1}, &out) != GOLEM_OK);
    CHECK(golem_adapter_descriptor_decode((golem_bytes){(uint8_t *)buf, sizeof(buf)}, &out) !=
          GOLEM_OK);
    d.features_supported = 1;
    CHECK(golem_adapter_descriptor_validate(&d) != GOLEM_OK);
    d.features_known = 8;
    CHECK(golem_adapter_descriptor_validate(&d) != GOLEM_OK);
    CHECK(example(&d) == 0);
    d.stages = 0;
    CHECK(golem_adapter_descriptor_validate(&d) != GOLEM_OK);
    d.stages = 128;
    CHECK(golem_adapter_descriptor_validate(&d) != GOLEM_OK);
    CHECK(example(&d) == 0);
    d.tool_count = 65;
    CHECK(golem_adapter_descriptor_validate(&d) != GOLEM_OK);
    d.tool_count = 2;
    strcpy(d.tools[0].id, "duplicate");
    strcpy(d.tools[1].id, "duplicate");
    CHECK(golem_adapter_descriptor_validate(&d) != GOLEM_OK);
    CHECK(example(&d) == 0);
    memset(d.adapter_id, 'x', sizeof(d.adapter_id));
    CHECK(golem_adapter_descriptor_validate(&d) != GOLEM_OK);
    CHECK(golem_adapter_descriptor_validate(NULL) == GOLEM_ERR_INVALID_ARGUMENT);
    CHECK(golem_adapter_descriptor_from_v1(NULL, &out) == GOLEM_ERR_INVALID_ARGUMENT);
    return 0;
}
static int compatibility(void)
{
    golem_adapter_descriptor c, o;
    CHECK(example(&c) == 0);
    c.features_known = c.features_supported = 7;
    c.inputs_known = c.inputs_supported = 15;
    c.sandbox = GOLEM_SANDBOX_OS;
    c.tool_count = 1;
    strcpy(c.tools[0].id, "read");
    c.tools[0].digest.bytes[0] = 1;
    o = c;
    golem_harness_requirements r = {0};
    r.size = sizeof(r);
    r.version = 1;
    r.stages = 1;
    r.inputs = 1;
    r.features = 1;
    r.sandbox = GOLEM_SANDBOX_OS;
    r.simulation = GOLEM_HARNESS_YES;
    r.effect = GOLEM_EFFECT_LOCAL;
    r.tool_count = 1;
    r.tools[0] = c.tools[0];
    CHECK(golem_harness_compatible(&c, &o, &r) == GOLEM_OK);
    o.features_supported = 0;
    CHECK(golem_harness_compatible(&c, &o, &r) == GOLEM_ERR_POLICY_DENIED);
    o = c;
    o.inputs_supported = 0;
    CHECK(golem_harness_compatible(&c, &o, &r) == GOLEM_ERR_POLICY_DENIED);
    o = c;
    o.sandbox = GOLEM_SANDBOX_UNKNOWN;
    CHECK(golem_harness_compatible(&c, &o, &r) == GOLEM_ERR_POLICY_DENIED);
    o = c;
    o.sandbox = GOLEM_SANDBOX_VM;
    CHECK(golem_harness_compatible(&c, &o, &r) == GOLEM_ERR_POLICY_DENIED);
    o = c;
    o.tools[0].digest.bytes[0] = 2;
    CHECK(golem_harness_compatible(&c, &o, &r) == GOLEM_ERR_POLICY_DENIED);
    o = c;
    strcpy(o.adapter_version, "v2");
    CHECK(golem_harness_compatible(&c, &o, &r) == GOLEM_ERR_IDENTITY_MISMATCH);
    o = c;
    r.inputs = 0;
    CHECK(golem_harness_compatible(&c, &o, &r) == GOLEM_ERR_INVALID_ARGUMENT);
    r.inputs = 1;
    r.features = 8;
    CHECK(golem_harness_compatible(&c, &o, &r) == GOLEM_ERR_INVALID_ARGUMENT);
    for (unsigned i = 0; i < 8; ++i)
        for (unsigned j = 0; j < 8; ++j)
            for (unsigned k = 0; k < 8; ++k) {
                c.features_supported = i;
                o = c;
                o.features_supported = j;
                r.features = k;
                CHECK(golem_harness_compatible(&c, &o, &r) ==
                      ((i & j & k) == k ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED));
            }
    return 0;
}
static int current(void)
{
    const char *ids[] = {"codex", "claude"};
    for (size_t i = 0; i < 2; ++i) {
        golem_adapter_descriptor d;
        CHECK(golem_adapter_descriptor_current(ids[i], "", &d) == GOLEM_OK);
        CHECK(d.current_agent && !*d.session_id && !*d.adapter_version && !d.features_known &&
              !d.inputs_known && !d.sandbox && !d.simulation && !d.hidden_prompt_known &&
              !d.effect);
        CHECK(golem_adapter_descriptor_current(ids[i], "session-1", &d) == GOLEM_OK &&
              !strcmp(d.session_id, "session-1"));
        golem_adapter_capability cap;
        CHECK(golem_adapter_descriptor_to_v1(&d, &cap) == GOLEM_ERR_INVALID_STATE);
    }
    return 0;
}
int main(int argc, char **argv)
{
    CHECK(argc == 2);
    if (!strcmp(argv[1], "codec"))
        return codec();
    if (!strcmp(argv[1], "invalid"))
        return invalid();
    if (!strcmp(argv[1], "compatibility"))
        return compatibility();
    if (!strcmp(argv[1], "current"))
        return current();
    return 1;
}
