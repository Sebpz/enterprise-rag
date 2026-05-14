"""
Module 1 — Ingestion Pipeline
Orchestrates loading → chunking → embedding → upserting into Qdrant.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator

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

    TODO: implement the steps below
    """
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

    # TODO: Step 1 — Load papers from HuggingFace
    # papers = loader.stream(categories=config.categories, limit=config.limit)

    # TODO: Step 2 — Filter out already-ingested paper IDs (check Postgres)
    # existing_ids = await get_ingested_ids()

    # TODO: Step 3 — Chunk each paper
    # chunks = chunker.chunk_papers(papers)

    # TODO: Step 4 — Embed in batches
    # embeddings = await embedder.embed_batch(chunks)

    # TODO: Step 5 — Upsert to Qdrant with metadata payload
    # await upsert_to_qdrant(embeddings, batch_size=config.upsert_batch_size)

    # TODO: Step 6 — Record ingestion run in Postgres

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
