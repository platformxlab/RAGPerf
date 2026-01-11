from RAGPipeline.TextsRAGPipline import TextsRAGPipeline
from RAGRequest.TextsRAGRequest import WikipediaRequests
from retriever.BaseRetriever import BaseRetriever
from vectordb.milvus_api import milvus_client


def pdf_test():

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
    pdf_test()
