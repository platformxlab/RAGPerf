# Manages the C/C++ building process and provides helper functions.
#
# Provides:
#   Function `proto_compile` to compile protobuf files into C++/Python sources.
#   Function `cxx_setup_target` to set up a C/C++ target with sources, includes, and depends.
#   Function `cxx_add_executable` to add an executable target.
#   Function `cxx_add_static_library` to add a static library target.
#   Function `cxx_add_dynamic_library` to add a dynamic library target.
#   Function `cxx_add_module` to add a module target.

include(${CMAKE_CURRENT_LIST_DIR}/utils.cmake)

message(STATUS "Using C++ Compiler: ${CMAKE_CXX_COMPILER}")

function(proto_compile name)
    cmake_parse_arguments(ARG
        ""
        "TARGET_NAME;SOURCE_DIR;CXX_DEST_DIR;PY_DEST_DIR;GEN_SOURCES;"
        "SOURCES;"
        ${ARGN}
    )

    # determine generation language
    string(COMPARE NOTEQUAL "${ARG_CXX_DEST_DIR}" "" GEN_CXX)
    string(COMPARE NOTEQUAL "${ARG_PY_DEST_DIR}" "" GEN_PY)
    if(NOT GEN_CXX AND NOT GEN_PY)
        message(FATAL_ERROR "proto_compile did not specify generation directory")
    endif()

    # determine all output dirs and protoc generation option
    set(PROTOC_OUTPUT_OPTIONS "")
    set(PROTOC_OUTPUT_DIRS "")
    if(GEN_CXX)
        list(APPEND PROTOC_OUTPUT_OPTIONS "--cpp_out=${ARG_CXX_DEST_DIR}")
        list(APPEND PROTOC_OUTPUT_DIRS ${ARG_CXX_DEST_DIR})
    endif()
    if(GEN_PY)
        list(APPEND PROTOC_OUTPUT_OPTIONS "--python_out=${ARG_PY_DEST_DIR}")
        list(APPEND PROTOC_OUTPUT_OPTIONS "--pyi_out=${ARG_PY_DEST_DIR}")
        list(APPEND PROTOC_OUTPUT_DIRS ${ARG_PY_DEST_DIR})
    endif()

    set(ALL_GENERATED_SOURCES "")
    # make the generated sources from respective proto file a group so that they will be generated
    # together if proto file updates or one of them is missing for some reason
    foreach(PROTO_SOURCE ${ARG_SOURCES})
        set(SOURCE_COMPILED "")
        set(HEADER_COMPILED "")
        set(GENERATED_SOURCES "")
        set(GENERATED_HEADERS "")
        get_filename_component(PROTO_SOURCE_NAME ${PROTO_SOURCE} NAME_WLE)
        # REVIEW: This method of getting protobuf compiled file is under the assumption of how
        # protobuf library today (30.2 as of writing) generates the output file names. This might
        # subject to change according to cmake documentation on FindProtobuf.
        # (https://cmake.org/cmake/help/latest/module/FindProtobuf.html)
        # NOTE: Following the convention that all generated files have the same name as source
        # files, with cxx output *.pb.cc and *.pb.h, python output *_pb2.py
        # generate c++ sources
        if(GEN_CXX)
            string(CONCAT SOURCE_COMPILED ${ARG_CXX_DEST_DIR} "/" ${PROTO_SOURCE_NAME} ".pb.cc")
            string(CONCAT HEADER_COMPILED ${ARG_CXX_DEST_DIR} "/" ${PROTO_SOURCE_NAME} ".pb.h")
            list(APPEND GENERATED_SOURCES ${SOURCE_COMPILED})
            list(APPEND GENERATED_HEADERS ${HEADER_COMPILED})
        endif()
        # generate python sources
        if(GEN_PY)
            string(CONCAT SOURCE_COMPILED ${ARG_PY_DEST_DIR} "/" ${PROTO_SOURCE_NAME} "_pb2.py")
            list(APPEND GENERATED_SOURCES ${SOURCE_COMPILED})
        endif()

        add_custom_command(
            # for language that generate headers, make sure headers are also in output with source
            # so they will also be generated if missing
            OUTPUT  ${GENERATED_SOURCES} ${GENERATED_HEADERS}
            COMMAND ${CMAKE_COMMAND} -E make_directory ${PROTOC_OUTPUT_DIRS}
            COMMAND protobuf::protoc -I=${ARG_SOURCE_DIR} ${PROTOC_OUTPUT_OPTIONS} ${PROTO_SOURCE}
            DEPENDS ${PROTO_SOURCE}
        )

        list(APPEND ALL_GENERATED_SOURCES ${GENERATED_SOURCES})
    endforeach()

    # return only the actual sources since header dependency will be solved by cmake
    set(${ARG_GEN_SOURCES} ${ALL_GENERATED_SOURCES} PARENT_SCOPE)
endfunction()

