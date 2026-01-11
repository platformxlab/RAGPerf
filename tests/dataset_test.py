import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datasetLoader.TextDatasetLoader import TextDatasetLoader
from datasetLoader.PDFDatasetLoader import PDFDatasetLoader
from datasetPreprocess.PDFDatasetPreprocess import PDFDatasetPreprocess
from datasetPreprocess.TextDatasetPreprocess import TextDatasetPreprocess
from encoder.sentenceTransformerEncoder import SentenceTransformerEncoder

from vectordb.milvus_api import milvus_client


def text_test():
    # Simple hard-coded test;

    # Get 1024 wiki doc texts
    length = 1024
    slice_id = 0

    loader = TextDatasetLoader(dataset_name="wikimedia/wikipedia")
    df = loader.get_dataset_slice(length=length, slice_id=slice_id)

    print(df.shape)
    print(df.head(3))  # peek original dataset

    # Chunk all the doc we get
    chunker = TextDatasetPreprocess()
    chunked_texts = chunker.chunking_text_to_text(df)

    print(len(chunked_texts))
    for i in range(3):
        print(chunked_texts[i])

    # Embedding chunked texts
    Embedder = SentenceTransformerEncoder(
        device="cuda:0", sentence_transformers_name="all-MiniLM-L6-v2"
    )
    vectors = Embedder.embedding(chunked_texts)

    print(vectors.shape)
    print(vectors[0])


def pdf_test():
    # Simple hard-coded test; change as you wish
    length = 16
    slice_id = 2

    loader = PDFDatasetLoader(dataset_name="common-pile/arxiv_papers")

    loader.download_pdf(100)

    df = loader.get_dataset_slice(length=length, offset=slice_id)

    print(df.head(3))  # peek
    print(df.shape)

    # Chunk all the doc we get
    chunker = PDFDatasetPreprocess()
    chunked_texts = chunker.chunking_PDF_to_text(df)

    print(len(chunked_texts))
    for i in range(3):
        print(chunked_texts[i])

    # Embedding chunked texts
    Embedder = SentenceTransformerEncoder(
        device="cuda:0", sentence_transformers_name="all-MiniLM-L6-v2"
    )
    vectors = Embedder.embedding(chunked_texts)

    print(vectors[0])

    collection_name = "pdf_test_collection"
    # connect to db_client
    # vector_db:
    # # collection_name: 'wikimedia_wikipedia_all_MiniLM_L6_v2_1'
    # collection_name: 'wikimedia_wikipedia_all_MiniLM_L6_v2_0_1_512' #IVF_FLAT
    # # collection_name: 'wikimedia_wikipedia_All_mpnet_base_v2_0_1_512' #DISKANN
    # # collection_name: 'wikimedia_wikipedia_Alibaba_NLP_gte_large_en_v1_5_0_1_512' #GPU_IVF
    # db_path: http://localhost:19530
    # db_token: root:Milvus
    # drop_previous_collection: false
    # type: milvus
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
    # db_client.create_collection(collection_name=collection_name, dim=Embedder.dim)

    db_client.insert_data_vector(
        vector=vectors,
        chunks=chunked_texts,
        collection_name=collection_name,
        insert_batch_size=4,
        create_collection=True,
    )

    db_client.build_index(
        collection_name=collection_name,
        index_type="GPU_IVF_FLAT",
        metric_type="L2",
    )


if __name__ == "__main__":
    pdf_test()
