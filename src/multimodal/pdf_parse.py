from pypdf import PdfReader
from structured_parser import general_parser
from tqdm import tqdm
import os
import sys
import time
import copy
import numpy as np


PDF_PARSER_CONFIG_DEFAULT = {
    "text_chunk_size": 512,
    "chunk_overlap": 0.1,
    "figure_extraction": True,
    "figure_caption": False,
    "table_extraction": False,
    "table_caption": False,
}


class rag_pdf_parser(general_parser):
    def __init__(self):
        self.type = "PDF"
        self.config = PDF_PARSER_CONFIG_DEFAULT.copy()
        self.fig_store = None
        self.text_chunks = []

    def __init__(self, pdf_dir_path, config=None):
        self.pdf_dir_path = pdf_dir_path
        self.config = config if config else PDF_PARSER_CONFIG_DEFAULT.copy()
        self.fig_store = None
        self.text_chunks = []

    def print_config(self):
        print(f"PDF Parser Config: {self.config}")

    def set_config(self, entry, value):
        if entry in self.config:
            self.config[entry] = value
            print(f"Config entry {entry} set to {value}.")
        else:
            print(
                f"Invalid config entry: {entry}. Available entries are: {list(self.config.keys())}"
            )
            return

    def set_fig_store(self, path):
        # check if path is dir or create a new dir
        if os.exists(path):
            if os.path.isdir(path):
                self.fig_store = path
            else:
                print(f"Path {path} is not a directory.")
        else:
            os.makedirs(path)
            self.fig_store = path
        print(f"Figure store set to: {self.fig_store}")

    def _parse_pdf(self, pdf_path):
        reader = PdfReader(pdf_path)
        for page_number, page in tqdm(
            enumerate(reader.pages), desc="Processing pages in {pdf_path}"
        ):
            # Extract text chunks
            text = page.extract_text()
            if text:
                # Split text into chunks
                # text_chunks = self._split_text_into_chunks(text)
                # self.text_chunks.extend(text_chunks)
                print(f"Page {page_number + 1} Text:\n{text}\n")

            # Extract figures (images) if needed
            if self.config["figure_extraction"]:
                for image_index, image in enumerate(page.images):
                    # image_data = image.get_data()
                    image_path = os.path.join(
                        "./", f"figure_page{page_number + 1}_{image_index}.jpg"
                    )
                    with open(image_path, "wb") as img_file:
                        img_file.write(image)
                    print(f"Saved figure from page {page_number + 1} to {image_path}")

    def parse(self, pdf_name=None):
        if pdf_name is None:
            # parse all pdfs in directory
            for pdf_file in os.listdir(self.pdf_dir_path):
                if pdf_file.endswith(".pdf"):
                    pdf_path = os.path.join(self.pdf_dir_path, pdf_file)
                    self._parse_pdf(pdf_path)

    def get_text_chunks(self):
        return self.text_chunks

    def get_figures(self):
        return self.figures


if __name__ == "__main__":
    testpdf_path = "/home/shaobol2/Documents/flatflash.pdf"

    reader = PdfReader(testpdf_path)
    for page_number, page in tqdm(enumerate(reader.pages), desc="Processing pages"):
        # Extract text chunks
        text = page.extract_text()
        if text:
            print(f"Page {page_number + 1} Text:\n{text}\n")
        for image_index, image in enumerate(page.images):
            # image_data = image.get_data()
            image_path = os.path.join("./", f"figure_page{page_number + 1}_{image_index}.jpg")
            with open(image_path, "wb") as img_file:
                img_file.write(image)
            print(f"Saved figure from page {page_number + 1} to {image_path}")
        # Extract figures (images) if needed
        # This part is left as a placeholder for future implementation
