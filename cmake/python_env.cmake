# Manage Python-related dependencies in the CMake build system.
#
# Provides:
#   Function `add_py3_pkg_dependencies` to add Python3 package dependencies to a CMake target.
#   Function `add_py3_pkg_requirements` to add global Python3 package requirements.
#   Target `generate_py3_requirements` to generate a Python3 requirements file.
#
# Function ::add_py3_pkg_dependencies(TARGET PKG_REQUIREMENTS)::
# Description:
#   Adds Python3 package dependencies to a CMake target.
# Arguments:
#   - TARGET: The CMake target that requires the Python3 packages.
#   - PKG_REQUIREMENTS: List of Python3 package requirements in the format that follows the Python PEP 440 standard.
# Required variables:
# ::PY3_PKG_EXISTENCE_DIR::
#   Directory to store Python3 package existence check files. Presumably a subdirectory of the
#   build directory.
# ::PY3_PKGDEP_CHK_SCRIPT::
#   Path to the Python3 script that checks for package requirements.
#
# Function ::find_py3_executable_module(MODULE_NAME):::
# Description:
#   Checks if a Python module is executable (i.e., has a __main__.py file).
# Arguments:
#   - MODULE_NAME: The name of the Python module to check.
# Required variables:
# ::PY3_EXEMOD_CHK_SCRIPT::
#   Path to the Python3 script that checks for executable modules.
# Returns:
#   - ${MODULE_NAME}_FOUND: True if the module is found, false otherwise.
#   - ${MODULE_NAME}_EXECUTABLE: The command to execute the module.
# Note:
#
# Function ::add_py3_pkg_requirements(<PKG_REQUIREMENTS> [ENV_SPECIFIC])::
# Description:
#   Adds a global Python3 package requirement to the build system.
# Arguments:
#   - PKG_REQUIREMENTS: List of Python3 package requirement in the format that follows the PEP 440 standard.
#   - ENV_SPECIFIC: If set, the package requirement is not added to the global list of requirements.
#
# Target ::generate_py3_requirements::
# Description:
#   Generates a python requirements file by combining all Python3 package requirements.
#
# Note:
# See exactly how version specifiers work at python PEP (PEP 440):
# https://peps.python.org/pep-0440/#version-specifiers
#
# Function ::add_py3_pkg_requirements(<PKG_REQUIREMENTS> [ENV_SPECIFIC])::
# Description:
#   Adds a global Python3 package requirement to the build system.
# Arguments:
#   - PKG_REQUIREMENTS: List of Python3 package requirement in the format that follows the PEP 440 standard.
#   - ENV_SPECIFIC: If set, the package requirement is not added to the global list of requirements.
#
# Target ::generate_py3_requirements::
# Description:
#   Generates a python requirements file by combining all Python3 package requirements.

include(${CMAKE_CURRENT_LIST_DIR}/misc.cmake)

include(${CMAKE_CURRENT_LIST_DIR}/misc.cmake)

include(${CMAKE_CURRENT_LIST_DIR}/misc.cmake)

find_package(Python3 COMPONENTS Interpreter REQUIRED)

