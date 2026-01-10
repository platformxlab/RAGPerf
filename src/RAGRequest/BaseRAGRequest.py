from abc import ABC, abstractmethod


# the class for gnerated workloads without worload mix
class BaseRAGRequest(ABC):
    def __init__(self, run_name, collection_name, req_type, dataset_name, req_count):
        self.run_name = run_name
        self.collection_name = collection_name
        self.dataset_name = dataset_name
        # self.dataprocessor = kwargs.get("dataprocessor")
        self.req_type = req_type
        self.req_count = req_count
        if req_type not in ["query", "update"]:
            raise ValueError(f"Invalid request type: {req_type}. Must be 'query' or 'update'.")
        # if req_type == "query":
        #     self.query_list = kwargs.get("query_list", None)
        #     # self.query_format = kwargs.get("query_format", None)
        #     self.ground_truth = kwargs.get("ground_truth", None)
        # elif req_type == "update":
        #     print("Update request type is not implemented yet.")
        # self.req_count = kwargs.get("req_count")

    @abstractmethod
    def init_requests(self):
        pass

    @abstractmethod
    def get_questions(self):
        pass
