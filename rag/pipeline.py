"""
Module 2 — RAG Core
Hybrid retrieval (dense + sparse), RRF fusion, reranking, and streaming generation.

Pipeline:
    query → embed → [dense search || BM25 search] → RRF fusion → rerank → prompt → LLM → stream
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import pickle
import time
from dataclasses import dataclass
from typing import AsyncIterator

import numpy as np
from jinja2 import Template

logger = logging.getLogger(__name__)


RAG_PROMPT_TEMPLATE = Template("""\
You are an expert ML research assistant. Answer based ONLY on the provided context.
If the answer is not in the context, say "I don't have enough information to answer that."
Cite paper IDs when making claims.

Context:
{% for chunk in chunks %}
[{{ loop.index }}] {{ chunk.title }} ({{ chunk.paper_id }})
{{ chunk.text }}
{% endfor %}

Question: {{ query }}

Answer:\
""")


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

    def __init__(self, bm25_cache_path: str = "./bm25_cache.pkl"):
        from ingestion.embedder import Embedder
        from qdrant_client import AsyncQdrantClient
        import cohere
        from openai import AsyncOpenAI

        self.embedder = Embedder()
        self.qdrant = AsyncQdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY") or None,
        )
        self.collection = os.getenv("QDRANT_COLLECTION", "arxiv_papers")
        self._cohere = cohere.AsyncClientV2(os.getenv("COHERE_API_KEY", ""))
        self._llm = AsyncOpenAI()
        self._bm25_index = None
        self._bm25_docs: list[dict] = []
        self._bm25_cache_path = bm25_cache_path

    async def _ensure_bm25_index(self, force_rebuild: bool = False) -> None:
        if self._bm25_index is not None and not force_rebuild:
            return

        from rank_bm25 import BM25Okapi

        if not force_rebuild and os.path.exists(self._bm25_cache_path):
            logger.info("Loading BM25 index from cache: %s", self._bm25_cache_path)
            with open(self._bm25_cache_path, "rb") as f:
                cached = pickle.load(f)
            self._bm25_index = cached["index"]
            self._bm25_docs = cached["docs"]
            logger.info("BM25 index loaded with %d documents.", len(self._bm25_docs))
            return

        logger.info("Building BM25 index by scrolling Qdrant collection…")
        all_payloads: list[dict] = []
        offset = None

        while True:
            results, next_offset = await self.qdrant.scroll(
                collection_name=self.collection,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in results:
                payload = point.payload or {}
                all_payloads.append(
                    {
                        "id": str(point.id),
                        "text": payload.get("text", ""),
                        "title": payload.get("title", ""),
                        "paper_id": payload.get("paper_id", ""),
                        "metadata": {
                            "chunk_index": payload.get("chunk_index", 0),
                            "authors": payload.get("authors", []),
                            "category": payload.get("category", ""),
                            "published_date": payload.get("published_date", ""),
                            "embedding_model": payload.get("embedding_model", ""),
                        },
                    }
                )
            if next_offset is None:
                break
            offset = next_offset

        tokenized = [doc["text"].lower().split() for doc in all_payloads]
        self._bm25_index = BM25Okapi(tokenized)
        self._bm25_docs = all_payloads
        logger.info("BM25 index built with %d documents.", len(all_payloads))

        with open(self._bm25_cache_path, "wb") as f:
            pickle.dump({"index": self._bm25_index, "docs": self._bm25_docs}, f)
        logger.info("BM25 index saved to cache: %s", self._bm25_cache_path)

    async def retrieve(
        self,
        query: str,
        top_k: int = 50,
        top_n: int = 5,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """
        Hybrid retrieval: dense + sparse, fused with RRF, then reranked.
        """
        await self._ensure_bm25_index()
        query_vec = await self.embedder.embed_query(query)
        dense_hits, sparse_hits = await asyncio.gather(
            self._dense_search(query_vec, top_k, filters),
            asyncio.to_thread(self._bm25_search, query, top_k),
        )
        fused = self._reciprocal_rank_fusion([dense_hits, sparse_hits])[:top_k]
        reranked = await self._rerank(query, fused, top_n)
        return reranked

    async def _dense_search(
        self,
        query_vec: list[float],
        top_k: int,
        filters: dict | None,
    ) -> list[RetrievedChunk]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

        must_conditions = []
        if filters:
            if "category" in filters:
                must_conditions.append(
                    FieldCondition(key="category", match=MatchValue(value=filters["category"]))
                )
            if "year" in filters:
                year = int(filters["year"])
                must_conditions.append(
                    FieldCondition(
                        key="published_year",
                        range=Range(gte=year, lte=year),
                    )
                )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        hits = await self.qdrant.search(
            collection_name=self.collection,
            query_vector=query_vec,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            RetrievedChunk(
                text=(payload := hit.payload or {}).get("text", ""),
                paper_id=payload.get("paper_id", ""),
                title=payload.get("title", ""),
                score=hit.score,
                metadata={
                    "chunk_index": payload.get("chunk_index", 0),
                    "authors": payload.get("authors", []),
                    "category": payload.get("category", ""),
                    "published_date": payload.get("published_date", ""),
                    "embedding_model": payload.get("embedding_model", ""),
                },
            )
            for hit in hits
        ]

    def _bm25_search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        if not self._bm25_index or not self._bm25_docs:
            return []
        scores = self._bm25_index.get_scores(query.lower().split())
        sorted_indices = np.argsort(scores)[::-1]
        chunks: list[RetrievedChunk] = []
        for idx in sorted_indices:
            if len(chunks) >= top_k:
                break
            score = float(scores[idx])
            if score <= 0:
                break
            doc = self._bm25_docs[idx]
            chunks.append(
                RetrievedChunk(
                    text=doc["text"],
                    paper_id=doc["paper_id"],
                    title=doc["title"],
                    score=score,
                    metadata=doc["metadata"],
                )
            )
        return chunks

    def _reciprocal_rank_fusion(
        self,
        ranked_lists: list[list[RetrievedChunk]],
        k: int = 60,
    ) -> list[RetrievedChunk]:
        """
        Merge multiple ranked lists using Reciprocal Rank Fusion.
        score(d) = sum(1 / (k + rank + 1)) across all lists, k=60.
        """
        rrf_scores: dict[str, float] = {}
        first_seen: dict[str, RetrievedChunk] = {}

        for ranked_list in ranked_lists:
            for rank, chunk in enumerate(ranked_list):
                doc_id = f"{chunk.paper_id}:{chunk.metadata.get('chunk_index', 0)}"
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
                if doc_id not in first_seen:
                    first_seen[doc_id] = chunk

        result: list[RetrievedChunk] = []
        for doc_id in sorted(rrf_scores, key=lambda d: rrf_scores[d], reverse=True):
            chunk = first_seen[doc_id]
            result.append(dataclasses.replace(chunk, score=rrf_scores[doc_id]))
        return result

    async def _rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        response = await self._cohere.rerank(
            query=query,
            documents=[c.text for c in chunks],
            top_n=min(top_n, len(chunks)),
            model="rerank-english-v3.0",
        )
        reranked: list[RetrievedChunk] = []
        for result in response.results:
            chunk = chunks[result.index]
            reranked.append(dataclasses.replace(chunk, score=result.relevance_score))
        return reranked

    def _build_citations(self, chunks: list[RetrievedChunk]) -> list[dict]:
        return [
            {
                "paper_id": chunk.paper_id,
                "title": chunk.title,
                "score": round(chunk.score, 4),
                "authors": chunk.metadata.get("authors", []),
                "category": chunk.metadata.get("category", ""),
                "published_date": chunk.metadata.get("published_date", ""),
            }
            for chunk in chunks
        ]

    async def stream(
        self,
        query: str,
        filters: dict | None = None,
    ) -> AsyncIterator[str]:
        """
        Full RAG pipeline with streaming token output.
        Yields tokens as generated, then a final citations sentinel string.
        Sentinel format: \\x00CITATIONS\\x00<json>
        """
        t0 = time.perf_counter()
        chunks = await self.retrieve(query, filters=filters)
        logger.debug(
            "Retrieval took %.1f ms, got %d chunks.",
            (time.perf_counter() - t0) * 1000,
            len(chunks),
        )

        prompt = RAG_PROMPT_TEMPLATE.render(chunks=chunks, query=query)
        stream_resp = await self._llm.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )

        async for event in stream_resp:
            delta = event.choices[0].delta.content
            if delta:
                yield delta

        yield f"\x00CITATIONS\x00{json.dumps(self._build_citations(chunks))}"

    async def close(self) -> None:
        """Close the Qdrant async client connection gracefully."""
        await self.qdrant.close()

    async def query(
        self,
        query: str,
        filters: dict | None = None,
    ) -> RAGResponse:
        """
        Non-streaming version — collects full response.
        Used by evaluation framework and agent tool calls.
        """
        t0 = time.perf_counter()
        chunks = await self.retrieve(query, filters=filters)
        retrieval_latency_ms = (time.perf_counter() - t0) * 1000

        prompt = RAG_PROMPT_TEMPLATE.render(chunks=chunks, query=query)
        t1 = time.perf_counter()
        completion = await self._llm.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        generation_latency_ms = (time.perf_counter() - t1) * 1000

        return RAGResponse(
            answer=completion.choices[0].message.content or "",
            citations=self._build_citations(chunks),
            chunks_used=chunks,
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=generation_latency_ms,
        )
