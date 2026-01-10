def main():
    import os, sys
    import utils.python_utils as pyutils
    import time

    if not any([p in arg for p in ["--log_dir", "--create_log_dir"] for arg in sys.argv]):
        sys.argv.append(f"--log_dir={os.path.join(pyutils.get_script_dir(__file__), 'output')}")
        sys.argv.append(f"--create_log_dir=True")

    from utils.logger import logging, Logger, log_time_breakdown, save_config_to_log_dir

    from config import load_config, get_db_collection_name
    from utils.python_utils import get_by_path
    import utils.colored_print as cprint

    # put those before any other imports to prevent loading wrong libstdc++.so
    from monitoring_sys.config_parser.msys_config_parser import StaticEnv, MacroTranslator
    from monitoring_sys import MSys
    from monitoring_sys.config_parser.msys_config_parser import MSysConfig

    import torch
    import argparse
    import pickle
    import _pickle as cPickle

    from vectordb.milvus_api import milvus_client
    from vectordb.lancedb_api import lance_client
    from vectordb.qdrant_api import qdrant_client
    from vectordb.chroma_api import chroma_client
    from vectordb.elastic_api import elastic_client

    from datasetLoader.TextDatasetLoader import TextDatasetLoader
    from datasetPreprocess.TextDatasetPreprocess import TextDatasetPreprocess
    from datasetLoader.PDFDatasetLoader import PDFDatasetLoader

    # from datasetPreprocess.PDFDatasetPreprocess import PDFDatasetPreprocess

    from RAGRequest.TextsRAGRequest import WikipediaRequests
    from RAGPipeline.TextsRAGPipline import TextsRAGPipeline
    from RAGPipeline.ImageRAGPipline import ImagesRAGPipeline
    from RAGPipeline.retriever.BaseRetriever import BaseRetriever
    from RAGPipeline.reranker.CrossEncoderReranker import CrossEncoderReranker
    from RAGPipeline.responser.TextsResponser import VLLMResponser
    from RAGPipeline.responser.ImagesResponser import ImageResponser

    from encoder.sentenceTransformerEncoder import SentenceTransformerEncoder
    from encoder.ColPaliEncoder import ColPaliEncoder
    from evaluator.RagasEvaluator import RagasEvaluator
    from evaluator.RagasOpenAI import RagasOpenAI
    from evaluator.Ragasvllm import Ragasvllm

    # avoid warning about TOKENIZERS_PARALLELISM
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    output_path = Logger().log_dirpath
    cprint.iprintf(f"Using output path: {output_path}")

    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, help="Path to the configuration file")
    parser.add_argument(
        "--msys-config", type=str, help="Path to the monitoring system configuration file"
    )
    # parser.add_argument("-d", "--dry_run", action="store_true", help="Run in dry run mode, no actual processing")
    args = parser.parse_known_args()[0]
    if not args.config:
        raise ValueError("Please provide a configuration file using --config")
    config = load_config(args.config)

    if not args.msys_config:
        raise ValueError(
            "Please provide a monitoring system configuration file using --msys-config"
        )
    with open(args.msys_config, "r") as fin:
        translated_config = (
            MacroTranslator(StaticEnv.get_static_env("global")).translate(fin).read()
        )
    with open(os.path.join(output_path, "translated_msys_config.yaml"), "w") as fout:
        fout.write(translated_config)
    monitor = MSys(MSysConfig.from_yaml_string(translated_config))
    monitor.report_status(verbose=False, detail=True)

    # set collection name
    if not config['sys']['vector_db']['collection_name'] == '':
        collection_name = get_db_collection_name(config['sys']['vector_db']['collection_name'])
    else:
        collection_name = get_db_collection_name(f"{config['run_name']}")
    cprint.iprintf(f"*** Start the run with collection {collection_name}")

    # set db
    if config["sys"]["vector_db"]["type"] == "milvus":
        db_client = milvus_client(
            db_path=config["sys"]["vector_db"]["db_path"],
            db_token=config["sys"]["vector_db"]["db_token"],
            collection_name=collection_name,
            drop_previous_collection=config["sys"]["vector_db"]["drop_previous_collection"],
            # dim=config["sys"]["vector_db"]["dim"],
            index_type=config["rag"]["build_index"]["index_type"],
            metric_type=config["rag"]["build_index"]["metric_type"],
        )
    elif config["sys"]["vector_db"]["type"] == "lancedb":
        db_client = lance_client(
            db_path=config["sys"]["vector_db"]["db_path"],
            collection_name=collection_name,
            # dim=config["sys"]["vector_db"]["dim"],
            index_type=config["rag"]["build_index"]["index_type"],
            metric_type=config["rag"]["build_index"]["metric_type"],
            drop_previous_collection=config["sys"]["vector_db"]["drop_previous_collection"],
        )
    elif config["sys"]["vector_db"]["type"] == "qdrant":
        db_client = qdrant_client(
            db_path=config["sys"]["vector_db"]["db_path"],
            collection_name=collection_name,
            # dim=config["sys"]["vector_db"]["dim"],
            index_type=config["rag"]["build_index"]["index_type"],
            metric_type=config["rag"]["build_index"]["metric_type"],
            drop_previous_collection=config["sys"]["vector_db"]["drop_previous_collection"],
        )
    elif config["sys"]["vector_db"]["type"] == "chroma":
        db_client = chroma_client(
            db_path=config["sys"]["vector_db"]["db_path"],
            collection_name=collection_name,
            # dim=config["sys"]["vector_db"]["dim"],
            index_type=config["rag"]["build_index"]["index_type"],
            metric_type=config["rag"]["build_index"]["metric_type"],
            drop_previous_collection=config["sys"]["vector_db"]["drop_previous_collection"],
        )
    elif config["sys"]["vector_db"]["type"] == "elasticsearch":
        db_client = elastic_client(
            db_path=config["sys"]["vector_db"]["db_path"],
            collection_name=collection_name,
            # dim=config["sys"]["vector_db"]["dim"],
            index_type=config["rag"]["build_index"]["index_type"],
            metric_type=config["rag"]["build_index"]["metric_type"],
            drop_previous_collection=config["sys"]["vector_db"]["drop_previous_collection"],
        )
    else:
        raise ValueError(f"Unsupported vector database type: {config['sys']['vector_db']['type']}")

    db_client.setup()
    cprint.iprintf(f"*** Vector DB setup done")

    # prepare workload
    dataset_name = config["bench"]["dataset"]
    save_config_to_log_dir(args.config)
    # for image RAG
    if config["bench"]["type"] == "image":
        pass
        # preprocess dataset
        with monitor:
            if config["rag"]["action"]["preprocess"]:
                log_time_breakdown("start")
                if dataset_name == "common-pile/arxiv_papers":
                    cprint.iprintf(
                        f"*** Start loading dataset: {dataset_name}, time : {time.monotonic_ns()} "
                    )
                    dataset_ratio = config["bench"]["preprocessing"]["dataset_ratio"]
                    loader = PDFDatasetLoader(dataset_name=dataset_name)
                    samples_length = int(loader.total_length * dataset_ratio)
                    loader.download_pdf(load_num=samples_length)
                    df = loader.get_dataset_slice(length=samples_length, offset=0)
                    cprint.iprintf(
                        f"*** Done Loaded dataset: {dataset_name}, total samples: {len(df)}, done"
                    )
                log_time_breakdown("chunking")
                chunker = PDFDatasetPreprocess()
                pages = chunker.chunking_PDF_to_image(df)

            # embedding
            if config["rag"]["action"]["embedding"]:
                cprint.iprintf(f"*** Start embedding images, time : {time.monotonic_ns()}")
                log_time_breakdown("embed")
                embedder = ColPaliEncoder(
                    device="cuda:0",
                    model_name=config["rag"]["embedding"]["sentence_transformers_name"],
                    embedding_batch_size=config["rag"]["embedding"]["batch_size"],
                )
                embedder.load_encoder()
                dict_list = embedder.embedding(pages)
                embedder.free_encoder()
                print(
                    f"***Embedding done, total {len(dict_list)} embeddings, time : {time.monotonic_ns()}"
                )

            if config["rag"]["action"]["insert"]:
                print(
                    f"***Start inserting embeddings into collection: {collection_name}, time : {time.monotonic_ns()}"
                )
                log_time_breakdown("insert")
                if config["sys"]["vector_db"]["type"] == "lancedb":
                    db_client.create_collection(
                        collection_name=collection_name,
                        dim=len(dict_list[0]["vector"]),
                        data_type="image",
                    )

                db_client.insert_data(
                    dict_list=dict_list,
                    collection_name=collection_name,
                    insert_batch_size=config["rag"]["insert"]["batch_size"],
                    create_collection=True,
                )
                print(
                    f"***Insertion done, total {len(dict_list)} embeddings inserted, time : {time.monotonic_ns()}"
                )
                log_time_breakdown("done")
        if config["rag"]["action"]["generation"] == True:
            RAGRequest = WikipediaRequests(
                run_name=config["run_name"],
                collection_name=collection_name,
                req_type="query",
                req_count=config["rag"]["retrieval"]["question_num"],
            )
            print(f"***End request preparation")

            # prepare pipeline
            retriever = BaseRetriever(
                collection_name=collection_name,
                top_k=config["rag"]["retrieval"]["top_k"],
                retrieval_batch_size=config["rag"]["retrieval"]["retrieval_batch_size"],
                client=db_client,
            )
            responser = ImageResponser(
                model=config["rag"]["generation"]["model"],
                device=config["rag"]["generation"]["device"],
            )
            embedder = ColPaliEncoder(
                device="cuda:0",
                model_name=config["rag"]["embedding"]["sentence_transformers_name"],
                embedding_batch_size=config["rag"]["embedding"]["batch_size"],
            )
            RAGPipline = ImagesRAGPipeline(
                retriever=retriever,
                responser=responser,
                embedder=embedder,
            )

            # pipeline.check()
            import utils.colored_print as cprint

            with monitor:
                RAGPipline.process(
                    RAGRequest,
                    batch_size=config["rag"]["pipeline"]["batch_size"],
                )

        return
    elif config["bench"]["type"] == "text":
        # preprocess dataset
        if config["rag"]["action"]["preprocess"]:
            # if True:
            log_time_breakdown("start")
            with monitor:
                # TODO: add length and offset into config
                # download and load dataset
                # if config["rag"]["action"]["preprocess"]:
                if dataset_name == "wikimedia/wikipedia":
                    dataset_ratio = config["bench"]["preprocessing"]["dataset_ratio"]
                    loader = TextDatasetLoader(dataset_name=dataset_name)
                    samples_length = int(loader.total_length * dataset_ratio)
                    df = loader.get_dataset_slice(length=samples_length, offset=0)
                    cprint.iprintf(
                        f"*** Done Loaded dataset: {dataset_name}, total samples: {len(df)}, done"
                    )
                elif dataset_name == "common-pile/arxiv_papers":
                    dataset_ratio = config["bench"]["preprocessing"]["dataset_ratio"]
                    loader = PDFDatasetLoader(dataset_name=dataset_name)
                    samples_length = int(loader.total_length * dataset_ratio)
                    loader.download_pdf(load_num=samples_length)
                    df = loader.get_dataset_slice(length=samples_length, offset=0)
                    cprint.iprintf(
                        f"*** Done Loaded dataset: {dataset_name}, total samples: {len(df)}, done"
                    )
                # chunking datasets
                if dataset_name == "wikimedia/wikipedia":
                    chunker = TextDatasetPreprocess(
                        chunk_size=config["bench"]["preprocessing"]["chunk_size"],
                        chunk_overlap=config["bench"]["preprocessing"]["chunk_overlap"],
                    )
                    log_time_breakdown("chunking")
                    chunked_texts = chunker.chunking_text_to_text(df)
                    cprint.iprintf(f"*** Chunking done, total {len(chunked_texts)} chunks")
                elif dataset_name == "common-pile/arxiv_papers":
                    chunker = PDFDatasetPreprocess()
                    log_time_breakdown("convert")  # todo separate chunking and converting
                    docs = chunker.convert_PDF_to_text(df)
                    log_time_breakdown("chunking")
                    chunked_texts = chunker.chunking_PDF_to_text(docs)
                    cprint.iprintf(f"*** Chunking done, total {len(chunked_texts)} chunks")

                embeddings_dim = None
                # embedding
                if config["rag"]["action"]["embedding"]:
                    cprint.iprintf(f"*** Start embedding texts")
                    log_time_breakdown("embed")
                    embedder = SentenceTransformerEncoder(
                        device="cuda:0",
                        sentence_transformers_name=config["rag"]["embedding"][
                            "sentence_transformers_name"
                        ],
                        embedding_batch_size=config["rag"]["embedding"]["batch_size"],
                    )
                    embedder.load_encoder()
                    embeddings_dim = embedder.dim
                    embeddings = embedder.embedding(chunked_texts)
                    embedder.free_encoder()
                    print(f"***Embedding done, total {len(embeddings)} embeddings")
                    if config["rag"]["embedding"]["store"] == True:
                        store_path = config["rag"]["embedding"]["filepath"]
                        # Store data
                        os.makedirs(os.path.dirname(store_path), exist_ok=True)
                        with open(store_path, 'wb') as handle:
                            pickle.dump(embeddings, handle, protocol=pickle.HIGHEST_PROTOCOL)

                if config["rag"]["embedding"]["load"] == True:
                    log_time_breakdown("load")
                    load_path = config["rag"]["embedding"]["filepath"]
                    with open(load_path, 'rb') as handle:
                        embeddings = cPickle.load(handle)
                    print(f"***Embedding loaded, total {len(embeddings)} embeddings")
                    # print(f"***Embedding example0: {embeddings[0]['vector']}")
                    # print(f"***Embedding example0: {embeddings[0]}")
                    # print(f"***Embedding dim: {len(embeddings[0]['vector'])}")
                    embeddings_dim = len(embeddings[0])
                    # chunked_texts = [emb['text'] for emb in embeddings]
                    # embeddings = [emb['vector'] for emb in embeddings]
                    # if len(embeddings) >= 7209543:
                    #     embeddings = embeddings[:7209543]
                    #     chunked_texts = chunked_texts[:7209543]

                # insertion
                if config["rag"]["action"]["insert"]:
                    log_time_breakdown("insert")
                    print(f"***Start inserting embeddings into collection: {collection_name}")
                    if config["sys"]["vector_db"]["type"] == "lancedb":
                        db_client.create_collection(
                            collection_name=collection_name, dim=embeddings_dim
                        )
                    db_client.insert_data_vector(
                        vector=embeddings,
                        chunks=chunked_texts,
                        collection_name=collection_name,
                        insert_batch_size=config["rag"]["insert"]["batch_size"],
                        create_collection=True,
                    )
                    print(f"***Insertion done, total {len(embeddings)} embeddings inserted")

                # build index
                if config['rag']['action']['build_index']:
                    log_time_breakdown("build")
                    db_client.build_index(
                        collection_name=collection_name,
                        index_type=config["rag"]["build_index"]["index_type"],
                        metric_type=config["rag"]["build_index"]["metric_type"],
                        # device=None,
                        # device=device
                    )
                    print(f"***Indexing done for collection: {collection_name}")
                log_time_breakdown("done")
        # query + retrieval + reranking + generation + evaluation
        if config["rag"]["action"]["generation"] == True:
            RAGRequest = WikipediaRequests(
                run_name=config["run_name"],
                collection_name=collection_name,
                req_type="query",
                req_count=config["rag"]["retrieval"]["question_num"],
            )
            print(f"***End request preparation")

            # prepare pipeline
            retriever = BaseRetriever(
                collection_name=collection_name,
                top_k=config["rag"]["retrieval"]["top_k"],
                retrieval_batch_size=config["rag"]["retrieval"]["retrieval_batch_size"],
                client=db_client,
            )
            if config['rag']['action']['reranking']:
                reranker = CrossEncoderReranker(
                    model_name=config["rag"]["reranking"]["rerank_model"],
                    top_n=config["rag"]["reranking"]["top_n"],
                    device=config["rag"]["reranking"]["device"],
                )
            else:
                reranker = None
            if config["rag"]["action"]["evaluate"]:
                evaluator = Ragasvllm(
                    llm_path=config["rag"]["evaluate"]["evaluator_model"],
                )
            else:
                evaluator = None
            responser = VLLMResponser(
                model=config["rag"]["generation"]["model"],
                device=config["rag"]["generation"]["device"],
                parallelism=config["rag"]["generation"]["parallelism"],
            )
            embedder = SentenceTransformerEncoder(
                device=config["rag"]["embedding"]["device"],
                sentence_transformers_name=config["rag"]["embedding"]["sentence_transformers_name"],
            )
            RAGPipline = TextsRAGPipeline(
                retriever=retriever,
                responser=responser,
                embedder=embedder,
                reranker=reranker,
                evaluator=evaluator,
            )

            # pipeline.check()
            import utils.colored_print as cprint

            with monitor:
                RAGPipline.process(
                    RAGRequest,
                    batch_size=config["rag"]["pipeline"]["batch_size"],
                )


if __name__ == "__main__":
    main()
