import torch, gc
from sentence_transformers import CrossEncoder
from RAGPipeline.reranker.BaseReranker import BaseReranker
from typing import List


class CrossEncoderReranker(BaseReranker):
    def __init__(self, model_name="cross-encoder/ms-marco-MiniLM-L-6-v2", top_n=5, device=None):
        super().__init__()
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = model_name
        self.top_n = top_n

    def load_reranker(self):
        self.model = CrossEncoder(self.model_name, device=self.device)

    def rerank(self, query, candidate_docs):
        pairs = [(query, doc) for doc in candidate_docs]
        scores = self.model.predict(pairs)
        ranked = sorted(zip(candidate_docs, scores), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in ranked[: self.top_n]]

    def batch_rerank(self, queries: List[str], candidate_docs_list: List[List[str]]):
        """
        queries: List[str], candidate_docs_list: List[List[str]]
        returns: List[List[str]] - top-k reranked document texts per query
        """
        assert len(queries) == len(candidate_docs_list), "Length mismatch"

        all_pairs = []
        index_ranges = []
        current = 0

        for query, docs in zip(queries, candidate_docs_list):
            pairs = [(query, doc) for doc in docs]
            all_pairs.extend(pairs)
            index_ranges.append((current, current + len(docs)))
            current += len(docs)

        all_scores = self.model.predict(all_pairs, batch_size=1)
        results = []

        for (start, end), docs in zip(index_ranges, candidate_docs_list):
            scores = all_scores[start:end]
            ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
            results.append([doc for doc, _ in ranked[: self.top_n]])

        return results

    def free_reranker(self):
        del self.model
        torch.cuda.synchronize()
        gc.collect()
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass
