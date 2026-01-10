from abc import ABC, abstractmethod


# should make the pipeline fully modular with request queue passing

# class ModularRAGPipeline(ABC):
#     def __init__(self, **kwargs):
#         # self.run_name = kwargs.get("run_name", "default_run")


class BaseRAGPipeline(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def process(self, request, batch_size=1) -> None:
        pass
