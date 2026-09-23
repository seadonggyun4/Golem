#include "../src/daemon/admission_internal.h"
#include "check.h"

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    if (size > GA_FRAME_SIZE * 16)
        return 0;
    ga_model *model = calloc(1, sizeof(*model));
    REQUIRE(model);
    golem_admission_checkpoint cp = {0};
    for (size_t offset = 0; size - offset >= GA_FRAME_SIZE; offset += GA_FRAME_SIZE) {
        ga_event event;
        memset(&event, 0xa5, sizeof(event));
        unsigned char saved[sizeof(event)];
        memcpy(saved, &event, sizeof(event));
        golem_status s = ga_decode(data + offset, cp, &event);
        if (s != GOLEM_OK) {
            REQUIRE(!memcmp(saved, &event, sizeof(event)));
            break;
        }
        uint8_t encoded[GA_FRAME_SIZE];
        REQUIRE(ga_encode(&event, cp, encoded) == GOLEM_OK);
        REQUIRE(!memcmp(encoded, data + offset, GA_FRAME_SIZE));
        if (ga_apply(model, &event) != GOLEM_OK)
            break;
        ++cp.records;
        memcpy(cp.head.bytes, encoded + 480, 32);
    }
    /* Rehash a raw frame to exercise schema validation past the integrity gate. */
    if (size == GA_FRAME_SIZE) {
        uint8_t frame[GA_FRAME_SIZE];
        memcpy(frame, data, sizeof(frame));
        memcpy(frame, "GADM0001", 8);
        memset(frame + 8, 0, 40);
        frame[8] = 1;
        golem_digest digest;
        REQUIRE(golem_digest_bytes((golem_bytes){frame, 480}, &digest) == GOLEM_OK);
        memcpy(frame + 480, digest.bytes, 32);
        ga_event event;
        if (ga_decode(frame, (golem_admission_checkpoint){0}, &event) == GOLEM_OK) {
            *model = (ga_model){0};
            (void)ga_apply(model, &event);
        }
    }
    free(model);
    return 0;
}
