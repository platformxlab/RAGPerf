### Evaluator

Examples of how to use it is documented in `example/monitoring_sys_lib`. Detailed documentations at [MonitoringSystem README](monitoring_sys/README.md)

This module provides evaluation tools for Retrieval-Augmented Generation (RAG) using **local language models**. It wraps local LLMs (e.g., Qwen2-7B-Instruct-GPTQ-Int8) to work with [RAGAS](https://github.com/explodinggradients/ragas) and enables metrics like `context_recall`, `faithfulness`, `answer_relevancy`, and `context_precision`.

#### Install Git LFS

> Required to download large model weights.

**Ubuntu/Debian:**
```bash
sudo apt install git-lfs
```

#### Usage

> Download LLM model and embedding model (e.g. Qwen2-7B-Instruct-GPTQ-Int8, bge-large-zh-v1.5)
```
git clone https://huggingface.co/Qwen/Qwen2-7B-Instruct-GPTQ-Int8
cd Qwen2-7B-Instruct-GPTQ-Int8
git lfs pull
git clone https://huggingface.co/BAAI/bge-large-zh-v1.5
cd bge-large-zh-v1.5
git lfs pull
```
> Set the LLM and embedding model path in config file `wiki_evaluatein`, Run the RAG system
```
python3 src/run.py --config config/wiki_evaluate.yaml
```