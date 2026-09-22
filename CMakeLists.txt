cmake_minimum_required(VERSION 3.21)
project(Golem VERSION 0.1.0 LANGUAGES C)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
    message(FATAL_ERROR "Use an out-of-source build, for example cmake --preset dev")
endif()

# Keep the installed standalone header in sync with package metadata.
file(STRINGS "${CMAKE_CURRENT_SOURCE_DIR}/include/golem/version.h" version_line
    REGEX "^#define GOLEM_VERSION_STRING ")
if(NOT version_line STREQUAL "#define GOLEM_VERSION_STRING \"${PROJECT_VERSION}\"")
    message(FATAL_ERROR "version.h and the CMake project version must match")
endif()

include(CTest)
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
option(GOLEM_WARNINGS_AS_ERRORS "Treat Golem warnings as errors" ON)
option(GOLEM_ENABLE_SANITIZERS "Enable AddressSanitizer and UndefinedBehaviorSanitizer" OFF)
option(GOLEM_BUILD_CLI "Build the headless C CLI" ON)
option(GOLEM_BUILD_BENCHMARKS "Build opt-in performance measurement tools" OFF)
option(GOLEM_BUILD_BINDINGS "Build the optional shared language binding ABI" OFF)
option(GOLEM_BUILD_NODE_BINDING "Build the optional Node-API addon" OFF)
if(GOLEM_BUILD_NODE_BINDING AND NOT GOLEM_BUILD_BINDINGS)
    message(FATAL_ERROR "Node binding requires GOLEM_BUILD_BINDINGS=ON")
endif()
option(GOLEM_BUILD_FUZZERS "Build instrumented Clang libFuzzer parser checks" OFF)
set(GOLEM_LIBFUZZER_LIBRARY "" CACHE FILEPATH "Optional libFuzzer archive for AppleClang installations without libFuzzer")
if(GOLEM_BUILD_FUZZERS AND NOT GOLEM_ENABLE_SANITIZERS)
    message(FATAL_ERROR "Fuzz builds require GOLEM_ENABLE_SANITIZERS=ON")
endif()
if(GOLEM_BUILD_FUZZERS AND NOT BUILD_TESTING)
    message(FATAL_ERROR "Fuzz builds require BUILD_TESTING=ON for seeded smoke tests")
endif()
find_package(OpenSSL 3.0 REQUIRED COMPONENTS Crypto)
find_package(PkgConfig REQUIRED)
pkg_check_modules(JSONC REQUIRED IMPORTED_TARGET json-c>=0.15)

add_library(golem STATIC
    src/daemon/storage.c
    src/daemon/recovery.c
    src/daemon/queue.c
    src/daemon/scheduler.c
    src/daemon/supervisor.c
    src/runtime/loop.c
    src/runtime/lease.c
    src/adapter_protocol/adapter.c
    src/adapter_protocol/model.c
    src/adapter_protocol/schema.c
    src/adapter_protocol/envelope_json.c
    src/adapter_protocol/envelope_msgpack.c
    src/adapter_protocol/gateway.c
    src/adapter_protocol/noop.c
    src/common/error.c
    src/common/diagnostic.c
    src/common/allocator.c
    src/common/arena.c
    src/common/span.c
    src/common/types.c
    src/common/version.c
    src/core/capsule.c
    src/core/memory.c
    src/core/stage_graph.c
    src/core/stage_run.c
    src/core/work_run.c
    src/core/authorization.c
    src/policy/autonomy.c
    src/policy/artifact.c
    src/policy/fallback.c
    src/optimization/selection.c
    src/optimization/execution.c
    src/cost/cache.c
    src/cost/usage.c
    src/cost/budget.c
    src/cost/ledger.c
    src/core/loop_controller.c
    src/journal/codec.c
    src/journal/event.c
    src/journal/capsule_codec.c
    src/journal/replay.c
    src/replay/engine.c
    src/replay/apply.c
    src/journal/file.c
    src/evidence/digest.c
    src/evidence/fs.c
    src/evidence/cas.c
    src/evidence/receipt.c
    src/evidence/read.c
    src/lineage/model.c
    src/lineage/query.c
    src/lineage/codec.c
    src/lineage/store.c)
