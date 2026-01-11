import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
tests_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
root_dir = os.path.abspath(os.path.join(tests_dir, os.pardir))
python_src_dir = os.path.join(root_dir, "src")
config_dir = os.path.join(root_dir, "config")
sys.path.append(python_src_dir)

# === before monitoring system import ===
# Keep this to enable absl to dump meaningful help message when invoked with
# --[no]help, --[no]helpfull, --[no]helpshort, and --[no]helpxml
# TODO: figure out why adding this line will make absl flags behave normal
from absl import flags as abflags
import utils.python_utils as pyutils

# auto log_dir if not specified
if not any([p in arg for p in ["--log_dir", "--create_log_dir"] for arg in sys.argv]):
    sys.argv.append(f"--log_dir={os.path.join(pyutils.get_script_dir(__file__), 'output')}")
    sys.argv.append(f"--create_log_dir=True")
