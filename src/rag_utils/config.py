from __future__ import annotations

import enum
import os
import abc
import utils.decorator as deco

import re
import torch
from sentence_transformers import SentenceTransformer


class RAGProperties(metaclass=deco.Singleton):
    class Type(enum.IntEnum):
        MODEL_NAME = enum.auto()
        CHUNK_SIZE = enum.auto()
        CHUNK_OVERLAP = enum.auto()

    def __init__(self, **kwargs):
        # default values
        self.__properties = {
            RAGProperties.Type.MODEL_NAME: "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
            RAGProperties.Type.CHUNK_SIZE: (chunk_size := 256),
            RAGProperties.Type.CHUNK_OVERLAP: round(chunk_size * 0.10),
        }
        print(self.__properties)
        # merge with input properties
        self.__properties |= kwargs

    def get(self, type):
        return self.__properties[type]


class Encoder:
    def __new__(cls, *args, **kwargs):
        raise TypeError("Cannot be instantiated")

    class Type(enum.IntEnum):
        TEXT = enum.auto()
        N_TYPES = enum.auto()

    @classmethod
    def get(cls, type, **kwargs):
        if type == Encoder.Type.TEXT:
            return SentenceTransformer(RAGProperties().get(RAGProperties.Type.MODEL_NAME), **kwargs)


def get_db_collection_name(
    name,
    replacement_str="_",
):
    # replace everything that is not a number, letter, or underscore with replacement_str
    pattern = r"[^\w\d_]+"
    occurrences = [(m.start(0), m.end(0)) for m in re.finditer(pattern, name)]
    occurrences_sorted = sorted(occurrences, key=lambda inst: inst[0])

    # look for continuous invalid strings
    substring_sorted = []
    last_substring_start = 0
    for occ_start, occ_end in occurrences_sorted:
        substring_sorted.append((last_substring_start, occ_start))
        last_substring_start = occ_end
    substring_sorted.append((last_substring_start, len(name)))

    # replace them by ignoring them on concatenation
    collection_name = name[substring_sorted[0][0] : substring_sorted[0][1]]
    for inst in substring_sorted[1:]:
        collection_name += replacement_str + name[inst[0] : inst[1]]

    return collection_name


# class VectorDB:
#     def __init__(self, path: str, embedding_dim: int, **db_kwargs: dict):
#         self._path = path
#         self._embedding_dim = embedding_dim
#         self._db_kwargs = db_kwargs

#     @abc.abstractmethod
#     def open(self):
#         pass

#     @abc.abstractmethod
#     def close(self):
#         pass
