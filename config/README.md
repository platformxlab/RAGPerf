# RAGPerf Configuration Guide

This document details the configuration parameters used in the RAGPerf. The configuration file is in YAML format and controls data processing, model selection, hardware allocation, and pipeline execution flow.

## 1. Top-Level Metadata

| Parameter      | Description                                                                                                                     |
| :------------- | :------------------------------------------------------------------------------------------------------------------------------ |
| **`run_name`** | A unique identifier for the current experiment (e.g., `default_run`). This is used for naming log files and output directories. |

---

## 2. Benchmark Data Settings (`bench`)

This section defines the dataset source and how text or images are preprocessed before ingestion.

```yaml
bench:
  dataset: wikimedia/wikipedia  # HuggingFace dataset path or local identifier
  type: text                    # Data modality ('text', 'image')
  preprocessing:
    chunk_size: 512             # Max tokens/chars per chunk
    chunk_overlap: 0            # Overlap between chunks
    chunktype: length           # Strategy (e.g., 'length')
    dataset_ratio: 0.001        # Percentage of dataset to use (0.001 = 0.1%)
```

---

## 3. RAG Pipeline Configuration (`rag`)

These settings control which stages of the pipeline run and the specific parameters for each component.

### 3.1 Pipeline Actions (`action`)
Boolean flags to enable or disable specific pipeline stages. This allows running only insertion, only retrieval, or a full end-to-end test.

```yaml
rag:
  action:
    preprocess: true    # Enable data chunking/loading
    embedding: true     # Enable vector embedding generation
    insert: true        # Enable insertion into VectorDB
    build_index: true   # Enable index creation (IVF, HNSW, etc.)
    retrieval: false    # Enable vector search
    reranking: false    # Enable cross-encoder reranking
    generation: false   # Enable LLM response generation
    evaluate: false     # Enable RAGAS evaluation
```

### 3.2 Embedding (`embedding`)
Configuration for the model that converts text/images into vectors.

| Parameter                    | Description                                                          |
| :--------------------------- | :------------------------------------------------------------------- |
| `device`                     | GPU device identifier (e.g., `cuda:0`).                              |
| `sentence_transformers_name` | Name of the model (e.g., `all-MiniLM-L6-v2`, `vidore/colpali-v1.2`). |
| `batch_size`                 | Number of items processed per batch during embedding.                |
| `embedding_framework`        | Backend framework (e.g., `sentence_transformers`).                   |

### 3.3 Vector Database Operations (`insert`, `build_index`)
Parameters for writing data and creating efficient search structures.

```yaml
rag:
  insert:
    batch_size: 512              # Number of vectors inserted per transaction
    collection_name: ''          # Optional override for collection name
    drop_previous_collection: false
  build_index:
    index_type: IVF_HNSW_SQ     # Type of index (IVF_PQ, HNSW, FLAT, etc.)
    metric_type: L2             # Distance metric (L2, IP, COSINE)
```

### 3.4 Retrieval & Reranking (`retrieval`, `reranking`)
Controls the search phase.

```yaml
rag:
  retrieval:
    question_num: 16         # Number of queries to run
    retrieval_batch_size: 4  # Batch size for querying VectorDB
    top_k: 10                # Number of results to fetch per query
  reranking:
    device: cuda:0
    rerank_model: Qwen/Qwen2.5-7B-Instruct # Model used for reranking
    top_n: 5                 # Number of results to keep after reranking
```

### 3.5 Generation (`generation`)
Settings for the Large Language Model (LLM) that generates the final answer.

| Parameter | Description                                                 |
| :-------- | :---------------------------------------------------------- |
| `device`  | GPU device identifier.                                      |
| `model`   | Path or name of the LLM (e.g., `Qwen/Qwen2.5-7B-Instruct`). |

### 3.6 Evaluation (`evaluate`)
Settings for automated quality assessment (e.g., using RAGAS).

| Parameter         | Description                                            |
| :---------------- | :----------------------------------------------------- |
| `evaluator_model` | Model used as the judge for metrics like faithfulness. |

---

## 4. System Configuration (`sys`)

Configures backend infrastructure, hardware allocation, and logging.

### 4.1 Vector Database (`vector_db`)
Connection details for the vector store backend.

```yaml
sys:
  vector_db:
    type: lancedb               # Backend type: 'lancedb', 'milvus', 'qdrant', 'elastic'
    db_path: /path/to/db        # File path (LanceDB) or URL (Milvus/Qdrant)
    collection_name: 'test_col' # Name of the collection/table
    drop_previous_collection: false
```

### 4.2 Devices (`devices`)

| Parameter   | Description                                              |
| :---------- | :------------------------------------------------------- |
| `cpu`       | CPU identifier.                                          |
| `gpu_count` | Number of GPUs available to the system.                  |
| `gpus`      | List of specific GPU IDs (e.g., `["cuda:0", "cuda:1"]`). |

### 4.3 Logging (`log`)

| Parameter     | Description                           |
| :------------ | :------------------------------------ |
| `metrics_log` | Path for the main execution log file. |