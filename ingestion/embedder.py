"""
Module 1 — Embedder
Wraps embedding models with version tracking.
Supports local (sentence-transformers) and OpenAI embeddings.
"""
from __future__ import annotations

import os
from typing import Literal

import numpy as np

# TODO: pip install sentence-transformers openai
# from sentence_transformers import SentenceTransformer
# from openai import AsyncOpenAI


# The embedding model name is stored with every vector in Qdrant.
# This is critical — if you ever change models, you must re-embed
# because vectors from different models live in incompatible spaces.
EMBEDDING_MODELS = {
    "local": {
        "name": "all-MiniLM-L6-v2",
        "dimensions": 384,
        "provider": "sentence-transformers",
    },
    "openai-small": {
        "name": "text-embedding-3-small",
        "dimensions": 1536,
        "provider": "openai",
    },
    "openai-large": {
        "name": "text-embedding-3-large",
        "dimensions": 3072,
        "provider": "openai",
    },
}


class Embedder:
    """
    Embedding model wrapper with version metadata.

    Usage:
        embedder = Embedder(provider="local")
        vectors = await embedder.embed_batch(["text one", "text two"])
        print(embedder.model_version)  # "all-MiniLM-L6-v2"
    """

    def __init__(self, provider: Literal["local", "openai-small", "openai-large"] = "local"):
        config = EMBEDDING_MODELS[provider]
        self.model_version = config["name"]   # stored as Qdrant payload metadata
        self.dimensions = config["dimensions"]
        self._provider = config["provider"]
        self._model = self._load_model(config)

    def _load_model(self, config: dict):
        """
        TODO: Load the appropriate model based on config["provider"].

        For "sentence-transformers":
            return SentenceTransformer(config["name"])

        For "openai":
            return AsyncOpenAI()  # client — model name passed at call time
        """
        raise NotImplementedError("TODO: implement _load_model")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts. Returns a list of float vectors.

        TODO:
        - For local: self._model.encode(texts, batch_size=64, show_progress_bar=True)
        - For OpenAI: client.embeddings.create(input=texts, model=self.model_version)
        - Normalise vectors to unit length (important for cosine similarity)
        - Handle rate limits / retries for OpenAI
        """
        raise NotImplementedError("TODO: implement embed_batch")

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string. Used at retrieval time."""
        vectors = await self.embed_batch([text])
        return vectors[0]
