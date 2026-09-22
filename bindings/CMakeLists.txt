if(GOLEM_BUILD_FUZZERS)
    message(FATAL_ERROR "Build language bindings separately from coverage-instrumented fuzz libraries")
endif()
if(NOT UNIX)
    message(FATAL_ERROR "Bindings currently support macOS/Linux")
endif()
# Reuse the existing strict CLI capsule parser and projections without launching
# the CLI or introducing a second parser/schema in either host language.
add_library(golem_binding SHARED native/bridge.c
    ${PROJECT_SOURCE_DIR}/src/cli/json.c ${PROJECT_SOURCE_DIR}/src/cli/capsule.c
    ${PROJECT_SOURCE_DIR}/src/cli/projection.c)
add_library(Golem::binding ALIAS golem_binding)
set_target_properties(golem_binding PROPERTIES EXPORT_NAME binding VERSION 1.0.0 SOVERSION 1
    C_VISIBILITY_PRESET hidden)
target_link_libraries(golem_binding PRIVATE Golem::golem PkgConfig::JSONC)
target_include_directories(golem_binding PUBLIC
    $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include> $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
golem_configure_target(golem_binding)
if(APPLE)
    set_property(TARGET golem_binding APPEND PROPERTY LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/native/exports.txt")
    target_link_options(golem_binding PRIVATE "LINKER:-exported_symbols_list,${CMAKE_CURRENT_SOURCE_DIR}/native/exports.txt")
else()
    set_property(TARGET golem_binding APPEND PROPERTY LINK_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/native/exports.map")
    target_link_options(golem_binding PRIVATE "LINKER:--version-script=${CMAKE_CURRENT_SOURCE_DIR}/native/exports.map")
endif()
install(TARGETS golem_binding EXPORT GolemTargets LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR})

if(GOLEM_BUILD_NODE_BINDING)
    find_program(GOLEM_NODE_EXECUTABLE NAMES node REQUIRED)
    get_filename_component(node_bin "${GOLEM_NODE_EXECUTABLE}" DIRECTORY)
    find_path(GOLEM_NODE_INCLUDE_DIR node_api.h HINTS "${node_bin}/../include/node"
        /usr/local/include/node /opt/homebrew/include/node /usr/include/node REQUIRED)
    add_library(golem_node MODULE typescript/native/addon.c)
    target_include_directories(golem_node PRIVATE ${GOLEM_NODE_INCLUDE_DIR})
    target_link_libraries(golem_node PRIVATE Golem::binding)
    target_compile_definitions(golem_node PRIVATE NAPI_VERSION=8)
    set_target_properties(golem_node PROPERTIES PREFIX "" SUFFIX ".node" C_VISIBILITY_PRESET hidden
        INSTALL_RPATH "$ORIGIN/../..")
    if(APPLE)
        set_target_properties(golem_node PROPERTIES INSTALL_RPATH "@loader_path/../..")
        target_link_options(golem_node PRIVATE "LINKER:-undefined,dynamic_lookup")
    endif()
    golem_configure_target(golem_node)
    install(TARGETS golem_node LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}/golem/node)
endif()
if(BUILD_TESTING)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    add_executable(golem_test_binding native/test_bridge.c)
    target_link_libraries(golem_test_binding PRIVATE Golem::binding)
    golem_configure_target(golem_test_binding)
    add_test(NAME binding_abi COMMAND golem_test_binding
        ${PROJECT_SOURCE_DIR}/samples/work-capsules/basic.json
        ${PROJECT_SOURCE_DIR}/tests/c/fixtures/journal/v1_default.hex)
    set_tests_properties(binding_abi PROPERTIES LABELS bindings TIMEOUT 30)
    # Host interpreters normally are not sanitizer-linked. Sanitized ABI coverage
    # runs in the native test executable; host tests run in normal builds.
    if(NOT GOLEM_ENABLE_SANITIZERS)
        add_test(NAME binding_python COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_python.py $<TARGET_FILE:golem_binding> ${PROJECT_SOURCE_DIR})
        set_tests_properties(binding_python PROPERTIES LABELS bindings TIMEOUT 60)
        if(GOLEM_BUILD_NODE_BINDING)
            add_test(NAME binding_typescript COMMAND ${GOLEM_NODE_EXECUTABLE}
                ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_node.mjs $<TARGET_FILE:golem_node> ${PROJECT_SOURCE_DIR})
            set_tests_properties(binding_typescript PROPERTIES LABELS bindings TIMEOUT 60)
        endif()
    endif()
endif()
