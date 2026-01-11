import torch, gc
from vllm import LLM, SamplingParams
from RAGPipeline.responser.BaseResponser import BaseResponser
from qwen_vl_utils import process_vision_info
from transformers import Qwen2VLForConditionalGeneration, Qwen2VLProcessor


class ImageResponser(BaseResponser):
    def __init__(self, model="Qwen/Qwen2-VL-7B-Instruct", device="cuda:0"):
        self.model_name = model
        self.device = device
        self.llm = None
        return

    def load_llm(self):
        print(f"***Loading LLM: {self.model_name} on {self.device}")
        self.vl_model = Qwen2VLForConditionalGeneration.from_pretrained(
            self.model_name,
            device_map=self.device,
        )
        self.vl_model.cuda().eval()
        min_pixels = 224 * 224
        max_pixels = 1024 * 1024
        self.vl_model_processor = Qwen2VLProcessor.from_pretrained(
            self.model_name,
            min_pixels=min_pixels,
            max_pixels=max_pixels,
            device_map=self.device,
        )
        print(f"***Loaded LLM: {self.model_name}")
        return

    def free_llm(self):
        del self.vl_model
        self.llm = None
        del self.vl_model_processor
        self.vl_model_processor = None
        gc.collect()
        torch.cuda.empty_cache()
        try:
            torch.cuda.ipc_collect()
        except Exception:
            pass

    def query_llm(self, prompts, max_tokens=500):
        # Prepare the inputs
        text = self.vl_model_processor.apply_chat_template(
            prompts, tokenize=False, add_generation_prompt=True
        )
        image_inputs, video_inputs = process_vision_info(prompts)
        inputs = self.vl_model_processor(
            text=[text],
            images=image_inputs,
            padding=True,
            return_tensors="pt",
        )
        inputs = inputs.to("cuda")

        # Generate text from the vl_model
        generated_ids = self.vl_model.generate(**inputs, max_new_tokens=max_tokens)
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]

        # Decode the generated text
        output_text = self.vl_model_processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        print("***answer:")
        print(output_text[0])
        return output_text
