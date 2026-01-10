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
# from monitor import MetricMonitorProcess
from vectordb.DBInstance import DBInstance

# chroma_api specific
import chromadb
from concurrent.futures import ThreadPoolExecutor


class chroma_client(DBInstance):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id_num = 0

    def setup(self):
        self.client = chromadb.PersistentClient(path=self.db_path)
        print(f"***Connected to Qdrant client at {self.db_path}\n")

    def has_collection(self, collection_name):
        collections = self.client.list_collections()
        collection_names = [c.name for c in collections]

        if collection_name in collection_names:
            print(f"***Collection: {collection_name} exists.")
            return True
        else:
            print(f"***Collection: {collection_name} does not exist.")
            return False

    def create_collection(self, collection_name, dim, consistency_level="Eventually", auto_id=True):
        if self.has_collection(collection_name=collection_name):
            print(f"***Collection: {collection_name} already exists.")
            return
        else:
            try:
                collection = self.client.create_collection(name=collection_name)
                print(f"***Created new collection: {collection_name}")
                return
            except Exception as e:
                print(f"***Failed to create collection: {collection_name}. Error: {e}")
                return

    def drop_collection(self, collection_name):
        self.client.delete_collection(name=collection_name)
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
            # raise ValueError(f"Vectors length {len(vector)} != Chunks length {len(chunks)}")
            # make the number to the smaller one
            min_len = min(len(vector), len(chunks))
            vector = vector[:min_len]
            chunks = chunks[:min_len]

        if self.has_collection(collection_name=collection_name) is False:
            self.create_collection(collection_name=collection_name, dim=len(vector[0]))
        else:
            self.drop_collection(collection_name=collection_name)
            self.create_collection(collection_name=collection_name, dim=len(vector[0]))

        collection = self.client.get_collection(name=collection_name)

        # Build list of points, one per record
        id_list = []
        embeddings_list = []
        documents_list = []
        for v, c in zip(vector, chunks):
            id_list.append(str(self.id_num))
            embeddings_list.append(v)
            documents_list.append(c)
            self.id_num += 1

        # print(f"***Start insert: {len(point_list)}")

        for i in tqdm(range(0, int(len(id_list)), insert_batch_size)):
            collection.add(
                ids=id_list[i : i + insert_batch_size],
                embeddings=embeddings_list[i : i + insert_batch_size],
                documents=documents_list[i : i + insert_batch_size],
            )
        print(f"***Insert done.")

        # return result

    def insert_data(
        self, dict_list, collection_name=None, insert_batch_size=1, create_collection=False
    ):
        total_chunks_num = len(dict_list)
        print(f"***Start insert: {total_chunks_num}")

        collection = self.client.get_collection(name=collection_name)

        id_list = []
        embeddings_list = []
        documents_list = []
        for d in dict_list:
            id_list.append(str(self.id_num))
            embeddings_list.append(d["vector"])
            documents_list.append(d["text"])
            self.id_num += 1

        batch_size = 1000
        for i in tqdm(range(0, len(id_list), batch_size)):
            collection.add(
                ids=id_list[i : i + batch_size],
                embeddings=embeddings_list[i : i + batch_size],
                documents=documents_list[i : i + batch_size],
            )

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

        collection = self.client.get_collection(name=collection_name)

        def search_thread(start_idx, end_idx):
            b_vectors = query_vector[start_idx:end_idx]

            if len(b_vectors) > 0:
                mres = collection.query(
                    query_embeddings=query_vector[start_idx:end_idx], n_results=topk
                )
                results[start_idx:end_idx] = mres["documents"]

        # start_time = time.time()
        # print(f"*** Start multithreaded search: total={self.retrieval_size}, batch_size={batch_size}, max_threads={max_threads}")
        if max_threads == 1 or not multithread:
            # Single-threaded search
            for i in tqdm(range(total_queries), desc="Searching batches"):
                start_idx = i * search_batch_size
                end_idx = min(start_idx + search_batch_size, total_queries)

                # q_embeddings = []
                # for vec in range(start_idx, end_idx):
                #     b_vectors.append(models.QueryRequest(query=query_vector[vec], limit=topk, with_payload=True))
                # b_results = (
                #     self.client.query_points(collection_name=collection_name, query=b_vectors, limit=topk)
                #     .nprobes(1)
                #     .to_list()
                # )
                # results[start_idx:end_idx] = b_results

                b_vectors = query_vector[start_idx:end_idx]
                if len(b_vectors) > 0:
                    mres = collection.query(
                        query_embeddings=query_vector[start_idx:end_idx], n_results=topk
                    )
                    results[start_idx:end_idx] = mres["documents"]
                # results[i] = self.client.query_points(collection_name=collection_name, query=query_vector[i], limit=topk)
        else:
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = []
                progress = tqdm(total=num_batches, desc="Searching batches")

                def callback(future):
                    progress.update(1)

                for i in range(num_batches):
                    start_idx = i * search_batch_size
                    end_idx = min(start_idx + search_batch_size, total_queries)
                    future = executor.submit(search_thread, start_idx, end_idx)
                    future.add_done_callback(callback)
                    futures.append(future)

                concurrent.futures.wait(futures)
                progress.close()

        # end_time = time.time()
        context_format = """Source #{source_idx}\nDetail: {source_detail}\n"""
        contexts_results = []
        with open("query.out", "w") as fout:
            for query_idx, query_results in enumerate(results):
                fout.write(f"=== Query #{query_idx + 1} Results ===\n")
                context = []

                if query_idx == 1:
                    print(query_results)

                for entry_idx, result in enumerate(query_results):
                    text = result
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
    print("Chroma client test")
    # change qdrant path to a local on
    chroma = chroma_client(
        db_path="/mnt/data1/shaobol2/chroma",
        collection_name="test_collection",
        dim=768,
        index_type="IVF_PQ",
        metric_type="L2",
    )

    chroma.setup()
    # lc.drop_collection("test_collection")
    chroma.create_collection("test_collection", dim=768)
    # test insertion
    dict_list = []
    for i in range(10000):
        dict_list.append(
            {
                "text": f"Sample text {i}",
                "vector": [random.random() for _ in range(768)],  # Example vector of size 768
            }
        )
    chroma.insert_data(
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
    results = chroma.query_search(
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
