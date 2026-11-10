/* Bootstrap changes are local owner-only. QC MCP may select exact read-only
 * enrollment-inspect packets; review/digest/enroll are not MCP mutations.
 * Parent holds the D01 guard and selects the exact packet hash outside model input. */
#include "../src/intent/product_gate.h"
#include "../src/execution/internal.h"
static int bootstrap_command(int argc, char **argv)
{
    if (argc != 6)
        return 2;
    char *end = NULL;
    long fd = strtol(argv[2], &end, 10);
    if (!*argv[2] || *end || fd < 3 || fd > INT_MAX)
        return 2;
    long reviewfd = strtol(argv[4], &end, 10);
    if (!*argv[4] || *end || reviewfd < 3 || reviewfd > INT_MAX)
        return 2;
    uint8_t *data = malloc(GI_DISPATCH_MAX + 1);
    if (!data)
        return 1;
    size_t size = fread(data, 1, GI_DISPATCH_MAX + 1, stdin);
    struct json_object *p = NULL, *out = NULL;
    golem_digest selected = {0}, actual = {0}, registration = {0}, policy = {0}, bundle = {0},
        bo = {0}, br = {0}, op = {0}, ah = {0}, wh = {0}, approval = {0};
    golem_status st = golem_digest_parse((golem_string_view){argv[5], strlen(argv[5])}, &selected);
    if (st == GOLEM_OK)
        st = size && size <= GI_DISPATCH_MAX && !ferror(stdin)
                 ? golem_digest_bytes((golem_bytes){data, size}, &actual) : GOLEM_ERR_OVERFLOW;
    if (st == GOLEM_OK && !dw_equal(&selected, &actual))
        st = GOLEM_ERR_APPROVAL_REQUIRED;
    if (st == GOLEM_OK)
        st = golem_json_parse((golem_bytes){data, size}, GI_DISPATCH_MAX, &p);
    const char *keys[] = {"schema", "operation", "work", "policy", "bundle", "control",
        "policy_sha256", "bundle_sha256", "policy_name", "bundle_name", "baseline",
        "sources", "definitions", "baseline_operation", "baseline_request", "publication_operation",
        "authority_sequence", "authority_head", "work_sequence", "work_head", "enrollment", "approval"};
    const char *mode = dw_text(p, "operation");
    if (st == GOLEM_OK && (!dw_keys(p, keys, 22) ||
        strcmp(dw_text(p, "schema"), "golem.intent-bootstrap-host.v1") ||
        (strcmp(mode, "review") && strcmp(mode, "enrollment-inspect") &&
         strcmp(mode, "enrollment-digest") && strcmp(mode, "enroll")) ||
        !dw_digest(p, "policy_sha256", &policy) || !dw_digest(p, "bundle_sha256", &bundle) ||
        !dw_digest(p, "baseline_operation", &bo) || !dw_digest(p, "baseline_request", &br) ||
        !dw_digest(p, "publication_operation", &op) || !dw_digest(p, "authority_head", &ah) ||
        !dw_digest(p, "work_head", &wh) || !dw_digest(p, "approval", &approval) ||
        dw_uint(p, "authority_sequence") == UINT64_MAX || dw_uint(p, "work_sequence") == UINT64_MAX))
        st = GOLEM_ERR_PARSE;
    if (st == GOLEM_OK)
        st = golem_digest_parse((golem_string_view){argv[3], strlen(argv[3])}, &registration);
    gi_journal *journal = NULL;
    authority_chain chain = {0};
    const char domain[] = "golem.intent.authority-registration.v1";
    if (st == GOLEM_OK)
        st = golem_digest_bytes((golem_bytes){(const uint8_t *)domain, sizeof(domain)-1}, &chain.initial);
    if (st == GOLEM_OK)
        st = gi_journal_open((int)fd, &journal);
    if (st == GOLEM_OK)
        st = gi_journal_visit(journal, visit_binding, &chain);
    if (st == GOLEM_OK && (!chain.found || !dw_equal(&chain.current, &registration)))
        st = GOLEM_ERR_POLICY_DENIED;
    gi_journal_close(journal);
    journal = NULL;
    struct stat info;
    product_guard guard = {(int)fd, 0, 0};
    if (st == GOLEM_OK) {
        if (fstat((int)fd, &info)) st = GOLEM_ERR_IO;
        else { guard.device = info.st_dev; guard.inode = info.st_ino; st = product_root_guard(&guard); }
    }
    gi_review_host_files files = {(int)reviewfd, dw_text(p,"policy_name"), dw_text(p,"bundle_name"),
                                  registration, product_root_guard, &guard};
    gi_review_host *host = NULL;
    if (st == GOLEM_OK)
        st = gi_review_host_open(product_text(p,"policy"), &policy, product_text(p,"bundle"), &bundle,
            product_text(p,"control"), &registration, gi_review_host_observe_files, &files, &host);
    struct json_object *src = dw_get(p,"sources"), *defs = dw_get(p,"definitions");
    size_t ns = json_object_is_type(src,json_type_array) ? json_object_array_length(src) : 0;
    size_t nd = json_object_is_type(defs,json_type_array) ? json_object_array_length(defs) : 0;
    gi_source_input *sources = NULL;
    golem_bytes *definitions = NULL;
    if (st == GOLEM_OK && (!ns || ns > 64 || !nd || nd > 256)) st = GOLEM_ERR_OVERFLOW;
    if (st == GOLEM_OK) {
        sources = calloc(ns,sizeof(*sources)); definitions = calloc(nd,sizeof(*definitions));
        if (!sources || !definitions) st = GOLEM_ERR_OUT_OF_MEMORY;
    }
    for (size_t i=0; st==GOLEM_OK && i<ns; ++i) {
        struct json_object *row = json_object_array_get_idx(src,i);
        const char *sk[] = {"control","text"};
        if (!dw_keys(row,sk,2)) st = GOLEM_ERR_PARSE;
        else sources[i]=(gi_source_input){product_text(row,"control"),product_text(row,"text")};
    }
    for (size_t i=0; st==GOLEM_OK && i<nd; ++i) {
        struct json_object *v=json_object_array_get_idx(defs,i);
        if (!json_object_is_type(v,json_type_string)) st=GOLEM_ERR_PARSE;
        else definitions[i]=(golem_bytes){(const uint8_t *)json_object_get_string(v),
                                           (size_t)json_object_get_string_len(v)};
    }
    gi_review_inputs inputs = {product_text(p,"baseline"),sources,ns,definitions,nd};
    gi_review_binding bound;
    if (st==GOLEM_OK) st=gi_review_bind(&inputs,&bound,NULL);
    if (st==GOLEM_OK) st=gi_review_host_binding(host,&registration,&bound.baseline,&policy);
    golem_document_store *work=NULL;
    gi_journal_receipt receipt={0};
    gi_journal_status snapshot={0};
    golem_digest spec={0}, observed_work_head={0};
    uint64_t observed_work_sequence=0;
    if (st==GOLEM_OK && !strcmp(mode,"review")) {
        if (*dw_text(p,"work") || product_text(p,"enrollment").size) st=GOLEM_ERR_POLICY_DENIED;
        if (st==GOLEM_OK) st=gi_journal_open((int)fd,&journal);
        if (st==GOLEM_OK) st=gi_review_host_publish(host,journal,&bo,&br,&bound.baseline,
            definitions,nd,&op,dw_uint(p,"authority_sequence"),&ah,&receipt);
    } else if (st==GOLEM_OK) {
        st=golem_document_store_open(dw_text(p,"work"),true,NULL,&work,NULL);
        if (st==GOLEM_OK) {
            observed_work_sequence=work->event_count; observed_work_head=work->last;
            st=ex_hash(work->spec,&spec);
        }
        if (st==GOLEM_OK && strcmp(mode,"enrollment-inspect") &&
            (work->event_count!=dw_uint(p,"work_sequence") || !dw_equal(&work->last,&wh)))
            st=GOLEM_ERR_STALE_RESULT;
        if (st==GOLEM_OK && !strcmp(mode,"enrollment-inspect")) {
            st=gi_journal_open((int)fd,&journal);
            if (st==GOLEM_OK) st=gi_journal_inspect(journal,&snapshot);
            if (st==GOLEM_OK && snapshot.pending) st=GOLEM_ERR_POLICY_DENIED;
        } else if (st==GOLEM_OK && !strcmp(mode,"enrollment-digest")) {
            golem_digest request;
            st=golem_digest_bytes(product_text(p,"enrollment"),&request);
            if (st==GOLEM_OK) st=gi_product_enrollment_approval(work,&request,&bo,&br,&op,
                dw_uint(p,"authority_sequence"),&ah,dw_uint(p,"work_sequence"),&wh,&approval);
        } else if (st==GOLEM_OK)
            st=gi_product_enroll(work,(int)fd,&inputs,product_text(p,"enrollment"),&approval,&bo,&br,&op,
                dw_uint(p,"authority_sequence"),&ah,dw_uint(p,"work_sequence"),&wh,
                gi_review_host_guard,host,&receipt);
    }
    gi_journal_close(journal);
    golem_status closed=golem_document_store_close(work);
    if (st==GOLEM_OK) st=closed;
    if (st==GOLEM_OK) {
        out=json_object_new_object();
        if (!out || !dw_add(out,"schema",json_object_new_string("golem.intent-bootstrap-result.v1")) ||
            !dw_add(out,"operation",json_object_new_string(mode)) ||
            !dw_add_digest(out,"approval_digest",&approval) || !dw_add_digest(out,"receipt",&receipt.digest) ||
            !dw_add_digest(out,"definitions_digest",&bound.definitions) ||
            !dw_add_digest(out,"work_spec_digest",&spec) ||
            !dw_add_digest(out,"work_head",&observed_work_head) ||
            !dw_add(out,"work_sequence",json_object_new_uint64(observed_work_sequence)) ||
            !dw_add_digest(out,"authority_head",&snapshot.head) ||
            !dw_add(out,"authority_sequence",json_object_new_uint64(snapshot.committed)) ||
            !dw_add(out,"sequence",json_object_new_uint64(receipt.sequence)) ||
            !dw_add(out,"execution_authorized",json_object_new_boolean(false))) st=GOLEM_ERR_OUT_OF_MEMORY;
        if (st==GOLEM_OK && puts(json_object_to_json_string_ext(out,JSON_C_TO_STRING_PLAIN))<0) st=GOLEM_ERR_IO;
    }
    if (st!=GOLEM_OK) fprintf(stderr,"intent.bootstrap code=%d uncertain_if_dispatched=true\n",(int)st);
    gi_review_host_close(host); free(sources); free(definitions); json_object_put(out); json_object_put(p); free(data);
    return st==GOLEM_OK?0:1;
}
