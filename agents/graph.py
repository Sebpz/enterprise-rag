"""
Module 7 — LangGraph Multi-Agent System
Orchestrator → routes to Retrieval Agent or Research Agent → Critique Agent → output.

Graph:
    input_guard → orchestrator → [retrieval | research → critique loop] → output_guard → END
"""
from __future__ import annotations

import asyncio
import logging
import operator
from typing import Annotated, TypedDict

logger = logging.getLogger(__name__)

# TODO: pip install langgraph
# from langgraph.graph import StateGraph, END
# from langgraph.checkpoint.postgres import PostgresSaver


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


# ── Node implementations (stubs) ──────────────────────────────────────────────

async def input_guardrail_node(state: AgentState) -> dict:
    """
    Run input guardrails on the user query.
    If blocked, set guardrail_status="blocked" and route="blocked".

    TODO: call guardrails.pipeline.GuardrailPipeline().check_input()
    """
    return {"guardrail_status": "pass", "route": "pending"}


async def orchestrator_node(state: AgentState) -> dict:
    """
    Classify query complexity and decompose if needed.

    TODO: Prompt the LLM with the query and ask:
    1. Is this a simple factual question (single retrieval) or complex (multi-step)?
    2. If complex, decompose into 2-4 sub-queries.

    Return {"route": "simple" | "complex", "sub_queries": [...]}
    """
    raise NotImplementedError("TODO: implement orchestrator_node")


async def retrieval_node(state: AgentState) -> dict:
    """
    Simple path: single RAG call for the original query.

    TODO: call rag.pipeline.RAGPipeline().query(state["query"])
    Append results to retrieved_contexts.
    """
    raise NotImplementedError("TODO: implement retrieval_node")


async def research_node(state: AgentState) -> dict:
    """
    Complex path: fan out sub-queries in parallel, aggregate results.

    TODO:
    1. Check budget: if total_tokens_used > BUDGET_LIMIT_TOKENS, set blocked
    2. Run all sub-queries concurrently with asyncio.gather
    3. Aggregate retrieved_contexts
    4. Generate a draft_answer synthesising all contexts
    """
    raise NotImplementedError("TODO: implement research_node")


async def critique_node(state: AgentState) -> dict:
    """
    Review the draft answer for completeness and accuracy.

    TODO: Prompt an LLM:
    "Review this answer against the question and contexts.
     Is it complete? Are there important gaps?
     If gaps exist, list the specific follow-up questions needed.
     If complete, respond with exactly: SATISFIED"

    If SATISFIED → set critique="SATISFIED"
    If gaps → set critique=<follow-up questions> and update sub_queries
    Increment critique_iterations.
    """
    raise NotImplementedError("TODO: implement critique_node")


async def output_guardrail_node(state: AgentState) -> dict:
    """
    Run output guardrails on the final answer.

    TODO: call guardrails.pipeline.GuardrailPipeline().check_output()
    Also format citations cleanly.
    """
    raise NotImplementedError("TODO: implement output_guardrail_node")


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_orchestrator(state: AgentState) -> str:
    """Conditional edge: where does the orchestrator route us?"""
    if state.get("guardrail_status") == "blocked":
        return "END"
    return state.get("route", "simple")


def route_after_critique(state: AgentState) -> str:
    """Continue the critique loop or exit?"""
    if state.get("critique") == "SATISFIED":
        return "output_guard"
    if state.get("critique_iterations", 0) >= MAX_ITERATIONS:
        logger.warning("Max critique iterations reached — forcing exit")
        return "output_guard"
    return "research"   # loop back


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph():
    """
    Assemble and compile the LangGraph state graph.

    TODO: uncomment once langgraph is installed and nodes are implemented.
    """
    # graph = StateGraph(AgentState)

    # graph.add_node("input_guard",   input_guardrail_node)
    # graph.add_node("orchestrator",  orchestrator_node)
    # graph.add_node("retrieval",     retrieval_node)
    # graph.add_node("research",      research_node)
    # graph.add_node("critique",      critique_node)
    # graph.add_node("output_guard",  output_guardrail_node)

    # graph.set_entry_point("input_guard")
    # graph.add_edge("input_guard", "orchestrator")
    # graph.add_conditional_edges("orchestrator", route_after_orchestrator, {
    #     "simple":  "retrieval",
    #     "complex": "research",
    #     "END":     END,
    # })
    # graph.add_edge("retrieval", "output_guard")
    # graph.add_edge("research",  "critique")
    # graph.add_conditional_edges("critique", route_after_critique, {
    #     "output_guard": "output_guard",
    #     "research":     "research",
    # })
    # graph.add_edge("output_guard", END)

    # # Optional: persist state to Postgres so conversations can be resumed
    # checkpointer = PostgresSaver.from_conn_string(settings.DATABASE_URL)
    # return graph.compile(checkpointer=checkpointer)

    raise NotImplementedError("TODO: implement build_graph — uncomment above once nodes are ready")


# Singleton — imported by the API route
agent_graph = None   # set to build_graph() once implemented
