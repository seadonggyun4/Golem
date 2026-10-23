#define _POSIX_C_SOURCE 200809L
#include "../src/intent/journal.h"
#include "../src/intent/schema.h"
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static golem_status registration_guard(void *context)
{
    /* Trusted host holds common-dir EX and validates the reviewed owner plan.
     * This private bridge cannot dispatch product actions or choose a lane. */
    return context ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED;
}

typedef struct authority_chain {
    golem_digest initial, current, successor, target;
    bool found, target_seen, allow_pending;
    uint64_t stop_before;
} authority_chain;

static golem_status successor_key(const golem_digest *previous, golem_digest *out)
{
    const char domain[] = "golem.intent.authority-change.v1";
    uint8_t bytes[sizeof(domain) + 32];
    memcpy(bytes, domain, sizeof(domain));
    memcpy(bytes + sizeof(domain), previous->bytes, 32);
    return golem_digest_bytes((golem_bytes){bytes, sizeof(bytes)}, out);
}

static golem_status visit_binding(void *context, const golem_digest *operation,
    const golem_digest *request, const gi_journal_operation *record)
{
    authority_chain *chain = context;
    if (chain->stop_before && record->sequence >= chain->stop_before) return GOLEM_OK;
    if (chain->allow_pending && !record->committed) return GOLEM_OK;
    bool initial = !memcmp(operation->bytes, chain->initial.bytes, 32);
    bool next = chain->found && !memcmp(operation->bytes, chain->successor.bytes, 32);
    if (!initial && !next) return GOLEM_OK;
    if (!record->committed || record->pending || record->lane != GI_QUOTA_INTAKE ||
        (initial && (chain->found || record->sequence != 1))) return GOLEM_ERR_INVALID_STATE;
    chain->current = *request;
    if (!memcmp(request->bytes, chain->target.bytes, 32)) chain->target_seen = true;
    chain->found = true;
    return successor_key(request, &chain->successor);
}

static int pending_command(int argc, char **argv)
{
    bool finish = !strcmp(argv[1], "--recover-pending-fd");
    if (argc != (finish ? 6 : 5)) return 2;
    char *end = NULL; errno = 0;
    long fd = strtol(argv[2], &end, 10);
    if (errno || !*argv[2] || *end || fd < 3 || fd > INT_MAX) return 2;
    bool initial = !strcmp(argv[4], "-");
    golem_digest target, previous = {{0}}, expected, operation, body;
    golem_status st = golem_digest_parse((golem_string_view){argv[3], strlen(argv[3])}, &target);
    if (st == GOLEM_OK && !initial)
        st = golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])}, &previous);
    if (st == GOLEM_OK && finish)
        st = golem_digest_parse((golem_string_view){argv[5], strlen(argv[5])}, &expected);
    uint8_t *payload = malloc(262145); size_t prefix = initial ? 0 : 32;
    if (!payload) st = GOLEM_ERR_OUT_OF_MEMORY;
    size_t n = 0;
    if (st == GOLEM_OK) {
        if (prefix) memcpy(payload, previous.bytes, prefix);
        n = fread(payload + prefix, 1, 262145 - prefix, stdin);
        if (ferror(stdin) || !n || n + prefix > 262144) st = GOLEM_ERR_OVERFLOW;
    }
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){payload + prefix, n}, &body);
    if (st == GOLEM_OK && memcmp(body.bytes, target.bytes, 32)) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){payload, n + prefix}, &body);
    gi_journal *j = NULL;
    if (st == GOLEM_OK) st = gi_journal_open((int)fd, &j);
    authority_chain chain = {0}; chain.allow_pending = true; chain.target = target;
    const char key[] = "golem.intent.authority-registration.v1";
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){(const uint8_t *)key, sizeof(key) - 1}, &chain.initial);
    if (st == GOLEM_OK) st = gi_journal_visit(j, visit_binding, &chain);
    if (st == GOLEM_OK && (initial ? chain.found :
        (!chain.found || chain.target_seen || memcmp(chain.current.bytes, previous.bytes, 32)))) st = GOLEM_ERR_INVALID_STATE;
    operation = chain.initial;
    if (st == GOLEM_OK && !initial) st = successor_key(&previous, &operation);
    gi_journal_pending_plan p;
    if (st == GOLEM_OK) st = gi_journal_pending_plan_get(j, &p);
    if (st == GOLEM_OK && (memcmp(p.operation.bytes, operation.bytes, 32) ||
        memcmp(p.request.bytes, target.bytes, 32) || memcmp(p.payload.bytes, body.bytes, 32) ||
        p.payload_bytes != n + prefix || (initial && p.sequence != 1))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && finish) {
        gi_journal_receipt receipt;
        st = gi_journal_pending_finish(j, &expected, registration_guard, payload, &receipt);
    }
    gi_journal_close(j); free(payload);
    if (st != GOLEM_OK) {
        printf("{\"schema\":\"golem.intent-native-recovery.v1\",\"error\":%d}\n", (int)st);
        return 1;
    }
    const golem_digest *fields[] = {&p.operation, &p.request, &p.head, &p.preparation, &p.payload, &p.snapshot};
    const char *names[] = {"operation", "request", "head", "preparation", "payload", "snapshot"};
    printf("{\"schema\":\"golem.intent-native-recovery.v1\",\"execution_authorized\":false,"
           "\"sequence\":%llu,\"payload_bytes\":%llu", (unsigned long long)p.sequence, (unsigned long long)p.payload_bytes);
    for (unsigned i = 0; i < 6; ++i) {
        char hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t size;
        if (golem_digest_format(fields[i], hex, sizeof(hex), &size) != GOLEM_OK) return 1;
        printf(",\"%s\":\"%s\"", names[i], hex);
    }
    printf("}\n"); return 0;
}

