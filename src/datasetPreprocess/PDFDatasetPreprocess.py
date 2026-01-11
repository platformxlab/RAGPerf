from datasetPreprocess.BaseDatasetPreprocess import BaseDatasetPreprocess
import torch
from docling_core.transforms.chunker import HierarchicalChunker
from docling.document_converter import DocumentConverter, PdfFormatOption
from tqdm import tqdm
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
)
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
import os
from pdf2image import convert_from_path


class PDFDatasetPreprocess(BaseDatasetPreprocess):
    def __init__(self):
        super().__init__()

    def convert_PDF_to_text(self, df):
        # using docling as document converting and chunking
        # Check if GPU or MPS is available

        accelerator_options = AcceleratorOptions(
            num_threads=8,
            device=AcceleratorDevice.CUDA if torch.cuda.is_available() else AcceleratorDevice.CPU,
        )
        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options = accelerator_options
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.do_cell_matching = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )
        docs = []
        for path in tqdm(df["content"], desc="convert pdf data"):
            # Convert the input file to Docling Document
            doc = converter.convert(path).document
            docs.append(doc)
        return docs

    def chunking_PDF_to_text(self, docs):
        # converter = DocumentConverter()
        chunker = HierarchicalChunker()
        chunked_texts = []
        for doc in tqdm(docs, desc="chunking pdf data"):
            # Perform hierarchical chunking
            texts = [chunk.text for chunk in chunker.chunk(doc)]
            chunked_texts.extend(texts)

        total_chunks_num = len(chunked_texts)
        print(f"Total chunks to process: {total_chunks_num}.")
        return chunked_texts

    def batch_chunking_PDF_to_text(self, df, batch_size=8):
        # Check if GPU or MPS is available
        accelerator_options = AcceleratorOptions(
            num_threads=8,
            device=AcceleratorDevice.CUDA if torch.cuda.is_available() else AcceleratorDevice.CPU,
        )
        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options = accelerator_options
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options.do_cell_matching = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )
        # converter = DocumentConverter()
        chunker = HierarchicalChunker()
        chunked_texts = []
        input_doc_paths = []
        for path in df["content"]:
            input_doc_paths.append(path)

        # Convert the input file to Docling Document
        docs = converter.convert_all(input_doc_paths)
        # Perform hierarchical chunking
        for doc in tqdm(docs, desc="chunking pdf data"):
            texts = [chunk.text for chunk in chunker.chunk(doc.document)]
            chunked_texts.extend(texts)

        total_chunks_num = len(chunked_texts)
        print(f"Total chunks to process: {total_chunks_num}.")
        return chunked_texts

    def chunking_PDF_to_image(self, df):
        saved_pages = []
        for path in tqdm(df["content"], desc=f"convert pdf to image"):
            if path.lower().endswith(".pdf"):
                images = convert_from_path(path)
                pdf_base = os.path.splitext(os.path.basename(path))[0]
                pdf_dir = os.path.dirname(path)
                pages_dir = os.path.join(pdf_dir, "pages")
                if not os.path.exists(pages_dir):
                    os.makedirs(pages_dir)
                for i, image in enumerate(images):
                    out_path = os.path.join(pages_dir, f"{pdf_base}_page_{i+1}.png")
                    image.save(out_path, "PNG")
                    saved_pages.append(out_path)
                    # print(f"Saved {out_path}")

        return saved_pages

    def chunking_text_to_text(self):
        return
