from abc import ABC, abstractmethod
import os
import time
import math
from RAGPipeline.responser.TextsResponser import VLLMResponser
from RAGPipeline.BaseRAGPipline import BaseRAGPipeline
from encoder.sentenceTransformerEncoder import SentenceTransformerEncoder
from RAGPipeline.retriever.BaseRetriever import BaseRetriever
from RAGPipeline.reranker.CrossEncoderReranker import CrossEncoderReranker
from evaluator.RagasEvaluator import RagasEvaluator
from datasets import Dataset
import utils.colored_print as cprint
from utils.logger import Logger, log_time_breakdown
from qwen_vl_utils import process_vision_info


# should make the pipeline fully modular with request queue passing

# class ModularRAGPipeline(ABC):
#     def __init__(self, **kwargs):
#         # self.run_name = kwargs.get("run_name", "default_run")


class ImagesRAGPipeline(BaseRAGPipeline):
    def __init__(
        self,
        retriever: BaseRetriever,
        responser: VLLMResponser,
        embedder: SentenceTransformerEncoder,
        evaluator: RagasEvaluator = None,
    ) -> None:

        self.retriever = retriever
        self.responser = responser
        self.embedder = embedder
        return

    def generate_prompt(self, questions, contexts):
        chat_template = [
            {
                "role": "user",
                "content": [{"type": "image", "image": image} for image in contexts]
                + [{"type": "text", "text": questions}],
            }
        ]
        return chat_template

    def process(self, request, batch_size=2) -> None:
        if request.req_type == "query":
            cprint.iprintf(
                f"*** Processing {request.req_count} questions with batch size {batch_size}"
            )
            # load models
            log_time_breakdown("start")
            cprint.iprintf(f"*** Loading models")
            self.embedder.load_encoder()
            self.responser.load_llm()
            cprint.iprintf(f"*** Loading models done")

            nrounds = int(math.ceil(request.req_count / batch_size))
            cprint.iprintf(f"*** Will run {nrounds} rounds")
            for round_idx in range(0, nrounds):
                start_sample_idx = round_idx * batch_size
                questions, gt_answer = request.get_questions(batch_size, start_idx=start_sample_idx)
            print(f"***Processing {request.req_count} questions")
            for i in range(0, request.req_count, batch_size):
                questions, gt_answer = request.get_questions(batch_size, start_idx=i)

                # encode questions TODO: parameter
                # Embedding chunked texts
                # self.embedder.load_encoder()
                log_time_breakdown("embed")
                embedding_start_time = time.monotonic_ns()
                vectors = self.embedder.embedding_query(questions)
                embedding_end_time = time.monotonic_ns()
                # self.embedder.free_encoder()
                cprint.iprintf(f"*** Embedding done")

                for i, query in enumerate(vectors):
                    query = query.float().numpy()
                    # retrieval
                    log_time_breakdown("retrieve")
                    retrieval_start_time = time.monotonic_ns()
                    results = self.retriever.search_db_image(query)
                    retrieval_end_time = time.monotonic_ns()
                    cprint.iprintf(f"*** Retrieval done")

                    # augment
                    log_time_breakdown("prompt")
                    prompt_start_time = time.monotonic_ns()
                    prompts = self.generate_prompt(questions[i], results)
                    prompt_end_time = time.monotonic_ns()
                    cprint.iprintf(f"*** Prompt generation done")
                    with open("prompt.out", "w") as fout:
                        for idx, prompt in enumerate(prompts):
                            fout.write(f"=== Prompt {idx + 1} ===\n")
                            fout.write(str(prompts) + "\n\n")

                    # generation
                    cprint.iprintf(f"*** Generating answers")
                    # self.responser.load_llm()
                    log_time_breakdown("generate")
                    generation_start_time = time.monotonic_ns()
                    responses = self.responser.query_llm(prompts)
                    generation_end_time = time.monotonic_ns()
                    # self.responser.free_llm()
                    cprint.iprintf(f"*** Generation done")

                    with open("response.out", "w") as fout:
                        for idx, response in enumerate(responses):
                            fout.write(f"=== response {idx + 1} ===\n")
                            fout.write(response.strip() + "\n\n")
            log_time_breakdown("free_models")

            # finished
            cprint.iprintf(f"*** Unloading models")
            self.embedder.free_encoder()
            self.responser.free_llm()
            cprint.iprintf(f"*** Unloading models done")
            log_time_breakdown("done")
            embedding_time = embedding_end_time - embedding_start_time
            retrieval_time = retrieval_end_time - retrieval_start_time
            prompt_time = prompt_end_time - prompt_start_time
            generation_time = generation_end_time - generation_start_time
            total_time = embedding_time + retrieval_time + prompt_time + generation_time
            print(
                f"At round {round_idx}\n"
                f"  embedding time:  {embedding_time} ns ({embedding_time / 1e9} s, ({embedding_time / total_time * 100:.2f}%)\n"
                f"  retrieval time:  {retrieval_time} ns ({retrieval_time / 1e9} s, ({retrieval_time / total_time * 100:.2f}%)\n"
                f"  prompt time:     {prompt_time} ns ({prompt_time / 1e9} s, ({prompt_time / total_time * 100:.2f}%)\n"
                f"  generation time: {generation_time} ns ({generation_time / 1e9} s, ({generation_time / total_time * 100:.2f}%)\n"
            )
            output_path = os.path.join(Logger().log_dirpath, "text_pipeline_stats.txt")
            with open(output_path, "a") as fout:
                fout.write(
                    f"{round_idx}\t"
                    f"{embedding_time}\t"
                    f"{retrieval_time}\t"
                    f"{prompt_time}\t"
                    f"{generation_time}\t"
                    f"{total_time}\n"
                )
        return