function(add_py3_pkg_dependencies target)
    cmake_parse_arguments(ARG "" "TARGET" "PKG_REQUIREMENTS;" ${ARGN})

    if(NOT DEFINED PY3_PKGDEP_CHK_SCRIPT OR NOT EXISTS ${PY3_PKGDEP_CHK_SCRIPT})
        message(FATAL_ERROR "Python3 package dependency check script not found")
    endif()

    if(NOT DEFINED PY3_PKG_EXISTENCE_DIR)
        message(FATAL_ERROR "Python3 package existence directory not defined")
    endif()

    # create the package existence check directory if it does not exist
    if(NOT EXISTS "${PY3_PKG_EXISTENCE_DIR}")
        file(MAKE_DIRECTORY ${PY3_PKG_EXISTENCE_DIR})
    endif()
    assert_valid_path(PY3_PKG_EXISTENCE_DIR)

    foreach(PKG_REQUIREMENT ${ARG_PKG_REQUIREMENTS})
        # convert the requirements string into a valid cmake target name
        string(REGEX MATCH
            "^([A-Za-z_][A-Za-z0-9_-]*)((~=|==|!=|<=|>=|<|>|===)(.*))?"
            PKG_REQUIREMENT_MATCH ${PKG_REQUIREMENT})
        set(PY3PKG_NAME "${CMAKE_MATCH_1}")
        set(PY3PKG_CONSTRAINT_FULL "${CMAKE_MATCH_2}")
        set(PY3PKG_CONSTRAINT "${CMAKE_MATCH_3}")
        set(PY3PKG_VERSION "${CMAKE_MATCH_4}")

        if(${PY3PKG_CONSTRAINT} STREQUAL "~=")
            set(PY3PKG_CONSTRAINT "CPEQ")
        elseif(${PY3PKG_CONSTRAINT} STREQUAL "==")
            set(PY3PKG_CONSTRAINT "EXEQ")
        elseif(${PY3PKG_CONSTRAINT} STREQUAL "!=")
            set(PY3PKG_CONSTRAINT "NTEQ")
        elseif(${PY3PKG_CONSTRAINT} STREQUAL "<=")
            set(PY3PKG_CONSTRAINT "LTEQ")
        elseif(${PY3PKG_CONSTRAINT} STREQUAL ">=")
            set(PY3PKG_CONSTRAINT "GTEQ")
        elseif(${PY3PKG_CONSTRAINT} STREQUAL "<")
            set(PY3PKG_CONSTRAINT "LT")
        elseif(${PY3PKG_CONSTRAINT} STREQUAL ">")
            set(PY3PKG_CONSTRAINT "GT")
        elseif(${PY3PKG_CONSTRAINT} STREQUAL "===")
            set(PY3PKG_CONSTRAINT "ABEQ")
        else()
            message(FATAL_ERROR "Unsupported package requirement constraint: ${PKG_REQUIREMENT}")
        endif()

        string(REPLACE "." "_" PY3PKG_VERSION "${PY3PKG_VERSION}")
        set(PKG_REQUIREMENT_TARGET_NAME "PY3PKG_REQ_${PY3PKG_NAME}_${PY3PKG_CONSTRAINT}_${PY3PKG_VERSION}")

        # create a custom target for each package requirement if not already defined
        if(NOT TARGET ${PKG_REQUIREMENT_TARGET_NAME})
            set(REQUIREMENT_FNAME
                "${PY3_PKG_EXISTENCE_DIR}/${PKG_REQUIREMENT_TARGET_NAME}.ok")

            add_custom_command(
                OUTPUT ${REQUIREMENT_FNAME}
                # suppress installed package version output
                COMMAND ${Python3_EXECUTABLE} ${PY3_PKGDEP_CHK_SCRIPT} ${PKG_REQUIREMENT} >/dev/null
                # if previous command failed (package not found), the touch command will never run
                COMMAND ${CMAKE_COMMAND} -E touch ${REQUIREMENT_FNAME}
                DEPENDS ${Python3_EXECUTABLE}
                VERBATIM
            )

            add_custom_target(
                ${PKG_REQUIREMENT_TARGET_NAME}
                DEPENDS ${REQUIREMENT_FNAME}
                COMMENT "Checking for required Python3 package: ${PKG_REQUIREMENT}"
            )
        endif()

        # add the package requirement target as a dependency to the specified target
        add_dependencies(${target} ${PKG_REQUIREMENT_TARGET_NAME})

        message(STATUS "Auto-requiring Python3 package: ${PKG_REQUIREMENT_MATCH} for target ${target}")
    endforeach()
endfunction()

set(EXTRA_PY3_PKG_REQUIREMENTS_VAR EXTRA_PY3_PKG_REQUIREMENTS)
set_property(GLOBAL PROPERTY ${EXTRA_PY3_PKG_REQUIREMENTS_VAR} "")

function(add_py3_pkg_requirements pkg_req)
    cmake_parse_arguments(ARG "OPTIONAL;ENV_SPECIFIC" "PKG_REQUIREMENT" "" ${ARGN})

    if(GENERATE_GLOBAL_PY3_DEPENDENCY AND ARG_ENV_SPECIFIC)
        message(STATUS
            "GENERATE_GLOBAL_PY3_DEPENDENCY set, global Python3 package requirement ${pkg_req} is not added")
    elseif(GENERATE_ESSENTIAL_PY3_DEPENDENCY AND ARG_OPTIONAL)
        message(STATUS
            "GENERATE_ESSENTIAL_PY3_DEPENDENCY set, global Python3 package requirement: ${pkg_req} is not added")
    else()
        set_property(GLOBAL APPEND PROPERTY ${EXTRA_PY3_PKG_REQUIREMENTS_VAR} "${pkg_req}")
        message(STATUS "Adding global Python3 package requirement: ${pkg_req}")
    endif()
