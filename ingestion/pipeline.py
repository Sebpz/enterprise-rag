"""
Module 1 — Ingestion Pipeline
Orchestrates loading → chunking → embedding → upserting into Qdrant.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from ingestion.chunker import Chunker, ChunkingConfig
from ingestion.embedder import Embedder
from ingestion.loader import ArxivLoader

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    limit: int = 10_000
    categories: list[str] = field(default_factory=lambda: ["cs.AI"])
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    batch_size: int = 100          # papers processed per batch
    upsert_batch_size: int = 256   # vectors upserted per Qdrant call


async def run_pipeline(config: PipelineConfig) -> dict:
    """
    Main entry point. Returns a summary dict with counts and timing.
    """
    import json
    import os
    import uuid

    import asyncpg
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    stats = {
        "started_at": datetime.utcnow().isoformat(),
        "papers_processed": 0,
        "chunks_created": 0,
        "skipped_existing": 0,
        "errors": 0,
    }

    loader = ArxivLoader()
    chunker = Chunker(config.chunking)
    embedder = Embedder()

    collection = os.getenv("QDRANT_COLLECTION", "arxiv_papers")
    conn = await asyncpg.connect(
        os.getenv("DATABASE_URL", "postgresql://raguser:ragpass@localhost:5432/ragdb")
    )
    qdrant = AsyncQdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )

    async def flush(batch: list[dict]) -> None:
        new_papers = [p for p in batch if p["id"] not in existing_ids]
        stats["skipped_existing"] += len(batch) - len(new_papers)
        if not new_papers:
            return

        chunks = chunker.chunk_papers(new_papers)
        if chunks:
            vectors = await embedder.embed_batch([c.text for c in chunks])
            points = [
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{c.paper_id}:{c.chunk_index}")),
                    vector=v,
                    payload={
                        "text": c.text,
                        "paper_id": c.paper_id,
                        "chunk_index": c.chunk_index,
                        **c.metadata,
                        "embedding_model": embedder.model_version,
                    },
                )
                for c, v in zip(chunks, vectors)
            ]
            for i in range(0, len(points), config.upsert_batch_size):
                await qdrant.upsert(
                    collection_name=collection,
                    points=points[i : i + config.upsert_batch_size],
                )
            stats["chunks_created"] += len(chunks)

        await conn.executemany(
            "INSERT INTO papers(id,title,authors,abstract,category,published_date,embedding_model) "
            "VALUES($1,$2,$3,$4,$5,$6,$7) ON CONFLICT(id) DO NOTHING",
            [
                (
                    p["id"],
                    p["title"],
                    p.get("authors", []),
                    p.get("abstract", ""),
                    p.get("categories", ""),
                    p.get("published_date"),
                    embedder.model_version,
                )
                for p in new_papers
            ],
        )
        existing_ids.update(p["id"] for p in new_papers)
        stats["papers_processed"] += len(new_papers)

    try:
        # Step 2 — Fetch already-ingested IDs for idempotency
        rows = await conn.fetch("SELECT id FROM papers")
        existing_ids: set[str] = {row["id"] for row in rows}

        # Ensure Qdrant collection exists with correct dimensions
        collections = await qdrant.get_collections()
        if collection not in [c.name for c in collections.collections]:
            await qdrant.create_collection(
                collection,
                vectors_config=VectorParams(size=embedder.dimensions, distance=Distance.COSINE),
            )

        # Steps 1, 3-5 — Stream → chunk → embed → upsert in batches
        batch: list[dict] = []
        for paper in loader.stream(categories=config.categories, limit=config.limit):
            batch.append(paper)
            if len(batch) >= config.batch_size:
                try:
                    await flush(batch)
                except Exception as e:
                    logger.error("Batch processing error: %s", e)
                    stats["errors"] += 1
                batch = []

        if batch:
            try:
                await flush(batch)
            except Exception as e:
                logger.error("Final batch processing error: %s", e)
                stats["errors"] += 1

        # Step 6 — Record ingestion run
        await conn.execute(
            "INSERT INTO ingestion_runs(completed_at,papers_processed,chunks_created,embedding_model,config) "
            "VALUES(NOW(),$1,$2,$3,$4)",
            stats["papers_processed"],
            stats["chunks_created"],
            embedder.model_version,
            json.dumps({
                "chunk_size": config.chunking.chunk_size,
                "chunk_overlap": config.chunking.chunk_overlap,
                "strategy": config.chunking.strategy,
            }),
        )

    finally:
        stats["completed_at"] = datetime.utcnow().isoformat()
        await conn.close()
        await qdrant.close()

    logger.info("Pipeline complete: %s", stats)
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest ArXiv papers into Qdrant")
    parser.add_argument("--limit", type=int, default=10_000)
    parser.add_argument("--category", action="append", dest="categories", default=["cs.AI"])
    parser.add_argument("--strategy", choices=["recursive", "semantic"], default="recursive")
    parser.add_argument("--chunk-size", type=int, default=512)
    args = parser.parse_args()

    cfg = PipelineConfig(
        limit=args.limit,
        categories=args.categories,
        chunking=ChunkingConfig(strategy=args.strategy, chunk_size=args.chunk_size),
    )
    asyncio.run(run_pipeline(cfg))
