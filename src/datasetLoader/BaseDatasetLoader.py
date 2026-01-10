from abc import ABC, abstractmethod
import pandas as pd


class BaseDatasetLoader(ABC):
    def __init__(self, dataset_name) -> None:
        self.dataset_name = dataset_name
        return

    @abstractmethod
    def get_dataset_slice(self, length, offset) -> pd.DataFrame:  # change to offset
        pass

    # TODO add a dataset free
