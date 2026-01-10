# Check for Python package dependencies
# Usage: python3 py3_require_package.py "package_name[specifier]"
# Outputs: the installed version for the package if the requirement is met
# Returns: 0 if the requirement is met, non-zero otherwise

from importlib.metadata import version, PackageNotFoundError
from packaging.requirements import Requirement
import sys, os

if "NO_COLOR" in os.environ and len(os.environ["NO_COLOR"]) != 0:
    RED = ""
    RESET = ""
else:
    RED = "\033[31m"
    RESET = "\033[0m"

assert len(sys.argv) >= 2, "Usage: python3 py3_require_package.py 'package_name[specifier]'"

req = Requirement(sys.argv[1])
try:
    installed_version = version(req.name)
except PackageNotFoundError:
    print(
        f"{RED}[PyPkg Dependency Checker] Package {req.name} is not installed.{RESET}",
        file=sys.stderr)
    sys.exit(1)
if installed_version not in req.specifier:
    print(
        f"{RED}[PyPkg Dependency Checker] Package {req.name} is installed "
        f"(version {installed_version}) but does not satisfy the requirement: "
        f"{req.name}{req.specifier}{RESET}",
        file=sys.stderr)
    sys.exit(1)
print(installed_version)