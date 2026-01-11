import torch, gc
from vllm import LLM, SamplingParams
from RAGPipeline.responser.BaseResponser import BaseResponser


class VLLMResponser(BaseResponser):
    def __init__(self, model="Qwen/Qwen2.5-7B-Instruct", device="cuda:0", parallelism=1):
        self.model_name = model
        self.device = device
        self.llm = None
        self.parallelism = parallelism
        return

    def load_llm(self):
        if self.llm is not None:
            print(f"***LLM already loaded: {self.model_name}")
            return
        print(f"***Loading LLM: {self.model_name} on {self.device}")
        self.llm = LLM(
            model=self.model_name,
            enforce_eager=True,
            # device=self.device,
            dtype=torch.bfloat16,
            trust_remote_code=True,
            gpu_memory_utilization=0.85,
            max_model_len=8096,
            tensor_parallel_size=self.parallelism,
        )
        print(f"***Loaded LLM: {self.model_name}")

    def free_llm(self):
        del self.llm
        self.llm = None
        gc.collect()
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass

    def query_llm(self, prompts, max_tokens=1024, temperature=0.7, top_p=0.9):
        # make load and free out of this function

        sampling_params = SamplingParams(
            max_tokens=max_tokens, temperature=temperature, top_p=top_p
        )

        # batch process
        assert self.llm is not None, "Query called when LLM is not loaded"
        results = self.llm.generate(prompts, sampling_params)
        assert len(results) == len(
            prompts
        ), f"Mismatch detected, generated {len(results)} responses for {len(prompts)} prompts"
        return [res.outputs[0].text for res in results]
