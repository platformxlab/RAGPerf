from pymilvus import MilvusClient
import argparse


class milvus_util:
    def __init__(self):
        self.client = MilvusClient(uri="http://localhost:19530", token="root:Milvus")
        print(f"***connect to milvus client\n")

    def load_collections(self, collection_name):
        self.client.load_collection(collection_name)
        print(f"***load collections {collection_name}.")

    def release_collections(self, collection_name):
        self.client.release_collection(collection_name)
        print(f"***release collections {collection_name}.")

    def release_all_collections(self):
        collections = self.client.list_collections()

        for collection_name in collections:
            self.client.release_collection(collection_name)
        print("***All collections released.")

    def drop_collection(self, collection_name):
        self.client.drop_collection(collection_name)
        print(f"***Dropped existing collection: {collection_name}")

    def create_collection(self, collection_name, dim):
        if self.client.has_collection(collection_name):
            print(f"***collection: {collection_name} already have")
            return
        print(f"***Creating new collection: {collection_name} with consistency_level: Eventually")

        self.client.create_collection(
            collection_name, dim, consistency_level="Eventually", auto_id=True
        )
        return

    def create_index(self, collection_name):
        print(f"***Creating index: {self.index_type} metics: {self.metric_type}")
        res = self.client.list_indexes(collection_name=collection_name)

        if len(res) > 0:
            self.client.release_collection(
                collection_name=collection_name,
            )
            self.client.drop_index(collection_name=collection_name, index_name=res[0])
            print(f"*** Drop index name: {res[0]}")
        print(f"*** Create index name: {self.index_type}_{self.metric_type}")

        index_params = MilvusClient.prepare_index_params()

        if self.index_type == "IVF_PQ":
            index_params.add_index(
                field_name="vector",
                metric_type=self.metric_type,
                index_type=self.index_type,
                index_name=f"{self.index_type}_{self.metric_type}",
                params={
                    "m": 4,  # Number of sub-vectors to split each vector into
                },
            )
        else:
            index_params.add_index(
                field_name="vector",
                metric_type=self.metric_type,
                index_type=self.index_type,
                index_name=f"{self.index_type}_{self.metric_type}",
            )

        # 4.3. Create an index file
        self.client.create_index(collection_name=collection_name, index_params=index_params)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db", type=str, default="http://localhost:19530", help="db client location"
    )
    parser.add_argument("--task", type=str, default="none", help="action to the db client")
    parser.add_argument("--collection", type=str, default="none", help="collection name")
    parser.add_argument("--dim", type=int, default=0, help="dimension of the collection")
    parser.add_argument("--index_type", type=str, default="IVF_PQ", help="index type")
    parser.add_argument(
        "--config", type=str, default="none", help="load collection name from config"
    )
    args = parser.parse_args()

    # if args.config != "none":
    #     config = load_config(args.config)
    #     if "dataset" in config:
    #         dataset_cfg.update(config["dataset"])
    #     if "pipeline" in config:
    #         pipeline_cfg.update(config["pipeline"])
    #     args.collection = dataset_cfg["collection_name"]
    #     args.index_type = dataset_cfg["index_type"]

    db_i = milvus_util()
    # db_i.client = MilvusClient(uri=args.db, token="root:Milvus")

    switch = {
        "load": db_i.load_collections,
        "release": db_i.release_collections,
        "release_all": db_i.release_all_collections,
        "drop": db_i.drop_collection,
        "create": db_i.create_collection,
        # "create_index": db_i.create_index
    }
    print("dimension: ", args.dim)
    if args.task == "create":
        db_i.create_collection(args.collection, args.dim)
    elif args.task in switch:
        switch[args.task](args.collection)
    else:
        print(f"***{args.task} is not a valid task")
    # db_i.client = MilvusClient(uri="http://localhost:195
