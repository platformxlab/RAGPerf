from __future__ import annotations

import utils.decorator as deco
import utils.env_variable as env
import utils.colored_print as cprint
import shutil

import os, sys, datetime, uuid, psutil, time
import logging

from absl import flags as abflags

abflags.DEFINE_string("log_dir", "log", "Path to dir that stores log files")
abflags.DEFINE_boolean(
    "create_log_dir", False, "Whether to create dir if designated log_dir does not exist"
)
abflags.DEFINE_boolean(
    "debug_no_logging_file", False, "Whether to disable logging to file, only print to stderr"
)


class LoggingCustomStreamFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%', validate=True, *, defaults=None):
        super().__init__(
            fmt=fmt, datefmt=datefmt, style=style, validate=validate, defaults=defaults
        )
        self.__formats = {
            level: f"{cprint.ColoredPrintSetting.MSG_COLOR_DICT[level]}{fmt}{cprint.ANSIColors.ENDC}"
            for level in (
                logging.DEBUG,
                logging.INFO,
                logging.WARNING,
                logging.ERROR,
                logging.CRITICAL,
            )
        }

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno in self.__formats:
            self._style._fmt = self.__formats[record.levelno]
        return super().format(record)


@deco.singleton
class Logger:
    """
    Wrapper of a two-level hierarchical logging.Logger
    """

    def __init__(self) -> None:
        # default log entry and log file time format
        self.__log_time_format = r"%Y-%m-%d %H:%M:%S %z"
        self.__dir_time_format = r"%Y-%m-%dT%H:%M:%S%z"

        self.__log_file_format = "[%(asctime)s](%(filename)s:%(lineno)d) %(levelname)s %(message)s"
        self.__log_stderr_format = "%(levelname)s %(message)s"

        abflags.FLAGS.unparse_flags()
        abflags.FLAGS(sys.argv, known_only=True)

        if not abflags.FLAGS.debug_no_logging_file:
            logging_folder = os.path.realpath(abflags.FLAGS.log_dir)

            # do not create folder by default if logging_folder is provided without create_dir_if_missing
            create_dir_if_missing = (
                not abflags.FLAGS["create_log_dir"].present or abflags.FLAGS.create_log_dir
            ) and (not abflags.FLAGS["log_dir"].present or abflags.FLAGS.create_log_dir)

            if not os.path.isdir(logging_folder):
                if not create_dir_if_missing:
                    cprint.eprintf(
                        f"Logger directory creation disabled with "
                        f"target directory {logging_folder} missing, abort",
                        file=sys.stderr,
                    )
                    exit(1)
                os.makedirs(logging_folder)

            dirname = datetime.datetime.now().astimezone().strftime(self.__dir_time_format)

            disambiguated_dirname = dirname
            disambiguated_abspath = os.path.join(logging_folder, dirname)
            while os.path.isdir(disambiguated_abspath):
                disambiguated_dirname = f"{dirname}.{uuid.uuid4()}"
                disambiguated_abspath = os.path.join(logging_folder, disambiguated_dirname)
            self.__log_folder = disambiguated_dirname
            self.__log_name = "python_rt.log"
            self.__log_dirpath = os.path.realpath(disambiguated_abspath)
            self.__log_path = os.path.realpath(os.path.join(disambiguated_abspath, self.__log_name))
            os.makedirs(os.path.join(logging_folder, self.__log_folder))

            # set logging file handler and format
            cur_root_handlers = logging.root.handlers
            assert len(cur_root_handlers) == 1
            cur_root_handlers[0].setFormatter(
                LoggingCustomStreamFormatter(
                    fmt=self.__log_stderr_format,
                    datefmt=self.__log_time_format,
                )
            )

            # add a file handler on top of the default stream handler
            handler = logging.FileHandler(
                filename=self.__log_path,
                mode="w",
                delay=True,
            )
            handler.setFormatter(
                logging.Formatter(
                    fmt=self.__log_file_format,
                    datefmt=self.__log_time_format,
                )
            )
            logging.root.addHandler(handler)
        else:
            self.__log_folder = ""
            self.__log_name = ""
            self.__log_dirpath = ""
            self.__log_path = ""

        # register this component and a default logger
        module_name = self.__get_readable_name(__file__, 0)
        self.__default_logger: logging.Logger = logging.root.getChild(module_name)
        self.__default_logger.setLevel(logging.DEBUG if env.is_debug() else logging.WARNING)
        self.__registered_logger_names = set()

    @property
    def default_logging_level(self) -> int:
        return self.__default_logger.level

    @property
    def log_folder(self) -> str:
        return self.__log_folder

    @property
    def log_filename(self) -> str:
        return self.__log_name

    @property
    def log_dirpath(self) -> str:
        return self.__log_dirpath

    @property
    def log_path(self) -> str:
        return self.__log_path

    @property
    def log_time_format(self) -> str:
        return self.__log_time_format

    @property
    def dir_time_format(self) -> str:
        return self.__dir_time_format

    def __get_comp_logger(self, comp_name: str) -> logging.Logger | None:
        return (
            logging.root.getChild(comp_name)
            if comp_name in self.__registered_logger_names
            else None
        )

    def __get_comp_logger_or_default(self, comp_name: str | None) -> logging.Logger:
        logger = None
        if comp_name is not None:
            logger = self.__get_comp_logger(comp_name)
        return self.__default_logger if logger is None else logger

    def __register_comp_logger(self, comp_name: str, level: str | int | None) -> None:
        if comp_name in self.__registered_logger_names:
            return
        self.__registered_logger_names.add(comp_name)
        self.__default_logger.getChild(comp_name).setLevel(
            level if level is not None else logging.NOTSET
        )

    def set_default_logging_level(self, level: str | int | None) -> int:
        self.__default_logger.setLevel(level if level is not None else logging.NOTSET)
        return self.__default_logger.level

    def set_component_logging_level(self, comp_name: str, level: str | int | None) -> int:
        logger = self.__get_comp_logger(comp_name)
        assert logger is not None, comp_logger.log(
            logging.ERROR, f"Component {comp_name} not registered"
        )
        logger.setLevel(level if level is not None else logging.NOTSET)
        return logger.getEffectiveLevel()

    def __get_readable_name(self, comp_name: str, name_level: int) -> str:
        """
        Get more human-readable name, interpreted from input component name (which is likely to be
        __file__ by design).

        Input Args:
            `comp_name`: input name, likely to be __file__ of corresponding component
            `name_level`: level of name to be returned, indicating number of directory levels
                included in front of the component name.

        Returns:
            more human-readable component name
        """
        comp_name = os.path.abspath(comp_name)

        dir_names = []
        comp_dir = os.path.dirname(comp_name)
        for _ in range(name_level):
            dir_names.append(os.path.basename(comp_dir))
            comp_dir = os.path.dirname(comp_dir)
        dir_name = " / ".join(dir_names).replace("_", " ").replace("-", " ")

        comp_name = os.path.basename(comp_name).split(".")[0]
        comp_name = comp_name.replace("_", " ").replace("-", " ")

        if len(dir_name) != 0:
            comp_name = f"{dir_name} / {comp_name}"
        if " " in comp_name:
            # for names with snake_case or kebab-case
            comp_name = " ".join([word.capitalize() for word in comp_name.split()])
        else:
            # for names with camelCase or PascalCase
            split_idxs = [0, *[i for i, c in enumerate(comp_name) if c.isupper()], len(comp_name)]
            comp_name = " ".join(
                [
                    comp_name[split_idxs[i] : split_idxs[i + 1]].capitalize()
                    for i in range(len(split_idxs) - 1)
                ]
            )
        return comp_name

    def register_component(
        self,
        comp_name: str,
        level: str | int | None = None,
        auto_readable: bool = True,
        name_level: int = 0,
    ) -> CompLogger:
        """
        Register a component with a name and logging level.

        If `auto_readable` is True, the component name will be converted to a more human-readable
        form, which is interpreted from the input component name (which is likely to be __file__ by
        design). The human-readable name will be formatted as:
        "[dir1] / [dir2] / ... / [component_name]", where [dir1], [dir2], ... are the directory
        names of the component file, and [component_name] is the name of the component file without
        extension, with underscores replaced by spaces and each word capitalized. The number of
        directory levels included in the name is determined by `name_level`. If a custom name is
        desired, set `auto_readable` to False and `comp_name` to the desired name.

        Args:
            `comp_name`: name of the component, likely to be __file__ of corresponding component
            `level`: logging level for this component, default to None (which means NOTSET)
            `auto_readable`: whether to convert the component name to a more human-readable form
                (default True)
            `name_level`: level of name to be returned, indicating number of directory levels
                included in front of the component name (default 1)

        Returns:
            A CompLogger instance for the component.

        Raises:
            AssertionError: if the component name is already registered.
        """
        if auto_readable:
            comp_name = self.__get_readable_name(comp_name, name_level)
        assert self.__get_comp_logger(comp_name) is None, comp_logger.log(
            logging.ERROR, f"Component name {comp_name} is registered twice"
        )
        self.__register_comp_logger(comp_name, level)
        return CompLogger(comp_name)

    def get_component_logging_header(self) -> str:
        return f"<%s> "

    def component_should_log(self, comp_name: str | None, level: int) -> bool:
        logger = None
        if comp_name is not None:
            logger = self.__get_comp_logger(comp_name)
        logger = self.__default_logger if logger is None else logger
        return logger.isEnabledFor(level)

    def log(
        self, comp_name: str | None, level: int, msg: str, *args, stacklevel=3, **kwargs
    ) -> None:
        """
        Log a message with the specified component name and logging level.

        Args:
            comp_name: The name of the component.
            level: The logging level.
            msg: The message to log.
            *args: Additional arguments to pass to the logger.
            stacklevel: The stack level to use for the logger, default to be 3 assuming calling from
                component logger.
            **kwargs: Additional keyword arguments to pass to the logger.
        """
        header: str = self.get_component_logging_header() if comp_name is not None else ""
        logger: logging.Logger = self.__get_comp_logger_or_default(comp_name)
        logger.log(level, header + msg, comp_name, *args, stacklevel=stacklevel, **kwargs)


