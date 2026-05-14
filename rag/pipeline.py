"""
Module 2 — RAG Core
Hybrid retrieval (dense + sparse), RRF fusion, reranking, and streaming generation.

Pipeline:
    query → embed → [dense search || BM25 search] → RRF fusion → rerank → prompt → LLM → stream
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    paper_id: str
    title: str
    score: float
    metadata: dict


@dataclass
class RAGResponse:
    answer: str
    citations: list[dict]
    chunks_used: list[RetrievedChunk]
    retrieval_latency_ms: float
    generation_latency_ms: float


class RAGPipeline:
    """
    The core RAG pipeline. Used directly by the API and as a tool by LangGraph agents.

    Usage:
        pipeline = RAGPipeline()

        # Streaming (for API / frontend)
        async for token in pipeline.stream("What is attention?"):
            print(token, end="")

        # Non-streaming (for eval + agent tool calls)
        response = await pipeline.query("What is attention?")
    """

    def __init__(self):
        # TODO: initialise components
        # self.embedder = Embedder()
        # self.qdrant = QdrantClient(url=settings.QDRANT_URL)
        # self.bm25 = BM25Index()          # built from your corpus at startup
        # self.reranker = Reranker()
        # self.llm = LLMClient()
        pass

    async def retrieve(
        self,
        query: str,
        top_k: int = 50,
        top_n: int = 5,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """
        Hybrid retrieval: dense + sparse, fused with RRF, then reranked.

        TODO: implement these steps in order

        Step 1 — embed the query (same model used during ingestion!)
        Step 2 — run dense search and BM25 search in parallel:
                     dense_hits, sparse_hits = await asyncio.gather(
                         self._dense_search(query_vec, top_k, filters),
                         self._bm25_search(query, top_k),
                     )
        Step 3 — fuse with Reciprocal Rank Fusion:
                     fused = reciprocal_rank_fusion([dense_hits, sparse_hits])[:top_k]
        Step 4 — rerank top_k → top_n with cross-encoder
        Step 5 — return top_n RetrievedChunk objects
        """
        raise NotImplementedError("TODO: implement retrieve()")

    async def _dense_search(self, query_vec: list[float], top_k: int, filters: dict | None) -> list:
        """
        TODO: Query Qdrant with the embedded query vector.
              Apply metadata filters if provided (e.g. category="cs.AI", year=2023).
        """
        raise NotImplementedError

    def _bm25_search(self, query: str, top_k: int) -> list:
        """
        TODO: Query the BM25 index with the raw query string.
              rank_bm25 library: index = BM25Okapi(tokenised_corpus)
              scores = index.get_scores(query.split())
        """
        raise NotImplementedError

    def _reciprocal_rank_fusion(
        self, ranked_lists: list[list], k: int = 60
    ) -> list:
        """
        Merge multiple ranked lists using Reciprocal Rank Fusion.

        RRF score for a document d across lists:
            score(d) = sum(1 / (k + rank(d, list_i)))  for each list_i

        k=60 is the standard default — higher k reduces the impact of top ranks.

        TODO: implement this. It's a clean ~15 line function that's worth
              understanding deeply — you'll be asked about it.
        """
        raise NotImplementedError("TODO: implement RRF")

    async def stream(
        self,
        query: str,
        filters: dict | None = None,
    ) -> AsyncIterator[str]:
        """
        Full RAG pipeline with streaming token output.
        Yields tokens as they're generated, then a final citations payload.

        TODO:
        1. Run retrieve()
        2. Build prompt from Jinja2 template
        3. Stream from LLM
        4. After stream completes, yield a special JSON "citations" event
        """
        raise NotImplementedError("TODO: implement stream()")

    async def query(self, query: str, filters: dict | None = None) -> RAGResponse:
        """
        Non-streaming version — collects full response.
        Used by evaluation framework and agent tool calls.
        """
        raise NotImplementedError("TODO: implement query()")
