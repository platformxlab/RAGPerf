from pymilvus import MilvusClient
from tqdm import tqdm
import re
import concurrent.futures

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# sys.path.reverse()
from vectordb.DBInstance import DBInstance


class milvus_client(DBInstance):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.type = "milvus"
        self.db_token = kwargs.get("db_token", "root:Milvus")

    def setup(self):
        self.client = MilvusClient(uri=self.db_path, token=self.db_token)
        print(f"***Connected to Milvus client at {self.db_path}\n")
        # return self.client

    def has_collection(self, collection_name):
        if self.client.has_collection(collection_name):
            print(f"***Collection: {collection_name} exists.")
            return True
        else:
            print(f"***Collection: {collection_name} does not exist.")
            return False

    def create_collection(self, collection_name, dim, consistency_level="Eventually", auto_id=True):
        if self.client.has_collection(collection_name):
            print(f"***Collection: {collection_name} already exists.")
            # load collection
            return self.client.load_collection(collection_name)
        else:
            try:
                self.client.create_collection(
                    collection_name, dim, consistency_level="Eventually", auto_id=True
                )
                print(
                    f"***Created new collection: {collection_name} with consistency_level: {consistency_level}"
                )
                return
            except Exception as e:
                print(f"***Failed to create collection: {collection_name}. Error: {e}")
                return

    def drop_collection(self, collection_name):
        if not self.client.has_collection(collection_name):
            print(f"***Collection: {collection_name} does not exist.")
            return
        self.client.drop_collection(collection_name)
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
        if collection_name is None:
            collection_name = self.default_collection
        if not self.client.has_collection(collection_name):
            if create_collection:
                # create_collection first
                self.create_collection(collection_name, dim=len(vector[0]))
            else:
                print(f"***Collection: {collection_name} does not exist. Please create it first.")
                return

        total_chunks_num = len(chunks)
        total_vectors_num = len(vector)
        if total_chunks_num != total_vectors_num and strict_check:
            print(
                f"***Error: The number of chunks ({total_chunks_num}) does not match the number of vectors ({total_vectors_num})."
            )
            return
        print(f"***Start insert: {total_chunks_num}")

        for i in tqdm(range(0, total_chunks_num, insert_batch_size), desc="inserting"):
            dict_list = [
                {"text": text, "vector": vector}
                for text, vector in zip(
                    chunks[i : i + insert_batch_size], vector[i : i + insert_batch_size]
                )
            ]
            self.client.insert(collection_name, data=dict_list, progress_bar=False)

        print(f"***Insert done.")

    def insert_data(
        self, dict_list, collection_name=None, insert_batch_size=1, create_collection=False
    ):
        if collection_name is None:
            collection_name = self.default_collection
        if not self.client.has_collection(collection_name):
            if create_collection:
                # create_collection first
                self.create_collection(collection_name, dim=len(dict_list[0]["vector"]))
            else:
                print(f"***Collection: {collection_name} does not exist. Please create it first.")
            return

        total_chunks_num = len(dict_list)
        print(f"***Start insert: {total_chunks_num}")

        for i in tqdm(range(0, total_chunks_num, insert_batch_size), desc="inserting"):
            self.client.insert(
                collection_name, data=dict_list[i : i + insert_batch_size], progress_bar=False
            )

        print(f"***Insert done.")

    def query_search(
        self,
        query_vector,
        topk,
        collection_name=None,
        search_batch_size=1,
        multithread=False,
        max_threads=1,
        consistency_level="Eventually",
        output_fields=["text", "vector"],
    ):
        if collection_name is None:
            collection_name = self.default_collection
        if not self.client.has_collection(collection_name):
            print(f"***Collection: {collection_name} does not exist. Please create it first.")
            return

        self.client.load_collection(collection_name)

        total_queries = len(query_vector)
        results = [None] * total_queries

        num_batches = (total_queries + search_batch_size - 1) // search_batch_size

        def search_thread(start_idx, end_idx):
            b_vectors = query_vector[start_idx:end_idx]
            b_results = self.client.search(
                collection_name,
                data=b_vectors,
                limit=topk,
                consistency_level="Eventually",
                output_fields=output_fields,
            )
            results[start_idx:end_idx] = b_results

        # start_time = time.time()
        # print(f"*** Start multithreaded search: total={self.retrieval_size}, batch_size={batch_size}, max_threads={max_threads}")
        if max_threads == 1 or not multithread:
            # Single-threaded search
            for i in range(num_batches):
                start_idx = i * search_batch_size
                end_idx = min(start_idx + search_batch_size, total_queries)
                b_vectors = query_vector[start_idx:end_idx]
                b_results = self.client.search(
                    collection_name,
                    data=b_vectors,
                    limit=topk,
                    consistency_level=consistency_level,
                    output_fields=output_fields,
                )
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

        context_format = """Source #{source_idx}\nDetail: {source_detail}\n"""
        contexts_results = []
        with open("query.out", "w") as fout:
            for query_idx, query_results in enumerate(results):
                fout.write(f"=== Query #{query_idx + 1} Results ===\n")
                context = []
                for entry_idx, result in enumerate(query_results):
                    entity = result.get("entity", {})
                    detail = re.sub(r"\n+", "\n", entity.get("text", ""))
                    formatted = context_format.format(source_idx=entry_idx, source_detail=detail)
                    context.append(formatted)
                    fout.write(
                        f"*** Retrieved result #{entry_idx}, id: {result.get('id')}, distance: {result.get('distance'):.4f}, doc length: {len(detail)}\n"
                    )
                fout.write("\n")
                contexts_results.append(context)

        # print(f"*** Milvus limited-thread search time: {round(end_time - start_time, 2)} seconds")
        # self.client.release_collection(collection_name)

        # if True:
        #     self.client.alter_collection_properties(
        #         collection_name=collection_name,
        #         properties={
        #             "mmap.enabled": True
        #         }
        #     )

        return contexts_results

    def query_search_image(
        self,
        query_vector,
        topk,
        collection_name=None,
        search_batch_size=1,
        multithread=False,
        max_threads=1,
        consistency_level="Eventually",
        output_fields=["text", "vector"],
    ):
        if collection_name is None:
            collection_name = self.default_collection
        if not self.client.has_collection(collection_name):
            print(f"***Collection: {collection_name} does not exist. Please create it first.")
            return

        self.client.load_collection(collection_name)

        total_queries = len(query_vector)
        results = [None] * total_queries

        num_batches = (total_queries + search_batch_size - 1) // search_batch_size

        def search_thread(start_idx, end_idx):
            b_vectors = query_vector[start_idx:end_idx]
            b_results = self.client.search(
                collection_name,
                data=b_vectors,
                limit=topk,
                consistency_level="Eventually",
                output_fields=output_fields,
            )
            results[start_idx:end_idx] = b_results

        # start_time = time.time()
        # print(f"*** Start multithreaded search: total={self.retrieval_size}, batch_size={batch_size}, max_threads={max_threads}")
        if max_threads == 1 or not multithread:
            # Single-threaded search
            for i in range(num_batches):
                start_idx = i * search_batch_size
                end_idx = min(start_idx + search_batch_size, total_queries)
                b_vectors = query_vector[start_idx:end_idx]
                b_results = self.client.search(
                    collection_name,
                    data=b_vectors,
                    limit=topk,
                    consistency_level=consistency_level,
                    output_fields=output_fields,
                )
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
                print(f"len results: {len(results)}")

                # get unique doc_id from db search
                doc_ids = set()
                for r_id in range(len(results)):
                    for r in range(len(results[r_id])):
                        doc_ids.add(results[r_id][r]["entity"]["doc_id"])

        return doc_ids

    def query(self, collection_name, filter_expr, output_fields=["text", "vector"], limit=10):
        results = self.client.query(
            collection_name=collection_name,
            filter_expr=filter_expr,
            output_fields=output_fields,
            limit=limit,
        )
        return results

    def build_index(self, collection_name, index_type, metric_type, idx_name=None, drop_index=True):
        if collection_name is None:
            collection_name = self.default_collection
        if not self.client.has_collection(collection_name):
            print(f"***Collection: {collection_name} does not exist. Please create it first.")
            return
        print(f"***Creating index: {index_type} metics: {metric_type}")
        res = self.client.list_indexes(collection_name=collection_name)

        self.client.flush(collection_name=collection_name)

        if drop_index and len(res) > 0:
            self.client.release_collection(
                collection_name=collection_name,
            )
            self.client.drop_index(collection_name=collection_name, index_name=res[0])
            print(f"*** Drop index name: {res[0]}")

        if idx_name is None:
            idx_name = f"{index_type}_{metric_type}"
            print(f"*** Index name to default: {idx_name}")
        print(f"*** Create index name: {idx_name}")

        index_params = self.client.prepare_index_params()

        # 4.2. Add an index on the vector field.
        if index_type == "IVF_PQ":
            index_params.add_index(
                field_name="vector",
                metric_type=metric_type,
                index_type=index_type,
                index_name=idx_name,
                params={
                    "m": 128,  # Number of sub-vectors to split eahc vector into
                },
            )
        else:
            index_params.add_index(
                field_name="vector",
                metric_type=metric_type,
                index_type=index_type,
                index_name=idx_name,
            )

        # 4.3. Create an index file
        self.client.create_index(collection_name=collection_name, index_params=index_params)

        # self.client.flush(collection_name=self.collection_name)

        res = self.client.list_indexes(collection_name=collection_name)

        index_describe = self.client.describe_index(
            collection_name=collection_name, index_name=res[0]
        )
        # self.client.flush(collection_name=collection_name)
        print(index_describe)


