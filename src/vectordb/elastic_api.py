# took from lancedb_api
import argparse
import sys, os
import random
from tqdm import tqdm
import re
import concurrent.futures
import lancedb

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.reverse()
from vectordb.DBInstance import DBInstance

# elastic_api specific
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, BulkIndexError

# local development installation in Docker:
# curl -fsSL https://elastic.co/start-local | sh


class elastic_client(DBInstance):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def setup(self):
        self.client = Elasticsearch(self.db_path, basic_auth=("elastic", "3C8zBzzx"))
        print(f"***Connected to Elasticsearch client at {self.db_path}\n")

    def has_collection(self, collection_name):
        if self.client.indices.exists(index=collection_name.lower()):
            print(f"***Collection: {collection_name} exists.")
            return True
        else:
            print(f"***Collection: {collection_name} does not exist.")
            return False

    def create_collection(self, collection_name, dim, consistency_level="Eventually", auto_id=True):
        if self.client.indices.exists(index=collection_name.lower()):
            self.client.indices.delete(index=collection_name.lower())
            # print(f"***Collection: {collection_name} already exists.")
            # return
        # else:
        try:
            mapping = {
                "mappings": {
                    "properties": {
                        "embedding": {
                            "type": "dense_vector",
                            "dims": dim,
                            "index": True,
                            "similarity": "cosine",
                        }
                    }
                }
            }

            b = self.client.indices.create(index=collection_name.lower(), body=mapping)
            print(f"***Created new collection: {collection_name}")
            return
        except Exception as e:
            print(f"***Failed to create collection: {collection_name}. Error: {e}")
            return

    def drop_collection(self, collection_name):
        self.client.indices.delete(index=collection_name.lower())
        print(f"***Dropped existing collection: {collection_name}")

    def insert_data_vector(
        self,
        vector,
        chunks,
        collection_name=None,
        insert_batch_size=1,
        strict_check=False,
        create_collection=False,
    ):
        if len(vector) != len(chunks):
            raise ValueError(f"Vectors length {len(vector)} != Chunks length {len(chunks)}")

        # Build list of points, one per record
        for i in tqdm(range(0, int(len(vector)), insert_batch_size)):
            dict_list = []
            for v, c in zip(vector[i : i + insert_batch_size], chunks[i : i + insert_batch_size]):
                record = {"_index": collection_name.lower(), "_source": {"text": c, "embedding": v}}
                dict_list.append(record)

            # print(f"***Start insert batch: {len(dict_list)}")
            bulk(self.client, dict_list)
        print(f"***Insert batch done.")

    def insert_data(
        self, dict_list, collection_name=None, insert_batch_size=1, create_collection=False
    ):
        total_chunks_num = len(dict_list)

        new_dict_list = []
        for d in dict_list:
            record = {
                "_index": collection_name.lower(),
                "_source": {"text": d["text"], "embedding": d["vector"]},
            }
            new_dict_list.append(record)

        print(f"***Start insert: {total_chunks_num}")

        try:
            bulk(self.client, new_dict_list)
        except BulkIndexError as e:
            for error in e.errors:
                print(error)

        print(f"***Insert done.")

    # def show_table(self, collection_name=None):
    #     tbl = self.client.open_table(collection_name)
    #     print(tbl.to_pandas())

    def query_search(
        self,
        query_vector,
        topk,
        collection_name=None,
        search_batch_size=1,
        multithread=False,
        max_threads=4,
        consistency_level="Eventually",
        output_fields=["text", "vector"],
        monitor=False,
    ):
        print(f"***Start query search in collection: {collection_name}")

        total_queries = len(query_vector)

        # Adjust search_batch_size if it exceeds total_queries
        if search_batch_size > total_queries:
            search_batch_size = total_queries

        results = [None] * total_queries

        num_batches = (total_queries + search_batch_size - 1) // search_batch_size

        # def search_thread(start_idx, end_idx):
        #     b_vectors = query_vector[start_idx:end_idx]

        #     # b_results = tbl.search(b_vectors, vector_column_name='vector').limit(topk).nprobes(3).to_list()
        #     b_results = self.client.query_points(collection_name=collection_name, query=b_vectors, with_payload=False, limit=topk).points

        #     results[start_idx:end_idx] = b_results

        # start_time = time.time()
        # print(f"*** Start multithreaded search: total={self.retrieval_size}, batch_size={batch_size}, max_threads={max_threads}")
        if max_threads == 1 or not multithread:
            # Single-threaded search
            for i in tqdm(range(num_batches), desc="Searching batches"):
                start_idx = i * search_batch_size
                end_idx = min(start_idx + search_batch_size, total_queries)

                b_vectors = []
                for vec in range(start_idx, end_idx):
                    b_vectors.append({})
                    b_vectors.append(
                        {
                            "knn": {
                                "field": "embedding",
                                "query_vector": query_vector[vec],
                                "k": topk,
                                "num_candidates": 100,
                            }
                        }
                    )
                mres = self.client.msearch(index=collection_name.lower(), searches=b_vectors)
                responses = mres["responses"]
                results[start_idx:end_idx] = responses
                # if start_idx == 0:
                #     print(results[start_idx]["hits"]["hits"])
                # results[i] = self.client.query_points(collection_name=collection_name, query=query_vector[i], limit=topk)
        else:
            # with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            #     futures = []
            #     progress = tqdm(total=num_batches, desc="Searching batches")

            #     def callback(future):
            #         progress.update(1)

            #     for i in range(num_batches):
            #         start_idx = i * search_batch_size
            #         end_idx = min(start_idx + search_batch_size, total_queries)d
            #         future = executor.submit(search_thread, start_idx, end_idx)
            #         future.add_done_callback(callback)
            #         futures.append(future)

            #     concurrent.futures.wait(futures)
            #     progress.close()
            print(("DEFAULT MULTITHREADING"))

        # print(results)

        # end_time = time.time()
        context_format = """Source #{source_idx}\nDetail: {source_detail}\n"""
        contexts_results = []
        with open("query.out", "w") as fout:
            for query_idx, query_results in enumerate(results):
                fout.write(f"=== Query #{query_idx + 1} Results ===\n")
                context = []

                for entry_idx, result in enumerate(query_results["hits"]["hits"]):
                    text = result["_source"]["text"]
                    formatted = context_format.format(source_idx=entry_idx, source_detail=text)
                    context.append(formatted)
                    fout.write(f"*** Retrieved result #{entry_idx}, doc length: {len(text)}\n")
                fout.write("\n")
                contexts_results.append(context)

        print(f"***Query search completed.")
        return contexts_results

    def build_index(
        self,
        collection_name,
        index_type,
        metric_type,
        num_partitions=256,
        num_sub_vectors=96,
        idx_name=None,
        drop_index=True,
        device=None,
        index_cache_size=None,
    ):
        # Color print the index metrics used
        print(f"Building index with parameters:", "cyan")
        print(f"  index_type: {index_type}", "green")

        # tbl = self.client.open_table(collection_name)
        # tbl.create_index(
        #     metric=metric_type,
        #     num_partitions=num_partitions,
        #     num_sub_vectors=num_sub_vectors,
        #     vector_column_name='vector',
        #     replace=drop_index,
        #     accelerator=device,
        #     index_cache_size=32,
        #     index_type=index_type,
        #     num_bits=8,
        #     max_iterations=50,
        #     sample_rate=256,
        #     m=20,
        #     ef_construction=300,
        # )

        return


