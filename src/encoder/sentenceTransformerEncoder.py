import time
import numpy as np
from sentence_transformers import SentenceTransformer
from encoder.BaseEncoder import BaseEncoder
import torch, gc


# TODO make this to abstactmethods
class SentenceTransformerEncoder(BaseEncoder):
    def __init__(
        self,
        device,
        sentence_transformers_name,
        embedding_batch_size=64,
    ) -> None:
        self.device = device
        self.sentence_transformers_name = sentence_transformers_name
        self.embedding_batch_size = embedding_batch_size
        self.encoder = None
        return

    def __del__(self):
        self.free_encoder()

    def load_encoder(self) -> None:
        self.encoder = SentenceTransformer(
            self.sentence_transformers_name,
            self.device,
            model_kwargs={"torch_dtype": "float16"},
        )
        self.dim = self.encoder.get_sentence_embedding_dimension()
        print(
            f"***Loaded encoder: {self.sentence_transformers_name}\n"
            f"***Embedding Dim: {self.dim}\n"
            f"***Max Seq Length: {self.encoder.get_max_seq_length()}"
        )
        return

    # TODO fix this
    def free_encoder(self) -> None:
        if self.encoder is not None:
            del self.encoder
            self.encoder = None
            torch.cuda.synchronize()
            gc.collect()
            torch.cuda.empty_cache()
            try:
                torch.cuda.ipc_collect()
            except Exception:
                pass
        return

    def embedding(self, texts) -> list[np.array]:
        embeddings = self.encoder.encode(
            texts, batch_size=self.embedding_batch_size, show_progress_bar=True
        )

        embeddings = np.vstack(embeddings)
        embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings.tolist()

    def multi_gpus_embedding(self, texts) -> list[np.array]:
        embeddings_start_time = time.time()
        print(f"***All dataset Embeddings start")
        pool = self.encoder.start_multi_process_pool(self.device)
        num_process = len(pool["processes"])
        print(f"***{num_process} processes been create, start embedding")

        embeddings = self.encoder.encode_multi_process(
            texts, pool, show_progress_bar=True, batch_size=self.embedding_batch_size
        )

        embeddings = np.vstack(embeddings)
        embeddings /= np.linalg.norm(embeddings, axis=1, keepdims=True)
        self.encoder.stop_multi_process_pool(pool)
        embeddings_end_time = time.time()
        print(f"***Embeddings shape: {embeddings.shape}")
        print(f"***All dataset Embeddings end :time :{embeddings_end_time - embeddings_start_time}")

        return embeddings

    # @property
    # def dataset_name(self):
    # return self.__dataset_name

    # TODO add a dataset free
