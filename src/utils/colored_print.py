import os, io, logging
from enum import Enum
import utils.env_variable as env

# respect NO_COLOR
no_color = env.no_color()


def color_settings(force_color: bool = False):
    global no_color
    no_color = force_color


class ANSIColors:
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    ENDC = "\033[0m"


class MessageLevel(Enum):
    EMERG = 0
    ALERT = 1
    CRIT = 2  # critical conditions
    ERR = 3  # error conditions
    WARNING = 4  # warning conditions
    NOTICE = 5  # normal but significant condition
    INFO = 6  # informational
    DEBUG = 7  # debug-level messages


class ColoredPrintSetting:
    MSG_COLOR_DICT: dict[int, str] = {
        logging.CRITICAL: ANSIColors.MAGENTA,
        logging.ERROR: ANSIColors.RED,
        logging.WARNING: ANSIColors.YELLOW,
        logging.INFO: ANSIColors.BLUE,
        logging.DEBUG: ANSIColors.CYAN,
    }


def colored_print(*args, ansi_color_str: str | ANSIColors, **kwargs) -> None:
    if no_color:
        print(*args, **kwargs)
    else:
        output_str = io.StringIO()
        with io.StringIO() as output_str:
            print(*args, file=output_str, end="")
            print(f"{ansi_color_str}{output_str.getvalue()}{ANSIColors.ENDC}", **kwargs)


def cprintf(*args, **kwargs):
    """Argument list same as print"""
    colored_print(
        *args, ansi_color_str=ColoredPrintSetting.MSG_COLOR_DICT[logging.CRITICAL], **kwargs
    )


def eprintf(*args, **kwargs):
    """Argument list same as print"""
    colored_print(*args, ansi_color_str=ColoredPrintSetting.MSG_COLOR_DICT[logging.ERROR], **kwargs)


def wprintf(*args, **kwargs):
    """Argument list same as print"""
    colored_print(
        *args, ansi_color_str=ColoredPrintSetting.MSG_COLOR_DICT[logging.WARNING], **kwargs
    )


def iprintf(*args, **kwargs):
    """Argument list same as print"""
    colored_print(*args, ansi_color_str=ColoredPrintSetting.MSG_COLOR_DICT[logging.INFO], **kwargs)


def dprintf(*args, **kwargs):
    """Argument list same as print"""
    colored_print(*args, ansi_color_str=ColoredPrintSetting.MSG_COLOR_DICT[logging.DEBUG], **kwargs)


def __check_level(level: str | int) -> int:
    # copying logging._checkLevel
    if isinstance(level, int):
        rv = level
    elif str(level) == level:
        if level not in logging._nameToLevel:
            raise ValueError("Unknown level: %r" % level)
        rv = logging._nameToLevel[level]
    else:
        raise TypeError("Level not an integer or a valid string: %r" % (level,))
    return rv


def lprintf(level: str | int, *args, **kwargs):
    """First arg is logging level Argument list same as print"""
    colored_print(
        *args, ansi_color_str=ColoredPrintSetting.MSG_COLOR_DICT[__check_level(level)], **kwargs
    )
