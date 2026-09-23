#include "internal.h"
#include <md4c.h>
#include <ctype.h>
#include <stdio.h>
#include <string.h>

/* MD4C supplies parsed block/span events: headings in code/quotes cannot fake
 * contract sections. We keep bounded semantic state, not a second Markdown AST. */
typedef struct md_contract {
    struct json_object *meta;
    unsigned depth, heading, titles;
    int section;
    char heading_text[128];
    size_t heading_size, useful[11];
    bool seen[11], parents[GOLEM_DOCUMENT_MAX_PARENTS], requirements[256];
    bool bad;
} md_contract;
/* Retain callback rejection even when a parser version loses its return code. */
static int reject(md_contract *c)
{
    c->bad = true;
    return 1;
}
static const char *const sections[] = {"Purpose",  "Scope",      "Parents",
                                       "Evidence", "Decisions",  "Requirements",
                                       "Work",     "Validation", "Risks"};
static const char *extra(const char *kind)
{
    if (strcmp(kind, "planning") == 0)
        return "Acceptance";
    if (strcmp(kind, "ux") == 0)
        return "Flows";
    if (strcmp(kind, "publishing") == 0)
        return "Interface";
    if (strcmp(kind, "development-plan") == 0)
        return "Changes";
    if (strcmp(kind, "development-result") == 0)
        return "Results";
    if (strcmp(kind, "qa-plan") == 0)
        return "Cases";
    if (strcmp(kind, "qa-result") == 0)
        return "Results";
    if (strcmp(kind, "completion") == 0)
        return "Outcome";
    if (strcmp(kind, "research") == 0)
        return "Sources";
    if (strcmp(kind, "discovery") == 0)
        return "Observations";
    if (strcmp(kind, "scope") == 0)
        return "Selection";
    if (strcmp(kind, "stage-selection") == 0)
        return "Stages";
    return "Failure";
}
static bool utf8(golem_bytes b)
{
    for (size_t i = 0; i < b.size;) {
        uint32_t cp = b.data[i++], min = 0;
        unsigned n = 0;
        if (cp < 0x80) {
            if (cp == 0 || (cp < 32 && cp != '\t' && cp != '\r' && cp != '\n'))
                return false;
            continue;
        }
        if (cp >= 0xc2 && cp <= 0xdf) {
            n = 1;
            cp &= 31;
            min = 0x80;
        } else if (cp >= 0xe0 && cp <= 0xef) {
            n = 2;
            cp &= 15;
            min = 0x800;
        } else if (cp >= 0xf0 && cp <= 0xf4) {
            n = 3;
            cp &= 7;
            min = 0x10000;
        } else
            return false;
        if (n > b.size - i)
            return false;
        while (n--) {
            unsigned c = b.data[i++];
            if ((c & 0xc0) != 0x80)
                return false;
            cp = (cp << 6) | (c & 63);
        }
        if (cp < min || cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff))
            return false;
    }
    return true;
}
static int enter_block(MD_BLOCKTYPE t, void *detail, void *ctx)
{
    md_contract *c = ctx;
    ++c->depth;
    if (c->depth > 128)
        return reject(c);
    if (t == MD_BLOCK_H) {
        unsigned level = ((MD_BLOCK_H_DETAIL *)detail)->level;
        if (c->depth != 2 || level > 2)
            return reject(c);
        c->heading = level;
        c->heading_size = 0;
        c->heading_text[0] = 0;
        if (level == 1 && (c->titles++ != 0 || c->section != -1))
            return reject(c);
    }
    if (t == MD_BLOCK_HTML)
        return reject(c);
    return 0;
}
static int leave_block(MD_BLOCKTYPE t, void *detail, void *ctx)
{
    (void)detail;
    md_contract *c = ctx;
    if (t == MD_BLOCK_H) {
        if (c->heading == 2) {
            int index = -1;
            for (int i = 0; i < 9; ++i)
                if (strcmp(c->heading_text, sections[i]) == 0)
                    index = i;
            if (strcmp(c->heading_text, extra(dw_text(c->meta, "kind"))) == 0)
                index = 9;
            if (index < 0 || c->seen[index] || c->titles != 1)
                return reject(c);
            c->section = index;
            c->seen[index] = true;
        } else if (c->heading_size < 4)
            return reject(c);
        c->heading = 0;
    }
    --c->depth;
    return 0;
}
static int enter_span(MD_SPANTYPE t, void *detail, void *ctx)
{
    md_contract *c = ctx;
    if (t == MD_SPAN_A) {
        MD_ATTRIBUTE *a = &((MD_SPAN_A_DETAIL *)detail)->href;
        if (a->size >= 10 && memcmp(a->text, "golem-doc:", 10) == 0) {
            if (c->section != 2)
                return reject(c);
            struct json_object *p = dw_get(c->meta, "parents");
            bool match = false;
            for (size_t i = 0; i < json_object_array_length(p); ++i) {
                struct json_object *v = json_object_array_get_idx(p, i);
                char expected[180];
                int n = snprintf(expected, sizeof(expected), "golem-doc:%s:%u:%s",
                                 dw_text(v, "document_id"), (unsigned)dw_uint(v, "revision"),
                                 dw_text(v, "digest"));
                if (n > 0 && (size_t)n == a->size && memcmp(expected, a->text, a->size) == 0) {
                    if (c->parents[i])
                        return reject(c);
                    c->parents[i] = true;
                    match = true;
                }
            }
            if (!match)
                return reject(c);
        } else if (c->section == 2)
            return reject(c); /* Parent links have one unambiguous scheme. */
    }
    return 0;
}
static int leave_span(MD_SPANTYPE t, void *detail, void *ctx)
{
    (void)t;
    (void)detail;
    (void)ctx;
    return 0;
}
static bool token_char(unsigned char ch)
{
    return ch >= 128 || isalnum(ch) || ch == '_' || ch == '-';
}
static bool placeholder(const char *s, size_t n)
{
    const char *words[] = {"todo", "tbd", "fixme", "pending", "placeholder", "none", "na"};
    for (size_t i = 0; i < sizeof(words) / sizeof(words[0]); ++i) {
        if (strlen(words[i]) != n)
            continue;
        bool same = true;
        for (size_t j = 0; j < n; ++j)
            if (tolower((unsigned char)s[j]) != words[i][j])
                same = false;
        if (same)
            return true;
    }
    return false;
}
static int text(MD_TEXTTYPE t, const MD_CHAR *s, MD_SIZE n, void *ctx)
{
    md_contract *c = ctx;
    if (t == MD_TEXT_HTML || t == MD_TEXT_NULLCHAR)
        return reject(c);
    if (c->heading) {
        if (t != MD_TEXT_NORMAL || n >= sizeof(c->heading_text) - c->heading_size)
            return reject(c);
        memcpy(c->heading_text + c->heading_size, s, n);
        c->heading_size += n;
        c->heading_text[c->heading_size] = 0;
        return 0;
    }
    if (c->section < 0 || (t != MD_TEXT_NORMAL && t != MD_TEXT_CODE))
        return 0;
    struct json_object *req = dw_get(c->meta, "requirement_ids");
    for (size_t i = 0; i < n;) {
        if (!token_char((unsigned char)s[i])) {
            ++i;
            continue;
        }
        size_t start = i;
        while (i < n && token_char((unsigned char)s[i]))
            ++i;
        size_t len = i - start;
        if (t == MD_TEXT_NORMAL && !placeholder(s + start, len))
            c->useful[c->section] += len;
        if (c->section == 5)
            for (size_t k = 0; k < json_object_array_length(req); ++k) {
                const char *id = json_object_get_string(json_object_array_get_idx(req, k));
                if (strlen(id) == len && memcmp(id, s + start, len) == 0)
                    c->requirements[k] = true;
            }
    }
    return 0;
}
golem_status dw_markdown(struct json_object *meta, golem_bytes b)
{
    if (!b.data || !b.size || b.size > GOLEM_DOCUMENT_MAX_BODY || !utf8(b))
        return GOLEM_ERR_PARSE;
    md_contract c = {0};
    c.meta = meta;
    c.section = -1;
    MD_PARSER p = {0};
    p.enter_block = enter_block;
    p.leave_block = leave_block;
    p.enter_span = enter_span;
    p.leave_span = leave_span;
    p.text = text;
    if (md_parse((const char *)b.data, (MD_SIZE)b.size, &p, &c) != 0 || c.bad || c.titles != 1)
        return GOLEM_ERR_REQUIREMENTS_UNMET;
    for (size_t i = 0; i < 10; ++i)
        if (!c.seen[i] || c.useful[i] < 8)
            return GOLEM_ERR_REQUIREMENTS_UNMET;
    struct json_object *parents = dw_get(meta, "parents"), *req = dw_get(meta, "requirement_ids");
    for (size_t i = 0; i < json_object_array_length(parents); ++i)
        if (!c.parents[i])
            return GOLEM_ERR_REQUIREMENTS_UNMET;
    for (size_t i = 0; i < json_object_array_length(req); ++i)
        if (!c.requirements[i])
            return GOLEM_ERR_REQUIREMENTS_UNMET;
    return GOLEM_OK;
}
