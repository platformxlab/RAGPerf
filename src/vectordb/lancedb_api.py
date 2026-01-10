import argparse
import sys, os
import random
from tqdm import tqdm
import re
import concurrent.futures
import lancedb
import pyarrow as pa


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.reverse()
from vectordb.DBInstance import DBInstance


class lance_client(DBInstance):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.type = "lancedb"

    def setup(self):
        self.client = lancedb.connect(self.db_path)
        print(f"***Connected to Lancedb client at {self.db_path}\n")

    def has_collection(self, collection_name):
        print(
            f"lancedb may not support has_collection, please check the collection exists by list_collections"
        )
        return True

    def create_collection(
        self, collection_name, dim, consistency_level="Eventually", auto_id=True, data_type="text"
    ):
        try:
            if self.drop_collection(collection_name):
                print(f"***Dropped existing collection: {collection_name}")
        except Exception as e:
            print(f"***No existing collection to drop: {collection_name}. Error: {e}")
            pass

        if data_type == "image":
            schema = pa.schema(
                [
                    pa.field("vector", pa.list_(pa.float32(), dim)),
                    pa.field("seq_id", pa.int32()),
                    pa.field("doc_id", pa.int32()),
                    pa.field("filepath", pa.string()),
                ]
            )
        elif data_type == "text":
            schema = pa.schema(
                [pa.field("text", pa.string()), pa.field("vector", pa.list_(pa.float32(), dim))]
            )
        try:
            self.client.create_table(
                collection_name,
                data=None,
                schema=schema,
                mode='create',
                exist_ok=False,
                on_bad_vectors='error',
                fill_value=0,
            )
            print(f"***Created new collection: {collection_name}")
            return
        except Exception as e:
            print(f"***Failed to create collection: {collection_name}. Error: {e}")
            return

    def drop_collection(self, collection_name):
        self.client.drop_table(collection_name)
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

        # Build list of dicts, one per record
        dict_list = []
        for v, c in zip(vector, chunks):
            record = {"vector": v, "text": c}
            dict_list.append(record)

        print(f"***Start insert: {len(dict_list)}")
        tbl = self.client.open_table(collection_name)
        result = tbl.add(dict_list, mode="append", on_bad_vectors="error")
        print(f"***Insert done.")
        return result

    def insert_data(
        self, dict_list, collection_name=None, insert_batch_size=1, create_collection=False
    ):
        total_chunks_num = len(dict_list)
        print(f"***Start insert: {total_chunks_num}")
        tbl = self.client.open_table(collection_name)
        result = tbl.add(dict_list, mode='append', on_bad_vectors='error')
        print(f"***Insert done.")

    def show_table(self, collection_name=None):
        tbl = self.client.open_table(collection_name)
        print(tbl.to_pandas())

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
    ):
        print(f"***Start query search in collection: {collection_name}")

        tbl = self.client.open_table(collection_name)

        total_queries = len(query_vector)

        # Adjust search_batch_size if it exceeds total_queries
        if search_batch_size > total_queries:
            search_batch_size = total_queries

        results = [None] * total_queries

        num_batches = (total_queries + search_batch_size - 1) // search_batch_size

        def search_thread(start_idx, end_idx):
            b_vectors = query_vector[start_idx:end_idx]

            # b_results = tbl.search(b_vectors, vector_column_name='vector').limit(topk).nprobes(3).to_list()
            b_results = tbl.search(b_vectors, vector_column_name='vector').limit(topk).to_list()

            results[start_idx:end_idx] = b_results

        # start_time = time.time()
        # print(f"*** Start multithreaded search: total={self.retrieval_size}, batch_size={batch_size}, max_threads={max_threads}")
        if max_threads == 1 or not multithread:
            # Single-threaded search
            for i in tqdm(range(num_batches), desc="Searching batches"):
                start_idx = i * search_batch_size
                end_idx = min(start_idx + search_batch_size, total_queries)
                b_vectors = query_vector[start_idx:end_idx]
                b_results = (
                    tbl.search(b_vectors, vector_column_name='vector')
                    # .distance_type("l2")
                    .limit(topk)
                    # .nprobes(1)
                    .to_list()
                )
                # tbl.search(np.random.random((1536))).distance_type("cosine").limit(10).to_list()
                # b_results = tbl.search(b_vectors, vector_column_name='vector').limit(topk).to_list()
                if len(b_results) != search_batch_size * topk:
                    raise ValueError(
                        f"len(b_results) must be n*topk n = {search_batch_size}, topk {topk}, but got {len(b_results)}"
                    )
                b_results = [b_results[i * topk : (i + 1) * topk] for i in range(search_batch_size)]
                results[start_idx:end_idx] = b_results
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
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
                for entry_idx, result in enumerate(query_results):
                    text = result["text"]
                    formatted = context_format.format(source_idx=entry_idx, source_detail=text)
                    context.append(formatted)
                    fout.write(f"*** Retrieved result #{entry_idx}, doc length: {len(text)}\n")
                fout.write("\n")
                contexts_results.append(context)

        print(f"***Query search completed.")
        return contexts_results

    def query_search_image(
        self,
        query_vector,
        topk,
        collection_name=None,
        search_batch_size=1,
        multithread=False,
        max_threads=4,
        consistency_level="Eventually",
        output_fields=["text", "vector"],
    ):
        print(f"***Start query search in collection: {collection_name}")

        tbl = self.client.open_table(collection_name)

        total_queries = len(query_vector)

        # Adjust search_batch_size if it exceeds total_queries
        if search_batch_size > total_queries:
            search_batch_size = total_queries

        results = [None] * total_queries

        num_batches = (total_queries + search_batch_size - 1) // search_batch_size

        def search_thread(start_idx, end_idx):
            b_vectors = query_vector[start_idx:end_idx]

            # b_results = tbl.search(b_vectors, vector_column_name='vector').limit(topk).nprobes(3).to_list()
            b_results = tbl.search(b_vectors, vector_column_name='vector').limit(topk).to_list()

            results[start_idx:end_idx] = b_results

        # start_time = time.time()
        # print(f"*** Start multithreaded search: total={self.retrieval_size}, batch_size={batch_size}, max_threads={max_threads}")
        if max_threads == 1 or not multithread:
            # Single-threaded search
            for i in tqdm(range(num_batches), desc="Searching batches"):
                start_idx = i * search_batch_size
                end_idx = min(start_idx + search_batch_size, total_queries)
                b_vectors = query_vector[start_idx:end_idx]
                b_results = (
                    tbl.search(b_vectors, vector_column_name='vector')
                    .limit(topk)
                    .nprobes(1)
                    .to_list()
                )
                # b_results = tbl.search(b_vectors, vector_column_name='vector').limit(topk).to_list()
                if len(b_results) != len(b_vectors) * topk:
                    raise ValueError(
                        f"len(b_results) must be n*topk n = {search_batch_size}, topk {topk}, but got {len(b_results)}"
                    )
                b_results = [b_results[i * topk : (i + 1) * topk] for i in range(search_batch_size)]
                results[start_idx:end_idx] = b_results
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
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
        doc_ids = set()
        with open("query.out", "w") as fout:
            for query_results in results:
                for result in query_results:
                    doc_ids.add(result["doc_id"])

        print(f"***Query search completed.")
        return doc_ids

    def query(self, collection_name, filter_expr, output_fields=None, limit=10):
        tbl = self.client.open_table(collection_name)
        if output_fields is not None:
            query = tbl.search().where(filter_expr).select(output_fields).to_pandas()
        else:
            query = tbl.search().where(filter_expr).to_pandas()
        return query

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

        tbl = self.client.open_table(collection_name)
        tbl.create_index(
            metric=metric_type,
            num_partitions=num_partitions,
            num_sub_vectors=num_sub_vectors,
            vector_column_name='vector',
            replace=drop_index,
            accelerator=device,
            index_cache_size=32,
            index_type=index_type,
            num_bits=8,
            max_iterations=50,
            sample_rate=256,
            m=20,
            ef_construction=300,
        )

        return


