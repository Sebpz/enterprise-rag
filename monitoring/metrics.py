"""
Module 6 — Prometheus Metrics
All custom metrics for the RAG platform.
Import and use these in your route handlers and pipeline code.
"""
from prometheus_client import Counter, Gauge, Histogram

# ── Latency ───────────────────────────────────────────────────────────────────
TTFT_HISTOGRAM = Histogram(
    "rag_ttft_seconds",
    "Time to first token in seconds",
    buckets=[0.1, 0.3, 0.5, 0.8, 1.0, 2.0, 5.0],
)

TOTAL_LATENCY = Histogram(
    "rag_response_seconds",
    "Total response generation time",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    labelnames=["mode"],   # "rag" or "agent"
)

RETRIEVAL_LATENCY = Histogram(
    "rag_retrieval_seconds",
    "Time spent in retrieval pipeline",
    labelnames=["step"],   # "dense", "sparse", "rerank"
)

# ── Throughput ────────────────────────────────────────────────────────────────
REQUESTS_COUNTER = Counter(
    "rag_requests_total",
    "Total requests processed",
    labelnames=["mode", "status"],   # status: "success", "error", "blocked"
)

# ── Quality (updated by eval pipeline) ───────────────────────────────────────
FAITHFULNESS_GAUGE      = Gauge("rag_faithfulness_score",    "Latest faithfulness from eval run")
ANSWER_RELEVANCE_GAUGE  = Gauge("rag_answer_relevance",      "Latest answer relevance from eval run")
CONTEXT_PRECISION_GAUGE = Gauge("rag_context_precision",     "Latest context precision from eval run")

# ── Safety ────────────────────────────────────────────────────────────────────
GUARDRAIL_COUNTER = Counter(
    "rag_guardrail_triggers_total",
    "Number of guardrail trigger events",
    labelnames=["guardrail_name", "decision", "reason_code"],
)

# ── Cost ──────────────────────────────────────────────────────────────────────
TOKENS_COUNTER = Counter(
    "rag_llm_tokens_total",
    "Total LLM tokens consumed",
    labelnames=["model", "direction"],   # direction: "input" or "output"
)

ESTIMATED_COST_COUNTER = Counter(
    "rag_estimated_cost_usd_total",
    "Estimated LLM API cost in USD",
    labelnames=["model"],
)

# ── Agent-specific ────────────────────────────────────────────────────────────
AGENT_ITERATIONS_HISTOGRAM = Histogram(
    "rag_agent_iterations",
    "Number of critique loop iterations per agent request",
    buckets=[1, 2, 3, 4, 5],
)

TOOL_CALLS_COUNTER = Counter(
    "rag_agent_tool_calls_total",
    "Total tool invocations by agents",
    labelnames=["tool_name", "status"],
)


# ── Usage example ─────────────────────────────────────────────────────────────
# In your route handler:
#
#   import time
#   from monitoring.metrics import TTFT_HISTOGRAM, REQUESTS_COUNTER, TOKENS_COUNTER
#
#   start = time.perf_counter()
#   async for token in pipeline.stream(query):
#       if is_first_token:
#           TTFT_HISTOGRAM.observe(time.perf_counter() - start)
#       yield token
#
#   REQUESTS_COUNTER.labels(mode="rag", status="success").inc()
#   TOKENS_COUNTER.labels(model="gpt-4o-mini", direction="output").inc(output_tokens)
