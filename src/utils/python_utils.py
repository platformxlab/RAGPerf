import os
import sys
import hashlib
import subprocess
from typing import Protocol, runtime_checkable


# NOTE [Python typing on SupportsRead and SupportsWrite]:
# The typing module does not provide SupportsRead and SupportsWrite instances for runtime type
# checking, a custom implementation is provided below. The str version for SupportsRead and
# SupportsWrite is provided below.
@runtime_checkable
class SupportsReadStr(Protocol):
    def read(self, size: int | None = -1, /) -> str: ...


@runtime_checkable
class SupportsWriteStr(Protocol):
    def write(self, data: str, /) -> None: ...


def get_script_path(file: str) -> str:
    return os.path.realpath(file)


def get_script_dir(file: str) -> str:
    return os.path.dirname(get_script_path(file))


def printerr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def safeval(val, default):
    if val:
        return val
    return default


def hash_file(algo, path):
    assert algo in hashlib.algorithms_available, f"Hash algorithm {algo} is not supported"
    assert os.path.isfile(path), f"File \"{path}\" does not exist (Working dir \"{os.getcwd()}\")"
    bufsize = 131072
    hs = hashlib.new(algo)
    buf = bytearray(bufsize)
    mv = memoryview(buf)
    with open(path, "rb", buffering=0) as fin:
        while nbytes := fin.readinto(mv):
            hs.update(mv[:nbytes])
    return hs.hexdigest()


dependency_check_funcs = {
    "f": lambda s: os.path.isfile(s),
    "d": lambda s: os.path.isdir(s),
    "e": lambda s: os.access(s, os.F_OK),
    "r": lambda s: os.access(s, os.R_OK),
    "w": lambda s: os.access(s, os.W_OK),
    "x": lambda s: os.access(s, os.X_OK),
}


def check_dependency(test_type, dependency):
    func = dependency_check_funcs.get(test_type)
    assert func is not None, f"Invalid type string {test_type}"

    if func(dependency):
        return os.path.realpath(dependency)


def get_by_path(obj, path):
    keys = path.split('.')
    for key in keys:
        try:
            key = int(key)
        except ValueError:
            pass
        obj = obj[key]
    return obj


# def set_by_path(obj, path, value):
#     keys = path.split('.')
#     for key in keys[:-1]:
#         try:
#             key = int(key)
#         except ValueError:
#             pass
#         obj = obj[key]
#     last_key = keys[-1]
#     try:
#         last_key = int(last_key)
#     except ValueError:
#         pass
#     obj[last_key] = value


def find_device_for_path(path: str, device_name_only: bool = True) -> str | None:
    path = os.path.realpath(path)
    if not os.path.exists(path):
        return None
    dev = os.stat(path).st_dev

    with open("/proc/mounts") as f:
        for line in f:
            line_split = line.split()
            target_dev, mount_point, *_ = line_split
            try:
                if os.stat(mount_point).st_dev == dev:
                    if device_name_only:
                        return os.path.basename(target_dev)
                    return target_dev
            except Exception:
                continue
    return None
