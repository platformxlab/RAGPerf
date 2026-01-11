import os, functools

IS_DEBUG_ENVIORN = "DEBUG"
NO_COLOR_ENVIORN = "NO_COLOR"


def check_env(env: str) -> None | str:
    return os.environ.get(env, None)


def check_env_exists(env: str) -> bool:
    return env in os.environ


def check_env_exists_and_not_empty(env: str) -> bool:
    val = os.environ.get(env, None)
    return val is not None and len(val) != 0


def check_env_true(env: str) -> bool:
    """
    A environment variable is considered true if the variable exists and it is
    1) an integer with non-zero value, or
    2) a non-empty string
    """
    val = os.environ.get(env, None)
    if val is None:
        return False
    is_digit = val.isdigit()
    return (is_digit and int(val) != 0) or (not is_digit and len(val) != 0)


def set_env(env: str, val: str | int) -> None | str:
    ret = os.environ.get(env, None)
    if isinstance(val, int):
        val = str(val)
    os.environ[env] = val
    return ret


@functools.cache
def is_debug() -> bool:
    return check_env_exists(IS_DEBUG_ENVIORN)


@functools.cache
def no_color() -> bool:
    return check_env_exists_and_not_empty(NO_COLOR_ENVIORN)