static int alias_command(int argc, char **argv)
{
    bool damage = !strcmp(argv[1], "--plan-damage-fd") || !strcmp(argv[1], "--preserve-damage-fd") ||
        !strcmp(argv[1], "--finish-damage-fd") || !strcmp(argv[1], "--detach-damage-fd");
    int fragment_action = (!strcmp(argv[1], "--preserve-fragment-fd") || !strcmp(argv[1], "--preserve-damage-fd")) ? 0 :
        (!strcmp(argv[1], "--finish-fragment-fd") || !strcmp(argv[1], "--finish-damage-fd")) ? 1 :
        (!strcmp(argv[1], "--detach-fragment-fd") || !strcmp(argv[1], "--detach-damage-fd")) ? 2 : -1;
    bool fragment = damage || fragment_action >= 0 || !strcmp(argv[1], "--plan-fragment-fd");
    bool remove = !strcmp(argv[1], "--remove-alias-fd");
    bool quarantine = !strcmp(argv[1], "--quarantine-partial-fd");
    bool replace = !strcmp(argv[1], "--replace-payload-fd");
    bool finish_envelope = !strcmp(argv[1], "--finish-envelope-fd");
    bool envelope = finish_envelope || !strcmp(argv[1], "--plan-envelope-fd");
    bool partial = fragment || envelope || quarantine || replace || !strcmp(argv[1], "--plan-partial-fd");
    if (argc != (fragment_action >= 0 ? 9 : quarantine || finish_envelope ? 8 : remove || replace ? 7 : 6)) return 2;
    char *end = NULL; errno = 0;
    long fd = strtol(argv[2], &end, 10);
    if (errno || !*argv[2] || *end || fd < 3 || fd > INT_MAX) return 2;
    if (strlen(argv[5]) != 1 || argv[5][0] < '0' || argv[5][0] > '2') return 2;
    unsigned kind = (unsigned)(argv[5][0] - '0');
    bool initial = !strcmp(argv[4], "-");
    golem_digest target, previous = {{0}}, expected, body, operation, approval, preservation;
    golem_status st = golem_digest_parse((golem_string_view){argv[3], strlen(argv[3])}, &target);
    if (st == GOLEM_OK && !initial) st = golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])}, &previous);
    if (st == GOLEM_OK && (remove || quarantine || replace || finish_envelope || fragment_action >= 0))
        st = golem_digest_parse((golem_string_view){argv[6], strlen(argv[6])}, &expected);
    if (st == GOLEM_OK && (quarantine || finish_envelope || fragment_action >= 0))
        st = golem_digest_parse((golem_string_view){argv[7], strlen(argv[7])}, &approval);
    if (st == GOLEM_OK && fragment_action >= 0)
        st = golem_digest_parse((golem_string_view){argv[8], strlen(argv[8])}, &preservation);
    if (replace && kind != 1) return 2;
    uint8_t *payload = malloc(262145); size_t prefix = initial ? 0 : 32, n = 0;
    if (!payload) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) {
        if (prefix) memcpy(payload, previous.bytes, prefix);
        n = fread(payload + prefix, 1, 262145 - prefix, stdin);
        if (ferror(stdin) || !n || n + prefix > 262144) st = GOLEM_ERR_OVERFLOW;
    }
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){payload + prefix, n}, &body);
    if (st == GOLEM_OK && memcmp(body.bytes, target.bytes, 32)) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){payload, n + prefix}, &body);
    gi_journal *j = NULL; gi_journal_alias_plan a; gi_journal_partial_plan p; gi_journal_envelope_plan e;
    gi_journal_fragment_plan f;
    if (st == GOLEM_OK) st = gi_journal_open((int)fd, &j);
    if (st == GOLEM_OK) {
        if (fragment) { st = damage ? gi_journal_damage_observe(j, kind, &f) : gi_journal_fragment_observe(j, kind, &f);
            if (st == GOLEM_OK) { p = f.original; a = p.source; } }
        else if (envelope) { st = gi_journal_envelope_observe(j, kind, &e); if (st == GOLEM_OK) { p = e.partial; a = p.source; } }
        else if (partial) { st = gi_journal_partial_observe(j, kind, &p); if (st == GOLEM_OK) a = p.source; }
        else st = gi_journal_alias_observe(j, kind, &a);
    }
    authority_chain chain = {0}; chain.target = target;
    const char key[] = "golem.intent.authority-registration.v1";
    if (st == GOLEM_OK) {
        chain.stop_before = a.sequence;
        st = golem_digest_bytes((golem_bytes){(const uint8_t *)key, sizeof(key) - 1}, &chain.initial);
    }
    if (st == GOLEM_OK) st = damage ? gi_journal_damage_visit(j, kind, visit_binding, &chain) :
                            fragment ? gi_journal_fragment_visit(j, kind, visit_binding, &chain) :
                            envelope ? gi_journal_envelope_visit(j, kind, visit_binding, &chain) :
                                       gi_journal_visit(j, visit_binding, &chain);
    if (st == GOLEM_OK && (initial ? (chain.found || a.sequence != 1) :
        (!chain.found || chain.target_seen || memcmp(chain.current.bytes, previous.bytes, 32)))) st = GOLEM_ERR_INVALID_STATE;
    operation = chain.initial;
    if (st == GOLEM_OK && !initial) st = successor_key(&previous, &operation);
    if (st == GOLEM_OK && (memcmp(a.operation.bytes, operation.bytes, 32) ||
        memcmp(a.request.bytes, target.bytes, 32) || memcmp(a.payload.bytes, body.bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && partial && p.payload_bytes != n + prefix) st = GOLEM_ERR_INVALID_STATE;
    if (st == GOLEM_OK && remove) st = gi_journal_alias_remove(j, kind, &expected, registration_guard, payload, &a);
    if (st == GOLEM_OK && quarantine)
        st = gi_journal_partial_quarantine(j, kind, &expected, &approval, registration_guard, payload, &p);
    if (st == GOLEM_OK && replace)
        st = gi_journal_payload_replace(j, &expected, (golem_bytes){payload, n + prefix}, registration_guard, payload, &p);
    if (st == GOLEM_OK && finish_envelope)
        st = gi_journal_envelope_finish(j, kind, &expected, &approval, registration_guard, payload, &e);
    if (st == GOLEM_OK && fragment_action >= 0)
        st = damage ? gi_journal_damage_apply(j, kind, (unsigned)fragment_action, &expected, &approval, &preservation,
                                       registration_guard, payload, &f) :
            gi_journal_fragment_apply(j, kind, (unsigned)fragment_action, &expected, &approval, &preservation,
                                       registration_guard, payload, &f);
    if (st == GOLEM_OK && fragment) p = f.original;
    if (st == GOLEM_OK && envelope) p = e.partial;
    if (st == GOLEM_OK && partial) a = p.source;
    if (st == GOLEM_OK && envelope) a.snapshot = e.snapshot;
    if (st == GOLEM_OK && fragment) a.snapshot = f.snapshot;
    gi_journal_close(j); free(payload);
    if (st != GOLEM_OK) {
        printf("{\"schema\":\"%s\",\"error\":%d}\n",
            damage ? "golem.intent-damage.v1" : fragment ? "golem.intent-fragment.v1" : envelope ? "golem.intent-envelope.v1" : partial ? "golem.intent-partial.v1" : "golem.intent-alias.v1", (int)st); return 1;
    }
    printf("{\"schema\":\"%s\",\"execution_authorized\":false,\"kind\":%u,"
           "\"sequence\":%llu,\"device\":%llu,\"inode\":%llu,\"bytes\":%llu,\"present\":%s,"
           "\"committed\":%llu,\"pending\":%s", damage ? "golem.intent-damage.v1" : fragment ? "golem.intent-fragment.v1" : envelope ? "golem.intent-envelope.v1" : partial ? "golem.intent-partial.v1" : "golem.intent-alias.v1",
           kind, (unsigned long long)a.sequence,
           (unsigned long long)a.device, (unsigned long long)a.inode, (unsigned long long)a.bytes,
           a.present ? "true" : "false", (unsigned long long)a.state.committed, a.state.pending ? "true" : "false");
    const golem_digest *digests[] = {&a.operation, &a.request, &a.preparation, &a.payload, &a.final_digest, &a.snapshot, &a.state.head};
    const char *names[] = {"operation", "request", "preparation", "payload", "final_digest", "snapshot", "head"};
    for (unsigned i = 0; i < 7; ++i) {
        char hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t size;
        if (golem_digest_format(digests[i], hex, sizeof(hex), &size) != GOLEM_OK) return 1;
        printf(",\"%s\":\"%s\"", names[i], hex);
    }
    printf(",\"usage\":[");
    for (unsigned lane = 0; lane < GI_QUOTA_LANES; ++lane) {
        printf("%s[", lane ? "," : "");
        for (unsigned axis = 0; axis < GI_QUOTA_AXES; ++axis)
            printf("%s%llu", axis ? "," : "", (unsigned long long)a.state.usage.lane[lane].value[axis]);
        printf("]");
    }
    printf("]");
    if (partial) {
        char hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t size;
        if (golem_digest_format(&p.approval, hex, sizeof(hex), &size) != GOLEM_OK) return 1;
        printf(",\"archived\":%s,\"payload_ready\":%s,\"directory_present\":%s,\"payload_bytes\":%llu,\"approval\":\"%s\"",
            p.archived ? "true" : "false", p.payload_ready ? "true" : "false", p.directory_present ? "true" : "false",
            (unsigned long long)p.payload_bytes, hex);
    }
    if (envelope) {
        char hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t size;
        if (golem_digest_format(&e.digest, hex, sizeof(hex), &size) != GOLEM_OK) return 1;
        printf(",\"envelope_final\":%s,\"envelope_pending\":%s,\"envelope_device\":%llu,"
               "\"envelope_inode\":%llu,\"envelope_bytes\":%llu,\"envelope_digest\":\"%s\"",
            e.final_present ? "true" : "false", e.pending_present ? "true" : "false",
            (unsigned long long)e.device, (unsigned long long)e.inode, (unsigned long long)e.bytes, hex);
    }
    if (fragment) {
        printf(",\"truncated_present\":%s,\"fragment_final\":%s,\"fragment_pending\":%s,"
            "\"truncated_device\":%llu,\"truncated_inode\":%llu,\"truncated_bytes\":%llu,"
            "\"object_device\":%llu,\"object_inode\":%llu,\"object_bytes\":%llu",
            f.truncated_present ? "true" : "false", f.final_present ? "true" : "false", f.pending_present ? "true" : "false",
            (unsigned long long)f.device, (unsigned long long)f.inode, (unsigned long long)f.bytes,
            (unsigned long long)f.object_device, (unsigned long long)f.object_inode, (unsigned long long)f.object_bytes);
        const golem_digest *ds[] = {&f.digest, &f.object_digest, &f.preservation_approval};
        const char *ns[] = {"truncated_digest", "object_digest", "preservation_approval"};
        for (unsigned i = 0; i < 3; ++i) {
            char hex[65]; size_t n;
            if (golem_digest_format(ds[i], hex, sizeof(hex), &n) != GOLEM_OK) return 1;
            printf(",\"%s\":\"%s\"", ns[i], hex);
        }
    }
    if (damage) {
        printf(",\"ancestor_device\":%llu,\"ancestor_inode\":%llu,\"ancestor_bytes\":%llu",
            (unsigned long long)f.envelope_device, (unsigned long long)f.envelope_inode,
            (unsigned long long)f.envelope_bytes);
        const golem_digest *ds[] = {&f.envelope_digest, &f.fragment_approval};
        const char *ns[] = {"ancestor_digest", "fragment_approval"};
        for (unsigned i = 0; i < 2; ++i) {
            char hex[65]; size_t n;
            if (golem_digest_format(ds[i], hex, sizeof(hex), &n) != GOLEM_OK) return 1;
            printf(",\"%s\":\"%s\"", ns[i], hex);
        }
    }
    printf("}\n"); return 0;
}

/* Fixed local-owner registration/change capability, not a public issuer API. */
static int object_fd(const char *s)
{
    char *end; errno = 0; long n = strtol(s, &end, 10);
    return errno || !*s || *end || n < 3 || n > INT_MAX ? -1 : (int)n;
}

static golem_status object_input(const char *arg, size_t limit, golem_bytes *out)
{
    int fd = object_fd(arg); struct stat a, b;
    if (fd < 0 || fstat(fd, &a) || !S_ISREG(a.st_mode) || a.st_uid != geteuid() ||
        (a.st_mode & 077) || a.st_size <= 0 || (uint64_t)a.st_size > limit) return GOLEM_ERR_INVALID_ARGUMENT;
    size_t n = (size_t)a.st_size, at = 0; uint8_t *data = malloc(n);
    if (!data) return GOLEM_ERR_OUT_OF_MEMORY;
    while (at < n) {
        ssize_t got = pread(fd, data + at, n - at, (off_t)at);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0) { free(data); return GOLEM_ERR_IO; }
        at += (size_t)got;
    }
    if (fstat(fd, &b) || a.st_dev != b.st_dev || a.st_ino != b.st_ino || a.st_size != b.st_size ||
        a.st_mode != b.st_mode || a.st_uid != b.st_uid) { free(data); return GOLEM_ERR_INVALID_STATE; }
    *out = (golem_bytes){data, n}; return GOLEM_OK;
}

