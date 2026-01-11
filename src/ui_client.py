import streamlit as st
import yaml
import subprocess
import os
import sys
import copy
import requests
import time

# --- Page Config ---
st.set_page_config(
    page_title="RAG Panel", page_icon="🎛️", layout="wide", initial_sidebar_state="expanded"
)

# --- 1. The Master Template (Hardcoded Defaults) ---
# This matches the structure of your uploaded qdrant_query.yaml
DEFAULT_TEMPLATE = {
    "run_name": "default_run",
    "bench": {
        "dataset": "wikimedia/wikipedia",
        "type": "text",
        "preprocessing": {
            "chunk_overlap": 0,
            "chunk_size": 512,
            "chunktype": "length",
            "dataset_ratio": 0.001,
        },
    },
    "sys": {
        "devices": {"cpu": "cpu", "gpu_count": 2, "gpus": ["cuda:0", "cuda:1"]},
        "log": {"metrics_log": "./log/default_run.log"},
        "vector_db": {
            "type": "lancedb",
            "collection_name": "lance_text_full_2",
            "db_path": "/mnt/data1/shaobol2/lancedb",
            "db_token": "",
            "drop_previous_collection": False,
        },
    },
    "rag": {
        "action": {
            "preprocess": False,
            "embedding": False,
            "insert": False,
            "build_index": False,
            "reranking": True,
            "retrieval": True,
            "generation": True,
            "evaluate": False,
        },
        "build_index": {"index_type": "IVF_HNSW_SQ", "metric_type": "L2"},
        "embedding": {
            "device": "cuda:0",
            "sentence_transformers_name": "all-MiniLM-L6-v2",
            "batch_size": 1024,
            "embedding_framework": "sentence_transformers",
            "model": "nomic-ai/nomic-embed-text-v2-moe",
            "store": False,
            "load": True,
            "filepath": "/home/shaobol2/RAGPipeline/wiki_entire.pickle",
        },
        "insert": {"batch_size": 2048, "collection_name": "", "drop_previous_collection": False},
        "generation": {"device": "cuda:0", "model": "Qwen/Qwen2.5-7B-Instruct", "parallelism": 1},
        "reranking": {
            "device": "cuda:0",
            "rerank_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "top_n": 5,
        },
        "evaluate": {"evaluator_model": "Qwen/Qwen2-7B-Instruct-GPTQ-Int8"},
        "retrieval": {"question_num": 192, "retrieval_batch_size": 64, "top_k": 10},
        "pipeline": {"batch_size": 64},
    },
}

# Dummy MSYS config required by the script
DEFAULT_MSYS = "../config/monitor/example_config.yaml"

# """
# global:
#   log_level: INFO
# monitor:
#   target: system
# """

TEMP_CONFIG_PATH = "temp_ui_config.yaml"
TEMP_MSYS_PATH = "temp_msys_config.yaml"

# --- 2. Session State Initialization ---
if "config" not in st.session_state:
    st.session_state["config"] = copy.deepcopy(DEFAULT_TEMPLATE)

config = st.session_state["config"]

# --- 3. UI Layout ---

st.title("🎛️ RAG Panel")

# Use Tabs to organize the massive amount of settings
tab_main, tab_rag, tab_models, tab_sys, tab_exec = st.tabs(
    ["📂 General & Data", "⚡ RAG Actions", "🧠 Models & Params", "🖥️ System & DB", "🚀 Execution"]
)

