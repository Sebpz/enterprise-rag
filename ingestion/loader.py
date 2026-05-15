"""
Module 1 — ArXiv Loader
Streams the ArXiv dataset from HuggingFace.
"""
from __future__ import annotations

import logging
from typing import Iterator

logger = logging.getLogger(__name__)

# Dataset: https://huggingface.co/datasets/arxiv_dataset
# Each record has: id, title, abstract, authors, categories, update_date


class ArxivLoader:
    """
    Streams ArXiv papers from the HuggingFace datasets library.

    Usage:
        loader = ArxivLoader()
        for paper in loader.stream(categories=["cs.AI"], limit=1000):
            print(paper["id"], paper["title"])
    """

    def stream(
        self,
        categories: list[str] | None = None,
        limit: int = 10_000,
        start_year: int = 2019,
    ) -> Iterator[dict]:
        """
        Stream ArXiv papers with optional category and date filtering.

        TODO:
        1. Load with streaming=True to avoid downloading the full dataset:
               from datasets import load_dataset
               ds = load_dataset("arxiv_dataset", split="train", streaming=True)

        2. Filter by category if provided:
               ds = ds.filter(lambda x: any(cat in x["categories"]
                                            for cat in categories))

        3. Filter by year (x["update_date"].startswith("202"))

        4. Yield up to `limit` records, logging progress every 1000

        5. Normalise the record into a consistent dict shape:
               {
                   "id": record["id"],
                   "title": record["title"],
                   "abstract": record["abstract"],
                   "authors": record["authors_parsed"],   # list of name lists
                   "categories": record["categories"],
                   "published_date": record["update_date"][:10],
               }

        Tip: The full dataset is large (~30GB). streaming=True is essential.
        For development, set limit=1000 and test with a small sample first.
        """
        from datasets import load_dataset

        try:
            ds = load_dataset(
                "arxiv_dataset",
                split="train",
                streaming=True,
                trust_remote_code=True,
            )

            if categories is not None:
                ds = ds.filter(
                    lambda record: any(cat in record["categories"] for cat in categories)
                )

            ds = ds.filter(
                lambda record: record["update_date"][:4] >= str(start_year)
            )

            count = 0
            for record in ds:
                if count >= limit:
                    break
                yield {
                    "id": record["id"],
                    "title": record["title"],
                    "abstract": record["abstract"],
                    "authors": record["authors_parsed"],
                    "categories": record["categories"],
                    "published_date": record["update_date"][:10],
                }
                count += 1
                if count % 1000 == 0:
                    logger.info("Loaded %d papers...", count)
        except Exception:
            logger.exception("Failed to load arxiv_dataset")
            raise

    def load_sample(self, n: int = 100) -> list[dict]:
        """Load a small sample synchronously — useful for testing."""
        return list(self.stream(limit=n))
