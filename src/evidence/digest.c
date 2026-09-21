#include "internal.h"
#include <string.h>

golem_status golem_evidence_report(golem_diagnostic *d, golem_status status, const char *message)
{
    if (d != NULL) (void)golem_diagnostic_set(d, status, GOLEM_DIAGNOSTIC_NO_OFFSET, message);
    return status;
}

golem_status golem_evidence_hash_begin(EVP_MD_CTX **out)
{
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    if (ctx == NULL) return GOLEM_ERR_OUT_OF_MEMORY;
    if (EVP_DigestInit_ex(ctx, EVP_sha256(), NULL) != 1) {
        EVP_MD_CTX_free(ctx);
        return GOLEM_ERR_CRYPTO;
    }
    *out = ctx;
    return GOLEM_OK;
}

golem_status golem_evidence_hash_end(EVP_MD_CTX *ctx, golem_digest *out)
{
    golem_digest digest;
    unsigned int size = 0;
    if (EVP_DigestFinal_ex(ctx, digest.bytes, &size) != 1 || size != GOLEM_DIGEST_SIZE)
        return GOLEM_ERR_CRYPTO;
    *out = digest;
    return GOLEM_OK;
}

golem_status golem_digest_bytes(golem_bytes bytes, golem_digest *out)
{
    if (out == NULL || (bytes.data == NULL && bytes.size != 0)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (bytes.size > GOLEM_SHA256_MAX_BYTES) return GOLEM_ERR_OVERFLOW;
    EVP_MD_CTX *ctx = NULL;
    golem_status status = golem_evidence_hash_begin(&ctx);
    if (status == GOLEM_OK && bytes.size != 0 && EVP_DigestUpdate(ctx, bytes.data, bytes.size) != 1)
        status = GOLEM_ERR_CRYPTO;
    if (status == GOLEM_OK) status = golem_evidence_hash_end(ctx, out);
    EVP_MD_CTX_free(ctx);
    return status;
}

golem_status golem_digest_parse(golem_string_view hex, golem_digest *out)
{
    if (out == NULL || (hex.data == NULL && hex.size != 0)) return GOLEM_ERR_INVALID_ARGUMENT;
    if (hex.size != 64) return GOLEM_ERR_PARSE;
    golem_digest value = {{0}};
    for (size_t i = 0; i < 64; ++i) {
        unsigned char c = (unsigned char)hex.data[i];
        unsigned int digit;
        if (c >= '0' && c <= '9') digit = c - '0';
        else if (c >= 'a' && c <= 'f') digit = c - 'a' + 10u;
        else return GOLEM_ERR_PARSE;
        value.bytes[i / 2] |= (uint8_t)(digit << ((i % 2 == 0) ? 4 : 0));
    }
    *out = value;
    return GOLEM_OK;
}

golem_status golem_digest_format(const golem_digest *digest, char *buffer, size_t capacity, size_t *required)
{
    if (digest == NULL || required == NULL || (buffer == NULL && capacity != 0))
        return GOLEM_ERR_INVALID_ARGUMENT;
    *required = GOLEM_DIGEST_HEX_CAPACITY;
    if (capacity < GOLEM_DIGEST_HEX_CAPACITY) return GOLEM_ERR_BUFFER_TOO_SMALL;
    const char hex[] = "0123456789abcdef";
    for (size_t i = 0; i < GOLEM_DIGEST_SIZE; ++i) {
        buffer[i * 2] = hex[digest->bytes[i] >> 4];
        buffer[i * 2 + 1] = hex[digest->bytes[i] & 15];
    }
    buffer[64] = '\0';
    return GOLEM_OK;
}
