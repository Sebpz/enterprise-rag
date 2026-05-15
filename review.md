  ---
  System Design Assessment: Enterprise RAG Platform

  Overview

  This is a well-structured, portfolio-grade RAG system for querying ArXiv ML papers. The architecture is ambitious — 9 modules covering ingestion, retrieval, agents,
  guardrails, evaluation, fine-tuning, monitoring, and a frontend — with coherent design intent throughout. The core RAG pattern (hybrid retrieval → rerank → generate → guard)
  is sound.

  The critical caveat: nearly all business logic is TODO stubs. The structure exists; the implementation doesn't. This review assesses design decisions, not working code.

  ---
  What's Well-Designed

  Hybrid retrieval with RRF fusion (rag/pipeline.py) is the right call. Dense search alone misses keyword-specific queries (model names, paper IDs, exact terms); BM25 alone
  misses semantic similarity. Fusing them with Reciprocal Rank Fusion before Cohere reranking is a well-validated pattern — no complaints here.

  Embedding model versioning in metadata is an underrated decision. Every vector stores embedding_model so you can run a canary migration when switching from all-MiniLM-L6-v2
  to text-embedding-3-small without corrupting search. Most RAG projects skip this and pay later.

  RAGAs CI gate in evals/run_evals.py — blocking merges when faithfulness or answer relevance drops >5% — is production thinking. This prevents prompt regressions from sneaking
   in through dependency updates or template edits.

  Dual-layer guardrails (input + output) with structured GuardrailResult objects and full audit logging to PostgreSQL is the right architecture. The decision to separate
  Decision (PASS/BLOCK/WARN) from ReasonCode (enumerated 8 reasons) makes dashboards and debugging tractable.

  The database schema is clean. conversations stores full request/response pairs with cost tracking; guardrail_events is a separate audit table (good — don't conflate these);
  eval_runs enables regression trending over time.

  ---
  Design Weaknesses

  1. The LangGraph agent graph has no real routing logic.

  The orchestrator node is supposed to classify queries as "simple" or "complex" and decompose complex ones into sub-queries. But there's no design for what makes a query
  complex, no threshold, no fallback. The critique loop (max 3 iterations) is defined, but the critique prompt will trivially keep producing non-"SATISFIED" responses unless
  the model is carefully prompted. Without a concrete stopping criterion, this loop will always hit the 3-iteration hard stop, meaning complex mode costs ~3x what it should.

  2. BM25 is implemented in-memory on a Python object, not integrated with Qdrant's sparse vectors.

  rank-bm25 is a pure-Python library that operates on a corpus held in RAM. At ingestion time, this corpus needs to be rebuilt on restart, which won't scale. Qdrant natively
  supports sparse vector indexing (via sparse_vectors with SPLADE or BM25-encoded weights) — that would make BM25 persistent and searchable at the same speed as dense. The
  current design means BM25 is either rebuilt on every API startup (slow) or not persisted (incorrect after restart).

  3. Rate limiting is split across two places with incomplete implementation.

  api/middleware/ratelimit.py uses slowapi for per-minute request limits, but the daily token limit is flagged as TODO with Redis. Meanwhile guardrails/pipeline.py has its own
  BUDGET_EXCEEDED check at the agent level (8000 tokens per conversation). These two systems overlap without coordination. The daily token limit is the expensive guard;
  shipping without it means a single user can run unlimited LLM calls.

  4. The API routes are empty.

  api/routes/chat.py is the most critical file — it wires guardrails, RAG, and agents together — and it's a stub. The SSE event format is defined (token, citations, agent_step,
   done, error), but there's no implementation. This is the integration point for 5 other modules; leaving it unimplemented means nothing can be tested end-to-end.

  5. Health checks don't check anything.

  GET /health is a liveness probe that returns 200 OK without checking Qdrant, PostgreSQL, or Redis connectivity. In a Docker Compose setup, services start in parallel and
  Qdrant commonly takes 5-10 seconds to initialize. The API will return healthy before it can actually serve requests.

  6. Ingestion idempotency check is incomplete.

  ingestion/pipeline.py checks Postgres before upserting to Qdrant, but Qdrant itself doesn't enforce uniqueness. If a paper is partially ingested (some chunks stored, some
  not, then crash), re-running the pipeline will see the paper_id in Postgres and skip it — leaving the Qdrant index in a corrupted partial state. The idempotency logic should
  check Qdrant point counts against expected chunk counts, not just Postgres.

  7. No connection pooling or startup validation.

  The FastAPI startup hook has a TODO for initializing Qdrant, Postgres, and Redis connections. Without connection pooling, every request creates a new database connection.
  Under any real load this will exhaust the PostgreSQL max_connections limit quickly.

  ---
  Structural Observations

  The fine-tuning module (fine_tuning/) is low-value relative to its complexity. The hypothesis — that QLoRA-tuned Mistral-7B produces better citation JSON than GPT-4o-mini
  with prompt engineering — is testable, but the answer is almost certainly "structured outputs via response_format={"type": "json_schema"} beats both." OpenAI's structured
  outputs guarantee schema compliance at zero fine-tuning cost. The module is interesting as a learning exercise but shouldn't be on the critical path for a production system.

  The frontend is scaffolded but not scaffolded. There's a hooks file (useStreamingChat.ts) with type signatures but no package.json, no create-next-app output, and no
  component files. The frontend can't be started.

  Module boundaries are clean — each directory has a single responsibility with minimal cross-module imports. This is good for testability, though the agents/graph.py properly
  depends on rag/pipeline.py and guardrails/pipeline.py, which is the right dependency direction.

  ---
  Priority Order for Implementation

  If you're building this out, the sequence that unblocks everything else:

  1. ingestion/ — get vectors into Qdrant (nothing works without data)
  2. rag/pipeline.py — implement dense search + BM25 + RRF + rerank
  3. api/routes/chat.py — wire up non-streaming RAG first, streaming second
  4. api/middleware/ratelimit.py — Redis-backed daily token limit
  5. guardrails/pipeline.py — at minimum: PII masking + faithfulness check
  6. api/routes/health.py — real dependency probes
  Structural Observations

  The fine-tuning module (fine_tuning/) is low-value relative to its complexity. The hypothesis — that QLoRA-tuned Mistral-7B produces better citation JSON than GPT-4o-mini
  with prompt engineering — is testable, but the answer is almost certainly "structured outputs via response_format={"type": "json_schema"} beats both." OpenAI's structured
  outputs guarantee schema compliance at zero fine-tuning cost. The module is interesting as a learning exercise but shouldn't be on the critical path for a production system.

  The frontend is scaffolded but not scaffolded. There's a hooks file (useStreamingChat.ts) with type signatures but no package.json, no create-next-app output, and no
  component files. The frontend can't be started.

  Module boundaries are clean — each directory has a single responsibility with minimal cross-module imports. This is good for testability, though the agents/graph.py properly
  depends on rag/pipeline.py and guardrails/pipeline.py, which is the right dependency direction.

  ---
  Priority Order for Implementation

  If you're building this out, the sequence that unblocks everything else:

  1. ingestion/ — get vectors into Qdrant (nothing works without data)
  2. rag/pipeline.py — implement dense search + BM25 + RRF + rerank
  3. api/routes/chat.py — wire up non-streaming RAG first, streaming second
  4. api/middleware/ratelimit.py — Redis-backed daily token limit
  5. guardrails/pipeline.py — at minimum: PII masking + faithfulness check
  6. api/routes/health.py — real dependency probes
  7. evals/run_evals.py — now you can measure quality
  8. agents/graph.py — multi-agent is additive once RAG is solid
  9. Frontend — can be built independently against a running API

  The fine-tuning module and Langfuse integration are stretch goals.

  ---
  Summary

  The architecture is well-conceived — the right components are present, the data flows make sense, and design choices like RRF fusion, embedding versioning, and RAGAs CI
  gating show real production awareness. The main risks are the BM25 persistence problem, the missing rate limiting, and the fact that the API routing layer (the integration
  point for everything) hasn't been written yet. A solid ~2-week implementation sprint focused on the ingestion → RAG → API path would produce a working system; the rest can
  follow.