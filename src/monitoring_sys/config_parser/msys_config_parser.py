from __future__ import annotations
from utils.logger import logging, Logger

comp_logger = Logger().register_component(__file__, name_level=0)

import io
import re
import os
import yaml
import json
import copy
from typing import TYPE_CHECKING, Any, Callable, Final, Sequence, Type, TypeVar
from utils.python_utils import SupportsReadStr


class MSysConfig:
    @classmethod
    def from_config_dict(cls, config_dict: dict[str, Any]) -> MSysConfig:
        return cls(config_dict)

    @classmethod
    def from_yaml_file(cls, fp: SupportsReadStr) -> MSysConfig:
        config_dict = yaml.safe_load(fp)
        assert isinstance(config_dict, dict), "Invalid YAML format, expect input to be a dict"
        return cls(config_dict)

    @classmethod
    def from_yaml_string(cls, yaml_string: str) -> MSysConfig:
        config_dict = yaml.safe_load(yaml_string)
        assert isinstance(config_dict, dict), "Invalid YAML format, expect input to be a dict"
        return cls(config_dict)

    def __init__(self, config_dict: dict[str, Any]):
        msys_config = config_dict.get("MSys", None)
        assert msys_config is not None, "Config file must have 'MSys' field"
        self.__config: dict[str, Any] = copy.deepcopy(msys_config)

        msys_init_config = self.__config.get("system", None)
        assert msys_init_config is not None, "Config file must have 'MSys.system' field"
        self.__init_config = msys_init_config

        msys_meter_configs = self.__config.get("meter", None)
        assert msys_meter_configs is not None, "Config file must have 'MSys.meter' field"
        self.__meter_configs = msys_meter_configs

        for meter_config in self.__meter_configs:
            assert isinstance(meter_config, dict), "Each meter config must be a dict"

    @property
    def init_config(self) -> dict[str, Any]:
        return copy.deepcopy(self.__init_config)

    @property
    def meter_configs(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.__meter_configs)

    def add_init_config(self, new_configs: dict[str, Any]) -> MSysConfig:
        self.__init_config.update(new_configs)
        return self


class StaticEnv:
    def __init__(self):
        self.__static_env: dict[str, str | list[str]] = {}

    def add_env(self, env: dict[str, str | list[str]] | list[dict[str, str | list[str]]]) -> None:
        if isinstance(env, dict):
            self.__static_env.update(env)
        elif isinstance(env, list):
            for item in env:
                if isinstance(item, dict):
                    self.__static_env.update(item)

    def get_env(self, env_name: str) -> str | list[str] | None:
        return self.__static_env.get(env_name, None)

    def disp_env(self) -> None:
        print(json.dumps(self.__static_env, indent=2))

    __envs: dict[str, StaticEnv] = {}

    @classmethod
    def get_static_env(cls, env_name: str) -> StaticEnv:
        if env_name not in cls.__envs:
            cls.__envs[env_name] = StaticEnv()
        return cls.__envs[env_name]


class MacroTranslator:
    def __init__(self, env: StaticEnv):
        self.__env = env
        self.__pattern = r"\${{\s*([^\s]+)\s*}}"
        self.__list_pattern = r"^(\s*)\${{\s*-\s*([^\s]+).*$"

    T = TypeVar("T", str, SupportsReadStr)

    def translate(self, text: T) -> T:
        def replace_macro(match: re.Match) -> str:
            macro_name = match.group(1)
            replacement = self.__env.get_env(macro_name)
            if replacement is None:
                comp_logger.log(
                    logging.WARNING,
                    f"String macro {match.group(0).strip()} is not defined in environment",
                )
                return match.group(0)
            if not isinstance(replacement, str):
                comp_logger.log(
                    logging.WARNING,
                    f"String macro {match.group(0).strip()} expansion expects a string "
                    f"but found a {type(replacement).__name__}",
                )
                return match.group(0)
            return replacement

        def replace_list_macro(match: re.Match) -> str:
            prefix = match.group(1)
            macro_name = match.group(2)
            replacement = self.__env.get_env(macro_name)
            if replacement is None:
                comp_logger.log(
                    logging.WARNING,
                    f"List macro {match.group(0).strip()} is not defined in environment",
                )
                return match.group(0)
            if not isinstance(replacement, list):
                comp_logger.log(
                    logging.WARNING,
                    f"List macro {match.group(0).strip()} expansion expects a list "
                    f"but found a {type(replacement).__name__}",
                )
                return match.group(0)
            return "\n".join(f"{prefix}- {item}" for item in replacement)

        if isinstance(text, str):
            return re.sub(
                self.__pattern,
                replace_macro,
                re.sub(self.__list_pattern, replace_list_macro, text, flags=re.MULTILINE),
            )
        elif isinstance(text, SupportsReadStr):
            return io.StringIO(
                re.sub(
                    self.__pattern,
                    replace_macro,
                    re.sub(
                        self.__list_pattern, replace_list_macro, text.read(), flags=re.MULTILINE
                    ),
                )
            )
        else:
            assert False, "Unsupported type for translation"


