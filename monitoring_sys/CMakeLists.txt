include(msys_defs.cmake)

# assumes variable PYTHON_SRC_DIR is already set to the path of the python source directory
assert_valid_path(PYTHON_SRC_DIR)
assert_valid_path(THIRD_PARTY_DIR)

# === Module name ===
set(MSYS_MODULE_NAME libmsys)

# === PYBIND11 related ===
find_program(PYBIND11_STUBGEN pybind11-stubgen)
message(STATUS "Found pybind11-stubgen at ${PYBIND11_STUBGEN}")
set(PYBIND11_MKDOC_MODULE_NAME pybind11_mkdoc)
set(PYBIND11_MKDOC_MODULE_PATH ${THIRD_PARTY_DIR}/pybind11_mkdoc)

# check for libclang compatibility before aborting because of pybind11-mkdoc not found
get_libclang_sharedlib_version(LIBCLANG_VERSION)
if(NOT LIBCLANG_VERSION STREQUAL "")
    add_py3_pkg_dependencies(${INTERFACE_GEN_TARGET}
        PKG_REQUIREMENTS clang==${LIBCLANG_VERSION}
    )
    add_py3_pkg_requirements("clang==${LIBCLANG_VERSION}" ENV_SPECIFIC)
else()
    message(WARNING "Failed to auto infer libclang version and set requirement for ${MSYS_TARGET}.")
endif()

if (NOT PYBIND11_STUBGEN)
    message(WARNING
        "pybind11-stubgen not found, refuse to generate ${MSYS_MODULE_NAME} targets")
    return()
endif()

# === Setup module build ===
# pybind11_add_module is analogous to cmake add_library calls
pybind11_add_module(${MSYS_MODULE_NAME}
    ${MSYS_SOURCES}
)
cxx_setup_target(${MSYS_MODULE_NAME}
    INCLUDES ${MSYS_INCLUDES}
    DEPENDS  ${MSYS_DEPENDS}
    COPTIONS -flto=auto -Wall -Wextra -Werror # treat every warning as an error
    TARGET   MSYS_TARGET)
# avoid weird lto-wrapper warning on serial compilation
# Note: seems like -Wl,-flto=auto does not work, use direct -flto instead
target_link_options(${MSYS_TARGET} PUBLIC -flto=auto)
# specify the module name for the python module through macro definition
target_compile_definitions(${MSYS_TARGET} PUBLIC MSYS_MODNAME=${MSYS_MODULE_NAME})

# === Set up the python module ===
# Conda environment does not provide Development.Module and corresponding cmake files to get
# ${Python3_EXTENSION_SUFFIX} is missing. Use python interpreter to get the suffix instead.
# REVIEW: Maybe find a way to do this logic to use Development.Module
if (NOT DEFINED Python3_EXTENSION_SUFFIX OR "${Python3_EXTENSION_SUFFIX}" STREQUAL "")
    message(STATUS "Python3_EXTENSION_SUFFIX is not found, check with interpreter")
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))"
        OUTPUT_VARIABLE Python3_EXTENSION_SUFFIX_RET
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    message(STATUS "Using Python3_EXTENSION_SUFFIX=${Python3_EXTENSION_SUFFIX_RET}")
    set(Python3_EXTENSION_SUFFIX ${Python3_EXTENSION_SUFFIX_RET})
endif()

# setup the CPython shared lib extension
set_target_properties(${MSYS_TARGET} PROPERTIES
    PREFIX ""
    SUFFIX "${Python3_EXTENSION_SUFFIX}"
)

# === Generate rich interface ===
# enable stubgen with more information gathered from pybind11-mkdoc
set(INTERFACE_GEN_TARGET msys_gen_interface)
# target interface file specifications
set(INTERFACE_HEADER_NAME "pybind11_defs.h")
set(INTERFACE_HEADER_DIR ${CMAKE_CURRENT_LIST_DIR}/generated/interface)
set(INTERFACE_SOURCES ${CMAKE_CURRENT_LIST_DIR}/src/interface.cc)
# make interface generation a pre-build target
set(INTERFACE_PATH ${INTERFACE_HEADER_DIR}/${INTERFACE_HEADER_NAME})
add_custom_command(
    OUTPUT ${INTERFACE_PATH}
    COMMAND ${CMAKE_COMMAND} -E make_directory ${INTERFACE_HEADER_DIR}
    # generate rich interface, redir stderr to devnull to avoid confusing fatal error message
    # of cannot find include files when it tries to resolve all dependencies that are not
    # actually needed
    COMMAND ${CMAKE_COMMAND} -E env PYTHONPATH=${PYBIND11_MKDOC_MODULE_PATH}
            ${Python3_EXECUTABLE} -m ${PYBIND11_MKDOC_MODULE_NAME}
                                  -o ${INTERFACE_PATH} ${INTERFACE_SOURCES} 2>/dev/null
    DEPENDS ${INTERFACE_SOURCES}
)
add_custom_target(${INTERFACE_GEN_TARGET}
    # make sure the interface header is generated before building the target
    DEPENDS ${INTERFACE_PATH}
    COMMENT "Generate rich interface for ${MSYS_MODULE_NAME}"
)
# enable rich interface by specifying macro so c++ program knows it
target_compile_definitions(${MSYS_TARGET} PUBLIC PYBIND11_RICH_INTERFACE)
add_dependencies(${MSYS_TARGET} ${INTERFACE_GEN_TARGET})

# === Install the module ===
# symlink the library to ${PYTHON_SRC_DIR}/monitoring_sys folder and generate stub for the lib after
# build complete
set(MODULE_DESTINATION ${PYTHON_SRC_DIR}/monitoring_sys)
add_custom_target(${MSYS_MODULE_NAME}_pymod
    # symlink the shared lib to target directory
    COMMAND ${CMAKE_COMMAND} -E create_symlink
                $<TARGET_FILE:${MSYS_TARGET}>
                ${MODULE_DESTINATION}/$<TARGET_FILE_NAME:${MSYS_TARGET}>
    COMMAND ${CMAKE_COMMAND} -E cmake_echo_color --cyan
                "Symlink-ed lib in ${MODULE_DESTINATION}/$<TARGET_FILE_NAME:${MSYS_TARGET}>"
    # generate stub using pybind11-stubgen
    COMMAND ${CMAKE_COMMAND} -E env PYTHONPATH=${MODULE_DESTINATION}
            ${PYBIND11_STUBGEN} ${MSYS_MODULE_NAME} --output-dir "${MODULE_DESTINATION}"
    COMMAND ${CMAKE_COMMAND} -E cmake_echo_color --cyan "Stub generated in ${MODULE_DESTINATION}"

    WORKING_DIRECTORY $<TARGET_FILE_DIR:${MSYS_TARGET}>
    DEPENDS ${MSYS_MODULE_NAME}
    COMMENT "Build libmsys and position output product to src/monitoring_sys"
    VERBATIM
)
