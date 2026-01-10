# Manage third-party library imports in the CMake build system.
#
# Required variables:
# ::THIRD_PARTY_DIR::
#   Directory containing third-party libraries. Presumably a subdirectory of the project root.

# assumes variable THIRD_PARTY_DIR is already set to the path of the third-party directory
assert_valid_path(THIRD_PARTY_DIR)

# === define submodule import rules ===
# pybind11 support
function(add_pybind11)
    set(PYBIND11_FOLDER ${THIRD_PARTY_DIR}/pybind11)
    # === import options ===
    # === import ===
    add_subdirectory(${PYBIND11_FOLDER} third_party/pybind11)
    # === src, include, depends, coptions, and loptions ===
    set(PYBIND11_INCLUDES ${PYBIND11_FOLDER}/include PARENT_SCOPE)
endfunction()

# protobuf support
function(add_proto)
    set(PROTO_FOLDER ${THIRD_PARTY_DIR}/protobuf)
    # === import options ===
    # build abseil as static, do not dynamic link
    set(Protobuf_USE_STATIC_LIBS ON)
    set(protobuf_BUILD_SHARED_LIBS ON)
    set(CMAKE_POSITION_INDEPENDENT_CODE ON)
    set(BUILD_SHARED_LIBS ON)
    # === import ===
    add_subdirectory(${PROTO_FOLDER} third_party/protobuf)
    # === src, include, depends, coptions, and loptions ===
endfunction()

# pre-c++20 time zone info support
function(add_date)
    set(DATELIB_FOLDER ${THIRD_PARTY_DIR}/date)
    # === import options ===
    set(USE_SYSTEM_TZ_DB ON)
    set(BUILD_TZ_LIB ON)
    set(ENABLE_DATE_INSTALL OFF)
    # === import ===
    add_subdirectory(${DATELIB_FOLDER} third_party/date)
    # === src, include, depends, coptions, and loptions ===
endfunction()

# === actually import the submodules ===
add_pybind11()

# NOTE: Refer to protobuf version naming here: https://protobuf.dev/support/version-support/
find_package(Protobuf 6 CONFIG QUIET)
if(${Protobuf_FOUND})
    message(STATUS "Using system protobuf v${Protobuf_VERSION} (at ${Protobuf_DIR})")
else()
    # use third-party proto if there is no existing installation
    message(STATUS "Using protobuf module in third_party/")
    add_proto()
endif()

add_date()
