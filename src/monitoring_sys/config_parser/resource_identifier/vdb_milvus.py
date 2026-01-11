from utils.logger import logging, Logger

comp_logger = Logger().register_component(__file__, name_level=1)

from monitoring_sys.config_parser.resource_identifier import vdb_base


class MilvusDockerCompose(vdb_base.VDBMonitoredProc):
    @staticmethod
    def required_services():
        return {"etcd", "minio", "standalone"}

    def __init__(self, docker_compose_path):
        super().__init__()

        self.__docker_compose_inst = vdb_base.DockerComposeClient(docker_compose_path)
        self.__service_descs = self.__docker_compose_inst.get_service_descs()
        service_counts = {
            service_name: 0 for service_name in MilvusDockerCompose.required_services()
        }

        for _, service_info in self.__service_descs.items():
            service_name = service_info["Service"]
            if service_name in service_counts:
                service_counts[service_name] += 1

        invalid_services = {
            service_name: service_count
            for service_name, service_count in service_counts.items()
            if service_count != 1
        }
        assert len(invalid_services) == 0, comp_logger.get_augmented_message(
            f"Milvus docker compose find invalid services {invalid_services}, service count should be one"
        )

    def get_process_with_desc(self):
        return {desc["PID"]: desc["Service"] for desc in self.__service_descs.values()}

    def get_process_pids(self) -> set[int]:
        return {desc["PID"] for desc in self.__service_descs.values()}
