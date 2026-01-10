from pdf2image import convert_from_path
import matplotlib.pyplot as plt

from colpali_engine.models import ColPali
from colpali_engine.models.paligemma.colpali.processing_colpali import ColPaliProcessor
from colpali_engine.utils.processing_utils import BaseVisualRetrieverProcessor
from colpali_engine.utils.torch_utils import ListDataset, get_torch_device
from src.vectordb.milvus_api import milvus_client
from PIL import Image
from torch.utils.data import DataLoader
import torch
from typing import List, cast
import os
from tqdm import tqdm
import concurrent.futures
import numpy as np
import re
from transformers import Qwen2VLForConditionalGeneration, Qwen2VLProcessor
from qwen_vl_utils import process_vision_info


def display_pdf_images(images_list):
    """Display all images in the provided list as subplots with 5 images per row."""
    num_images = len(images_list)
    num_rows = num_images // 5 + (1 if num_images % 5 > 0 else 0)
    fig, axes = plt.subplots(num_rows, 5, figsize=(20, 4 * num_rows))
    axes = axes.flatten()
    for i, img in enumerate(images_list):
        if i < len(axes):
            ax = axes[i]
            ax.imshow(img)
            ax.set_title(f"Page {i+1}")
            ax.axis('off')
    for j in range(num_images, len(axes)):
        axes[j].axis('off')
    plt.tight_layout()
    plt.show()


class PDFDatasetProcessor:
    def __init__(self, encoder_model_name="vidore/colpali-v1.2", collection_name="PDF_1"):
        self.encoder_model_name = encoder_model_name
        self.collection_name = collection_name
        self.pages_dir = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._setup_encoder()
        self._setup_db()

    def _setup_encoder(self):
        """Initialize ColPali encoder."""
        device = get_torch_device("cuda")

        model = ColPali.from_pretrained(
            self.encoder_model_name,
            dtype=torch.bfloat16,
            device_map=device,
        ).eval()

        self.encoder = model
        self.processor = cast(
            ColPaliProcessor, ColPaliProcessor.from_pretrained(self.encoder_model_name)
        )

    def _setup_db(self):
        # set db
        self.db_client = milvus_client(
            db_path="http://localhost:19530",
            db_token="root:Milvus",
            collection_name=self.collection_name,
            drop_previous_collection=True,
            # dim=config["sys"]["vector_db"]["dim"],
            index_type="HNSW",
            metric_type="IP",
        )

        self.db_client.setup()

    # input: pdf path
    # output: none
    # save png file into pages/ dir
    def PDFtoimage(self, pdf_path):
        """
        Convert all PDF files in pdf_path to images.
        Saves each page as '{pdf_path}/pages/{pdf_filename}_page_{i+1}.png'.
        """
        self.pages_dir = os.path.join(pdf_path, "pages/")

        if os.path.exists(self.pages_dir):
            print(f"'{self.pages_dir}' directory already exists. Skipping PDF to image conversion.")
            return

        os.makedirs(self.pages_dir, exist_ok=True)

        for filename in os.listdir(pdf_path):
            if filename.lower().endswith(".pdf"):
                path = os.path.join(pdf_path, filename)
                images = convert_from_path(path)

                pdf_base = os.path.splitext(filename)[0]
                for i, image in enumerate(images):
                    out_path = os.path.join(self.pages_dir, f"{pdf_base}_page_{i+1}.png")
                    image.save(out_path, "PNG")
                    print(f"Saved {out_path}")

    def PDFembedding(self):
        """Generate embeddings for each page in PDF.

        Returns:
            List[ dict{"colbert_vecs", "doc_id", "filepath"}]
        """

        if self.pages_dir == None:
            print(f"self.pages_dir' directory have not create. Run PDFtoimage(pdf_path) first.")
            return

        images = [Image.open(self.pages_dir + name) for name in os.listdir(self.pages_dir)]

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

        filepaths = [self.pages_dir + name for name in os.listdir(self.pages_dir)]
        data = []
        for i in range(len(filepaths)):
            data.append(
                {
                    "colbert_vecs": ds[i].float().numpy(),
                    "doc_id": i,
                    "filepath": filepaths[i],
                }
            )
        return data

    def PDFinsert(self, data):
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
        self.db_client.insert_data(
            dict_list, collection_name=self.collection_name, create_collection=True
        )


