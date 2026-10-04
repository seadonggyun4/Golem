#include "golem/system_error.h"
#include <errno.h>
#include <string.h>

static _Thread_local golem_system_error_scope *active;

golem_status golem_system_error_begin(golem_system_error_scope *scope)
{
    if (!scope) return GOLEM_ERR_INVALID_ARGUMENT;
    for (golem_system_error_scope *p = active; p; p = p->parent)
        if (p == scope) return GOLEM_ERR_INVALID_STATE;
    *scope = (golem_system_error_scope){.parent = active};
    active = scope;
    return GOLEM_OK;
}
golem_status golem_system_error_end(golem_system_error_scope *scope)
{
    if (!scope || scope != active) return GOLEM_ERR_INVALID_STATE;
    active = scope->parent;
    scope->parent = NULL;
    return GOLEM_OK;
}
static bool label(char *out, const char *in)
{
    size_t i = 0;
    if (!in) in = "unknown";
    for (; i + 1 < GOLEM_SYSTEM_ERROR_LABEL_CAPACITY && in[i]; ++i) {
        unsigned char c = (unsigned char)in[i];
        out[i] = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                 (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-' ? (char)c : '_';
    }
    out[i] = 0;
    return in[i] != 0;
}
golem_status golem_system_error_note(golem_status status, const char *component,
                                   const char *operation, int saved_errno)
{
    int preserved = errno;
    if (active && status != GOLEM_OK) {
        golem_system_error e = {.status = status, .error_number = saved_errno > 0 ? saved_errno : 0};
        bool a = label(e.component, component), b = label(e.operation, operation);
        e.truncated = a || b;
        if (active->count == GOLEM_SYSTEM_ERROR_CAPACITY) {
            memmove(active->entries + 1, active->entries + 2,
                    (GOLEM_SYSTEM_ERROR_CAPACITY - 2) * sizeof(e));
            --active->count;
            if (active->omitted != SIZE_MAX) ++active->omitted;
        }
        active->entries[active->count++] = e;
    }
    errno = preserved;
    return status;
}
const char *golem_system_error_name(int n)
{
    if (!n) return "NOT_APPLICABLE";
#define NAME(e) if (n == e) return #e
    NAME(EACCES); NAME(EPERM); NAME(ENOENT); NAME(EEXIST); NAME(ENOSPC);
    NAME(EROFS); NAME(EIO); NAME(EBADF); NAME(EINTR); NAME(EAGAIN);
    NAME(EWOULDBLOCK); NAME(EMFILE); NAME(ENFILE); NAME(ENOMEM); NAME(EINVAL);
    NAME(ENOTDIR); NAME(EISDIR); NAME(ELOOP); NAME(ENAMETOOLONG); NAME(EPIPE);
    NAME(ECONNREFUSED); NAME(ECONNRESET); NAME(ETIMEDOUT); NAME(EADDRINUSE);
    NAME(ENOTSUP); NAME(ENOSYS); NAME(EOVERFLOW); NAME(EXDEV);
    NAME(ECHILD); NAME(ESRCH); NAME(ENOEXEC); NAME(E2BIG); NAME(ETXTBSY);
    NAME(EBUSY); NAME(EOPNOTSUPP); NAME(EFBIG); NAME(ENODEV); NAME(ENOTEMPTY);
    NAME(EDEADLK);
#undef NAME
    return "UNKNOWN_ERRNO";
}
const char *golem_system_error_action(int n)
{
    if (n == EDEADLK)
        return "Inspect thread ownership and join dependencies; do not repeat a join blindly.";
    if (n == ECHILD || n == ESRCH)
        return "Inspect child ownership and reap state; do not signal a possibly reused process identifier.";
    if (n == ENOEXEC || n == E2BIG || n == ETXTBSY)
        return "Check executable format, argument budget and deployment state before considering another execution.";
    if (n == EPERM || n == EACCES || n == EROFS)
        return "Inspect host permissions, sandbox and mount policy; do not bypass authorization.";
    if (n == ENOSPC || n == EMFILE || n == ENFILE || n == ENOMEM)
        return "Inspect storage and process limits; preserve existing evidence before intervention.";
    if (n == EAGAIN || n == EWOULDBLOCK || n == EADDRINUSE || n == EEXIST)
        return "Inspect owners and existing state; do not delete locks or repeat effects blindly.";
    if (n == ENOENT || n == ENOTDIR || n == ELOOP)
        return "Check resource identity, existence and symlink policy before recovery.";
    if (n == ECONNREFUSED || n == ECONNRESET || n == ETIMEDOUT || n == EPIPE)
        return "Inspect peer readiness and prior request effects before reconnecting.";
    return "Inspect original evidence and operation state; failure does not establish rollback or safe retry.";
}
