"""Lokale Embeddings mit fastembed. Es verlassen keine Texte den Rechner."""

from collections.abc import Sequence
from typing import Protocol

from fastembed import TextEmbedding


class Embedder(Protocol):
    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedder:
    def __init__(self, model_name: str) -> None:
        # Das Modell liegt seit dem Docker-Build im Cache (FASTEMBED_CACHE_PATH).
        self._model = TextEmbedding(model_name=model_name)

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.passage_embed(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        vector = next(iter(self._model.query_embed(text)))
        return list(vector.tolist())
