# === path resolution ===
from common import *

# === monitoring system import ===
from monitoring_sys import MSys

# === after monitoring system import ===
from utils.logger import logging, Logger

# === start of normal code ===
from monitoring_sys.config_parser.msys_config_parser import MSysConfig, StaticEnv, MacroTranslator
import utils.colored_print as cprint
import time

# reuse logger output folder
output_path = os.path.join(Logger().log_dirpath)


input_config_file = os.path.join(config_dir, "monitor", "example_config.yaml")
with open(input_config_file, "r") as fin:
    translated_config = MacroTranslator(StaticEnv.get_static_env("global")).translate(fin).read()
with open(os.path.join(output_path, "translated_msys_config.yaml"), "w") as fout:
    fout.write(translated_config)
monitor = MSys(MSysConfig.from_yaml_string(translated_config))

cprint.iprintf("Start test run")
ret = monitor.test_run()
monitor.report_status(verbose=False, detail=True)
cprint.iprintf(f"Test run finished w/ ret code {ret}")
if not ret:
    exit(1)

with monitor:
    time.sleep(5)
