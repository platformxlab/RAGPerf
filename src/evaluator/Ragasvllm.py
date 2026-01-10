import os

os.environ["OUTLINES_CACHE_DIR"] = "vllm_cache"
os.environ['VLLM_WORKER_MULTIPROC_METHOD'] = 'spawn'

import typing as t
import torch, gc

from ragas.metrics import LLMContextPrecisionWithReference, LLMContextRecall
from ragas import evaluate, EvaluationDataset
from vllm import AsyncLLMEngine, LLM, SamplingParams
from vllm.engine.arg_utils import AsyncEngineArgs


import uuid

from langchain_core.callbacks import Callbacks
from langchain_core.outputs import LLMResult, Generation
from langchain_core.prompt_values import PromptValue
from ragas.cache import CacheInterface
from ragas.llms import BaseRagasLLM
from ragas.run_config import RunConfig

from evaluator.BaseEvaluator import BaseEvaluator
from datasets import Dataset
from typing import List, Optional, Any
from ragas.metrics import (
    LLMContextRecall,
    Faithfulness,
    FactualCorrectness,
    AnswerAccuracy,
    BleuScore,
)
import asyncio


class vLLMWrapper(BaseRagasLLM):
    """
    A wrapper class that adapts vLLM's inference engine to the Ragas-compatible BaseRagasLLM interface.

    This class enables using vLLM for scoring and evaluation tasks within the Ragas framework by implementing
    the `generate_text` and `agenerate_text` method that produces LangChain-compatible `LLMResult` objects.
    Source: https://github.com/explodinggradients/ragas/blob/main/ragas/src/ragas/llms/base.py#L123

    Attributes:
        llm: The vLLM model instance, typically created via `vllm.LLM(...)`.
        sampling_params: A `SamplingParams` object defining temperature, top_p, etc.
        run_config: Optional configuration for controlling how evaluations are executed.
        cache: Optional cache for storing/reusing model outputs.

    """

    def __init__(
        self,
        vllm_model,
        sampling_params,
        run_config: t.Optional[RunConfig] = None,
        cache: t.Optional[CacheInterface] = None,
    ):
        super().__init__(cache=cache)
        self.llm = vllm_model
        self.sampling_params = sampling_params

        if run_config is None:  # legacy code
            run_config = RunConfig()
        self.set_run_config(run_config)

    def is_finished(self, response: LLMResult) -> bool:
        """
        Verify that generation finished correctly by looking at finish_reason.
        `response` contains the n outputs of a single input, thus:
            len(response.generations) == 1
            len(response.generations[0]) == n
        """
        is_finished_list = []
        for single_generation in response.generations[0]:
            # generation_info is provided with `finish_reason`
            finish_reason = single_generation.generation_info.get("finish_reason")
            is_finished_list.append(finish_reason == 'stop')

        # if all the n outputs finished correctly, return True
        return all(is_finished_list)

    def generate_text(
        self,
        prompt: PromptValue,
        n: int = 1,
        temperature: t.Optional[float] = None,
        stop: t.Optional[t.List[str]] = None,
        callbacks: Callbacks = None,
    ) -> LLMResult:
        temperature = None
        stop = None
        callbacks = None

        prompt = prompt.to_string()
        self.sampling_params.n = n

        vllm_result = self.llm.generate(prompt, self.sampling_params)[0]

        generations = [
            [
                Generation(
                    text=output.text.strip(),
                    generation_info={'finish_reason': output.finish_reason},
                )
                for output in vllm_result.outputs
            ]
        ]
        ragas_expected_result = LLMResult(generations=generations)

        return ragas_expected_result

    async def agenerate_text(
        self,
        prompt: PromptValue,
        n: int = 1,
        temperature: t.Optional[float] = None,
        stop: t.Optional[t.List[str]] = None,
        callbacks: Callbacks = None,
    ) -> LLMResult:
        temperature = None
        stop = None
        callbacks = None

        prompt = prompt.to_string()
        self.sampling_params.n = n
        request_id = str(uuid.uuid4())
        results_generator = self.llm.generate(prompt, self.sampling_params, request_id=request_id)
        vllm_result = None
        async for request_output in results_generator:
            vllm_result = request_output
        generations = [
            [
                Generation(
                    text=output.text.strip(),
                    generation_info={'finish_reason': output.finish_reason},
                )
                for output in vllm_result.outputs
            ]
        ]
        ragas_expected_result = LLMResult(generations=generations)

        return ragas_expected_result

    def set_run_config(self, run_config: RunConfig):
        self.run_config = run_config

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(llm={self.llm.__class__.__name__}(...))"


# run_config = RunConfig(timeout=800, max_wait=800)
class Ragasvllm(BaseEvaluator):
    def __init__(self, llm_path="Qwen/Qwen2.5-7B-Instruct"):
        self.run_config = RunConfig(timeout=800, max_wait=800)
        # self.embedding_model = MyEmbedding(emb_path, self.run_config)
        self.llm_name = llm_path

        self.sampling_params = SamplingParams(
            temperature=0.6,
            top_p=0.9,
            max_tokens=8096,
        )

    def load_evaluator_model(self):
        # todo set device from config
        self.llm: AsyncLLMEngine = AsyncLLMEngine.from_engine_args(
            AsyncEngineArgs(
                model=self.llm_name,
                task='generate',  # generation task
                enforce_eager=True,
                # device=self.device,
                dtype=torch.bfloat16,
                trust_remote_code=True,
                gpu_memory_utilization=0.8,
                max_model_len=8192,
                tensor_parallel_size=2,
            )
        )

    async def free_evaluator_model(self):
        if self.llm is not None:
            # self.llm.shutdown_background_loop()
            del self.llm
            self.llm = None
        try:
            import torch.distributed as dist

            if dist.is_available() and dist.is_initialized():
                dist.destroy_process_group()
        except Exception:
            pass

        gc.collect()
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass

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
            # metrics=[FactualCorrectness(), AnswerAccuracy(), BleuScore()],
            metrics=[FactualCorrectness(), AnswerAccuracy(), LLMContextRecall()],
            llm=vLLMWrapper(self.llm, self.sampling_params),
            # embeddings=self.embedding_model,
            run_config=self.run_config,
        )

        df = result.to_pandas()
        print(df.head())
        df.to_csv("evaluate_result.csv", index=False)
        asyncio.get_event_loop().close()
        return

    def evaluate_dataset(self, dataset):

        self.load_evaluator_model()
        try:
            result = evaluate(
                dataset,
                metrics=[FactualCorrectness(), AnswerAccuracy(), LLMContextRecall()],
                llm=vLLMWrapper(self.llm, self.sampling_params),
                # embeddings=self.embedding_model,
                run_config=self.run_config,
            )
            print("*" * 50)
            print(result)
            print("*" * 50)
            df = result.to_pandas()
            print(df.head())
            df.to_csv("evaluate_result.csv", index=False)

        finally:
            # IMPORTANT: free the async engine INSIDE the loop
            # delegate to an async helper and run it with asyncio.run
            asyncio.run(self._async_free())
        return

    async def _async_free(self):
        # your async free (with await self.llm.aclose(), etc.)
        await self.free_evaluator_model()
