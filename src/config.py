import re
import os
import yaml

# config should be three parts:
# 1. general config
# 2. pipeline config
# 3. benchmark config
deafult_runname = "default_run"

DEFAULT_SYS_CONFIG = {
    "devices": {
        "cpu": "cpu",
        "gpus": ["cuda:0", "cuda:1"],
        "gpu_count": 2,
    },
    "vector_db": {
        "type": "milvus",
        "db_path": "http://localhost:19530",
        "db_token": "root:Milvus",
        "collection_name": "",
        "drop_previous_collection": False,
    },
    "log": {
        "metrics_log": "./log/default_run.log",
    },
}

DEFAULT_RAG_CONFIG = {
    "action": {
        "preprocess": True,
        "embedding": True,
        "insert": False,
        "build_index": False,
        "retrieval": False,
        "reranking": False,
        "generation": False,
        "evaluate": False,
    },
    # ingest part
    "embedding": {
        "model": "nomic-ai/nomic-embed-text-v2-moe",
        "batch_size": 128,
        "embedding_framework": "sentence_transformers",  #
        "sentence_transformers_name": "all-MiniLM-L6-v2",  #
    },
    "insert": {
        "batch_size": 512,
        "drop_previous_collection": False,
        "collection_name": "",
    },
    "build_index": {
        "index_type": "IVF_FLAT",
        "metric_type": "L2",
    },
    # retrieval part
    "retrieval": {
        "top_k": 5,
        "question_num": 1,
        "retrieval_batch_size": 1,
    },
    "reranking": {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "device": "cuda:0",
    },
    # generation
    "generation": {
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "device": "cuda:0",
    },
    "evaluate": {
        "evaluator_model": "ragdata/Qwen2-7B-Instruct-GPTQ-Int8",
        "evaluator_embedding": "ragdata/bge-large-zh-v1.5",
    },
}

DEFAULT_BENCHMARK_CONFIG = {
    "dataset": "wikimedia/wikipedia",
    "preprocessing": {
        "chunktype": "length",
        "chunk_size": 512,
        "chunk_overlap": 0,
        "dataset_ratio": 0.01,
    },
}


def load_config(config_path):
    # check
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    if not config_path.endswith(".yaml"):
        raise ValueError("Config file should be an yaml file")
    # load
    print(f"load config file: {config_path}")
    with open(config_path, "r") as file:
        return yaml.safe_load(file)


def config_to_log_path(config_path="config/config.yaml") -> str:
    if not config_path.endswith(".yaml"):
        raise ValueError("Config path must end with .yaml")

    log_path = config_path.replace("config", "log").replace(".yaml", ".log")
    return log_path


def get_db_collection_name(
    name,
    replacement_str="_",
):
    # replace everything that is not a number, letter, or underscore with replacement_str
    pattern = r"[^\w\d_]+"
    occurrences = [(m.start(0), m.end(0)) for m in re.finditer(pattern, name)]
    occurrences_sorted = sorted(occurrences, key=lambda inst: inst[0])

    # look for continuous invalid strings
    substring_sorted = []
    last_substring_start = 0
    for occ_start, occ_end in occurrences_sorted:
        substring_sorted.append((last_substring_start, occ_start))
        last_substring_start = occ_end
    substring_sorted.append((last_substring_start, len(name)))

    # replace them by ignoring them on concatenation
    collection_name = name[substring_sorted[0][0] : substring_sorted[0][1]]
    for inst in substring_sorted[1:]:
        collection_name += replacement_str + name[inst[0] : inst[1]]

    return collection_name


def output_config(config, output_path):
    """
    Save the configuration to a YAML file.
    """
    if not output_path.endswith(".yaml"):
        raise ValueError("Output path must end with .yaml")
    # if not os.path.exists(os.path.dirname(output_path)):

    with open(output_path, "w") as file:
        yaml.dump(config, file, default_flow_style=False)
    print(f"Configuration saved to {output_path}")


def generate_default_config():
    config = {
        "run_name": deafult_runname,
        "sys": DEFAULT_SYS_CONFIG,
        "rag": DEFAULT_RAG_CONFIG,
        "bench": DEFAULT_BENCHMARK_CONFIG,
    }
    return config


# output_config(generate_default_config(), "./config/example.yaml")
