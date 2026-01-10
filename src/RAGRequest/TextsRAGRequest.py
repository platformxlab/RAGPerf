import datasets
from RAGRequest.BaseRAGRequest import BaseRAGRequest


class WikipediaRequests(BaseRAGRequest):
    def __init__(self, run_name, collection_name, req_type, req_count):
        # Ensure dataset_name is fixed to "wikimedia/wikipedia"
        dataset_name = "wikimedia/wikipedia"
        self.query_list = None
        super().__init__(run_name, collection_name, req_type, dataset_name, req_count)

    def init_requests(self, num):
        if self.req_type == "query":
            questions, gt_answers = self.get_questions(num)
            query_list = {"questions": questions, "ground_truth_answers": gt_answers}
            # ground_truth =  data_processor.get_ground_truth(questions, gt_answers)

    def get_questions(self, batch_size, start_idx=0):
        if self.req_type != "query":
            raise ValueError("This request type is not supported for question retrieval.")
        if self.query_list is not None:
            questions = self.query_list["questions"][start_idx : start_idx + batch_size]
            gt_answers = self.query_list["ground_truth_answers"][start_idx : start_idx + batch_size]
            return questions, gt_answers
        else:
            try:
                ds = datasets.load_dataset("sentence-transformers/natural-questions", split="train")
            except ConnectionError as e:
                if datasets.config.HF_DATASETS_OFFLINE:
                    print(
                        "***Dataset autodownload disabled and no dataset is found under "
                        f"HF_CACHE_HOME: <{datasets.config.HF_CACHE_HOME}>"
                    )
                raise e

            # Extract questions and answers
            questions = ds["query"][start_idx : start_idx + batch_size]
            gt_answers = ds["answer"][start_idx : start_idx + batch_size]

        return questions, gt_answers