add_library(Golem::golem ALIAS golem)
target_compile_features(golem PUBLIC c_std_17)
target_link_libraries(golem PRIVATE OpenSSL::Crypto PkgConfig::JSONC)
set_target_properties(golem PROPERTIES C_STANDARD 17 C_STANDARD_REQUIRED YES C_EXTENSIONS NO POSITION_INDEPENDENT_CODE YES)
target_include_directories(golem PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)

function(golem_configure_target target)
    set_target_properties(${target} PROPERTIES C_STANDARD 17 C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
    if(CMAKE_C_COMPILER_ID MATCHES "^(GNU|Clang|AppleClang)$")
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
        if(GOLEM_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE -Werror)
        endif()
    elseif(MSVC)
        target_compile_options(${target} PRIVATE /W4)
        if(GOLEM_WARNINGS_AS_ERRORS)
            target_compile_options(${target} PRIVATE /WX)
        endif()
    else()
        message(FATAL_ERROR "Unsupported compiler: define a warning policy before use")
    endif()
    if(GOLEM_ENABLE_SANITIZERS)
        if(NOT CMAKE_C_COMPILER_ID MATCHES "^(GNU|Clang|AppleClang)$" OR WIN32)
            message(FATAL_ERROR "Sanitizers currently require GCC/Clang on a Unix platform")
        endif()
        target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all)
        # Static library consumers must link the matching sanitizer runtime.
        target_link_options(${target} PUBLIC -fsanitize=address,undefined -fno-sanitize-recover=all)
    endif()
endfunction()
golem_configure_target(golem)

if(GOLEM_BUILD_FUZZERS)
    if(NOT CMAKE_C_COMPILER_ID MATCHES "^(Clang|AppleClang)$")
        message(FATAL_ERROR "libFuzzer requires Clang")
    endif()
    if(GOLEM_LIBFUZZER_LIBRARY AND (NOT APPLE OR NOT CMAKE_C_COMPILER_ID STREQUAL "AppleClang"
            OR NOT EXISTS "${GOLEM_LIBFUZZER_LIBRARY}"))
        message(FATAL_ERROR "GOLEM_LIBFUZZER_LIBRARY requires AppleClang and an existing macOS libFuzzer archive")
    endif()
    target_compile_options(golem PRIVATE -fsanitize=fuzzer-no-link)
    target_link_options(golem INTERFACE -fsanitize=fuzzer-no-link)
endif()

if(GOLEM_BUILD_CLI)
    add_executable(golem_cli src/cli/main.c src/cli/lineage.c src/cli/adapter.c
        src/cli/io.c src/cli/json.c src/cli/capsule.c src/cli/projection.c src/cli/runtime.c src/cli/work.c
        src/cli/daemon.c src/cli/daemon_worker.c)
    set_target_properties(golem_cli PROPERTIES OUTPUT_NAME golem)
    target_link_libraries(golem_cli PRIVATE Golem::golem PkgConfig::JSONC OpenSSL::Crypto)
    golem_configure_target(golem_cli)
    install(TARGETS golem_cli RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
endif()

if(BUILD_TESTING)
    add_subdirectory(tests/c)
endif()
if(BUILD_TESTING OR GOLEM_BUILD_FUZZERS)
    add_subdirectory(fuzz)
endif()
if(GOLEM_BUILD_BENCHMARKS)
    add_subdirectory(bench)
endif()
if(GOLEM_BUILD_BINDINGS)
    add_subdirectory(bindings)
endif()

install(TARGETS golem EXPORT GolemTargets ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(FILES LICENSE NOTICE COMMERCIAL-LICENSE.md
    DESTINATION ${CMAKE_INSTALL_DATADIR}/licenses/Golem)
install(DIRECTORY include/golem DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT GolemTargets NAMESPACE Golem:: DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Golem)
configure_package_config_file(cmake/GolemConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/GolemConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Golem)
write_basic_package_version_file(${CMAKE_CURRENT_BINARY_DIR}/GolemConfigVersion.cmake
    VERSION ${PROJECT_VERSION} COMPATIBILITY ExactVersion)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/GolemConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/GolemConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Golem)
