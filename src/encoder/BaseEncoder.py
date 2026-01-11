from abc import ABC, abstractmethod
from sentence_transformers import SentenceTransformer
import numpy as np
import time


# TODO make this to abstactmethods
class BaseEncoder(ABC):
    def __init__() -> None:
        pass

    @abstractmethod
    def load_encoder(self) -> None:
        pass

    @abstractmethod
    def free_encoder(self) -> None:
        pass

    @abstractmethod
    def embedding(self, texts) -> list[np.array]:
        pass

    @abstractmethod
    def multi_gpus_embedding(self, texts) -> list[np.array]:
        pass

    # @property
    # def dataset_name(self):
    # return self.__dataset_name

    # TODO add a dataset free
