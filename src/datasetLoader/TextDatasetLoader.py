from datasetLoader.BaseDatasetLoader import BaseDatasetLoader
import pandas as pd
import datasets
from datasets import load_dataset, config, Dataset


class TextDatasetLoader(BaseDatasetLoader):
    def __init__(self, dataset_name="wikimedia/wikipedia"):
        super().__init__(dataset_name=dataset_name)
        # support wiki dataset on huggingface
        if dataset_name == "wikimedia/wikipedia":
            try:
                ds = load_dataset(dataset_name, "20231101.en")
            except ConnectionError as e:
                if config.HF_DATASETS_OFFLINE is True:
                    print(
                        "***Dataset autodownload disabled and no dataset is found under "
                        f"HF_CACHE_HOME: <{config.HF_CACHE_HOME}>"
                    )
                raise e
            self.dataset = ds["train"]
        else:
            raise ValueError(f"{self.dataset_name} Dataset not support.")
        self.total_length = len(self.dataset)
        return

    # return a dataframe with column {content: text}  and {metadata: something}
    def get_dataset_slice(self, length, offset):
        if self.dataset_name == "wikimedia/wikipedia":
            start_idx = offset * length
            end_idx = (offset + 1) * length

            # check slice within range
            if start_idx >= self.total_length:
                raise ValueError(
                    f"Slice {offset} out of range. Dataset has {self.total_length} samples."
                )

            table = self.dataset.select(range(start_idx, end_idx))

            df = pd.DataFrame({"content": table["text"], "metadata": table["id"]})

            print(f"Loaded {len(df)} documents from index {start_idx} to {end_idx}")
            return df
        else:
            raise ValueError(f"{self.dataset_name} Dataset not support.")
