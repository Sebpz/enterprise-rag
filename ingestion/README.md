# Module 1 — Ingestion Pipeline

Loads ArXiv papers from HuggingFace, chunks text, generates embeddings, and upserts into Qdrant with metadata.

## What You'll Build
- `loader.py` — Stream ArXiv dataset from HuggingFace
- `chunker.py` — Configurable chunking strategies (recursive + semantic)
- `embedder.py` — Embedding model wrapper with version tracking
- `pipeline.py` — Orchestration with idempotency

## Key Concepts to Demonstrate
- **Chunking strategy trade-offs** — recursive vs semantic, chunk size impact on retrieval
- **Embedding versioning** — every vector tagged with model name so you can swap models safely
- **Idempotency** — re-runs skip already-ingested papers (tracked in Postgres)
- **Metadata filtering** — category, date, authors stored as Qdrant payload for scoped queries

## Running

```bash
# Ingest 10k cs.AI papers (recommended starting point)
python -m ingestion.pipeline --limit 10000 --category cs.AI

# Ingest multiple categories
python -m ingestion.pipeline --limit 50000 --category cs.AI --category cs.LG

# Compare chunking strategies (generates eval metrics)
python -m ingestion.pipeline --strategy semantic --limit 1000 --eval
```

## Interview Talking Points
- "I implemented two chunking strategies and ran retrieval evals at different chunk sizes to find the optimal configuration for this corpus."
- "Every vector is tagged with the embedding model version — so when I upgraded models, I could do a canary rollout and compare retrieval quality before full re-indexing."

## TODO (your implementation)
- [ ] Implement `loader.py` — stream from `datasets.load_dataset("arxiv_dataset", streaming=True)`
- [ ] Implement `chunker.py` — `RecursiveCharacterTextSplitter` first, then add semantic variant
- [ ] Implement `embedder.py` — wrap `SentenceTransformer`, add version to metadata
- [ ] Implement `pipeline.py` — check Postgres before upserting, log progress
- [ ] Write `tests/test_chunker.py` — verify chunk sizes and overlap
