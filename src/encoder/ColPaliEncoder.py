import time
import numpy as np
from encoder.BaseEncoder import BaseEncoder
import torch, gc

import os
from typing import List, cast
from PIL import Image
from tqdm import tqdm
from torch.utils.data import DataLoader

from colpali_engine.models import ColPali
from colpali_engine.models.paligemma.colpali.processing_colpali import ColPaliProcessor
from colpali_engine.utils.processing_utils import BaseVisualRetrieverProcessor
from colpali_engine.utils.torch_utils import ListDataset, get_torch_device


# TODO make this to abstactmethods
class ColPaliEncoder(BaseEncoder):
    def __init__(
        self,
        device,
        model_name,
        embedding_batch_size=64,
    ) -> None:
        self.device = device
        self.model_name = model_name
        self.embedding_batch_size = embedding_batch_size
        self.encoder = None
        return

    def __del__(self):
        self.free_encoder()

    def load_encoder(self) -> None:

        model = ColPali.from_pretrained(
            self.model_name,
            device_map=self.device,
        ).eval()
        self.dim = model.config.hidden_size
        self.encoder = model
        self.processor = cast(ColPaliProcessor, ColPaliProcessor.from_pretrained(self.model_name))

        return

    # TODO fix this
    def free_encoder(self) -> None:
        if self.encoder is not None:
            del self.encoder
            self.encoder = None
        if self.processor:
            del self.processor
            self.processor = None

        torch.cuda.synchronize()
        gc.collect()
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass
        return

    def embedding(self, pages):

        images = [Image.open(name) for name in pages]

        dataloader = DataLoader(
            dataset=ListDataset[str](images),
            batch_size=1,
            shuffle=False,
            collate_fn=lambda x: self.processor.process_images(x),
        )

        ds: List[torch.Tensor] = []
        for batch_doc in tqdm(dataloader, "embedding pdf's images"):
            with torch.no_grad():
                batch_doc = {k: v.to(self.encoder.device) for k, v in batch_doc.items()}
                embeddings_doc = self.encoder(**batch_doc)
            ds.extend(list(torch.unbind(embeddings_doc.to("cpu"))))

        filepaths = [name for name in pages]
        data = []
        for i in range(len(filepaths)):
            data.append(
                {
                    "colbert_vecs": ds[i].float().numpy(),
                    "doc_id": i,
                    "filepath": filepaths[i],
                }
            )

        dict_list = []
        for pdf in tqdm(data, "insert pdf's image"):
            # Insert ColBERT embeddings and metadata for a document into the collection.
            colbert_vecs = [vec for vec in pdf["colbert_vecs"]]
            seq_length = len(colbert_vecs)
            doc_ids = [pdf["doc_id"] for i in range(seq_length)]
            seq_ids = list(range(seq_length))
            dict_list.extend(
                [
                    {
                        "vector": colbert_vecs[i],
                        "seq_id": seq_ids[i],
                        "doc_id": doc_ids[i],
                        "filepath": pdf["filepath"],
                    }
                    for i in range(seq_length)
                ]
            )
        return dict_list

    def embedding_query(self, queries) -> List[torch.Tensor]:
        dataloader = DataLoader(
            dataset=ListDataset[str](queries),
            batch_size=1,
            shuffle=False,
            collate_fn=lambda x: self.processor.process_queries(x),
        )

        qs: List[torch.Tensor] = []
        for batch_query in dataloader:
            with torch.no_grad():
                batch_query = {k: v.to(self.encoder.device) for k, v in batch_query.items()}
                embeddings_query = self.encoder(**batch_query)
            qs.extend(list(torch.unbind(embeddings_query.to("cpu"))))
        return qs

    # @property
    # def dataset_name(self):
    # return self.__dataset_name

    # TODO add a dataset free
    def multi_gpus_embedding(self, texts):
        pass