class PDFRagPipeline:
    def __init__(self, pdf_dir, encoder_model_name="vidore/colpali-v1.2", collection_name="PDF_1"):
        self.encoder_model_name = encoder_model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.collection_name = collection_name
        self.pages_dir = os.path.join(pdf_dir, "pages/")
        self._setup_db()
        self._setup_encoder()

    def _setup_db(self):
        # set db
        self.db_client = milvus_client(
            db_path="http://localhost:19530",
            db_token="root:Milvus",
            collection_name=self.collection_name,
            drop_previous_collection=True,
            # dim=config["sys"]["vector_db"]["dim"],
            index_type="HNSW",
            metric_type="IP",
        )

        self.db_client.setup()

    def _setup_encoder(self):
        """Initialize ColPali encoder."""
        device = get_torch_device("cuda")

        model = ColPali.from_pretrained(
            self.encoder_model_name,
            dtype=torch.bfloat16,
            device_map=device,
        ).eval()

        self.encoder = model
        self.processor = cast(
            ColPaliProcessor, ColPaliProcessor.from_pretrained(self.encoder_model_name)
        )

    def _setup_llm(self):
        self.vl_model = Qwen2VLForConditionalGeneration.from_pretrained(
            "Qwen/Qwen2-VL-7B-Instruct",
            dtype=torch.bfloat16,
        )
        self.vl_model.cuda().eval()
        min_pixels = 224 * 224
        max_pixels = 1024 * 1024
        self.vl_model_processor = Qwen2VLProcessor.from_pretrained(
            "Qwen/Qwen2-VL-7B-Instruct", min_pixels=min_pixels, max_pixels=max_pixels
        )
        return

    def QueriesEmbedding(self, queries):
        """Generate embeddings for queries.

        Returns:
            List[vector]
        """
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
            print(qs[0])
        return qs

    def PDFsearch(self, embeddings, top_k=1):
        # Perform a vector search on the collection to find the top-k most similar documents.
        # topk set to a reasonable large num
        # results = self.db_client.query_search(embeddings, topk=50, collection_name=self.collection_name, output_fields=["vector", "seq_id", "doc_id", "filepath"])
        # search_params = {"metric_type": "IP", "params": {}}
        results = self.db_client.search(
            collection_name=self.collection_name,
            data=embeddings,
            limit=int(50),
            output_fields=["vector", "seq_id", "doc_id", "filepath"],
            # search_params=search_params,
        )

        print(f"len results: {len(results)}")
        # get unique doc_id from db search
        doc_ids = set()
        for r_id in range(len(results)):
            for r in range(len(results[r_id])):
                doc_ids.add(results[r_id][r]["entity"]["doc_id"])

        scores = []

        def rerank_single_doc(doc_id, data, client, collection_name):
            # Rerank a single document by retrieving its embeddings and calculating the similarity with the query.
            doc_colbert_vecs = client.db_query(
                collection_name=collection_name,
                filter=f"doc_id in [{doc_id}]",
                output_fields=["seq_id", "vector", "filepath"],
                limit=1000,
            )
            doc_vecs = np.vstack(
                [doc_colbert_vecs[i]["vector"] for i in range(len(doc_colbert_vecs))]
            )
            score = np.dot(data, doc_vecs.T).max(1).sum()
            return (score, doc_id, doc_colbert_vecs[0]["filepath"])

        with concurrent.futures.ThreadPoolExecutor(max_workers=300) as executor:
            futures = {
                executor.submit(
                    rerank_single_doc, doc_id, embeddings, self.db_client, self.collection_name
                ): doc_id
                for doc_id in doc_ids
            }
            for future in concurrent.futures.as_completed(futures):
                score, doc_id, filepath = future.result()
                scores.append((score, doc_id, filepath))

        scores.sort(key=lambda x: x[0], reverse=True)
        if len(scores) >= top_k:
            return scores[:top_k]
        else:
            return scores

    def GetPDF(self, filepath):
        """
        Loads and returns the image at the given filepath.
        """
        if os.path.exists(filepath):
            image = Image.open(filepath)
            return image
        else:
            print(f"File does not exist: {filepath}")
            return None

    def PDFquery(self, query, top_k=1, max_new_tokens=500):
        """High-level interface for querying PDF pages."""

        # load llm model
        self._setup_llm()

        # query search
        results = self.PDFsearch(query, top_k)
        images_list = []
        for hits in results:
            images_list.append(self.GetPDF(hits[2]))
        chat_template = [
            {
                "role": "user",
                "content": [{"type": "image", "image": image} for image in images_list]
                + [{"type": "text", "text": query}],
            }
        ]

        # Prepare the inputs
        text = self.vl_model_processor.apply_chat_template(
            chat_template, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(chat_template)
        inputs = self.vl_model_processor(
            text=[text],
            images=image_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to("cuda")

        # Generate text from the vl_model
        generated_ids = self.vl_model.generate(**inputs, max_new_tokens=max_new_tokens)
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]

        # Decode the generated text
        output_text = self.vl_model_processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        print("***answer:")
        print(output_text[0])
        return output_text


def main_test():

    # INSERT
    # DatasetProcessor = PDFDatasetProcessor(collection_name="PDF_2")
    # DatasetProcessor.PDFtoimage("./pdf")
    # embedding = DatasetProcessor.PDFembedding()
    # DatasetProcessor.PDFinsert(embedding)

    # QUERY
    RagPipeline = PDFRagPipeline("/home/yuanxu4/RAGPipeline/pdf/", collection_name="PDF_2")

    queries = ["How to end-to-end retrieval with ColBert?"]
    eb = RagPipeline.QueriesEmbedding(queries)
    for query in eb:
        query = query.float().numpy()
        RagPipeline.PDFquery(query)
    return


if __name__ == "__main__":
    main_test()