# test
if __name__ == "__main__":
    print("Elastic client test")
    # change qdrant path to a local on
    elastic = elastic_client(
        db_path="http://localhost:9200",
        collection_name="test_collection",
        dim=768,
        index_type="IVF_PQ",
        metric_type="L2",
    )

    elastic.setup()
    # lc.drop_collection("test_collection")
    elastic.create_collection("test_collection", dim=768)
    # test insertion
    dict_list = []
    for i in range(10000):
        dict_list.append(
            {
                "text": f"Sample text {i}",
                "vector": [random.random() for _ in range(768)],  # Example vector of size 768
            }
        )
    elastic.insert_data(
        dict_list, collection_name="test_collection", insert_batch_size=10, create_collection=False
    )
    # lc.show_table("test_collection")
    # qc.build_index(
    #     "test_collection",
    #     index_type="IVF_HNSW_PQ",
    #     metric_type="L2",
    #     num_partitions=256,
    #     num_sub_vectors=96,
    #     drop_index=True,
    #     device=None,
    #     index_cache_size=None,
    # )
    results = elastic.query_search(
        query_vector=[[random.random() for _ in range(768)] for _ in range(2)],
        topk=2,
        collection_name="test_collection",
        search_batch_size=2,
        multithread=False,
        max_threads=4,
        consistency_level="Eventually",
        output_fields=["text", "vector"],
        monitor=True,
    )
    print("Query results:")
    print(results)
