# === helper functions ===
function(get_libclang_sharedlib_version OUTPUT_VAR)
    assert_valid_path(LIBCLANG_FIND_VERSION_SCRIPT)
    execute_process(
        COMMAND ${Python3_EXECUTABLE} ${LIBCLANG_FIND_VERSION_SCRIPT}
        OUTPUT_VARIABLE LIBCLANG_VERSION
        RESULT_VARIABLE LIBCLANG_VERSION_RESULT
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )

    if(NOT LIBCLANG_VERSION_RESULT EQUAL 0)
        message(WARNING "Failed to get libclang version from shared library.")
        set(${OUTPUT_VAR} "" PARENT_SCOPE)
        return()
    endif()

    set(${OUTPUT_VAR} "${LIBCLANG_VERSION}" PARENT_SCOPE)
endfunction()

# === targets ===
function(generate_list_targets_target)
    set(LIST_TARGET_TARGET_NAME list_targets)
    if(NOT TARGET ${LIST_TARGET_TARGET_NAME})
        add_custom_target(${LIST_TARGET_TARGET_NAME}
            COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target help
            COMMENT "List all available targets"
        )
    endif()
endfunction()
cmake_language(DEFER DIRECTORY ${CMAKE_SOURCE_DIR} CALL generate_list_targets_target)
