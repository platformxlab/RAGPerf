from typing import List
from datasets import Dataset
from ragas.metrics import faithfulness, context_recall, context_precision, answer_relevancy
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.run_config import RunConfig
import asyncio
from evaluator.BaseEvaluator import BaseEvaluator

from langchain_openai import ChatOpenAI
from ragas.embeddings import OpenAIEmbeddings
import openai
from ragas import EvaluationDataset
import os

os.environ["OPENAI_API_KEY"] = "your_openai_api_key_here"  # Replace with your actual OpenAI API key


# run_config = RunConfig(timeout=800, max_wait=800)
class RagasOpenAI(BaseEvaluator):
    def __init__(self, llm_path, emb_path):
        self.llm = ChatOpenAI(model="gpt-4o")
        self.openai_client = openai.OpenAI()
        self.embeddings = OpenAIEmbeddings(client=self.openai_client)
        self.run_config = RunConfig(
            timeout=120,  # Adjust the timeout as needed
            max_retries=15,  # Increase the number of retries
            max_wait=90,  # Adjust the maximum wait time
            log_tenacity=True,  # Enable logging for retry attempts
        )

    def evaluate_single(self, question: str, answer: str, contexts: List[str], ground_truth: str):

        dataset = Dataset.from_dict(
            {
                'question': [question],
                'answer': [answer],
                'contexts': [contexts],
                'ground_truth': [ground_truth],
            }
        )
        print(
            {
                'question': [question],
                'answer': [answer],
                'contexts': [contexts],
                'ground_truth': [ground_truth],
            }
        )

        result = evaluate(
            dataset,
            metrics=[context_recall, context_precision, answer_relevancy, faithfulness],
            llm=self.my_llm,
            embeddings=self.embedding_model,
            run_config=self.run_config,
        )

        df = result.to_pandas()
        print(df.head())
        df.to_csv("evaluate_result.csv", index=False)
        loop = asyncio.get_event_loop()
        loop.close()
        return

    def evaluate_dataset(self, dataset):
        evaluation_dataset = EvaluationDataset.from_list(dataset)
        # evaluator_llm = LangchainLLMWrapper(self.llm)
        result = evaluate(
            evaluation_dataset,
            metrics=[context_recall, context_precision, answer_relevancy, faithfulness],
            llm=self.llm,
            embeddings=self.embeddings,
            run_config=self.run_config,
        )
        print("*" * 50)
        print(result)
        print("*" * 50)
        df = result.to_pandas()
        print(df.head())
        df.to_csv("evaluate_result.csv", index=False)
        loop = asyncio.get_event_loop()
        loop.close()
        return


# data_samples = {
#     'question': [
#         'When was the first Super Bowl?',
#         'Who won the most Super Bowls?'
#     ],
#     'answer': [
#         'The first Super Bowl was held on Jan 15, 1967',
#         'The most Super Bowls have been won by The New England Patriots'
#     ],
#     'contexts': [
#         [
#             'The first AFL–NFL World Championship Game was an American football game played on January 15, 1967, at the Los Angeles Memorial Coliseum in Los Angeles, California.'],
#         [
#             'The New England Patriots have won the Super Bowl a record six times, surpassing the Pittsburgh Steelers who have won it six times as well.']
#     ],
#     'ground_truth': [
#         'The first Super Bowl was held on January 15, 1967',
#         'The New England Patriots have won the Super Bowl a record six times'
#     ]
# }

# dataset = Dataset.from_dict(data_samples)
