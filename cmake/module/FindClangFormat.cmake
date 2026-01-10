# FindClangFormat.cmake
#
# Tries to find clang-format of a specific version.
#
# Result Variables:
#   CLANG_FORMAT_EXECUTABLE — the path to the clang-format binary
#   CLANG_FORMAT_FOUND      — true if a suitable clang-format was found
#   CLANG_FORMAT_VERSION    — the version of clang-format found
#
# Cite: https://cmake.org/pipermail/cmake/2014-January/056677.html

# set search paths for clang-format
string(REPLACE ":" ";" CLANG_FORMAT_SEARCH_PATHS $ENV{PATH})

# reset output variables
set(CLANG_FORMAT_FOUND OFF)
unset(CLANG_FORMAT_EXECUTABLE)
unset(CLANG_FORMAT_VERSION)

# try to find clang-format executable in all search paths
foreach(CLANG_FORMAT_SEARCH_PATH ${CLANG_FORMAT_SEARCH_PATHS})
    file(REAL_PATH "${CLANG_FORMAT_SEARCH_PATH}" CLANG_FORMAT_SEARCH_PATH_REAL EXPAND_TILDE)
    file(GLOB CLANG_FORMAT_EXE_LIST ${CLANG_FORMAT_SEARCH_PATH_REAL}/clang-format*)
    foreach(CLANG_FORMAT_EXE_CANDIDATE ${CLANG_FORMAT_EXE_LIST})
        # Extract the version number from the output
        execute_process(
            COMMAND ${CLANG_FORMAT_EXE_CANDIDATE} --version
            OUTPUT_VARIABLE CLANG_FORMAT_CANDIDATE_VERSION_OUTPUT
            OUTPUT_STRIP_TRAILING_WHITESPACE
            ERROR_QUIET)
        string(REGEX MATCH
            "version ([0-9]+\\.[0-9]+\\.[0-9]+)"
            _ # discard the full match
            "${CLANG_FORMAT_CANDIDATE_VERSION_OUTPUT}")
        set(CLANG_FORMAT_CANDIDATE_VERSION "${CMAKE_MATCH_1}")

        # match the version number
        if(CLANG_FORMAT_CANDIDATE_VERSION)
            # Compare with required version
            if(DEFINED CLANG_FORMAT_REQUIRED_VERSION AND
                CLANG_FORMAT_CANDIDATE_VERSION VERSION_LESS CLANG_FORMAT_REQUIRED_VERSION)
                continue()
            endif()
        endif()

        # if we reach here, either a version requirement is not set or the candidate version matches
        set(CLANG_FORMAT_FOUND ON)
        set(CLANG_FORMAT_EXECUTABLE "${CLANG_FORMAT_EXE_CANDIDATE}")
        set(CLANG_FORMAT_VERSION "${CLANG_FORMAT_CANDIDATE_VERSION}")
        break()
    endforeach()
endforeach()

# standard cmake arguments handling
include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(ClangFormat
  REQUIRED_VARS CLANG_FORMAT_EXECUTABLE CLANG_FORMAT_VERSION
  VERSION_VAR CLANG_FORMAT_VERSION
)