# Settings
with tab_main:
    st.subheader("Run Settings")
    config['run_name'] = st.text_input("Run Name", config['run_name'])

    st.subheader("Benchmark Data")
    col1, col2 = st.columns(2)
    with col1:
        config['bench']['dataset'] = st.text_input("Dataset Name", config['bench']['dataset'])
        config['bench']['type'] = st.selectbox(
            "Data Type", ["text", "image"], index=0 if config['bench']['type'] == "text" else 1
        )

        st.write("Dataset Ratio")

        # 1. Define distinct keys for the widgets
        key_slider = "ratio_slider"
        key_input = "ratio_input"

        # 2. Initialize both keys in session state if missing
        if key_slider not in st.session_state:
            initial_val = float(config['bench']['preprocessing']['dataset_ratio'])
            st.session_state[key_slider] = initial_val
            st.session_state[key_input] = initial_val

        def on_slider_change():
            st.session_state[key_input] = st.session_state[key_slider]
            config['bench']['preprocessing']['dataset_ratio'] = st.session_state[key_slider]

        def on_input_change():
            # When input changes, force slider to match (clamped 0-1)
            val = max(0.0, min(1.0, st.session_state[key_input]))
            st.session_state[key_slider] = val
            config['bench']['preprocessing']['dataset_ratio'] = val

        # 4. Widgets
        rc1, rc2 = st.columns([3, 1])
        with rc1:
            st.slider(
                "Ratio Slider",
                min_value=0.0,
                max_value=1.0,
                step=0.001,
                key=key_slider,
                on_change=on_slider_change,
                label_visibility="collapsed",
            )
        with rc2:
            st.number_input(
                "Ratio Input",
                min_value=0.0,
                max_value=1.0,
                step=0.001,
                format="%.4f",
                key=key_input,
                on_change=on_input_change,
                label_visibility="collapsed",
            )

    with col2:
        config['bench']['preprocessing']['chunk_size'] = st.number_input(
            "Chunk Size", value=config['bench']['preprocessing']['chunk_size']
        )
        config['bench']['preprocessing']['chunk_overlap'] = st.number_input(
            "Chunk Overlap", value=config['bench']['preprocessing']['chunk_overlap']
        )
        config['bench']['preprocessing']['chunktype'] = st.text_input(
            "Chunk Type", config['bench']['preprocessing']['chunktype']
        )


#  RAG Actions
with tab_rag:
    st.subheader("Pipeline Stages")
    st.info("Toggle the stages you want to execute in this run.")

    actions = config['rag']['action']

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        actions['preprocess'] = st.toggle("1. Preprocess", value=actions['preprocess'])
        actions['embedding'] = st.toggle("2. Embedding", value=actions['embedding'])
    with c2:
        actions['insert'] = st.toggle("3. Insert to DB", value=actions['insert'])
        actions['build_index'] = st.toggle("4. Build Index", value=actions['build_index'])
    with c3:
        actions['retrieval'] = st.toggle("5. Retrieval", value=actions['retrieval'])
        actions['reranking'] = st.toggle("6. Reranking", value=actions['reranking'])
    with c4:
        actions['generation'] = st.toggle("7. Generation", value=actions['generation'])
        actions['evaluate'] = st.toggle("8. Evaluate", value=actions['evaluate'])

# --- TAB 3: Models & Parameters ---
with tab_models:
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### 🧬 Embedding")
        emb = config['rag']['embedding']
        emb['sentence_transformers_name'] = st.text_input(
            "Sentence Transformer", emb['sentence_transformers_name']
        )
        emb['model'] = st.text_input("Embedding Model", emb['model'])
        emb['batch_size'] = st.number_input("Embed Batch Size", value=emb['batch_size'])
        emb['device'] = st.text_input("Embed Device", emb['device'])

        st.caption("Storage")
        emb['load'] = st.checkbox("Load Embeddings from File", value=emb['load'])
        emb['store'] = st.checkbox("Store Embeddings to File", value=emb['store'])
        emb['filepath'] = st.text_input("Pickle Filepath", emb['filepath'])

        st.markdown("### 🔎 Retrieval")
        ret = config['rag']['retrieval']
        ret['top_k'] = st.number_input("Top K", value=ret['top_k'])
        ret['question_num'] = st.number_input("Question Count", value=ret['question_num'])
        ret['retrieval_batch_size'] = st.number_input(
            "Retrieval Batch Size", value=ret['retrieval_batch_size']
        )

    with col_b:
        st.markdown("### 🤖 Generation (LLM)")
        gen = config['rag']['generation']
        # gen['model'] = st.text_input("LLM Model ID", gen['model'])
        gen['model'] = st.selectbox(
            "LLM Model",
            [
                "Qwen/Qwen2.5-7B-Instruct",
                "mistralai/mixtral-8x7b-instruct-v0.1",
                "openai/gpt-oss-20b",
                "Qwen/Qwen2.5-72B-Instruct",
            ],
            index=(
                [
                    "Qwen/Qwen2.5-7B-Instruct",
                    "mistralai/mixtral-8x7b-instruct-v0.1",
                    "openai/gpt-oss-20b",
                    "Qwen/Qwen2.5-72B-Instruct",
                ].index(gen['model'])
                if gen['model']
                in [
                    "Qwen/Qwen2.5-7B-Instruct",
                    "mistralai/mixtral-8x7b-instruct-v0.1",
                    "openai/gpt-oss-20b",
                    "Qwen/Qwen2.5-72B-Instruct",
                ]
                else 0
            ),
        )
        gen['device'] = st.text_input("LLM Device", gen['device'])
        gen['parallelism'] = st.number_input("Parallelism", value=gen['parallelism'])

        st.markdown("### ⚖️ Reranking")
        rer = config['rag']['reranking']
        rer['rerank_model'] = st.text_input("Reranker Model", rer['rerank_model'])
        rer['top_n'] = st.number_input("Top N Rerank", value=rer['top_n'])

        st.markdown("### 📈 Evaluation")
        config['rag']['evaluate']['evaluator_model'] = st.text_input(
            "Evaluator Model", config['rag']['evaluate']['evaluator_model']
        )

