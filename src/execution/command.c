#include "internal.h"
#include <stdio.h>
#include <string.h>

/* Convenience guard, NOT an interpreter detector. Trusted binaries can execute
 * arbitrary code. Host review and OS isolation remain independent boundaries. */
static bool shell_name(const char *path)
{
    const char *base = strrchr(path, '/');
    base = base ? base + 1 : path;
    const char *names[] = {"sh", "bash", "dash", "zsh", "ksh", "mksh", "ash",
                           "csh", "tcsh", "fish", "busybox"};
    for (size_t i = 0; i < sizeof(names) / sizeof(names[0]); ++i)
        if (!strcmp(base, names[i]))
            return true;
    return false;
}

static const char *argument(struct json_object *gate, size_t index)
{
    const char *s = json_object_get_string(json_object_array_get_idx(dw_get(gate, "argv"), index));
    return s ? s : "";
}

static bool contains(struct json_object *paths, const char *path)
{
    for (size_t i = 0; i < json_object_array_length(paths); ++i)
        if (!strcmp(json_object_get_string(json_object_array_get_idx(paths, i)), path))
            return true;
    return false;
}

golem_status ex_command_validate(struct json_object *gate, struct json_object *repo)
{
    struct json_object *e = dw_get(gate, "execution");
    const char *kind = dw_text(e, "kind");
    const char *keys[] = {"kind", "executable_digest", "script", "script_digest"};
    bool shell = !strcmp(kind, "SHELL_SCRIPT");
    golem_digest ignored;
    if ((!shell && strcmp(kind, "DIRECT")) || !dw_keys(e, keys, shell ? 4 : 2) ||
        !dw_digest(e, "executable_digest", &ignored))
        return GOLEM_ERR_PARSE;
    if (!shell)
        return shell_name(argument(gate, 0)) ? GOLEM_ERR_POLICY_DENIED : GOLEM_OK;
    /* Only a file operand, never -c/-s, interactive/login flags, or a command
     * string. Remaining argv entries are literal script positional parameters. */
    const char *script = dw_text(e, "script");
    char absolute[4096];
    int n = snprintf(absolute, sizeof(absolute), "%s/%s", dw_text(repo, "root"), script);
    if (!shell_name(argument(gate, 0)) || !ds_path(script) ||
        !dw_digest(e, "script_digest", &ignored) || n < 0 || (size_t)n >= sizeof(absolute) ||
        strcmp(argument(gate, 1), absolute) ||
        !contains(dw_get(gate, "protected_paths"), script) ||
        !contains(dw_get(repo, "paths"), script))
        return GOLEM_ERR_POLICY_DENIED;
    return GOLEM_OK;
}

static golem_status matches(const char *path, struct json_object *execution, const char *field)
{
    golem_digest expected;
    golem_receipt actual;
    if (!dw_digest(execution, field, &expected))
        return GOLEM_ERR_PARSE;
    golem_status st = golem_digest_file(path, &actual, NULL);
    return st != GOLEM_OK ? st : dw_equal(&actual.digest, &expected)
        ? GOLEM_OK : GOLEM_ERR_STALE_RESULT;
}

golem_status ex_command_check(struct json_object *gate, struct json_object *plan)
{
    struct json_object *e = dw_get(gate, "execution"), *repo = NULL;
    if (!e)
        return shell_name(argument(gate, 0)) ? GOLEM_ERR_APPROVAL_REQUIRED : GOLEM_OK;
    struct json_object *repos = dw_get(plan, "repositories");
    for (size_t i = 0; i < json_object_array_length(repos); ++i) {
        struct json_object *r = json_object_array_get_idx(repos, i);
        if (!strcmp(dw_text(r, "id"), dw_text(gate, "repository")))
            repo = r;
    }
    golem_status st = repo ? ex_command_validate(gate, repo) : GOLEM_ERR_REQUIREMENTS_UNMET;
    if (st == GOLEM_OK)
        st = matches(argument(gate, 0), e, "executable_digest");
    if (st == GOLEM_OK && !strcmp(dw_text(e, "kind"), "SHELL_SCRIPT"))
        st = matches(argument(gate, 1), e, "script_digest");
    return st;
}

golem_status ex_command_approve(struct json_object *contract, const golem_digest *shell)
{
    golem_status st = ex_contract(contract);
    if (st != GOLEM_OK)
        return st;
    struct json_object *gates = dw_get(contract, "gates");
    for (size_t i = 0; i < json_object_array_length(gates); ++i) {
        struct json_object *g = json_object_array_get_idx(gates, i), *e = dw_get(g, "execution");
        if (!e && shell_name(argument(g, 0)))
            return GOLEM_ERR_APPROVAL_REQUIRED;
        if (!strcmp(dw_text(e, "kind"), "SHELL_SCRIPT")) {
            golem_digest expected;
            st = ex_hash(contract, &expected);
            if (st != GOLEM_OK)
                return st;
            if (!shell || !dw_equal(shell, &expected))
                return GOLEM_ERR_APPROVAL_REQUIRED;
        }
    }
    return GOLEM_OK;
}
