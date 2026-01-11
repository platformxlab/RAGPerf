from __future__ import annotations
from utils.logger import logging, Logger

comp_logger = Logger().register_component(__file__, name_level=1)

import os
import abc
import subprocess
import textwrap
import json
from typing import Any

from monitoring_sys.config_parser.resource_identifier import base


class VDBMonitoredProc(base.MonitoredProc):
    pass


class DockerComposeClient:
    def __init__(self, config_path) -> None:
        assert os.path.exists(config_path), comp_logger.get_augmented_message(
            f"Path {config_path} does not exist"
        )
        if os.path.isdir(config_path):
            config_path = os.path.join(config_path, "docker-compose.yml")
        assert os.path.isfile(config_path), comp_logger.get_augmented_message(
            f"Docker compose config does not exist in {config_path}"
        )
        self.__docker_compose_config_path = os.path.abspath(config_path)

    @staticmethod
    def required_fields():
        return {"Service", "ID", "PID"}

    @staticmethod
    def query_active_docker_compose_config_path(name: str) -> str | None:
        p = subprocess.Popen(
            [
                "docker",
                "inspect",
                "--format",
                r"""'{{ index .Config.Labels "com.docker.compose.project.config_files" }}'""",
                name,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        pret_stdout, pret_stderr = [msg.decode().strip() for msg in p.communicate()]
        docker_compose_config_path = pret_stdout.strip("'")

        if p.returncode != 0:
            comp_logger.log(
                logging.WARNING,
                f"Docker inspect on container with name {name} failed "
                f"with retcode {p.returncode} and message :\n"
                f"{textwrap.indent(pret_stderr, '  ')}",
            )
            return None
        return os.path.dirname(docker_compose_config_path)

    def get_service_descs(self):
        p = subprocess.Popen(
            [
                "docker",
                "compose",
                "-f",
                self.__docker_compose_config_path,
                "ps",
                "--format=json",
                "--status=running",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        pret_stdout, pret_stderr = [msg.decode().strip() for msg in p.communicate()]

        assert p.returncode == 0, comp_logger.get_augmented_message(
            f"Docker compose failed in with retcode {p.returncode} and message :\n"
            + textwrap.indent(pret_stderr, '  ')
        )

        container_descs = {}
        for desc in (json.loads(chunk) for chunk in pret_stdout.split('\n')):
            p = subprocess.Popen(
                ["docker", "inspect", "-f", r"{{.State.Pid}}", desc["ID"]], stdout=subprocess.PIPE
            )
            pid_str, _ = p.communicate()
            assert p.returncode == 0
            desc["PID"] = int(pid_str.strip())

            container_descs[desc["ID"]] = {
                field: desc[field] for field in DockerComposeClient.required_fields()
            }
        return container_descs
