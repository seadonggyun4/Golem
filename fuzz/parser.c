#include "golem/lineage.h"
#include "check.h"

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
    golem_receipt r;
    memset(&r, 0xa5, sizeof(r));
    unsigned char saved[sizeof(r)]; memcpy(saved, &r, sizeof(r));
    if (golem_receipt_decode((golem_bytes){data, size}, &r) == GOLEM_OK) {
        uint8_t wire[GOLEM_RECEIPT_SIZE]; size_t n;
        REQUIRE(golem_receipt_encode(&r, wire, sizeof(wire), &n) == GOLEM_OK);
        REQUIRE(n == size && memcmp(wire, data, n) == 0);
    } else REQUIRE(memcmp(saved, &r, sizeof(r)) == 0);
    golem_digest digest;
    if (golem_digest_parse((golem_string_view){(const char *)data, size}, &digest) == GOLEM_OK) {
        char text[65]; size_t n; golem_digest again;
        REQUIRE(golem_digest_format(&digest, text, sizeof(text), &n) == GOLEM_OK);
        REQUIRE(golem_digest_parse((golem_string_view){text, n - 1}, &again) == GOLEM_OK);
        REQUIRE(memcmp(digest.bytes, again.bytes, sizeof(digest.bytes)) == 0);
    }
    golem_lineage *graph = NULL;
    if (golem_lineage_decode((golem_bytes){data, size}, NULL, &graph, NULL) == GOLEM_OK) {
        size_t n;
        REQUIRE(golem_lineage_encode(graph, NULL, 0, &n, NULL) == GOLEM_ERR_BUFFER_TOO_SMALL);
        REQUIRE(n == size);
        uint8_t *wire = malloc(n); REQUIRE(wire != NULL);
        REQUIRE(golem_lineage_encode(graph, wire, n, &n, NULL) == GOLEM_OK);
        REQUIRE(memcmp(wire, data, n) == 0);
        free(wire); golem_lineage_free(graph);
    } else REQUIRE(graph == NULL);
    return 0;
}
