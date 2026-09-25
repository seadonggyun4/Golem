#include "../../src/common/json.h"
#include "test.h"
#include <string.h>

int main(void)
{
    /* Literal backslashes are data, not decoded NUL characters. Exercise both
     * object names and values: json-c cannot retain NUL in object names. */
    for (size_t slashes = 1; slashes <= 12; ++slashes) {
        for (unsigned key = 0; key < 2; ++key) {
            char text[128];
            size_t n = 0;
            const char *prefix = key ? "{\"" : "{\"value\":\"";
            memcpy(text, prefix, strlen(prefix));
            n = strlen(prefix);
            memset(text + n, '\\', slashes);
            n += slashes;
            const char *suffix = key ? "u0000\":1}" : "u0000\"}";
            memcpy(text + n, suffix, strlen(suffix));
            n += strlen(suffix);
            struct json_object *out = NULL;
            golem_status st = golem_json_parse((golem_bytes){(const uint8_t *)text, n},
                                               sizeof(text), &out);
            CHECK(st == (slashes % 2 ? GOLEM_ERR_PARSE : GOLEM_OK));
            if (slashes % 2)
                CHECK(out == NULL);
            json_object_put(out);
        }
    }
    const char *bad[] = {"{\"a\":1,\"\\u0061\":2}", "{\"a\":{\"b\":1,\"b\":2}}",
                         "{\"a\":\"\\u0000\"}", "{\"a\\u0000b\":1}", "{\"a\":1} {}"};
    for (size_t i = 0; i < sizeof(bad) / sizeof(*bad); ++i) {
        struct json_object *out = NULL;
        CHECK(golem_json_parse((golem_bytes){(const uint8_t *)bad[i], strlen(bad[i])},
                               1024, &out) == GOLEM_ERR_PARSE);
        CHECK(out == NULL);
    }
    return 0;
}
