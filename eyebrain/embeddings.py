from __future__ import annotations

import hashlib
import math
import os
import re
from collections.abc import Iterable, Sequence
from typing import Protocol

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "been",
    "by",
    "did",
    "get",
    "has",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "their",
    "to",
    "when",
    "where",
    "with",
}
SYNONYMS = {
    "left": ("leave",),
    "leaves": ("leave",),
    "leaving": ("leave",),
    "knocked": ("knock",),
    "knocks": ("knock",),
    "fallen": ("fall",),
    "waiting": ("wait",),
}


class Embedder(Protocol):
    name: str

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        ...


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _features(text: str) -> Iterable[str]:
    tokens = [token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS]
    for token in tokens:
        yield token
        yield from SYNONYMS.get(token, ())
        if token.endswith("s") and len(token) > 3:
            yield token[:-1]
        if token.endswith("ed") and len(token) > 4:
            yield token[:-2]
        if token.endswith("ing") and len(token) > 5:
            yield token[:-3]
    for left, right in zip(tokens, tokens[1:]):
        yield f"{left}_{right}"


class HashingEmbedder:
    """Small deterministic local embedder for demos and tests.

    FastEmbed gives better semantics, but it may need a model download on first run.
    The hashing backend keeps the hackathon demo runnable offline.
    """

    name = "hash"

    def __init__(self, dimension: int = 4096) -> None:
        self.dimension = dimension

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._encode_one(text) for text in texts]

    def _encode_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for feature in _features(text):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dimension
            vector[bucket] += 1.0
        return _normalize(vector)


class FastEmbedder:
    name = "fastembed"

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=model_name)

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [list(map(float, embedding)) for embedding in self.model.embed(list(texts))]


def make_embedder(name: str | None = None) -> Embedder:
    backend = (name or os.getenv("EYEBRAIN_EMBEDDER") or "hash").lower()
    if backend == "hash":
        return HashingEmbedder()
    if backend == "fastembed":
        return FastEmbedder()
    raise ValueError(f"unknown embedder backend: {backend}")


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))
