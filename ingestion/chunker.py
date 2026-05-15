"""
Module 1 — Chunker
Splits paper text into chunks for embedding.
Supports recursive (fixed-size) and semantic (meaning-aware) strategies.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class ChunkingConfig:
    strategy: Literal["recursive", "semantic"] = "recursive"
    chunk_size: int = 512        # tokens
    chunk_overlap: int = 50      # tokens of overlap between chunks
    # Semantic chunker settings (only used when strategy="semantic")
    breakpoint_threshold: float = 0.85


@dataclass
class Chunk:
    """A single text chunk with its source metadata."""
    text: str
    paper_id: str
    chunk_index: int             # position within the paper
    total_chunks: int            # how many chunks this paper produced
    metadata: dict               # title, authors, category, date, embedding_model


class Chunker:
    def __init__(self, config: ChunkingConfig = ChunkingConfig()):
        self.config = config
        self._splitter = self._build_splitter()

    def _build_splitter(self):
        """
        TODO: Return the appropriate LangChain splitter based on config.strategy.

        Recursive (start here):
            RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                model_name="gpt-4",
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )

        Semantic (add later — requires an embedding model):
            SemanticChunker(
                embeddings=<your_embedding_model>,
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=self.config.breakpoint_threshold,
            )
        """
        if self.config.strategy == "recursive":
            from langchain.text_splitter import RecursiveCharacterTextSplitter
            return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                model_name="gpt-4",
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )
        elif self.config.strategy == "semantic":
            from langchain_experimental.text_splitter import SemanticChunker
            from langchain_openai import OpenAIEmbeddings
            return SemanticChunker(
                embeddings=OpenAIEmbeddings(),
                breakpoint_threshold_type="percentile",
                breakpoint_threshold_amount=self.config.breakpoint_threshold,
            )
        else:
            raise ValueError(f"Unknown chunking strategy: {self.config.strategy!r}")

    def chunk_paper(self, paper: dict) -> list[Chunk]:
        """
        Chunk a single paper dict into a list of Chunk objects.

        paper dict shape:
            {
                "id": "1706.03762",
                "title": "Attention Is All You Need",
                "abstract": "...",
                "authors": ["Vaswani", ...],
                "categories": "cs.CL",
                "update_date": "2017-06-12",
            }

        TODO:
        1. Combine title + abstract into a single text block
           (title gives the embedding model important context)
        2. Split using self._splitter
        3. Wrap each split into a Chunk dataclass with metadata
        """
        text = f"{paper['title']}\n\n{paper['abstract']}"
        splits = self._splitter.split_text(text)
        if not splits:
            return []
        total = len(splits)
        return [
            Chunk(
                text=split,
                paper_id=paper["id"],
                chunk_index=i,
                total_chunks=total,
                metadata={
                    "title": paper["title"],
                    "authors": paper["authors"],
                    "category": paper["categories"],
                    "published_date": paper["published_date"],
                    "embedding_model": "",
                },
            )
            for i, split in enumerate(splits)
        ]

    def chunk_papers(self, papers: list[dict]) -> list[Chunk]:
        """Chunk a list of papers. Returns a flat list of all chunks."""
        all_chunks = []
        for paper in papers:
            try:
                chunks = self.chunk_paper(paper)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.warning("Failed to chunk paper %s: %s", paper.get("id", "unknown"), e)
        return all_chunks


# ── Quick sanity check ────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_paper = {
        "id": "test-001",
        "title": "Test Paper",
        "abstract": "This is a test abstract. " * 100,  # ~500 words
        "authors": ["Author One"],
        "categories": "cs.AI",
        "published_date": "2024-01-01",
    }
    chunker = Chunker()
    chunks = chunker.chunk_paper(sample_paper)
    print(f"Produced {len(chunks)} chunks")
    print(f"First chunk: {chunks[0].text[:100]}...")
