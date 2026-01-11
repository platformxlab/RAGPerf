#!/bin/bash

# Prepend this before every script that use this utils file
# script_dir="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
# script_name="$( basename -- "${BASH_SOURCE[0]}" )"
# source "$script_dir"/bash_utils.sh || exit 254 # replace with correct relative path if needed

# Get script path
# script_dir="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Color strings {{{
# Respect env variable NO_COLOR
if [[ -z "${NO_COLOR}" ]]; then
    RED="$(tput setaf 1)"
    GREEN="$(tput setaf 2)"
    YELLOW="$(tput setaf 3)"
    BLUE="$(tput setaf 4)"
    MAGENTA="$(tput setaf 5)"
    CYAN="$(tput setaf 6)"
    ENDC="$(tput sgr0)"
else
    RED=""
    GREEN=""
    YELLOW=""
    BLUE=""
    MAGENTA=""
    CYAN=""
    ENDC=""
fi
# }}}

printerr() {
    # shellcheck disable=SC2059
    printf "$1" "${@:2}" >&2
}

wprinterr() {
    # shellcheck disable=SC2059
    printf "${YELLOW}$1${ENDC}" "${@:2}" >&2
}

eprinterr() {
    # shellcheck disable=SC2059
    printf "${RED}$1${ENDC}" "${@:2}" >&2
}

dump_stack() {
    # $1 skip stack level
    if [ "$#" -eq 1 ]; then
        local i="$1"
    else
        local i=0
    fi
    local line_no function_name file_name
    wprinterr "Traceback (most recent call last):\n"
    while caller "$i"; do
        (( i++ ))
    done | while read -r line_no function_name file_name; do
        wprinterr "  File \"%s\", line %s, in %s\n" "$file_name" "$line_no" "$function_name"
        wprinterr "    %s\n" "$(sed "${line_no}q;d" "$file_name" | sed "s/^\s*//g")"
    done
}

show_current_stackframe() {
    # $1 skip stack level
    if [ "$#" -eq 1 ]; then
        local i="$1"
    else
        local i=0
    fi
    local line_no function_name file_name
    caller "$i" | while read -r line_no function_name file_name; do
        printerr "Abort at file \"%s\", line %s, in %s\n" "$file_name" "$line_no" "$function_name"
    done
}

__assert() {
    # $1 dump stack skip level
    # $2 should the value equal to zero?
    # $3 [optional] value to be judge on
    # $4 [optional] message
    # $5... [optional] arguments to be formatted
    # return: 0 on success, 1 otherwise, 255 internal error
    local err_str="Assertion Failed"
    if [ "$#" -eq 0 ]; then
        printf "__assert() internal error, called with no args\n"
        exit 255
    elif [ "$#" -eq 1 ] || [ "$#" -eq 2 ]; then
        # assert with no args
        :
    elif { [ "$2" -ne 0 ] && [ "$3" -ne 0 ]; } || { [ "$2" -eq 0 ] && [ "$3" -eq 0 ]; }; then
        if [ "$#" -ge 4 ]; then err_str="$err_str: $4"; fi
    else
        # assert not triggered
        return 0
    fi
    printf "$err_str\n" "${@:5}"
    dump_stack $(( 1 + "$1" ))
    return 1
}

exit_on_retval() {
    # $1 override return value, 0 to forward
    local retval=$?
    local act_retval=0
    if [ "$#" -eq 0 ]; then
        act_retval="$retval"
    elif [ "$#" -eq 1 ]; then
        act_retval="$1"
        if ! is_valid_errcode "$act_retval"; then
            act_retval="${predef_errcode_revmap[$act_retval]}"
        fi
        if [[ $act_retval =~ ^[0-9]+$ ]] && (( "$act_retval" >= 0 )) && (( "$act_retval" <= 255 )); then
            [ "$act_retval" -eq 0 ] && act_retval="$retval"
        else
            assert 0 \
                "exit_on_retval internal error, return value <%s> is not an integer between 0 and 255" \
                "$act_retval"
            exit 255
        fi
    else
        assert 0 "exit_on_retval internal error, argument ill-formatted"
        exit 255
    fi
    if [ "$retval" -ne 0 ]; then exit "$act_retval"; fi
    return $retval
}

# assert & assert_zero
# $1 [optional] value to be judge on
# $2 [optional] message
# $3... [optional] arguments to be formatted
# return 1 if assertion failed
assert()                   { __assert 1 0 "$@"; }
assert_zero()              { __assert 1 1 "$@"; }

# assert_exit_default & assert_zero_exit_default
# $1 [optional] value to be judge on
# $2 [optional] message
# $3... [optional] arguments to be formatted
# exit 1 if assertion failed
assert_exit_default()      { __assert 1 0 "$@"; exit_on_retval; }
assert_zero_exit_default() { __assert 1 1 "$@"; exit_on_retval; }


