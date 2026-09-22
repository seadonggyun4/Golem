#ifndef GOLEM_BINDING_H
#define GOLEM_BINDING_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#if defined(__GNUC__) || defined(__clang__)
#define GOLEM_BINDING_API __attribute__((visibility("default")))
#else
#define GOLEM_BINDING_API
#endif
#define GOLEM_BINDING_ABI_VERSION 1u
#define GOLEM_BINDING_CAPSULE_MAX 131072u
#define GOLEM_BINDING_JOURNAL_MAX 16777216u
#define GOLEM_BINDING_VALIDATE 1u
#define GOLEM_BINDING_REPLAY 2u

/* Optional libgolem_binding ABI (not part of the static Golem::golem archive).
 * No native struct layouts, callbacks, global errors, clocks or filesystem I/O.
 * Inputs are borrowed immutable accessible bytes for this synchronous call.
 * Outputs must not alias inputs/each other. Operations validate capsule JSON or
 * replay journal bytes using the same C implementations as the CLI/Core.
 * Return codes are numeric golem_status values (0=OK). On success *out is a
 * library-owned UTF-8 JSON allocation, *size excludes its trailing NUL. Copy it
 * before exactly one golem_binding_free; never use a foreign allocator to free.
 * Errors preserve outputs; no partially reconstructed run escapes. free(NULL)
 * is allowed. Version/status text are process-lifetime values; do not free.
 * Independent calls are reentrant; host retains loaded library until all calls
 * and returned allocations finish. Invalid pointers are caller errors, not a
 * sandbox boundary. Unknown operations/oversized inputs are rejected.
 * Replay accepts valid unfinished prefixes, never executes agents, repairs
 * storage, restores leases, verifies CAS or authenticates acceptance. RUNNING
 * requires reconciliation. All 64-bit counters in JSON are decimal strings. */
/* Journal byte strings that cannot be projected as valid UTF-8 JSON are rejected
 * with GOLEM_ERR_PARSE rather than silently replaced by a host runtime. */
GOLEM_BINDING_API uint32_t golem_binding_abi_version(void);
GOLEM_BINDING_API int32_t golem_binding_call(uint32_t operation, const uint8_t *data,
    size_t size, char **out, size_t *out_size);
GOLEM_BINDING_API void golem_binding_free(void *result);
GOLEM_BINDING_API const char *golem_binding_status_message(int32_t status);
#ifdef __cplusplus
}
#endif
#endif