function(cxx_setup_target name)
    cmake_parse_arguments(ARG "" "NAME;TARGET" "SOURCES;INCLUDES;DEPENDS;COPTIONS;LOPTIONS;" ${ARGN})

    target_include_directories(${name} PUBLIC ${ARG_INCLUDES})
    target_link_libraries(${name} PUBLIC ${ARG_DEPENDS})

    list(TRANSFORM ARG_LOPTIONS PREPEND "LINKER:")
    target_compile_options(${name} PUBLIC ${ARG_COPTIONS})
    target_link_options(${name} PUBLIC ${ARG_LOPTIONS})


    if(EXPORT_TARGET_CONFIG)
        # FIXME: pretty print indent length hardcoded
        pad_string(indent_str "" 12 POST)
        string(CONCAT replace_str "\n" "${indent_str}")
        # list one source/include/depend per line
        string(REPLACE ";" ${replace_str} sources  "${ARG_SOURCES}")
        string(REPLACE ";" ${replace_str} includes "${ARG_INCLUDES}")
        string(REPLACE ";" ${replace_str} depends  "${ARG_DEPENDS}")
        # list all coptions and loptions in one line
        string(REPLACE ";" " " coptions "${ARG_COPTIONS}")
        string(REPLACE ";" " " loptions "${ARG_LOPTIONS}")

        string(CONCAT target_config_verbose
            "Cmake Location: ${CMAKE_CURRENT_SOURCE_DIR}\n"
            "  Compile target: ${name}\n"
            "  Sources:  ${sources}\n"
            "  Includes: ${includes}\n"
            "  Depends:  ${depends}\n"
            "  Compile Options: ${coptions}\n"
            "  Link Options: ${loptions}\n"
        )
        message(STATUS ${target_config_verbose})
    endif()

    # return target name to caller if ARG_TARGET is specified
    if(DEFINED ARG_TARGET AND NOT ${ARG_TARGET} STREQUAL "")
        set(${ARG_TARGET} ${name} PARENT_SCOPE)
    endif()
endfunction()

function(cxx_add_executable name)
    cmake_parse_arguments(ARG "" "NAME;TARGET" "SOURCES;INCLUDES;DEPENDS;COPTIONS;LOPTIONS;" ${ARGN})

    set(TARGET_NAME ${name})
    add_executable(${TARGET_NAME} ${ARG_SOURCES})
    cxx_setup_target(${TARGET_NAME} ${ARGN})
    if(DEFINED ARG_TARGET AND NOT ${ARG_TARGET} STREQUAL "")
        set(${ARG_TARGET} ${TARGET_NAME} PARENT_SCOPE)
    endif()
endfunction()

function(cxx_add_static_library name)
    cmake_parse_arguments(ARG "" "NAME;TARGET" "SOURCES;INCLUDES;DEPENDS;COPTIONS;LOPTIONS;" ${ARGN})

    set(TARGET_NAME ${name}-stc)
    add_library(${TARGET_NAME} MODULE ${ARG_SOURCES})
    cxx_setup_target(${TARGET_NAME} ${ARGN})
    set_target_properties(${TARGET_NAME} PROPERTIES OUTPUT_NAME ${name})
    if(DEFINED ARG_TARGET AND NOT ${ARG_TARGET} STREQUAL "")
        set(${ARG_TARGET} ${TARGET_NAME} PARENT_SCOPE)
    endif()
endfunction()

function(cxx_add_dynamic_library name)
    cmake_parse_arguments(ARG "" "NAME;TARGET" "SOURCES;INCLUDES;DEPENDS;COPTIONS;LOPTIONS;" ${ARGN})

    set(TARGET_NAME ${name}-dyn)
    add_library(${TARGET_NAME} MODULE ${ARG_SOURCES})
    cxx_setup_target(${TARGET_NAME} ${ARGN})
    set_target_properties(${TARGET_NAME} PROPERTIES OUTPUT_NAME ${name})
    if(DEFINED ARG_TARGET AND NOT ${ARG_TARGET} STREQUAL "")
        set(${ARG_TARGET} ${TARGET_NAME} PARENT_SCOPE)
    endif()
endfunction()

function(cxx_add_module name)
    cmake_parse_arguments(ARG "" "NAME;TARGET" "SOURCES;INCLUDES;DEPENDS;COPTIONS;LOPTIONS;" ${ARGN})

    set(TARGET_NAME ${name}-mod)
    add_library(${TARGET_NAME} MODULE ${ARG_SOURCES})
    cxx_setup_target(${TARGET_NAME} ${ARGN})
    set_target_properties(${TARGET_NAME} PROPERTIES OUTPUT_NAME ${name})
    if(DEFINED ARG_TARGET AND NOT ${ARG_TARGET} STREQUAL "")
        set(${ARG_TARGET} ${TARGET_NAME} PARENT_SCOPE)
    endif()
endfunction()
