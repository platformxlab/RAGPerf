from typing import List, Optional, Any
from datasets import Dataset
from ragas.metrics import faithfulness, context_recall, context_precision, answer_relevancy
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import BaseRagasEmbeddings
from ragas.run_config import RunConfig
from FlagEmbedding import FlagModel
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun
import asyncio
from evaluator.BaseEvaluator import BaseEvaluator


class MyLLM(LLM):
    tokenizer: AutoTokenizer = None
    model: AutoModelForCausalLM = None

    def __init__(self, mode_name_or_path: str):
        super().__init__()
        self.tokenizer = AutoTokenizer.from_pretrained(mode_name_or_path)
        self.model = AutoModelForCausalLM.from_pretrained(mode_name_or_path, device_map="auto")
        self.model.generation_config = GenerationConfig.from_pretrained(mode_name_or_path)

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        input_ids = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        model_inputs = self.tokenizer([input_ids], return_tensors="pt").to('cuda')
        generated_ids = self.model.generate(model_inputs.input_ids, max_new_tokens=4096)
        generated_ids = [
            output_ids[len(input_ids) :]
            for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        response = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return response

    @property
    def _llm_type(self):
        return "local_llm"


class MyEmbedding(BaseRagasEmbeddings):

    def __init__(self, path, run_config, max_length=512, batch_size=256):
        self.model = FlagModel(
            path,
            query_instruction_for_retrieval="Generate a representation for this sentence to retrieve related articles: ",
        )
        self.max_length = max_length
        self.batch_size = batch_size
        self.run_config = run_config

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode_corpus(texts, self.batch_size, self.max_length).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.model.encode_queries(text, self.batch_size, self.max_length).tolist()

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> List[float]:
        return await asyncio.to_thread(self.embed_query, text)

    def close(self):
        try:
            self.model.stop_self_pool()
        except Exception as e:
            print(f"Warning during embedder cleanup: {e}")


# run_config = RunConfig(timeout=800, max_wait=800)
class RagasEvaluator(BaseEvaluator):
    def __init__(self, llm_path, emb_path):
        self.run_config = RunConfig(timeout=800, max_wait=800)
        self.embedding_model = MyEmbedding(emb_path, self.run_config)
        self.my_llm = LangchainLLMWrapper(MyLLM(llm_path), self.run_config)

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
        result = evaluate(
            dataset,
            metrics=[context_recall, context_precision, answer_relevancy, faithfulness],
            llm=self.my_llm,
            embeddings=self.embedding_model,
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
