from abc import ABC, abstractmethod
import torch


class BaseReranker(ABC):
    def __init__(self, device=None):
        pass

    @abstractmethod
    def load_reranker(self):
        pass

    @abstractmethod
    def rerank(self, query, candidate_docs):
        pass

    @abstractmethod
    def batch_rerank(self, queries, candidate_docs_list):
        pass

    @abstractmethod
    def free_reranker(self):
        pass
