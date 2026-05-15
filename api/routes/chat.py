"""
Module 3 — Chat Route
Main RAG and agent query endpoint with SSE streaming.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


# ── Request / Response models ─────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    mode: Literal["rag", "agent"] = "rag"
    filters: dict | None = None        # e.g. {"category": "cs.AI", "year": 2023}
    stream: bool = True
    prompt_version: str = "v2"         # which Jinja2 template to use


class ChatResponse(BaseModel):
    trace_id: str
    answer: str
    citations: list[dict]
    latency_ms: float
    mode: str


# ── Streaming SSE helper ──────────────────────────────────────────────────────
def sse_event(data: dict) -> str:
    """Format a dict as a Server-Sent Events message."""
    return f"data: {json.dumps(data)}\n\n"


# ── Pipeline singletons ───────────────────────────────────────────────────────
_rag_pipeline = None
_guardrail_pipeline = None


def get_rag_pipeline():
    global _rag_pipeline
    if _rag_pipeline is None:
        from rag.pipeline import RAGPipeline
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


def get_guardrail_pipeline():
    global _guardrail_pipeline
    if _guardrail_pipeline is None:
        from guardrails.pipeline import GuardrailPipeline
        _guardrail_pipeline = GuardrailPipeline()
    return _guardrail_pipeline


# ── Conversation logging ──────────────────────────────────────────────────────
async def _log_conversation(
    trace_id: str, user_id: str, query: str, mode: str, response: str, citations: list
) -> None:
    import os
    import asyncpg
    try:
        conn = await asyncpg.connect(
            os.getenv("DATABASE_URL", "postgresql://raguser:ragpass@localhost:5432/ragdb")
        )
        try:
            await conn.execute(
                "INSERT INTO conversations(trace_id,user_id,query,mode,response,citations) "
                "VALUES($1,$2,$3,$4,$5,$6)",
                trace_id, user_id, query, mode, response, json.dumps(citations),
            )
        finally:
            await conn.close()
    except Exception as e:
        logger.warning("Failed to log conversation: %s", e)


# ── Streaming generators ──────────────────────────────────────────────────────
_CITATION_SENTINEL = "\x00CITATIONS\x00"


async def stream_rag_response(request: ChatRequest, trace_id: str):
    """
    Generator that yields SSE events for a RAG query.

    Event types:
        {"type": "token",     "content": "..."}   — each LLM token
        {"type": "citations", "data": [...]}       — after generation completes
        {"type": "done",      "trace_id": "..."}   — signals stream end
        {"type": "error",     "detail": "..."}     — on failure
    """
    guardrails = get_guardrail_pipeline()
    rag = get_rag_pipeline()

    # 1. Input guardrails
    input_result = await guardrails.check_input(request.query, trace_id)
    if not input_result.passed:
        yield sse_event({"type": "error", "detail": f"Blocked: {input_result.blocked_by}"})
        return

    # 2. Stream RAG — detect citation sentinel in the token stream
    full_answer: list[str] = []
    citations: list[dict] = []

    try:
        async for token in rag.stream(request.query, request.filters):
            if token.startswith(_CITATION_SENTINEL):
                citations = json.loads(token[len(_CITATION_SENTINEL):])
            else:
                full_answer.append(token)
                yield sse_event({"type": "token", "content": token})
    except Exception as e:
        logger.exception("RAG stream error: %s", e)
        yield sse_event({"type": "error", "detail": str(e)})
        return

    answer_text = "".join(full_answer)

    # 3. Output guardrails — runs after streaming; client should handle trailing error
    output_result = await guardrails.check_output(answer_text, citations, trace_id)
    if not output_result.passed:
        yield sse_event({"type": "error", "detail": f"Output blocked: {output_result.blocked_by}"})
        return

    # 4. Citations + done
    yield sse_event({"type": "citations", "data": citations})
    yield sse_event({"type": "done", "trace_id": trace_id})

    # 5. Persist conversation (non-blocking)
    await _log_conversation(
        trace_id=trace_id, user_id="", query=request.query,
        mode="rag", response=answer_text, citations=citations,
    )


async def stream_agent_response(request: ChatRequest, trace_id: str):
    """
    Generator for a LangGraph multi-agent query.

    Additional event types beyond RAG:
        {"type": "agent_step", "node": "orchestrator", "output": "..."}
        {"type": "tool_call",  "tool": "rag_search",   "query": "..."}
    """
    guardrails = get_guardrail_pipeline()

    # 1. Input guardrails
    input_result = await guardrails.check_input(request.query, trace_id)
    if not input_result.passed:
        yield sse_event({"type": "error", "detail": f"Blocked: {input_result.blocked_by}"})
        return

    # 2. Check if agent graph is available; fall back to RAG if not
    try:
        from agents.graph import agent_graph
    except ImportError:
        agent_graph = None

    if agent_graph is None:
        async for event in stream_rag_response(request, trace_id):
            yield event
        return

    # 3. Stream agent graph
    try:
        async for chunk in agent_graph.astream(
            {"query": request.query, "trace_id": trace_id, "user_id": ""},
            config={"recursion_limit": 10},
        ):
            for node_name, node_output in chunk.items():
                if "draft_answer" in node_output:
                    yield sse_event({
                        "type": "agent_step",
                        "node": node_name,
                        "output": node_output.get("draft_answer", ""),
                    })
                if "final_answer" in node_output:
                    yield sse_event({"type": "token", "content": node_output["final_answer"]})
                if "citations" in node_output:
                    yield sse_event({"type": "citations", "data": node_output["citations"]})
    except Exception as e:
        logger.exception("Agent stream error: %s", e)
        yield sse_event({"type": "error", "detail": str(e)})
        return

    yield sse_event({"type": "done", "trace_id": trace_id})


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main query endpoint. Supports both RAG and multi-agent modes.
    Returns a streaming SSE response when request.stream=True.
    """
    import uuid
    trace_id = str(uuid.uuid4())

    if request.stream:
        generator = (
            stream_agent_response(request, trace_id)
            if request.mode == "agent"
            else stream_rag_response(request, trace_id)
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Trace-ID": trace_id,
            },
        )

    # Non-streaming path (used by eval framework)
    t0 = time.perf_counter()
    guardrails = get_guardrail_pipeline()
    rag = get_rag_pipeline()

    input_result = await guardrails.check_input(request.query, trace_id)
    if not input_result.passed:
        raise HTTPException(
            status_code=400,
            detail=f"Query blocked by guardrails: {input_result.blocked_by}",
        )

    rag_response = await rag.query(request.query, request.filters)

    output_result = await guardrails.check_output(
        rag_response.answer, rag_response.citations, trace_id
    )
    if not output_result.passed:
        raise HTTPException(
            status_code=400,
            detail=f"Response blocked by guardrails: {output_result.blocked_by}",
        )

    latency_ms = (time.perf_counter() - t0) * 1000

    await _log_conversation(
        trace_id=trace_id, user_id="", query=request.query,
        mode=request.mode, response=rag_response.answer, citations=rag_response.citations,
    )

    return ChatResponse(
        trace_id=trace_id,
        answer=rag_response.answer,
        citations=rag_response.citations,
        latency_ms=round(latency_ms, 1),
        mode=request.mode,
    )