# === Initialize Global StaticEnv ===
# TODO: Change these to be more user friendly in the future
global_env = StaticEnv.get_static_env("global")
# get all fields in MemMetadata.Probe and put them into StaticEnv
from proto.mem_metrics_pb2 import MemMetadata

global_env.add_env(
    {
        f"mem_mon.probe.{name}": str(val.number)
        for name, val in MemMetadata.Probe.DESCRIPTOR.values_by_name.items()
    }
)

from proto.gpu_metrics_pb2 import GPUMetadata

# get all fields in GPUMetadata.[NVML|GPM]Probe and put them into StaticEnv
global_env.add_env(
    [
        {
            f"gpu_mon.probe.{name}": str(val.number)
            for name, val in GPUMetadata.NVMLProbe.DESCRIPTOR.values_by_name.items()
        },
        {
            f"gpu_mon.probe.{name}": str(val.number)
            for name, val in GPUMetadata.GPMProbe.DESCRIPTOR.values_by_name.items()
        },
    ]
)

from proto.proc_metrics_pb2 import ProcMetadata

# get all fields in ProcMetadata.Probe and put them into StaticEnv
global_env.add_env(
    {
        f"proc_mon.probe.{name}": str(val.number)
        for name, val in ProcMetadata.Probe.DESCRIPTOR.values_by_name.items()
    }
)


import pynvml

pynvml.nvmlInit()
global_env.add_env(
    {
        f"gpus.all_gpus": [str(idx) for idx in range(pynvml.nvmlDeviceGetCount())],
    }
)

from monitoring_sys.config_parser.resource_identifier.this_process import ThisProcess
import utils.python_utils as pyutils

src_dev = pyutils.find_device_for_path(os.path.abspath(__file__))
src_dev2 = pyutils.find_device_for_path(os.path.abspath("/mnt/data1"))
print(f"Source file device: {src_dev}, /mnt/data1 device: {src_dev2}")
assert src_dev is not None, "Cannot find device for current source file"
global_env.add_env(
    {
        "this_process.pids": [str(pid) for pid in ThisProcess().get_process_pids()],
        "this_process.used_disks": [src_dev, src_dev2],
    }
)

from monitoring_sys.config_parser.resource_identifier.vdb_base import DockerComposeClient
from monitoring_sys.config_parser.resource_identifier.vdb_milvus import MilvusDockerCompose

# Vector DB
vdbs_pids: list[str] = []
vdbs_used_disks: list[str] = []
try:
    # milvus
    milvus_config_path = DockerComposeClient.query_active_docker_compose_config_path(
        "milvus-standalone"
    )
    milvus_docker_compose = MilvusDockerCompose(milvus_config_path)

    # processes
    milvus_pids = [str(pid) for pid in milvus_docker_compose.get_process_pids()]
    vdbs_pids.extend(milvus_pids)
    global_env.add_env({"vdb.milvus.pids": milvus_pids})

    # used disks
    assert milvus_config_path is not None
    milvus_used_disk = pyutils.find_device_for_path(milvus_config_path)
    assert milvus_used_disk is not None
    milvus_used_disks = [milvus_used_disk]
    global_env.add_env({"vdb.milvus.used_disks": milvus_used_disks})
    vdbs_used_disks.extend(milvus_used_disks)
except Exception:
    pass
global_env.add_env({"vdbs.pids": vdbs_pids})
global_env.add_env({"vdbs.used_disks": vdbs_used_disks})

global_env.add_env(
    {
        "pylogger.log_dirpath": Logger().log_dirpath,
    }
)
