# Helper functions & targets

# Pad a string to a specified length with spaces
# ::OUTPUT_VAR:: Name of the variable to store the padded string
# ::STR:: The string to pad
# ::LEN:: The target length of the string
# ::LOCATION:: Where to add padding: PRE (before), POST (after)
function(pad_string OUTPUT_VAR STR LEN LOCATION)
    string(LENGTH "${STR}" strlen)

    if(strlen LESS ${LEN})
        math(EXPR padding_length "${LEN} - ${strlen}")
        string(REPEAT " " ${padding_length} padding)
        if(${LOCATION} STREQUAL PRE)
            set(STR "${padding}${STR}")
        elseif(${LOCATION} STREQUAL POST)
            set(STR "${STR}${padding}")
        else()
            message(FATAL_ERROR "Invalid pad_string LOCATION")
        endif()
    endif()

    set(${OUTPUT_VAR} "${STR}" PARENT_SCOPE)
endfunction()

# Asserts that a given path variable is defined and exists
# ::VAR_NAME:: Name of the variable to check
function(assert_valid_path VAR_NAME)
    if(NOT DEFINED ${VAR_NAME})
        message(FATAL_ERROR "Path variable '${VAR_NAME}' is not set.")
    endif()

    # Use indirect expansion to get the value of the variable
    set(VAR_VALUE "${${VAR_NAME}}")

    if(NOT EXISTS "${VAR_VALUE}")
        message(FATAL_ERROR "Path '${VAR_VALUE}' (from variable '${VAR_NAME}') does not exist.")
    endif()
endfunction()
