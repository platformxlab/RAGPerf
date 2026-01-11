from utils.logger import logging, Logger

comp_logger = Logger().register_component(__file__)

import json
import re


class VDBConfig:
    @property
    def version(self):
        return 0.1

    def generate_config_file(self):
        pass

    def write_to_file(self, filepath):
        with open(filepath, "w") as fout:
            json.dump(self.generate_config_file(), fout)

    pass
