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

# qdrant_api specific
from qdrant_client import QdrantClient, models

# from qdrant_client.models import Distance, VectorParams

## deployed form docker
# docker pull qdrant/qdrant
# docker run -p 6333:6333 -p 6334:6334 \
# -v "${db_path}/qdrant_storage:/qdrant/storage:z" \
# qdrant/qdrant


class qdrant_client(DBInstance):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id_num = 0

    def setup(self):
        self.client = QdrantClient(url=self.db_path, timeout=200)
        print(f"***Connected to Qdrant client at {self.db_path}\n")

    def has_collection(self, collection_name):
        if self.client.collection_exists(collection_name=collection_name):
            print(f"***Collection: {collection_name} exists.")
            return True
        else:
            print(f"***Collection: {collection_name} does not exist.")
            return False

    def create_collection(self, collection_name, dim, consistency_level="Eventually", auto_id=True):
        if self.client.collection_exists(collection_name=collection_name):
            print(f"***Collection: {collection_name} already exists.")
            return
        else:
            try:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(size=dim, distance=models.Distance.DOT),
                )
                print(f"***Created new collection: {collection_name}")
                return
            except Exception as e:
                print(f"***Failed to create collection: {collection_name}. Error: {e}")
                return

    def drop_collection(self, collection_name):
        self.client.delete_collection(collection_name=collection_name)
        print(f"***Dropped existing collection: {collection_name}")

    def insert_data_vector(
        self,
        vector,
        chunks,
        collection_name=None,
        insert_batch_size=32,
        strict_check=False,
        create_collection=False,
    ):
        if len(vector) != len(chunks):
            raise ValueError(f"Vectors length {len(vector)} != Chunks length {len(chunks)}")

        if not self.client.collection_exists(collection_name=collection_name):
            self.create_collection(collection_name=collection_name, dim=len(vector[0]))

        # Build list of points, one per record
        count = 0

        total_count = min(len(vector), len(chunks))
        # pbar = tqdm(total=total_count, desc="Inserting batches")
        for i in tqdm(range(0, total_count, insert_batch_size), desc="Inserting batches"):
            point_list = []
            end_idx = min(i + insert_batch_size, total_count)
            for v, c in zip(vector[i:end_idx], chunks[i:end_idx]):
                record = models.PointStruct(id=self.id_num, vector=v, payload={"chunk": c})
                self.id_num += 1
                point_list.append(record)

            # print(f"***Start insert: {len(point_list)}")
            operation_info = self.client.upsert(
                collection_name=collection_name,
                wait=True,
                points=point_list,
            )
            # pbar.update(len(point_list))
        print(f"***Insert done.")
        # return result

    def insert_data(
        self, dict_list, collection_name=None, insert_batch_size=1, create_collection=False
    ):
        total_chunks_num = len(dict_list)
        print(f"***Start insert: {total_chunks_num}")

        point_list = []
        for dict in dict_list:
            record = {
                "id": self.id_num,
                "payload": {"chunk": dict["text"]},
                "vector": dict["vector"],
            }
            self.id_num += 1
            point_list.append(record)

        batch_size = 1000
        for i in tqdm(range(0, len(point_list), batch_size)):
            batch = point_list[i : i + batch_size]
            self.client.upsert(collection_name=collection_name, points=batch, wait=True)

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
            for i in tqdm(range(total_queries), desc="Searching batches"):
                start_idx = i * search_batch_size
                end_idx = min(start_idx + search_batch_size, total_queries)

                b_vectors = []
                for vec in range(start_idx, end_idx):
                    b_vectors.append(
                        models.QueryRequest(query=query_vector[vec], limit=topk, with_payload=True)
                    )
                # b_results = (
                #     self.client.query_points(collection_name=collection_name, query=b_vectors, limit=topk)
                #     .nprobes(1)
                #     .to_list()
                # )
                # results[start_idx:end_idx] = b_results

                results[start_idx:end_idx] = self.client.query_batch_points(
                    collection_name=collection_name, requests=b_vectors
                )
                # results[i] = self.client.query_points(collection_name=collection_name, query=query_vector[i], limit=topk)
        else:
            # with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            #     futures = []
            #     progress = tqdm(total=num_batches, desc="Searching batches")

            #     def callback(future):
            #         progress.update(1)

            #     for i in range(num_batches):
            #         start_idx = i * search_batch_size
            #         end_idx = min(start_idx + search_batch_size, total_queries)
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

                for entry_idx, result in enumerate(query_results):
                    text = result[1][entry_idx].payload['chunk']
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
    print("Qdrant client test")
    # change qdrant path to a local on

    qc = qdrant_client(
        db_path="localhost:6333",
        collection_name="test_collection",
        dim=768,
        index_type="IVF_PQ",
        metric_type="L2",
    )

    qc.setup()
    qc.create_collection("test_collection", dim=768)
    # lc.drop_collection("test_collection")
    # lc.create_collection("test_collection", dim=768)
    # test insertion
    dict_list = []
    for i in range(1000):
        dict_list.append(
            {
                "text": f"Sample text {i}",
                "vector": [random.random() for _ in range(768)],  # Example vector of size 768
            }
        )

    qc.insert_data(
        dict_list, collection_name="test_collection", insert_batch_size=10, create_collection=True
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
    results = qc.query_search(
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
