from utils.logger import logging, Logger

comp_logger = Logger().register_component(__file__, name_level=1)

import abc
import utils.decorator as deco
from typing import Any


class MonitoredProc(abc.ABC):
    @abc.abstractmethod
    def __init__(self):
        pass

    @abc.abstractmethod
    def get_process_with_desc(self) -> dict[int, dict[str, Any]]:
        pass

    @abc.abstractmethod
    def get_process_pids(self) -> set[int]:
        pass

    def pids(self) -> set[int]:
        return self.get_process_pids()
