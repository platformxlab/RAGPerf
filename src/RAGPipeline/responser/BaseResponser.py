from abc import ABC, abstractmethod


class BaseResponser(ABC):
    def __init__(self, device=None):
        pass

    def __del__(self):
        pass

    @abstractmethod
    def load_llm(self) -> None:
        pass

    @abstractmethod
    def free_llm(self) -> None:
        pass

    @abstractmethod
    def query_llm(self, prompts, max_tokens=500, temperature=0.7, top_p=0.9) -> list[str]:
        pass
