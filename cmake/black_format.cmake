find_package(Python3 COMPONENTS Interpreter REQUIRED)

set(BLACK_FORMATTER_VERSION_REQUIREMENT ~=25.0)
add_py3_pkg_requirements("black${BLACK_FORMATTER_VERSION_REQUIREMENT}" OPTIONAL)
find_py3_executable_module(black VERSION_REQUIREMENT ${BLACK_FORMATTER_VERSION_REQUIREMENT} VERBOSE off)

if(NOT black_FOUND)
    message(STATUS "[Python Formatting] Matched black not found. Python formatting targets will not be available.")

    add_custom_target(install_black_py3pkg_requirements
        COMMAND ${Python3_EXECUTABLE} -m pip install "black${BLACK_FORMATTER_VERSION_REQUIREMENT}"
        COMMENT "Installing black${BLACK_FORMATTER_VERSION_REQUIREMENT}"
    )
else()
    message(STATUS "[Python Formatting] Using black ${black_VERSION}")

    if (NOT Python3_FOUND)
        message(FATAL_ERROR "[Python Formatting] Python3 interpreter not found")
    endif()

    find_file(BLACK_FORMAT_FILE .black-format
        PATHS "${BLACK_FORMAT_DIR}"
        NO_DEFAULT_PATH)

    # format code in place
    add_custom_target(python-format
        COMMAND ${Python3_EXECUTABLE} -m ${black_MODULE}
            --config "${BLACK_FORMAT_FILE}"
            --target-version py310
            --skip-string-normalization
            --exclude "${CMAKE_SOURCE_DIR}/third_party"
            "${CMAKE_SOURCE_DIR}"
        COMMAND echo "Black formatting complete"
        DEPENDS "${BLACK_FORMAT_FILE}"
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
        VERBATIM)

    # check for format violations
    add_custom_target(python-check-format
        COMMAND ${Python3_EXECUTABLE} -m ${black_MODULE}
            --config "${BLACK_FORMAT_FILE}"
            --check
            --diff
            --color
            --target-version py310
            --skip-string-normalization
            --exclude "${CMAKE_SOURCE_DIR}/third_party"
            "${CMAKE_SOURCE_DIR}"
        COMMAND echo "Black formatting complete"
        DEPENDS "${BLACK_FORMAT_FILE}"
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
        VERBATIM)
endif()