#include "../../src/inventory/internal.h"
#include "test.h"
#include <string.h>

int main(int argc, char **argv)
{
    CHECK(argc == 4 || argc == 5);
    golem_bytes policy = {(const uint8_t *)argv[2], strlen(argv[2])};
    golem_inventory_reply out = {0};
    golem_status st = golem_inventory_policy_validate(policy, NULL);
    if (st == GOLEM_OK && !strcmp(argv[1], "capture"))
        st = golem_inventory_capture(argv[3], policy, &out, NULL);
    else if (st == GOLEM_OK && argc == 5) {
        struct json_object *a = json_object_from_file(argv[3]), *b = json_object_from_file(argv[4]);
        const char *old = json_object_to_json_string_ext(a, JSON_C_TO_STRING_PLAIN);
        const char *current = json_object_to_json_string_ext(b, JSON_C_TO_STRING_PLAIN);
        st = golem_inventory_compare((golem_bytes){(const uint8_t *)old, strlen(old)},
                                     (golem_bytes){(const uint8_t *)current, strlen(current)},
                                     policy, &out, NULL);
        json_object_put(a);
        json_object_put(b);
    } else if (st == GOLEM_OK)
        st = GOLEM_ERR_INVALID_ARGUMENT;
    if (st == GOLEM_OK)
        CHECK(fwrite(out.data, 1, out.size, stdout) == out.size);
    else
        fprintf(stderr, "%s\n", golem_status_string(st));
    golem_inventory_reply_free(&out);
    return st == GOLEM_OK ? 0 : 1;
}