# assert_exit & assert_zero_exit
# $1 exit code when assertion failed
# $2 [optional] value to be judge on
# $3 [optional] message
# $4... [optional] arguments to be formatted
# exit <exit_code> if assertion failed
assert_exit()              { __assert 1 0 "${@:2}"; exit_on_retval "$1"; }
assert_zero_exit()         { __assert 1 1 "${@:2}"; exit_on_retval "$1"; }

# assert_false_exit
# $1 exit code when assertion failed
# $2 [optional] message
# $3... [optional] arguments to be formatted
# exit <exit_code> if assertion failed
assert_false_exit()        { __assert 1 1 1 "${@:2}"; exit_on_retval "$1"; }

declare -A predef_errcode
declare -A predef_errcode_revmap
declare -A predef_errcode_dscr

is_valid_errcode() {
    [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -ge 0 ] && [ "$1" -le 255 ]
    return $?
}

define_errcode() {
    #1 errcode
    #2 errstr
    #3 errdscr
    local errcode="$1"
    local errstr="$2"
    local errdscr="$3"
    if ! is_valid_errcode "$errcode"; then
        assert_false_exit 255 \
            "Error when defining errcode, exit code <%s> is not an integer between 0 and 255" \
            "$errcode"
    fi
    if is_valid_errcode "$errstr"; then
        assert_false_exit 255 \
            "Error when defining errcode, error string <%s> cannot be an integer between 0 and 255" \
            "$errstr"
    fi
    if [[ -v predef_errcode[$errcode] ]] && [[ $err_str != "${predef_errcode[$errcode]}" ]]; then
        assert_false_exit 255 \
            "Error when defining errcode, errcode %d already defined with errstr %s" \
            "$errcode" "${predef_errcode[$errcode]}"
    fi

    predef_errcode[$errcode]="$errstr"
    predef_errcode_revmap[$errstr]=$errcode
    predef_errcode_dscr[$errcode]="$errdscr"
}

get_errcode_from_errstr() {
    local errstr="$1"
    [[ -v predef_errcode_revmap[$errstr] ]] || assert_false_exit 255 \
        "Error when defining errcode, error string <%s> cannot be an integer between 0 and 255" \
        "$errstr"
    printf "%d" "${predef_errcode_revmap[$errstr]}"
}

# predefined error codes
define_errcode 0 "normal_termination" "script terminates correctly"
define_errcode 253 "user_abort" "user abort"
define_errcode 254 "dependency_error" "dependency error"
define_errcode 255 "internal_error" "internal error"

display_predef_errcode() {
    printerr "Return values\n"
    for errcode in $(echo "${!predef_errcode_dscr[@]}" | xargs -n1 | sort -h); do
        local errcode_dscr="${predef_errcode_dscr[$errcode]}"
        printerr "  %-3s %s\n" "$errcode" "$errcode_dscr"
    done
}

