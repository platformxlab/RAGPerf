from datasetLoader.BaseDatasetLoader import BaseDatasetLoader
import pandas as pd
import datasets
import os
import requests
from tqdm import tqdm


# TODO add a delete method
class PDFDatasetLoader(BaseDatasetLoader):
    def __init__(
        self,
        dataset_name="common-pile/arxiv_papers",
        output_dir="/mnt/data1/yuanxu4/local_dataset/arxiv",
    ):
        super().__init__(dataset_name=dataset_name)
        if self.dataset_name == "common-pile/arxiv_papers":
            try:
                ds = datasets.load_dataset(self.dataset_name)
            except ConnectionError as e:
                if datasets.config.HF_DATASETS_OFFLINE is True:
                    print(
                        "***Dataset autodownload disabled and no dataset is found under "
                        f"HF_CACHE_HOME: <{datasets.config.HF_CACHE_HOME}>"
                    )
                raise e
            self.dataset = ds["train"]
        else:
            raise ValueError(f"{self.dataset_name} Dataset not support.")
        self.total_length = len(ds["train"])
        self.output_dir = output_dir

    def download_pdf(self, load_num):
        if self.dataset_name == "common-pile/arxiv_papers":
            if load_num >= self.total_length:
                load_num = self.total_length
            table = self.dataset
            # Directory to store PDFs
            if not self.output_dir:
                self.output_dir = os.path.join("local_dataset", "arxiv")
            os.makedirs(self.output_dir, exist_ok=True)

            # check dir already have the datasets
            if len(os.listdir(self.output_dir)) >= load_num:
                print("dataset already exists")
                return
            pbar = tqdm(total=load_num, desc="Downloading papers")
            for i, example in enumerate(table):
                url = example["metadata"]["url"]
                if "arxiv.org/abs/" in url:
                    url = url.replace("arxiv.org/abs/", "arxiv.org/pdf/")
                paper_id = example["id"]
                filename = f"{paper_id}.pdf"
                local_path = os.path.join(self.output_dir, filename)

                if not os.path.exists(local_path):
                    try:
                        response = requests.get(url, timeout=10)
                        if response.status_code == 200:
                            with open(local_path, "wb") as f:
                                f.write(response.content)
                            load_num -= 1
                            pbar.update(1)
                            if load_num == 0:
                                return
                        else:
                            print(f"Failed to download {url}: status {response.status_code}")
                            continue
                    except Exception as e:
                        print(f"Error downloading {url}: {e}")
                        continue
        else:
            raise ValueError(f"{self.dataset_name} Dataset not support.")

    # return a dataframe with column {content: local pdf path}  and {metadata: url}
    def get_dataset_slice(self, length, offset):
        # support Arxiv dataset on huggingface
        if self.dataset_name == "common-pile/arxiv_papers":
            if not self.output_dir:
                self.output_dir = os.path.join("local_dataset", "arxiv")
            os.makedirs(self.output_dir, exist_ok=True)

            all_files = sorted([f for f in os.listdir(self.output_dir) if f.endswith(".pdf")])
            total_len = len(all_files)
            start_idx = offset * length
            end_idx = (offset + 1) * length

            # check slice within range
            if start_idx >= total_len:
                raise ValueError(f"Slice {offset} out of range. Dataset has {total_len} samples.")

            slice_files = all_files[start_idx:end_idx]

            # Directory to store PDFs

            local_paths = [os.path.join(self.output_dir, f) for f in slice_files]

            df = pd.DataFrame({"content": local_paths})

            print(f"Loaded {len(df)} documents from index {start_idx} to {end_idx}")
            return df
        else:
            raise ValueError(f"{self.dataset_name} Dataset not support.")
