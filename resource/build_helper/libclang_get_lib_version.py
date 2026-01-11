# Get current system libclang version
# Usage: python3 libclang_get_lib_version.py [path_to_libclang.so]
# Outputs: the version number of the libclang shared library
# Returns: the version number of the libclang shared library

import ctypes
import sys, subprocess

# Determine libclang_path
if len(sys.argv) == 1:
    # Find using ldconfig
    p = subprocess.Popen(["ldconfig", "-p"], stdout=subprocess.PIPE, stderr=sys.stderr)
    sharedlibs, _ = p.communicate()
    assert p.returncode == 0, "Failed to run ldconfig command."

    import re
    line = [
        line.strip()
        for line in sharedlibs.decode().splitlines()
        if re.search(r"libclang-[0-9]+", line)
    ][-1]  # Get the last line that matches the regex
    libclang_path = line.split("=>")[-1].strip()
elif len(sys.argv) == 2:
    # Load a given libclang.so
    libclang_path = sys.argv[1]
else:
    sys.exit(1)

lib = ctypes.CDLL(libclang_path)

# Define CXString struct
class CXString(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.c_void_p),
        ("private_flags", ctypes.c_uint)
    ]

# Declare function signatures
lib.clang_getClangVersion.restype = CXString
lib.clang_getCString.argtypes = [CXString]
lib.clang_getCString.restype = ctypes.c_char_p
lib.clang_disposeString.argtypes = [CXString]

# Call the function
version = lib.clang_getClangVersion()
version_str = lib.clang_getCString(version).decode()
lib.clang_disposeString(version)

import sys, re
# Extract the version number using regex
match = re.search(r'version (\d+\.\d+\.\d+)', version_str)
if match:
    version_number = match.group(1)
    print(version_number)
else:
    sys.exit(1)