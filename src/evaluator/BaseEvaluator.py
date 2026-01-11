from abc import ABC, abstractmethod


class BaseEvaluator(ABC):
    def __init__(self, dataset_name: str) -> None:
        self.__dataset_name = dataset_name

    def __init__(self) -> None:
        pass

    @abstractmethod
    def evaluate_single(
        self, question: str, answer: str, contexts: list[str], ground_truth: str
    ) -> None:
        pass

    @abstractmethod
    def evaluate_dataset(self, dataset) -> None:
        pass
