cmake_minimum_required(VERSION 3.22)

project(rag_sys LANGUAGES C CXX)

# === CMake Options ===
option(FORMATTING_ONLY
    "Only generate format related targets" OFF)
option(GENERATE_GLOBAL_PY3_DEPENDENCY
    "Generate global Python3 package requirements, only asserted when excluding env-specific packages" OFF)
option(GENERATE_ESSENTIAL_PY3_DEPENDENCY
    "Generate essential Python3 package requirements (i.e., excluding formatting, QoL, etc.)" OFF)

# === CMake policy ===
# make CMAKE_INTERPROCEDURAL_OPTIMIZATION applies globally
set(CMAKE_POLICY_DEFAULT_CMP0069 NEW)

# === C/C++ standard ===
set(CMAKE_C_STANDARD 17)
set(CMAKE_CXX_STANDARD 20)

# === Cmake configurations ===
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_VERBOSE_MAKEFILE OFF)
# build type & optimization
set(CMAKE_BUILD_TYPE Release)
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()

# === Custom configurations ===
# Print all target building information formulated using cmake/build_helper.cmake:function(cxx_setup_target)
set(EXPORT_TARGET_CONFIG OFF)

# === Prioritize executables and libraries in conda environment ===
# if(DEFINED ENV{CONDA_PREFIX})
#     execute_process(
#         COMMAND [=[echo $SHELL; echo "${CONDA_PREFIX:-'$(dirname $(which conda))/../'}"]=]
#         OUTPUT_VARIABLE CONDA_CMAKE_PREFIX_PATH
#         COMMAND_ECHO STDOUT
#         ECHO_OUTPUT_VARIABLE
#     )
#     list(APPEND CMAKE_PREFIX_PATH "${CONDA_CMAKE_PREFIX_PATH}")
# endif()

# === Custom repository-wide variables ===
set(PYTHON_SRC_DIR ${CMAKE_SOURCE_DIR}/src)
set(RESOURCE_DIR ${CMAKE_SOURCE_DIR}/resource)

# === Create necessary directories ===
file(MAKE_DIRECTORY ${RESOURCE_DIR}/generated)

# === Include custom module subdirectories ===
set(CMAKE_MODULE_PATH
    ${CMAKE_SOURCE_DIR}/cmake/module
    ${CMAKE_MODULE_PATH})

# === Include utilities ===
# cmake utilities
include(cmake/utils.cmake)

# python utilities
set(PY3_PKG_EXISTENCE_DIR ${CMAKE_BINARY_DIR}/py3_pkg_info)
set(PY3_PKGDEP_CHK_SCRIPT ${RESOURCE_DIR}/build_helper/py3_require_package.py)
set(PY3_EXEMOD_CHK_SCRIPT ${RESOURCE_DIR}/build_helper/py3_require_executable_module.py)
include(cmake/python_env.cmake)

# === Code Formatting configuration ===
set(CLANG_FORMAT_DIR ${RESOURCE_DIR}/clang_format)
set(BLACK_FORMAT_DIR ${RESOURCE_DIR}/black_format)
include(cmake/clang_format.cmake)
include(cmake/black_format.cmake)
if(FORMATTING_ONLY)
    message(STATUS "Only running clang-format, skipping other configurations.")
    return()
endif()

# === Include other predefined cmake files ===
# c++ build helper
include(cmake/build_helper.cmake)

# misc
set(LIBCLANG_FIND_VERSION_SCRIPT ${RESOURCE_DIR}/build_helper/libclang_get_lib_version.py)
include(cmake/misc.cmake)

# third-party library import
set(THIRD_PARTY_DIR ${CMAKE_SOURCE_DIR}/third_party)
include(cmake/third_party.cmake)

# === Custom project-wide variables ===

# === Include subdirectories ===
add_subdirectory(monitoring_sys)
add_subdirectory(example)

# === Status report ===
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
