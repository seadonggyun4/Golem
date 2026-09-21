#include "internal.h"
#include <string.h>

static golem_status validate(const golem_receipt *r)
{
    if (r == NULL) return GOLEM_ERR_INVALID_ARGUMENT;
    if (r->version != GOLEM_RECEIPT_VERSION || r->algorithm != GOLEM_DIGEST_SHA256)
        return GOLEM_ERR_UNSUPPORTED_VERSION;
    if (r->size > GOLEM_SHA256_MAX_BYTES) return GOLEM_ERR_OVERFLOW;
    return GOLEM_OK;
}

golem_status golem_receipt_encode(const golem_receipt *r, void *buffer, size_t capacity, size_t *required)
{
    if (required == NULL || (buffer == NULL && capacity != 0)) return GOLEM_ERR_INVALID_ARGUMENT;
    golem_status status = validate(r);
    if (status != GOLEM_OK) return status;
    *required = GOLEM_RECEIPT_SIZE;
    if (capacity < GOLEM_RECEIPT_SIZE) return GOLEM_ERR_BUFFER_TOO_SMALL;
    uint8_t encoded[GOLEM_RECEIPT_SIZE] = {'H', 'W', 'E', 'R', 1, 0, 1, 0};
    for (size_t i = 0; i < 8; ++i) encoded[8 + i] = (uint8_t)(r->size >> (8 * i));
    memcpy(encoded + 16, r->digest.bytes, GOLEM_DIGEST_SIZE);
    memcpy(buffer, encoded, sizeof(encoded));
    return GOLEM_OK;
}

golem_status golem_receipt_decode(golem_bytes bytes, golem_receipt *out)
{
    if (out == NULL || (bytes.data == NULL && bytes.size != 0)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (bytes.size != GOLEM_RECEIPT_SIZE || memcmp(bytes.data, "HWER", 4) != 0) return GOLEM_ERR_PARSE;
    golem_receipt r = {0};
    r.version = (uint16_t)(bytes.data[4] | ((uint16_t)bytes.data[5] << 8));
    r.algorithm = (uint16_t)(bytes.data[6] | ((uint16_t)bytes.data[7] << 8));
    for (size_t i = 0; i < 8; ++i) r.size |= (uint64_t)bytes.data[8 + i] << (8 * i);
    memcpy(r.digest.bytes, bytes.data + 16, GOLEM_DIGEST_SIZE);
    golem_status status = validate(&r);
    if (status == GOLEM_OK) *out = r;
    return status;
}

golem_status golem_evidence_receipt_store(golem_evidence_store *store,
    const golem_receipt *receipt, golem_digest *out, golem_diagnostic *d)
{
    if (out == NULL) return golem_evidence_report(d, GOLEM_ERR_INVALID_ARGUMENT, NULL);
    uint8_t bytes[GOLEM_RECEIPT_SIZE];
    size_t required;
    golem_status status = golem_receipt_encode(receipt, bytes, sizeof(bytes), &required);
    golem_receipt stored;
    if (status == GOLEM_OK)
        status = golem_evidence_put(store, (golem_bytes){bytes, sizeof(bytes)}, &stored, d);
    if (status == GOLEM_OK) *out = stored.digest;
    return golem_evidence_report(d, status, NULL);
}
