import os, sys
import importlib.util

if len(sys.argv) != 2:
    print(
        f"{os.path.basename(sys.argv[0])} requires a module name as an argument",
        file=sys.stderr)
    exit(2)

def is_executable(module_name: str) -> bool:
    # First check if the module can be imported
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return False

    # If it's a package, try looking for module_name.__main__
    # (rather than module_name/__main__.py directly)
    main_spec = importlib.util.find_spec(f"{module_name}.__main__")
    if main_spec is not None and main_spec.origin and main_spec.origin.endswith("__main__.py"):
        return True

    return False

if not is_executable(sys.argv[1]):
    exit(1)