static golem_status object_guard(void *context)
{
    int *fds = context; char byte = 'G'; ssize_t n;
    do { n = write(fds[1], &byte, 1); } while (n < 0 && errno == EINTR);
    if (n != 1) return GOLEM_ERR_POLICY_DENIED;
    do { n = read(fds[0], &byte, 1); } while (n < 0 && errno == EINTR);
    return n == 1 && byte == 'A' ? GOLEM_OK : GOLEM_ERR_POLICY_DENIED;
}

static int store_objects_command(int argc, char **argv)
{
    if (argc < 13 || (argc - 11) % 2) return 2;
    int root = object_fd(argv[2]), guards[] = {object_fd(argv[8]), object_fd(argv[9])};
    if (root < 0 || guards[0] < 0 || guards[1] < 0) return 2;
    char *end; errno = 0; unsigned long long seq = strtoull(argv[6], &end, 10);
    if (errno || !*argv[6] || *end || argv[6][0] == '-') return 2;
    golem_digest registration, operation, request, head;
    golem_digest *digests[] = {&registration, &operation, &request, &head};
    const unsigned indices[] = {3, 4, 5, 7};
    golem_status st = GOLEM_OK;
    for (size_t i = 0; st == GOLEM_OK && i < 4; ++i)
        st = golem_digest_parse((golem_string_view){argv[indices[i]], strlen(argv[indices[i]])}, digests[i]);
    size_t count = (size_t)(argc - 11) / 2, total = 0;
    gi_source_input *sources = calloc(count, sizeof(*sources)); golem_bytes baseline = {0};
    if (!sources) st = GOLEM_ERR_OUT_OF_MEMORY;
    if (st == GOLEM_OK) st = object_input(argv[10], 262144, &baseline);
    for (size_t i = 0; st == GOLEM_OK && i < count; ++i) {
        st = object_input(argv[11 + 2*i], 262144, &sources[i].control);
        if (st == GOLEM_OK) st = object_input(argv[12 + 2*i], 16777216, &sources[i].text);
        total += sources[i].text.size;
        if (total > 67108864) st = GOLEM_ERR_OVERFLOW;
    }
    gi_journal *j = NULL; authority_chain chain = {0};
    const char key[] = "golem.intent.authority-registration.v1";
    if (st == GOLEM_OK) st = gi_journal_open(root, &j);
    if (st == GOLEM_OK) st = golem_digest_bytes((golem_bytes){(const uint8_t *)key, sizeof(key)-1}, &chain.initial);
    if (st == GOLEM_OK) st = gi_journal_visit(j, visit_binding, &chain);
    if (st == GOLEM_OK && (!chain.found || memcmp(chain.current.bytes, registration.bytes, 32))) st = GOLEM_ERR_INVALID_STATE;
    gi_journal_receipt receipt;
    if (st == GOLEM_OK) st = gi_journal_store_objects(j, &operation, &request, seq, &head,
        baseline, sources, count, object_guard, guards, &receipt);
    gi_journal_close(j); free((void *)baseline.data);
    if (sources) for (size_t i = 0; i < count; ++i) { free((void *)sources[i].control.data); free((void *)sources[i].text.data); }
    free(sources);
    if (st != GOLEM_OK) {
        printf("{\"schema\":\"golem.intent-object-store-result.v1\",\"execution_authorized\":false,\"error\":%d}\n", (int)st);
        return 1;
    }
    char hex[GOLEM_DIGEST_HEX_CAPACITY]; size_t required;
    if (golem_digest_format(&receipt.digest, hex, sizeof(hex), &required) != GOLEM_OK) return 1;
    printf("{\"schema\":\"golem.intent-object-store-result.v1\",\"execution_authorized\":false,"
           "\"registration_sha256\":\"%s\",\"sequence\":%llu,\"event_digest\":\"%s\",\"replayed\":%s}\n",
           argv[3], (unsigned long long)receipt.sequence, hex, receipt.replayed ? "true" : "false");
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 4) return 2;
    if (!strcmp(argv[1], "--store-objects-fd")) return store_objects_command(argc, argv);
    if (!strcmp(argv[1], "--plan-fragment-fd") || !strcmp(argv[1], "--preserve-fragment-fd") ||
        !strcmp(argv[1], "--finish-fragment-fd") || !strcmp(argv[1], "--detach-fragment-fd")) return alias_command(argc, argv);
    if (!strcmp(argv[1], "--plan-damage-fd") || !strcmp(argv[1], "--preserve-damage-fd") ||
        !strcmp(argv[1], "--finish-damage-fd") || !strcmp(argv[1], "--detach-damage-fd")) return alias_command(argc, argv);
    if (!strcmp(argv[1], "--plan-envelope-fd") || !strcmp(argv[1], "--finish-envelope-fd"))
        return alias_command(argc, argv);
    if (!strcmp(argv[1], "--plan-partial-fd") || !strcmp(argv[1], "--quarantine-partial-fd") ||
        !strcmp(argv[1], "--replace-payload-fd")) return alias_command(argc, argv);
    if (!strcmp(argv[1], "--plan-alias-fd") || !strcmp(argv[1], "--remove-alias-fd"))
        return alias_command(argc, argv);
    if (!strcmp(argv[1], "--plan-pending-fd") || !strcmp(argv[1], "--recover-pending-fd"))
        return pending_command(argc, argv);
    bool change = !strcmp(argv[1], "--change-fd");
    bool verify = !strcmp(argv[1], "--verify-change-fd");
    bool check = !strcmp(argv[1], "--check-change-fd");
    bool enroll = !strcmp(argv[1], "--register-fd");
    if (((change || verify || check) && argc != 5) || (!change && !verify && !check && argc != 4) ||
        (!change && !verify && !check && !enroll && strcmp(argv[1], "--inspect-fd"))) return 2;
    char *end = NULL;
    errno = 0;
    long fd = strtol(argv[2], &end, 10);
    if (errno || !*argv[2] || *end || fd < 3 || fd > INT_MAX) return 2;
    gi_journal *journal = NULL;
    golem_status status = gi_journal_open((int)fd, &journal);
    golem_digest expected, target;
    authority_chain chain = {0};
    const char key[] = "golem.intent.authority-registration.v1";
    if (status == GOLEM_OK) status = golem_digest_parse((golem_string_view){argv[3], strlen(argv[3])}, &expected);
    if (status == GOLEM_OK && (change || verify || check))
        status = golem_digest_parse((golem_string_view){argv[4], strlen(argv[4])}, &target);
    else if (status == GOLEM_OK) target = expected;
    if (status == GOLEM_OK) status = golem_digest_bytes((golem_bytes){(const uint8_t *)key, sizeof(key) - 1}, &chain.initial);
    gi_journal_status observed;
    if (status == GOLEM_OK) status = gi_journal_inspect(journal, &observed);
    if (status == GOLEM_OK && observed.pending) status = GOLEM_ERR_INVALID_STATE;
    if (status == GOLEM_OK) {
        chain.target = target;
        status = gi_journal_visit(journal, visit_binding, &chain);
    }
    if (status == GOLEM_OK && chain.found && memcmp(chain.current.bytes, verify ? target.bytes : expected.bytes, 32))
        status = GOLEM_ERR_INVALID_STATE;
    if (status == GOLEM_OK && !chain.found && (!enroll || observed.committed))
        status = GOLEM_ERR_INVALID_STATE;
    if (status == GOLEM_OK && (change || check) && chain.target_seen)
        status = GOLEM_ERR_INVALID_ARGUMENT;
    if (status == GOLEM_OK && verify) {
        golem_digest operation;
        gi_journal_operation binding;
        status = successor_key(&expected, &operation);
        if (status == GOLEM_OK) status = gi_journal_lookup(journal, &operation, &target, &binding);
        if (status == GOLEM_OK && (!binding.committed || binding.pending || binding.lane != GI_QUOTA_INTAKE))
            status = GOLEM_ERR_INVALID_STATE;
    }
    if (status == GOLEM_OK && (change || (enroll && !chain.found))) {
        /* Change payload retains predecessor digest followed by exact new record.
         * Request digest binds the record, operation binds the predecessor. */
        size_t prefix = change ? 32 : 0;
        uint8_t *payload = malloc(262145);
        if (!payload) status = GOLEM_ERR_OUT_OF_MEMORY;
        else {
            if (prefix) memcpy(payload, expected.bytes, prefix);
            size_t n = fread(payload + prefix, 1, 262145 - prefix, stdin);
            golem_digest actual;
            if (ferror(stdin) || n == 0 || n + prefix > 262144) status = GOLEM_ERR_OVERFLOW;
            if (status == GOLEM_OK) status = golem_digest_bytes((golem_bytes){payload + prefix, n}, &actual);
            if (status == GOLEM_OK && memcmp(actual.bytes, target.bytes, 32)) status = GOLEM_ERR_INVALID_STATE;
            gi_journal_receipt receipt;
            if (status == GOLEM_OK) status = gi_journal_append(journal, GI_QUOTA_INTAKE,
                change ? &chain.successor : &chain.initial, &target,
                observed.committed, &observed.head, (golem_bytes){payload, n + prefix},
                registration_guard, payload, &receipt);
            free(payload);
        }
        if (status == GOLEM_OK) chain.current = target;
    }
    if (status == GOLEM_OK) status = gi_journal_inspect(journal, &observed);
    gi_journal_close(journal);
    if (status != GOLEM_OK) {
        printf("{\"schema\":\"golem.intent-journal-inspection.v1\",\"execution_authorized\":false,\"error\":%d}\n", (int)status);
        return 1;
    }
    char head[GOLEM_DIGEST_HEX_CAPACITY], current[GOLEM_DIGEST_HEX_CAPACITY]; size_t required;
    if (golem_digest_format(&observed.head, head, sizeof(head), &required) != GOLEM_OK ||
        golem_digest_format(&chain.current, current, sizeof(current), &required) != GOLEM_OK) return 1;
    printf("{\"schema\":\"golem.intent-journal-inspection.v1\",\"execution_authorized\":false,"
           "\"registration_sha256\":\"%s\",\"committed\":%llu,\"pending\":%s,\"head\":\"%s\",\"usage\":[",
           current, (unsigned long long)observed.committed, observed.pending ? "true" : "false", head);
    for (unsigned lane = 0; lane < GI_QUOTA_LANES; ++lane) {
        printf("%s[", lane ? "," : "");
        for (unsigned axis = 0; axis < GI_QUOTA_AXES; ++axis)
            printf("%s%llu", axis ? "," : "", (unsigned long long)observed.usage.lane[lane].value[axis]);
        printf("]");
    }
    printf("]}\n");
    return 0;
}