endfunction()

function(generate_py3_requirements)
    cmake_parse_arguments(ARG "" "INPUT_FILE;OUTPUT_FILE;" "" ${ARGN})

    set(GEN_PY3_PKGREQ_TARGET generate_py3_requirements)
    find_program(PIP_COMPILE_EXECUTABLE pip-compile)
    if(NOT PIP_COMPILE_EXECUTABLE)
        string(ASCII 27 Esc)
        message(STATUS
            "${Esc}[33m"
            "pip-compile not found, target ${GEN_PY3_PKGREQ_TARGET} will not be available. "
            "To install pip-compile, run `python3 -m pip install pip-tools`"
            "${Esc}[m"
        )
        return()
    endif()

    # create generated directory at input directory if it does not already exist
    get_filename_component(INPUT_DIR ${ARG_INPUT_FILE} DIRECTORY)
    cmake_path(APPEND GENERATED_DIR ${INPUT_DIR} "generated")
    if(NOT EXISTS ${GENERATED_DIR})
        file(MAKE_DIRECTORY ${GENERATED_DIR})
    endif()

    # write extra package requirements to a generated requirements file
    set(EXTRA_REQUIREMENTS_FILE "${GENERATED_DIR}/extra.in")
    set(NEW_EXTRA_REQUIREMENTS_FILE "${GENERATED_DIR}/extra.new.in")
    get_property(EXTRA_PY3_PKG_REQUIREMENTS GLOBAL PROPERTY ${EXTRA_PY3_PKG_REQUIREMENTS_VAR})
    set(EXTRA_PY3_PKG_REQUIREMENTS_CONTENTS "# === GENERATED BY CMAKE START ===\n")
    if(EXTRA_PY3_PKG_REQUIREMENTS)
        foreach(EXTRA_PY3_PKG_REQUIREMENT ${EXTRA_PY3_PKG_REQUIREMENTS})
            string(APPEND EXTRA_PY3_PKG_REQUIREMENTS_CONTENTS "${EXTRA_PY3_PKG_REQUIREMENT}\n")
        endforeach()
    endif()
    string(APPEND EXTRA_PY3_PKG_REQUIREMENTS_CONTENTS "# === GENERATED BY CMAKE END ===\n")
    file(WRITE ${NEW_EXTRA_REQUIREMENTS_FILE} "${EXTRA_PY3_PKG_REQUIREMENTS_CONTENTS}")

    # prevent cmake generate the target if cmake is run again but no changes are made
    if(EXISTS ${EXTRA_REQUIREMENTS_FILE})
        execute_process(
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    ${NEW_EXTRA_REQUIREMENTS_FILE} ${EXTRA_REQUIREMENTS_FILE}
        )
    else()
        execute_process(
            COMMAND ${CMAKE_COMMAND} -E copy
                    ${NEW_EXTRA_REQUIREMENTS_FILE} ${EXTRA_REQUIREMENTS_FILE}
        )
    endif()

    # merging all requirements, use relative path to avoid absolute path shown in generated file
    set(COMBINED_REQUIREMENTS_FILE "${GENERATED_DIR}/combined.in")
    cmake_path(RELATIVE_PATH COMBINED_REQUIREMENTS_FILE
        BASE_DIRECTORY ${CMAKE_SOURCE_DIR}
        OUTPUT_VARIABLE COMBINED_REQUIREMENTS_FILE_REL)
    cmake_path(RELATIVE_PATH ARG_OUTPUT_FILE
        BASE_DIRECTORY ${CMAKE_SOURCE_DIR}
        OUTPUT_VARIABLE OUTPUT_FILE_REL)

    add_custom_command(
        OUTPUT ${ARG_OUTPUT_FILE}
        COMMAND ${CMAKE_COMMAND} -E copy ${EXTRA_REQUIREMENTS_FILE} ${COMBINED_REQUIREMENTS_FILE_REL}
        COMMAND ${CMAKE_COMMAND} -E cat ${ARG_INPUT_FILE} >> ${COMBINED_REQUIREMENTS_FILE_REL}
        COMMAND ${PIP_COMPILE_EXECUTABLE} ${COMBINED_REQUIREMENTS_FILE_REL}
                --output-file ${OUTPUT_FILE_REL}
                --strip-extras >/dev/null 2>&1 # silence output
        DEPENDS ${EXTRA_REQUIREMENTS_FILE} ${ARG_INPUT_FILE}
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
        COMMENT "Generating Python3 requirements file via pip-compile, this may take a while"
    )

    add_custom_target(${GEN_PY3_PKGREQ_TARGET}
        DEPENDS ${ARG_OUTPUT_FILE}
        COMMENT "Generated Python3 requirements file to ${ARG_OUTPUT_FILE}"
    )

    message(STATUS "Python3 requirements file generation destination: ${ARG_OUTPUT_FILE}")
