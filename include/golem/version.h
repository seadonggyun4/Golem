#ifndef GOLEM_VERSION_H
#define GOLEM_VERSION_H
#define GOLEM_VERSION_MAJOR 0
#define GOLEM_VERSION_MINOR 1
#define GOLEM_VERSION_PATCH 0
#define GOLEM_VERSION_STRING "0.1.0"
#ifdef __cplusplus
extern "C" {
#endif
/* Borrowed immutable process-lifetime string; never free.
 * Pre-1.0 APIs do not promise a stable ABI. */
const char *golem_version_string(void);
#ifdef __cplusplus
}
#endif
#endif