# --- TAB 4: System & DB ---
with tab_sys:
    col_x, col_y = st.columns(2)

    with col_x:
        st.subheader("Vector Database")
        vdb = config['sys']['vector_db']
        vdb['type'] = st.selectbox(
            "DB Type",
            ["qdrant", "milvus", "lancedb", "chroma", "elasticsearch"],
            index=(
                ["qdrant", "milvus", "lancedb", "chroma", "elasticsearch"].index(vdb['type'])
                if vdb['type'] in ["qdrant", "milvus", "lancedb", "chroma", "elasticsearch"]
                else 0
            ),
        )
        vdb['db_path'] = st.text_input("DB Path/URL", vdb['db_path'])
        vdb['collection_name'] = st.text_input("Collection Name", vdb['collection_name'])
        vdb['drop_previous_collection'] = st.checkbox(
            "Drop Previous Collection", vdb['drop_previous_collection']
        )

        st.caption("Index Settings")
        idx = config['rag']['build_index']
        idx['index_type'] = st.text_input("Index Type", idx['index_type'])
        idx['metric_type'] = st.text_input("Metric Type", idx['metric_type'])

    with col_y:
        st.subheader("System Resources")
        dev = config['sys']['devices']
        dev['gpu_count'] = st.number_input("GPU Count", value=dev['gpu_count'])
        current_gpus = ",".join(dev['gpus'])
        new_gpus = st.text_input("GPUs (comma separated)", current_gpus)
        dev['gpus'] = [x.strip() for x in new_gpus.split(",") if x.strip()]
        config['sys']['log']['metrics_log'] = st.text_input(
            "Log File Path", config['sys']['log']['metrics_log']
        )

# Execution
with tab_exec:
    st.subheader("🚀 Ready to Launch")

    # Save Config Helper
    def save_current_config():
        with open(TEMP_CONFIG_PATH, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        with open(TEMP_MSYS_PATH, "w") as f:
            f.write(DEFAULT_MSYS)

    col_run, col_preview = st.columns([1, 2])

    with col_run:
        if st.button("▶ START BENCHMARK", type="primary", use_container_width=True):
            save_current_config()

            # Locate script
            script_name = "run_new.py"
            if os.path.exists(script_name):
                script_path = script_name
            elif os.path.exists(os.path.join("..", script_name)):
                script_path = os.path.join("..", script_name)
            else:
                st.error(f"Cannot find {script_name}")
                st.stop()

            cmd = [
                sys.executable,
                "-u",
                script_path,
                "--config",
                TEMP_CONFIG_PATH,
                "--msys-config",
                DEFAULT_MSYS,
            ]

            st.divider()
            st.write("### 📜 Live Terminal Output")
            log_placeholder = st.empty()
            full_logs = ""

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        full_logs += line
                        # Truncate to avoid UI freezing if logs are huge
                        display_logs = (
                            full_logs
                            if len(full_logs) < 10000
                            else "...[older logs truncated]...\n" + full_logs[-10000:]
                        )
                        log_placeholder.code(display_logs, language="bash")

                if process.returncode == 0:
                    st.success("✅ Process Finished Successfully")
                else:
                    st.error(f"❌ Process Failed (Code {process.returncode})")
            except Exception as e:
                st.error(f"Execution Error: {e}")

    with col_preview:
        with st.expander("📄 Review Generated YAML Config", expanded=False):
            st.code(yaml.dump(config, default_flow_style=False), language="yaml")