# test
if __name__ == "__main__":
    print("Lance client test")
    # change lance path to a local on
    lc = lance_client(
        db_path="/mnt/nvme1n1/shaobol2/ragdata/lancedb",
        collection_name="test_collection",
        dim=768,
        index_type="IVF_PQ",
        metric_type="L2",
    )

    lc.setup()
    # lc.drop_collection("test_collection")
    # lc.create_collection("test_collection", dim=768)
    # test insertion
    # dict_list = []
    # for i in range(10000000):
    #     dict_list.append({
    #         "text": f"Sample text {i}",
    #         "vector": [random.random() for _ in range(768)]  # Example vector of size 768
    #     })
    # lc.insert_data(dict_list, collection_name="test_collection", insert_batch_size=10, create_collection=False)
    # lc.show_table("test_collection")
    lc.build_index(
        "test_collection",
        index_type="IVF_HNSW_PQ",
        metric_type="L2",
        num_partitions=256,
        num_sub_vectors=96,
        drop_index=True,
        device=None,
        index_cache_size=None,
    )
    # results = lc.query_search(
    #     query_vector=[[random.random() for _ in range(768)] for _ in range(2)],
    #     topk=2,
    #     collection_name="test_collection",
    #     search_batch_size=2,
    #     multithread=False,
    #     max_threads=4,
    #     consistency_level="Eventually",
    #     output_fields=["text", "vector"],
    #     monitor=True
    # )
    # print("Query results:")
    # print(results)
