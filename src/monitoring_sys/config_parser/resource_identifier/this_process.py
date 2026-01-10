from utils.logger import logging, Logger

comp_logger = Logger().register_component(__file__, name_level=1)

import os

from monitoring_sys.config_parser.resource_identifier import base


class ThisProcess(base.MonitoredProc):
    def __init__(self, description: str = "ThisProcess") -> None:
        self.__pid = os.getpid()
        self.__description = description

    def get_process_with_desc(self) -> dict[int, dict[str, str]]:
        return {self.__pid: {"Desc": self.__description}}

    def get_process_pids(self) -> set[int]:
        return {self.__pid}
