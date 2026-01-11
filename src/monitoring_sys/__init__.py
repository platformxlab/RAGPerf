from __future__ import annotations

import sys
from unittest import mock

# NOTE: Supports for generating helps for flags is useful, and
# absl.app.define_help_flags provides that functionality. But in the process of
# importing absl.app, it will try to import absl.logging also. Importing
# absl.logging is not desired as it have more than expected compared to its c++
# counterpart (e.g., defining more flags are are not desired). Also, this
# library is using a customized logging scheme based on python logging module,
# so absl.logging should not be imported. We void the absl.logging module before
# importing the absl.app.define_help_flags to avoid undesired behavior.
with mock.patch.dict("sys.modules", {"absl.logging": mock.Mock()}):
    from absl import flags as abflags
    from absl.app import define_help_flags

from utils.logger import logging, Logger

comp_logger = Logger().register_component("MSys", auto_readable=False)

# real imports
import io
import re
import json
import types
import typing
import utils.colored_print as cprint
import monitoring_sys.libmsys as lms
from utils.python_utils import SupportsReadStr

# fuse c++ side interface into this module
from monitoring_sys.libmsys import *

from monitoring_sys.config_parser.msys_config_parser import MSysConfig


class MSys:
    @staticmethod
    def from_config_dict(config_dict: dict) -> MSys:
        return MSys(MSysConfig.from_config_dict(config_dict))

    @staticmethod
    def from_yaml_file(fp: SupportsReadStr) -> MSys:
        return MSys(MSysConfig.from_yaml_file(fp))

    @staticmethod
    def from_yaml_string(yaml_string: str) -> MSys:
        return MSys(MSysConfig.from_yaml_file(io.StringIO(yaml_string)))

    @staticmethod
    def from_msys_config(msys_config: MSysConfig) -> MSys:
        return MSys(msys_config)

    def __init__(self, msys_config: MSysConfig):
        self.__msys_config = msys_config
        self.__msys_id = lms.getMonitoringSystem(**msys_config.init_config)
        self.__msys_add_meter_functions = self.msys_add_monitor_functions

        for meter_property in msys_config.meter_configs:
            assert isinstance(meter_property, dict)
            meter_type = meter_property.pop("type", None)
            assert meter_type is not None, "Each meter must have a 'type' field"

            add_meter_func = self.__msys_add_meter_functions.get(meter_type, None)
            assert add_meter_func is not None, (
                f"Unknown meter type: {meter_type}, "
                f"available meters: {list(self.__msys_add_meter_functions.keys())}"
            )
            ret = add_meter_func(self.__msys_id, **meter_property)
            assert (
                ret
            ), f"Failed to add meter: {meter_type} with properties: {json.dumps(meter_property)}"

    def test_run(self) -> bool:
        return lms.testRun(self.__msys_id)

    def report_status(self, verbose: bool = False, detail: bool = False) -> None:
        lms.reportStatus(self.__msys_id, verbose, detail)

    def start_recording(self) -> bool:
        return lms.startRecording(self.__msys_id)

    def stop_recording(self) -> bool:
        return lms.stopRecording(self.__msys_id)

    def __enter__(self):
        assert self.start_recording(), "[MSys] Failed to start recording"
        return self

    def __exit__(self, exctype, value, tb):
        ret = self.stop_recording()
        if not ret:
            comp_logger.log(logging.ERROR, "[MSys] Failed to stop recording")
        if exctype is not None:
            comp_logger.log(logging.ERROR, f"Exception occurred in MSys monitor region")
            return False
        return True

    @property
    def msys_add_monitor_functions(self) -> dict[str, typing.Callable]:
        monitor_func_pattern = r"^add(.*)ToSystem$"
        return {
            regex_match.group(1): getattr(lms, func_name)
            for func_name in dir(lms)
            if (
                isinstance(getattr(lms, func_name), types.BuiltinFunctionType)
                and (regex_match := re.match(monitor_func_pattern, func_name))
            )
        }


# === code to run after importing module ===
# call absl helper to show all defined flags for all the imported modules
define_help_flags()
abflags.FLAGS.unparse_flags()

# filter argv and parse only known flags via absl
known_flags = set(abflags.FLAGS)
filtered_argv = [sys.argv[0]]  # keep program name
for arg in sys.argv[1:]:
    if arg.startswith("--"):
        key = arg.split("=")[0][2:]  # remove '--'
        if key in known_flags:
            filtered_argv.append(arg)
    else:
        filtered_argv.append(arg)
abflags.FLAGS(filtered_argv)

# initialize the monitoring system properly
assert initialize(Logger().log_dirpath), "[MSys] Initialization failed"
