
# Vector Database Module

This module provides a unified interface for interacting with various locally deployable Vector Databases. RAGPerf abstracts the low-level client management, allowing you to switch between different backends (e.g., changing from LanceDB to Milvus) by simply modifying a configuration file.

## 📦 Supported Databases

We currently support the following vector databases and index types:

| Database          | Supported Index Types     | Device Support | Notes                                            |
| :---------------- | :------------------------ | :------------- | :----------------------------------------------- |
| **LanceDB**       | IVF-PQ, IVF-Flat, HNSW    | CPU/GPU        | Embedded, serverless, highly memory efficient.   |
| **Milvus**        | HNSW, IVF, DiskANN, ScaNN | CPU/GPU        | Requires a running server instance (Docker/K8s). |
| **Qdrant**        | HNSW                      | CPU/GPU        | Requires a running server instance.              |
| **Chroma**        | HNSW                      | CPU            | Embedded or Client/Server.                       |
| **Elasticsearch** | HNSW, Flat                | CPU            | Requires a running server instance.              |

---

## 🛠️ Setup Instructions by Type

Before running the benchmark, ensure you have installed the necessary Python dependencies. If you followed the main installation guide, these should already be in your environment.

### 1. LanceDB (Recommended for Local Testing)

LanceDB does not require a separate server installation. To install lanceDB, run `pip install lancedb`.

Change the configuration (`config/your_config.yaml`):
```yaml
vector_db:
  type: "lancedb"
  db_path: "/mnt/data/my_lancedb"  # Path to store the database files
  collection_name: "wiki_vectors"
```

### 2. Milvus (GPU via Docker Compose)

If you plan to use **Milvus** as the vector store, follow the official guide to run Milvus with GPU support using Docker Compose:
➡️ **[Run Milvus with GPU Support Using Docker Compose](https://milvus.io/docs/install_standalone-docker-compose-gpu.md)**

After Milvus is up, point your pipeline config to its url:

```yaml
vector_db:
  collection_name: 'milvus_test'
  db_path: http://localhost:19530
  db_token: root:Milvus
  drop_previous_collection: false
  type: milvus
```

### 3. Qdrant (Docker)
To use Qdrant, run the official Docker container. This exposes the database on port 6333.

```bash
docker run -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage:z \
    qdrant/qdrant
```
Change the configuration to use Qdrant:
```yaml
vector_db:
  type: "qdrant"
  db_path: "http://localhost:6333" # Qdrant server URL
  collection_name: "test_collection"
  # Qdrant doesn't typically need a token for local docker, but if configured:
  # db_token: "your-api-key"
```

### 4. Chroma (Embedded or Client/Server)
Chroma is often used in an embedded mode (similar to LanceDB) but can also run as a server. To quickly set up the chroma, run `pip install chroma_db`.

Change the configuration to use Chroma:
```yaml
vector_db:
  type: "chroma"
  db_path: "./chroma_data" # Local path for db data storage
  collection_name: "chroma_test"
```

###  5. Elasticsearch (Docker with kNN)
Elasticsearch supports dense vector search natively. Ensure you have the necessary memory allocated to Docker. Run Elasticsearch with docker:
```bash
docker run -p 9200:9200 -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -m 4GB docker.elastic.co/elasticsearch/elasticsearch:8.11.1
```
Change the configuration to include the elasticsearch url:
```yaml
vector_db:
  type: "elasticsearch"
  db_path: "http://localhost:9200"
  collection_name: "elastic_test"
  drop_previous_collection: true # Elastic indices often need fresh creation for mapping changes
```


## Adding a New Vector Database
This pipeline uses an abstract base class, DBInstance (defined in [DBInstance.py](./DBInstance.py)), to enforce a consistent API across all vector stores. To add support for a new database (e.g., Weaviate, Pinecone), follow these steps:

1. Create a New Class: Create a new file (e.g., MyNewDB.py) in vectordb.
2. Inherit form DBInstance: Implement all abstract methods defined in the base class.

```python
from .DBInstance import DBInstance

class MyNewDB(DBInstance):
    def setup(self):
        # Initialize client connection
        pass

    def create_collection(self, collection_name):
        # creating a collection
        pass

    def has_collection(self, collection_name):
        # Check existence
        pass

    def drop_collection(self, collection_name):
        # Clean up
        pass

    def insert_data(self, vectors, chunks, collection_name=None):
        # Batch insertion logic
        pass

    def query_search(self, query_vector, collection_name=None):
        # Search logic returning top_k results
        pass
```

3. Register the Class: Add your new class to the in `run_new.py` so it can be instantiated via the config type string.
