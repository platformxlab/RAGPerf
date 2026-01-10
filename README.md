# RASB: RAG-based AI System Benchmarking Framework

**RASB** is an open-source framework designed to benchmark the End-to-End system performance of Retrieval-Augmented Generation (RAG) applications. Built with a fully modular architecture, it offers user-friendly and highly customizable framework that allows precise measurement of throughput, latency, and scalability across different RAG configurations.

<!-- CI/CD Status -->
[![C/C++ Format Check](https://github.com/platformxlab/RAGPerf/actions/workflows/clang-format.yml/badge.svg)](https://github.com/platformxlab/RAGPerf/actions/workflows/clang-format.yml)
[![Python Format Check](https://github.com/platformxlab/RAGPerf/actions/workflows/black-format.yml/badge.svg)](https://github.com/platformxlab/RAGPerf/actions/workflows/black-format.yml)

<!-- Repo Characteristics -->
![CMake](https://img.shields.io/badge/CMake-008fba.svg?style=flat&logo=cmake&logoColor=ffffff)
![C++](https://img.shields.io/badge/c++-00599c.svg?style=flat&logo=c%2B%2B&logoColor=ffffff)
![Python](https://img.shields.io/badge/python-3670a0?style=flat&logo=python&logoColor=ffe465)
![OS Linux](https://img.shields.io/badge/OS-Linux-fcc624?style=flat&logo=linux&logoColor=ffffff)
[![Code style: clang-format](https://img.shields.io/badge/C/C++_Code_Style-clang--format-2a3e50?style=flat&logo=llvm&logoColor=cccccc)](resource/clang_format/.clang-format)
[![Code style: black](https://img.shields.io/badge/Python_Code_Style-black-000000?style=flat&logo=black&logoColor=ffffff)](resource/black_format/.black-format)

## Key Features

**🚀 Holistic System-Centric Benchmarking**: RASB moves beyond simple accuracy metrics to profile the performance of RAG systems. It measures end-to-end throughput (QPS), latency breakdown, and hardware efficiency, helping you identify whether a bottleneck lies in I/O-bound retrieval or compute-bound prefill/decoding stages.

**🧩 Modular Architecture**: RASB employs a configuration-driven design that abstracts the entire RAG pipeline—Embedding, Vector Database, Reranking, and Generation—behind uniform interfaces. You can seamlessly swap components—switching from Milvus to LanceDB, or from ChatGPT to Qwen—without rewriting code. This enables fine-grained analysis of specific component trade-offs.

**📊 Detailed Full-Stack Profiling**: RASB integrates a lightweight system profiler that runs as a background daemon. It captures granular hardware metrics with minimal overhead, including GPU/CPU utilization, memory usage (host RAM vs. GPU VRAM), PCIe throughput, and Disk I/O. This allows for deep analysis of resource contention between RAG components.

**🔄 Dynamic Workload Generation**: Simulates the evolution of real-world knowledge bases. The workload generator can interleave standard search queries with insert, update, and delete operations. This allows you to stress-test how a RAG system handles high-concurrency requests while maintaining data freshness.

**🖼️ Multi-Modal Capabilities**: RASB supports diverse data modalities beyond plain text. It includes specialized pipelines for Visual RAG (PDFs, Images) using OCR or ColPali visual embeddings, and Audio RAG using ASR models like Whisper. This enables benchmarking of complex, unstructured enterprise data pipelines.

---

<!-- omit from toc -->
## Table of Contents

- [RASB: RAG-based AI System Benchmarking Framework](#rasb-rag-based-ai-system-benchmarking-framework)
  - [Key Features](#key-features)
  - [Installation](#installation)
    - [1) Create a virtual environment](#1-create-a-virtual-environment)
    - [2) Python dependencies](#2-python-dependencies)
    - [3) Install monitor system](#3-install-monitor-system)
  - [Running RASB](#running-rasb)
    - [Quick Start with Web UI](#quick-start-with-web-ui)
      - [1) Preparation](#1-preparation)
      - [2) Config your Benchmark and run](#2-config-your-benchmark-and-run)
    - [Run with Command Line (CLI)](#run-with-command-line-cli)
      - [1) Preparation](#1-preparation-1)
      - [2) Running the Benchmark](#2-running-the-benchmark)
      - [3) Output Analysis](#3-output-analysis)
  - [Supported RAG Pipeline Modules](#supported-rag-pipeline-modules)
    - [VectorDB](#vectordb)
    - [Monitoring System](#monitoring-system)

## Installation

### 1) Create a virtual environment
To run RASB, we highly recommend using an isolated Python environment (e.g., Conda).

**Conda (recommended)**
```bash
# Install Miniconda/Mambaforge from the official site if you don't have Conda
conda create -n rasb python=3.10
conda activate rasb
```

### 2) Python dependencies
Execute the following instructions to install all the dependencies for the project.
We use `pip-tools` to ensure reproducible dependency resolution.

```bash
# install pip-compile for python package dependency resolution
python3 -m pip install pip-tools

# configure MSys and generate a list of all required python packages
mkdir build && cd build
cmake ..
make generate_py3_requirements
python3 -m pip install -r ../requirement.txt
```

### 3) Install monitor system
<!-- REVIEW: Put installation instructions here instead of readme in monitoring system module -->
RASB uses a custom, low-overhead monitoring daemon. Please refer to the documentations at [MonitoringSystem README](monitoring_sys/README.md) for compilation and installation instructions.

## Running RASB
RASB provides an Interactive Web UI for ease of use. Or you can use the Command Line (CLI) for automation.

### Quick Start with Web UI
#### 1) Preparation
Set these once in your shell rc file (e.g., `~/.bashrc` or `~/.zshrc`) or export them in every new shell:
```bash
# Make local "src" importable
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH+:$PYTHONPATH}"

# Where to cache Hugging Face models (optional, adjust path as needed)
export HF_HOME="/mnt/data/hf_home"
```
Install streamlit and run the RASB client.
```bash
# install streamlit
python3 -m pip install streamlit
# run RASB
streamlit run ui_client.py
```
Open the UI with the reported url with your web browser, the default url is `http://localhost:8501`.

#### 2) Config your Benchmark and run
To run the benchmark, we first need to setup the retriever like a vectorDB. See [vectordb](#vectordb). The in the webpage, customize your own workload setting. ![config](./doc/figures/ragconfig.png)

Then in the execute page, click execute to execute the workload. You may also need to check the config file before the execution, see [here](./config/README.md) for config explaination. ![config](./doc/figures/run.png)

### Run with Command Line (CLI)
#### 1) Preparation
Set these once in your shell rc file (e.g., `~/.bashrc` or `~/.zshrc`) or export them in every new shell:
```bash
# Make local "src" importable
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH+:$PYTHONPATH}"

# Where to cache Hugging Face models (optional, adjust path as needed)
export HF_HOME="/mnt/data/hf_home"
```

#### 2) Running the Benchmark
To run the benchmark, you first need to setup the vectorDB as the retriever. See [vectordb](#vectordb) for a supported list and quick setup guide. Change the db_path to your local vectordb path in config file.
```
vector_db:
    db_path: /mnt/data/vectordb
```
First run the **preprocess/insert** phase to insert the dataset:

```bash
# 1) Build/insert into the vector store (LanceDB example)
python3 src/run_new.py \
  --config config/lance_insert.yaml \
  --msys-config config/monitor/example_config.yaml
```
After the insertion stage, proceed to the **query/evaluate** stage. Run the following:
```bash
# 2) Retreival and Query
python3 src/run_new.py \
  --config config/lance_query.yaml \
  --msys-config config/monitor/example_config.yaml
```
To customize your own workload setting, you may reference the provided config file within `./config` folder. The detailed parameter are listed [here](config/README.md)

#### 3) Output Analysis
You can check the output result within the `./output` folder. To visualize the output results, run `python3 example/monitoring_sys_lib/test_parser.py`, the visualized figures will be located within the `./output`.

## Supported RAG Pipeline Modules

### VectorDB

RASB already intergrates with many popular vectorDBs. To setup, check the detailed documentations at [VectorDB README](src/vectordb/README.md)

Want to add a new DB? Check our RASB API at [VectorDB API](src/vectordb/README.md#adding-a-new-vector-database) to standardize operations. To add a new database

### Monitoring System

Examples of how to use it is documented in `example/monitoring_sys_lib`. Detailed documentations at [MonitoringSystem README](monitoring_sys/README.md)