abort() {
    # $1 error code/error string
    # $3 [optional] message
    # $4... [optional] arguments to be formatted
    local exit_input="$1"
    local extra_dscr=""
    if is_valid_errcode "$exit_input"; then
        exit_code="$exit_input"
    else
        exit_code="${predef_errcode_revmap[$exit_input]}"
    fi
    if [[ -v predef_errcode[$exit_code] ]]; then extra_dscr=" (${predef_errcode[$exit_code]})"; fi
    if [[ $# -ge 2 ]]; then
        printf "Abort%s: $2\n" "$extra_dscr" "${@:3}"
    else
        printf "Abort%s\n" "$extra_dscr"
    fi
    show_current_stackframe 1
    exit "$exit_code"
}

check_and_abort() {
    # $1 exit code
    # $3 [optional] message
    # $4... [optional] arguments to be formatted
    if [[ $1 -ge 64 ]]; then
        abort "${@}"
    fi
}

check_dependency() {
    # $1 check type
    # $2 dependency
    # $3 [optional] verbose (default to true)
    local retval
    test -"$1" "$2"
    retval=$?
    if [ $retval -eq 2 ]; then
        assert_false_exit internal_error
    elif [ $retval -eq 0 ]; then
        printf "%s" "$(realpath "$2")"
        return 0
    else
        printf "%s" "$2"
        if [ $# -le 2 ]; then
            printerr "Dependency <%s> not found\n" "$2"
        fi
        return "$(get_errcode_from_errstr dependency_error)"
    fi
}

pretty_countdown() {
    [ "$#" -ge 2 ]; assert_zero_exit $?

    local from=$2
    local interval=1
    local wait_time remaining
    for wait_time in $(seq 0 "$interval" "$(echo "$from + $interval - 1" | bc)"); do
        remaining="$(echo "scale=9; $from - $wait_time" | bc)"
        printf "\r\033[2K%s %s" "$1" "$remaining"
        sleep "$(echo "$interval + (($interval > $remaining) * ($remaining - $interval))" | bc)"
    done
    printf "\r\033[2K%s 0" "$1"
    printf "\n"
}

display_time() {
    printf "### Current time BEGIN ###########################################\n"
    timedatectl | sed -e "s/^/# /"
    printf "### Current time END #############################################\n"
}

# The input content should follow the below format:
# 1. Each line is treated as an entry
# 2. The key and value is separated using specified delimiter (could be multiple char)
# Note that:
# 1. Delimiter searching is greedy, from left to right
as_associative_arr() {
    # $1 variable name, should be an associate array
    # $2 content
    # $3 delimiter
    [ "$#" -eq 3 ]; assert_zero $?

    local row rows assignment_expr
    readarray rows <<< "$2"
    for row in "${rows[@]}"; do
        assignment_expr="$(sed -re "s/([^\\$3 ]*)\s*\\$3\s*(.*)\s*/[\"\1\"]=\"\2\"/" <<< "$row")"
        if [[ $assignment_expr =~ \[.*\]=.* ]]; then
            eval "$1$assignment_expr"
        else
            printerr "Error when translate line \"%s\", skipping insertion\n" "$row"
        fi
    done
}

# https://stackoverflow.com/questions/1527049/how-can-i-join-elements-of-a-bash-array-into-a-delimited-string
str_join() {
    # $1 delimiter
    # $2... strings to be concatenated
    local d=${1-} f=${2-}
    if shift 2; then
        printf %s "$f" "${@/#/$d}"
    fi
}

display_options() {
    # $1 option list <option:explanation>
    # $2 default option
    # $3 result var name
    # $4 print option long descriptions
    # $5 [optional] message
    # $6... [optional] arguments to be formatted
    local -n options_ref="$1"
    local display_options=()
    local default_selection="$2"
    local result_var="$3"
    local message="$5"
    local short_format=1
    local option_selected=0
    # determine if option is using short format
    for option in "${!options_ref[@]}"; do
        if [[ ${#option} -ne 1 ]]; then
            short_format=0
            break;
        fi
    done
    # display header message
    if [[ -z $message ]]; then message="Select from options"; fi
    # shellcheck disable=SC2059
    printf "$message\n" "${@:6}"
    for option in "${!options_ref[@]}"; do
        if [[ $short_format -ne 0 ]]; then
            [[ $option == [a-z] ]] || \
                assert_false_exit 255 "%s internal error, option <%s> is ill-formatted, not matching regex [a-z]" \
                    "${FUNCNAME[0]}" "$option"
            if [[ "$default_selection" == "$option" ]]; then
                option="${option^^}"
                option_selected=1
            fi
            print_delimiter=""
        else
            [[ $option =~ [a-z]+ ]] || \
                assert_false_exit 255 "%s internal error, option <%s> is ill-formatted, not matching regex [a-z]+" \
                    "${FUNCNAME[0]}" "$option"
            if [[ "$default_selection" == "$option" ]]; then
                option="[$option]"
                option_selected=1
            fi
            print_delimiter="/"
        fi
        display_options+=( "$option" )
    done
    [[ $option_selected -eq 1 ]] || \
        assert_false_exit 255 "Default option %s is not found in option list" "$default_selection"
    # display option and help messages
    local max_opt_len=0
    local default_mark_str="(default) "
    for option in "${!options_ref[@]}"; do
        local opt_len="${#option}"
        max_opt_len=$(( max_opt_len > opt_len ? max_opt_len : opt_len ))
    done
    for option in "${!options_ref[@]}"; do
        if [[ "$default_selection" == "$option" ]]; then default_str="$default_mark_str"; else default_str=""; fi
        # shellcheck disable=SC2059
        printf "  %${#default_mark_str}s%${max_opt_len}s: %s\n" "$default_str" "$option" "${options_ref[$option]}"
    done
    # display selection prompt
    printf "  Selection (%s) ? " "$(str_join "$print_delimiter" "${display_options[@]}")"
    selection=""
    while :; do
        read -r selection
        selection="${selection,,}"
        if [[ -z "$selection" ]]; then selection="$default_selection"; fi
        if [[ -v options_ref[$selection] ]]; then
            printf -v "$result_var" "%s" "$selection"
            return
        else
            # display re-selection prompt
            printf "  Invalid selection (%s) ? " "$(str_join "$print_delimiter" "${display_options[@]}")"
        fi
    done
}

display_yes_no_option() {
    # $1 message
    # $2... [optional] arguments to be formatted
    declare -A options
    declare selection
    options=(
        ["y"]="confirm"
        ["n"]="deny"
    )
    display_options options n selection 0 "$@"
    unset options
    if [ "$selection" == "y" ]; then return 0; fi
    return 1;
}

# pretty printing
time_print_interval() {
  total_time="$1"
  interval="$2"
  current_time=0
  while [ "$current_time" -lt "$total_time" ]; do
    sleep_time=$(("$total_time" - "$current_time"))
    sleep_time=$(("$sleep_time" > "$interval" ? "$interval" : "$sleep_time"))
    echo "$current_time/$total_time sleep $sleep_time"
    sleep "$sleep_time"
    current_time=$(("$current_time" + "$interval"))
  done
}
