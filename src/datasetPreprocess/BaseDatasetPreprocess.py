from langchain.text_splitter import RecursiveCharacterTextSplitter
from abc import ABC, abstractmethod
import pandas as pd


# TODO: make this to abstract class
class BaseDatasetPreprocess(ABC):
    def __init__(self) -> None:
        return

    # return a list ["text"], pass to embedding model to get vector
    @abstractmethod
    def chunking_text_to_text(self, df) -> list[str]:
        pass

    @abstractmethod
    def chunking_PDF_to_text(self, df) -> list[str]:
        pass

    @abstractmethod
    def chunking_PDF_to_image(self, df) -> list:
        pass