# test
# if __name__ == "__main__":
#     client = MilvusClient(uri="http://localhost:19530", token="root:Milvus")
#     idx_name= "test"
#     collection_name = "wikimedia_wikipedia_all_MiniLM_L6_v2_0_1_512"
#     client.release_collection(collection_name=collection_name)
#     client.drop_index(collection_name=collection_name, index_name=idx_name)

#     index_params = client.prepare_index_params()

#     index_params.add_index(
#                 field_name="vector",
#                 metric_type="L2",
#                 index_type="GPU_IVF_FLAT",
#                 index_name=idx_name
#             )
#     client.create_index(
#             collection_name= collection_name,
#             index_params=index_params
#         )
#     print(f"***Created index: {idx_name} on collection: {collection_name}")

#     #test search
#     # vectors = [[random.random() for i in range(512)] for j in range(10)]  # Example vectors

#         # self.client.flush(collection_name=self.collection_name)

#         res = self.client.list_indexes(
#             collection_name=collection_name
#         )

#     print("Milvus client test")
#     mc = milvus_client(
#         db_path="http://localhost:19530",
#         collection_name="test_collection",
#         dim=768,
#         index_type="IVF_PQ",
#         metric_type="L2"
#     )

#     mc.setup()
#     mc.has_collection("test_collection")
#     mc.create_collection("test_collection", dim=768)
# mc.drop_collection("test_collection")
# test insertion
# vectors = [[random.random() for i in range(768)] for j in range(10)]  # Example vectors
# print(vectors)
# mc.insert_data(vectors, ["text1", "text2", "text3", "text4", "text5", "text6", "text7", "text8", "text9", "text10"], "test_collection")
# mc.build_index("test_collection", "IVF_PQ", "L2", drop_index=True)
# query_vector = [vectors[0],vectors[3]]  # Example query vectors
# results = mc.query_search(query_vector, topk=2, collection_name="test_collection", search_batch_size=2, multithread=True, max_threads=4)
# print("Query results:", results)