endfunction()

# include standard cmake arguments handling
include(FindPackageHandleStandardArgs)
# similar to find_package
function(find_py3_executable_module module_name)
    cmake_parse_arguments(ARG "REQUIRED;VERBOSE" "MODULE_NAME;VERSION_REQUIREMENT" "" ${ARGN})

    set(${module_name}_FOUND OFF)
    unset(${module_name}_MODULE)

    assert_valid_path(PY3_EXEMOD_CHK_SCRIPT)
    execute_process(
        COMMAND ${Python3_EXECUTABLE} ${PY3_EXEMOD_CHK_SCRIPT} ${module_name}
        RESULT_VARIABLE PYTHON_EXEMOD_FOUND)

    # executable module found
    if(PYTHON_EXEMOD_FOUND EQUAL 0)
        # get exemod version
        execute_process(
            COMMAND ${Python3_EXECUTABLE} ${PY3_PKGDEP_CHK_SCRIPT} ${module_name}
            OUTPUT_VARIABLE ${module_name}_VERSION
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
        set(${module_name}_FOUND ON)

        if(ARG_VERSION_REQUIREMENT)
            # check if the module version matches the requirement
            execute_process(
                COMMAND ${Python3_EXECUTABLE} ${PY3_PKGDEP_CHK_SCRIPT} "${module_name}${ARG_VERSION_REQUIREMENT}"
                OUTPUT_QUIET
                RESULT_VARIABLE MODULE_VERSION_RESULT
                OUTPUT_STRIP_TRAILING_WHITESPACE
            )
            if(NOT MODULE_VERSION_RESULT EQUAL 0)
                set(${module_name}_FOUND OFF)
            endif()
        endif()

        if(${module_name}_FOUND)
            set(${module_name}_MODULE "${module_name}")
        endif()
    endif()

    find_package_handle_standard_args(${module_name}
        REQUIRED_VARS ${module_name}_FOUND ${module_name}_MODULE ${module_name}_VERSION
        VERSION_VAR ${module_name}_VERSION
    )

    if(${module_name}_FOUND)
        message(STATUS "Found Python3 executable module: ${${module_name}_MODULE} (version ${${module_name}_VERSION})")
        set(${module_name}_FOUND ${${module_name}_FOUND} PARENT_SCOPE)
        set(${module_name}_MODULE ${${module_name}_MODULE} PARENT_SCOPE)
        set(${module_name}_VERSION ${${module_name}_VERSION} PARENT_SCOPE)
    else()
        set(SEVERITY WARNING)
        if (ARG_REQUIRED)
            set(SEVERITY FATAL_ERROR)
        elseif (ARG_VERBOSE)
            set(SEVERITY STATUS)
        endif()
        message(${SEVERITY} "Python3 executable module: ${module_name} not found.")
    endif()
endfunction()

# call the function after all other configurations are done
cmake_language(DEFER DIRECTORY ${CMAKE_SOURCE_DIR} CALL generate_py3_requirements
    INPUT_FILE ${RESOURCE_DIR}/requirements.in
    OUTPUT_FILE ${CMAKE_SOURCE_DIR}/requirement.txt
)
