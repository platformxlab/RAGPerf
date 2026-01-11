# Manage the formatting of C/C++ source code using clang-format.
#
# Required variables:
# ::CLANG_FORMAT_DIR::
#   Directory containing the clang-format configuration files and scripts.
#
# Provides:
#   Target `format` to format the code in place.
#   Target `check-format` to check for formatting violations.
#
# Target ::cpp-format::
# Description:
#   Formats the code in place using clang-format.
#
# Target ::check-cpp-format::
# Description:
#   Checks for formatting violations using clang-format.

find_package(Python3 COMPONENTS Interpreter REQUIRED)
# use clang-format to enforce coding styles
# only clang-format version 14 or later supports --style=file:<format-file-path>
find_package(ClangFormat 14)

if(NOT CLANG_FORMAT_FOUND)
    message(STATUS "[C/CPP Formatting] Matched clang-format not found. Cpp formatting targets will not be available.")
else()
    message(STATUS "[C/CPP Formatting] Using clang-format ${CLANG_FORMAT_VERSION} (at ${CLANG_FORMAT_EXECUTABLE})")

    if (NOT Python3_FOUND)
        message(FATAL_ERROR "[C/CPP Formatting] Python3 interpreter not found")
    endif()

    # create formatting helper targets
    # using third party clang format python wrapper
    find_file(RUN_CLANG_FORMAT run_clang_format.py
        PATHS "${CLANG_FORMAT_DIR}"
        NO_DEFAULT_PATH)
    find_file(CLANG_FORMAT_FILE .clang-format
        PATHS "${CLANG_FORMAT_DIR}"
        NO_DEFAULT_PATH)
    file(GLOB CLANG_FORMAT_IGNORE_FILES "${CMAKE_SOURCE_DIR}/.clang-format-ignore")

    if(NOT RUN_CLANG_FORMAT)
        message(FATAL_ERROR "[C/CPP Formatting] run_clang_format.py not found. Check for repo integrity.")
    endif()

    # format code in place
    add_custom_target(cpp-format
        COMMAND "${Python3_EXECUTABLE}" "${RUN_CLANG_FORMAT}"
            "${CMAKE_SOURCE_DIR}"
            --clang-format-executable "${CLANG_FORMAT_EXECUTABLE}"
            --clang-format-style-file "${CLANG_FORMAT_FILE}"
            --clang-format-ignore     "${CLANG_FORMAT_IGNORE_FILES}"
            --recursive
            --in-place
        COMMAND echo "Clang-format complete"
        DEPENDS "${RUN_CLANG_FORMAT}"
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}")

    # check for format violations
    add_custom_target(cpp-check-format
        COMMAND "${Python3_EXECUTABLE}" "${RUN_CLANG_FORMAT}"
            "${CMAKE_SOURCE_DIR}"
            --clang-format-executable "${CLANG_FORMAT_EXECUTABLE}"
            --clang-format-style-file "${CLANG_FORMAT_FILE}"
            --clang-format-ignore     "${CLANG_FORMAT_IGNORE_FILES}"
            --recursive
        COMMAND echo "Clang-format check complete"
        DEPENDS "${RUN_CLANG_FORMAT}"
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}")
endif()
