import sys
import os

from datasetLoader.TextDatasetLoader import TextDatasetLoader
from datasetLoader.PDFDatasetLoader import PDFDatasetLoader
from datasetPreprocess.PDFDatasetPreprocess import PDFDatasetPreprocess
from datasetPreprocess.TextDatasetPreprocess import TextDatasetPreprocess
from encoder.sentenceTransformerEncoder import SentenceTransformerEncoder

from RAGPipeline.TextsRAGPipline import TextsRAGPipeline
from RAGRequest.TextsRAGRequest import WikipediaRequests
from RAGPipeline.retriever.BaseRetriever import BaseRetriever
from vectordb.milvus_api import milvus_client


def insert_pdf():

    length = 16
    slice_id = 2

    loader = PDFDatasetLoader(dataset_name="common-pile/arxiv_papers")
    loader.download_pdf(100)

    df = loader.get_dataset_slice(length=length, offset=slice_id)

    chunker = PDFDatasetPreprocess()
    chunked_texts = chunker.chunking_PDF_to_text(df)

    Embedder = SentenceTransformerEncoder(
        device="cuda:0", sentence_transformers_name="all-MiniLM-L6-v2"
    )
    vectors = Embedder.embedding(chunked_texts)

    collection_name = "pdf_test_collection"

    db_client = milvus_client(
        db_path="http://localhost:19530",
        db_token="root:Milvus",
        collection_name=collection_name,
        drop_previous_collection=False,
        # dim=config["sys"]["vector_db"]["dim"],
        index_type="GPU_IVF_FLAT",
        metric_type="L2",
    )

    db_client.setup()

    db_client.insert_data_vector(
        vector=vectors,
        chunks=chunked_texts,
        collection_name=collection_name,
        insert_batch_size=4,
        create_collection=True,
    )

    return


def query_pdf():
    collection_name = "pdf_test_collection"
    db_client = milvus_client(
        db_path="http://localhost:19530",
        db_token="root:Milvus",
        collection_name=collection_name,
        drop_previous_collection=False,
        # dim=config["sys"]["vector_db"]["dim"],
        index_type="GPU_IVF_FLAT",
        metric_type="L2",
    )
    db_client.setup()

    Retriever = BaseRetriever(collection_name=collection_name, client=db_client)
    RAGPipline = TextsRAGPipeline(retriever=Retriever)
    RAGRequest = WikipediaRequests(
        run_name="default_run", collection_name=collection_name, req_type="query", req_count=4
    )
    RAGPipline.process(RAGRequest)


if __name__ == "__main__":
    insert_pdf()
    query_pdf()
