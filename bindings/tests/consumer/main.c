#include "golem/binding.h"
#include <string.h>
int main(void)
{
    const char *json = "{\"id\":\"installed\",\"goal\":\"validate\",\"scope\":[\"local\"],"
        "\"permissions\":{\"planning\":\"DENY\"},\"stages\":[\"planning\"],"
        "\"acceptance\":[\"checked\"],\"expected_artifacts\":[],\"required_gates\":[]}";
    char *out = NULL; size_t size = 0;
    if (golem_binding_abi_version() != 1 || golem_binding_call(1, (const uint8_t *)json, strlen(json), &out, &size) != 0) return 1;
    int failed = out == NULL || size != strlen(out) || strstr(out, "\"valid\":true") == NULL;
    golem_binding_free(out); return failed;
}
