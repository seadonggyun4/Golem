if(GOLEM_BUILD_FUZZERS)
    message(FATAL_ERROR "Benchmark and fuzz instrumentation must use separate builds")
endif()
add_executable(golem_bench main.c workloads.c)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS main.c workloads.c workloads.h)
file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/main.c" bench_main_hash)
file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/workloads.c" bench_workloads_hash)
file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/workloads.h" bench_header_hash)
string(SHA256 bench_workload "${bench_main_hash}|${bench_workloads_hash}|${bench_header_hash}")
string(SHA256 bench_flags "${CMAKE_C_FLAGS}|${CMAKE_C_FLAGS_RELEASE}|${CMAKE_C_FLAGS_DEBUG}|${CMAKE_C_FLAGS_RELWITHDEBINFO}|${CMAKE_C_FLAGS_MINSIZEREL}|${CMAKE_INTERPROCEDURAL_OPTIMIZATION}|${CMAKE_OSX_ARCHITECTURES}|${CMAKE_OSX_DEPLOYMENT_TARGET}")
target_link_libraries(golem_bench PRIVATE Golem::golem PkgConfig::JSONC OpenSSL::Crypto)
target_compile_definitions(golem_bench PRIVATE
    GOLEM_BENCH_CONFIG="$<CONFIG>"
    GOLEM_BENCH_COMPILER="${CMAKE_C_COMPILER_ID}-${CMAKE_C_COMPILER_VERSION}"
    GOLEM_BENCH_FLAGS="${bench_flags}"
    GOLEM_BENCH_WORKLOAD="${bench_workload}"
    GOLEM_BENCH_SANITIZED=$<BOOL:${GOLEM_ENABLE_SANITIZERS}>)
golem_configure_target(golem_bench)
if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_test(NAME benchmark_contract COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/test_bench.py $<TARGET_FILE:golem_bench>)
    set_tests_properties(benchmark_contract PROPERTIES LABELS benchmark TIMEOUT 90)
endif()
