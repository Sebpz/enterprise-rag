"""
Module 7 — LangGraph Multi-Agent System
Orchestrator → routes to Retrieval Agent or Research Agent → Critique Agent → output.

Graph:
    input_guard → orchestrator → [retrieval | research → critique loop] → output_guard → END
"""
from __future__ import annotations

import asyncio
import json
import logging
import operator
import os
from typing import Annotated, TypedDict

logger = logging.getLogger(__name__)


# ── Agent State ───────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    """
    Shared state passed between all nodes in the graph.
    Annotated[list, operator.add] means new items are appended, not replaced.
    """
    query: str
    trace_id: str
    user_id: str

    # Orchestrator outputs
    route: str                              # "simple" | "complex" | "blocked"
    sub_queries: list[str]                  # decomposed sub-questions

    # Accumulated retrieval results
    retrieved_contexts: Annotated[list, operator.add]

    # Generation
    draft_answer: str
    critique: str                           # Critique Agent feedback
    critique_iterations: int               # loop counter — hard stop at MAX_ITERATIONS
    final_answer: str
    citations: list[dict]

    # Safety + budget
    guardrail_status: str                   # "pass" | "blocked"
    guardrail_reason: str
    total_tokens_used: int                  # budget guardrail
    total_cost_usd: float


MAX_ITERATIONS = 3          # hard stop on critique loops
BUDGET_LIMIT_TOKENS = 8000  # block if a conversation exceeds this


# ── RAGPipeline singleton ─────────────────────────────────────────────────────
# Reuse a single instance to avoid rebuilding the BM25 index on every node call.

_rag_pipeline = None


def get_rag_pipeline():
    global _rag_pipeline
    if _rag_pipeline is None:
        from rag.pipeline import RAGPipeline
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


# ── Node implementations ──────────────────────────────────────────────────────

async def input_guardrail_node(state: AgentState) -> dict:
    """Run input guardrails on the user query."""
    from guardrails.pipeline import GuardrailPipeline
    pipeline = GuardrailPipeline()
    result = await pipeline.check_input(state["query"], state.get("trace_id", ""))
    if not result.passed:
        return {
            "guardrail_status": "blocked",
            "guardrail_reason": result.blocked_by or "unknown",
            "route": "blocked",
        }
    return {"guardrail_status": "pass", "route": "pending"}


async def orchestrator_node(state: AgentState) -> dict:
    """
    Classify query complexity and decompose if needed.
    Uses gpt-4o-mini with JSON mode. Defaults to simple route on failure.
    Short-circuits immediately if the input guardrail already blocked the query.
    """
    # Issue #7: short-circuit if input_guard already blocked the request.
    if state.get("guardrail_status") == "blocked":
        return {}

    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    query = state["query"]

    prompt = (
        "You are an AI orchestrator. Analyze the user query and respond in JSON.\n"
        "A query is 'complex' if it requires comparing multiple papers, synthesizing "
        "information across different topics, or contains multiple distinct sub-questions. "
        "Otherwise classify as 'simple'.\n"
        "If complex, decompose into 2-4 focused sub-questions.\n\n"
        f"Query: {query}\n\n"
        "Respond with ONLY valid JSON:\n"
        "{\"route\": \"simple\"|\"complex\", \"sub_queries\": [\"sub-q1\", \"sub-q2\"]}\n\n"
        f"For simple queries, sub_queries should be [\"{query}\"]."
    )

    try:
        completion = await client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(completion.choices[0].message.content or "{}")
        route = parsed.get("route", "simple")
        if route not in ("simple", "complex"):
            route = "simple"
        sub_queries = parsed.get("sub_queries", [query])
        if not isinstance(sub_queries, list) or not sub_queries:
            sub_queries = [query]
        return {"route": route, "sub_queries": sub_queries}
    except Exception as e:
        logger.warning("orchestrator_node failed, defaulting to simple: %s", e)
        return {"route": "simple", "sub_queries": [query]}


async def retrieval_node(state: AgentState) -> dict:
    """Simple path: single RAG call for the original query."""
    # Issue #5: apply the same budget guardrail as research_node.
    if state.get("total_tokens_used", 0) > BUDGET_LIMIT_TOKENS:
        return {
            "guardrail_status": "blocked",
            "guardrail_reason": "budget_exceeded",
            "final_answer": "Request exceeded token budget. Please try a simpler query.",
        }

    rag = get_rag_pipeline()
    response = await rag.query(state["query"])
    context_dicts = [
        {"text": c.text, "paper_id": c.paper_id, "title": c.title, "score": c.score}
        for c in response.chunks_used
    ]
    return {
        "retrieved_contexts": context_dicts,
        "draft_answer": response.answer,
        "citations": response.citations,
        "final_answer": response.answer,
    }


async def research_node(state: AgentState) -> dict:
    """Complex path: fan out sub-queries in parallel, synthesize results."""
    if state.get("total_tokens_used", 0) > BUDGET_LIMIT_TOKENS:
        return {
            "guardrail_status": "blocked",
            "guardrail_reason": "budget_exceeded",
            "final_answer": "Request exceeded token budget. Please try a simpler query.",
        }

    rag = get_rag_pipeline()
    sub_queries = state.get("sub_queries") or [state["query"]]

    responses = await asyncio.gather(
        *[rag.query(sq) for sq in sub_queries],
        return_exceptions=True,
    )

    all_contexts: list[dict] = []
    all_citations: list[dict] = []
    context_texts: list[str] = []

    for resp in responses:
        if isinstance(resp, Exception):
            logger.warning("Sub-query failed: %s", resp)
            continue
        for chunk in resp.chunks_used:
            all_contexts.append(
                {"text": chunk.text, "paper_id": chunk.paper_id, "title": chunk.title}
            )
            context_texts.append(f"[{chunk.title}]: {chunk.text}")
        all_citations.extend(resp.citations)

    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    synthesis_prompt = (
        f"Original question: {state['query']}\n\n"
        "Relevant context from multiple sources:\n"
        + "\n\n".join(context_texts[:10])
        + "\n\nSynthesize a comprehensive answer that addresses the original question."
    )
    completion = await client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": synthesis_prompt}],
    )
    draft = completion.choices[0].message.content or ""
    tokens_used = completion.usage.total_tokens if completion.usage else 0

    return {
        "retrieved_contexts": all_contexts,
        "draft_answer": draft,
        "citations": all_citations,
        "total_tokens_used": state.get("total_tokens_used", 0) + tokens_used,
    }


async def critique_node(state: AgentState) -> dict:
    """
    Review the draft answer for completeness and accuracy.
    Returns SATISFIED or a list of follow-up questions as new sub_queries.
    """
    from openai import AsyncOpenAI
    client = AsyncOpenAI()

    iterations = state.get("critique_iterations", 0) + 1

    # Issue #1: force exit after 2 iterations regardless of critique output,
    # well before the hard MAX_ITERATIONS cap, to prevent runaway loops.
    if iterations >= 2:
        logger.info("critique_node: iteration limit reached — forcing output_guard")
        return {
            "critique": "SATISFIED",
            "final_answer": state.get("draft_answer", ""),
            "critique_iterations": iterations,
        }

    context_summary = "\n".join(
        f"- {c.get('title', '')}: {c.get('text', '')[:200]}"
        for c in state.get("retrieved_contexts", [])[:5]
    )
    critique_prompt = (
        f"Question: {state['query']}\n\n"
        f"Context available:\n{context_summary}\n\n"
        f"Draft answer:\n{state.get('draft_answer', '')}\n\n"
        "Review this answer. If the draft answer covers the question fully using the "
        "available context, respond with EXACTLY the word: SATISFIED\n"
        "Only list follow-up questions if there are SPECIFIC factual gaps that CAN be "
        "answered from academic papers (not opinion or missing data). List one question "
        "per line.\n"
        "If you are unsure, respond SATISFIED — it is better to output an imperfect "
        "answer than to loop."
    )

    completion = await client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": critique_prompt}],
    )
    critique_text = (completion.choices[0].message.content or "").strip()
    tokens_used = completion.usage.total_tokens if completion.usage else 0

    if critique_text == "SATISFIED":
        return {
            "critique": "SATISFIED",
            "final_answer": state.get("draft_answer", ""),
            "critique_iterations": iterations,
            "total_tokens_used": state.get("total_tokens_used", 0) + tokens_used,
        }

    follow_ups = [line.strip("- ").strip() for line in critique_text.splitlines() if line.strip()]
    return {
        "critique": critique_text,
        "sub_queries": follow_ups[:4],
        "critique_iterations": iterations,
        "total_tokens_used": state.get("total_tokens_used", 0) + tokens_used,
    }


async def output_guardrail_node(state: AgentState) -> dict:
    """Run output guardrails on the final answer. Also formats citations."""
    from guardrails.pipeline import GuardrailPipeline
    pipeline = GuardrailPipeline()

    final_answer = state.get("final_answer") or state.get("draft_answer", "")
    context_chunks = state.get("retrieved_contexts", [])

    result = await pipeline.check_output(final_answer, context_chunks, state.get("trace_id", ""))
    if not result.passed:
        return {
            "guardrail_status": "blocked",
            "guardrail_reason": result.blocked_by or "output_guardrail",
            "final_answer": f"Response blocked by safety guardrails: {result.blocked_by}",
        }
    return {"guardrail_status": "pass", "final_answer": final_answer}


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_orchestrator(state: AgentState) -> str:
    """Conditional edge: where does the orchestrator route us?"""
    if state.get("guardrail_status") == "blocked":
        return "END"
    route = state.get("route", "simple")
    if route not in ("simple", "complex"):
        return "simple"
    return route


def route_after_critique(state: AgentState) -> str:
    """Continue the critique loop or exit?"""
    if state.get("critique") == "SATISFIED":
        return "output_guard"
    if state.get("critique_iterations", 0) >= MAX_ITERATIONS:
        logger.warning("Max critique iterations reached — forcing exit")
        return "output_guard"
    return "research"


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph():
    """Assemble and compile the LangGraph state graph."""
    from langgraph.graph import StateGraph, END

    graph = StateGraph(AgentState)

    graph.add_node("input_guard",  input_guardrail_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("retrieval",    retrieval_node)
    graph.add_node("research",     research_node)
    graph.add_node("critique",     critique_node)
    graph.add_node("output_guard", output_guardrail_node)

    graph.set_entry_point("input_guard")
    graph.add_edge("input_guard", "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {"simple": "retrieval", "complex": "research", "END": END},
    )
    graph.add_edge("retrieval", "output_guard")
    graph.add_edge("research", "critique")
    graph.add_conditional_edges(
        "critique",
        route_after_critique,
        {"output_guard": "output_guard", "research": "research"},
    )
    graph.add_edge("output_guard", END)

    return graph.compile()


# Singleton — imported by the API route; None if langgraph not installed
try:
    agent_graph = build_graph()
    logger.info("Agent graph compiled successfully")
except Exception as e:
    logger.warning("Failed to build agent graph: %s — agent mode unavailable", e)
    agent_graph = None