class CompLogger:
    def __init__(self, comp_name: str):
        self.__comp_name = comp_name
        self.__logger = Logger()

    def log(self, level: int, msg: str, *args, **kwargs) -> None:
        self.__logger.log(self.__comp_name, level, msg, *args, **kwargs)

    @property
    def comp_name(self) -> str:
        return self.__comp_name

    def get_augmented_message(self, msg: str) -> str:
        header: str = (
            Logger().get_component_logging_header() if self.__comp_name is not None else ""
        )
        return header % self.__comp_name + msg


comp_logger = Logger().register_component(__file__)

import re
import sys
import atexit
import signal
import traceback

# saving the default exception handler
default_excepthook = sys.excepthook


def exc_handler(exctype, value, tb):
    """
    Replaced exception handler, added the functionality to log the exception and raise a SIGABRT.
    """
    # remove default stream handler so exceptions do not print to stderr
    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler):
            logging.root.removeHandler(handler)

    # invoke the default exception hook
    default_excepthook(exctype, value, tb)

    log_filename = Logger().log_path
    # only log when there is a log file
    if len(log_filename) != 0:
        # format message and log it
        msg = re.subn(r"%", r"%%", "".join(traceback.format_exception(exctype, value, tb)))[0]
        comp_logger.log(logging.FATAL, msg)
        # comp_logger must exist at this point
        # NOTE a ":0" is appended so that the colon in filename does not confuse some smart file path
        # resolvers (e.g. in VSCode)
        cprint.wprintf(
            comp_logger.get_augmented_message(f"Log saved to file {log_filename}:0"),
            file=sys.stderr,
        )
    # raise sigterm to signal program termination
    signal.raise_signal(signal.SIGABRT)


# register the custom exception handler with system
sys.excepthook = exc_handler


def log_time_breakdown(tag: str):
    time_ns = time.monotonic_ns()
    with open(os.path.join(Logger().log_dirpath, "time_break_down.txt"), "a") as fout:
        fout.write(f"{tag}, {time_ns}\n")
    return


def save_config_to_log_dir(config_path: str):
    """Copy the given config file into log_dirpath/config/"""
    log_dir = Logger().log_dirpath
    config_dir = os.path.join(log_dir, "config")
    os.makedirs(config_dir, exist_ok=True)

    # Copy config file
    dest_path = os.path.join(config_dir, os.path.basename(config_path))
    shutil.copy2(config_path, dest_path)
    print(f"[INFO] Config file saved to {dest_path}")
