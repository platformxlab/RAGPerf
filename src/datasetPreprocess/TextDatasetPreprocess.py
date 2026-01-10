from datasetPreprocess.BaseDatasetPreprocess import BaseDatasetPreprocess
from langchain.text_splitter import RecursiveCharacterTextSplitter


class TextDatasetPreprocess(BaseDatasetPreprocess):
    def __init__(self, chunk_size=512, chunk_overlap=0.1):
        super().__init__()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    # TODO add more chunking stratgy
    def chunking_text_to_text(self, df):
        chunked_texts = []
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
        )
        for text in df["content"]:
            chunks = text_splitter.split_text(text)
            chunked_texts.extend(chunks)
        total_chunks_num = len(chunked_texts)
        print(f"Total chunks to process: {total_chunks_num}.")
        return chunked_texts

    def chunking_PDF_to_image(self):
        return

    def chunking_PDF_to_text(self):
        return
