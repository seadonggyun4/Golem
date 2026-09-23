#include "internal.h"
#include <string.h>

golem_status golem_journal_chain_extend(const golem_digest *previous, golem_bytes bytes,
                                        golem_digest *out)
{
    golem_digest frame;
    golem_status status = golem_digest_bytes(bytes, &frame);
    if (status != GOLEM_OK)
        return status;
    static const char domain[] = "golem.journal.chain.v1";
    uint8_t binding[sizeof(domain) - 1 + 2 * GOLEM_DIGEST_SIZE];
    memcpy(binding, domain, sizeof(domain) - 1);
    memcpy(binding + sizeof(domain) - 1, previous->bytes, GOLEM_DIGEST_SIZE);
    memcpy(binding + sizeof(domain) - 1 + GOLEM_DIGEST_SIZE, frame.bytes, GOLEM_DIGEST_SIZE);
    return golem_digest_bytes((golem_bytes){binding, sizeof(binding)}, out);
}

golem_status golem_journal_inspect(golem_bytes bytes, golem_journal_inspection *out)
{
    if (out == NULL || (bytes.data == NULL && bytes.size != 0))
        return GOLEM_ERR_INVALID_ARGUMENT;
    golem_journal_inspection report = {0};
    golem_status status = golem_digest_bytes(bytes, &report.source_digest);
    if (status != GOLEM_OK)
        return status;
    golem_journal_reader reader;
    status = golem_journal_reader_init(&reader, bytes);
    if (status != GOLEM_OK)
        return status;
    (void)golem_diagnostic_clear(&report.failure);
    for (;;) {
        golem_journal_record record;
        bool present = false;
        size_t start = reader.offset;
        report.stream_status =
            golem_journal_reader_next(&reader, &record, &present, &report.failure);
        if (report.stream_status != GOLEM_OK || !present)
            break;
        status = golem_journal_chain_extend(
            &report.chain_head, (golem_bytes){bytes.data + start, reader.offset - start},
            &report.chain_head);
        if (status != GOLEM_OK)
            return status;
        report.valid_bytes = reader.offset;
        ++report.records;
    }
    *out = report;
    return GOLEM_OK;
}
