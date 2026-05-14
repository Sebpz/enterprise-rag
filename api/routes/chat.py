"""
Module 3 — Chat Route
Main RAG and agent query endpoint with SSE streaming.
"""
from __future__ import annotations

import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
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


async def stream_rag_response(request: ChatRequest, trace_id: str):
    """
    Generator that yields SSE events for a RAG query.

    Event types:
        {"type": "token",     "content": "..."}   — each LLM token
        {"type": "citations", "data": [...]}       — after generation completes
        {"type": "done",      "trace_id": "..."}   — signals stream end
        {"type": "error",     "detail": "..."}     — on failure
    """
    # TODO:
    # 1. Run input guardrails — if blocked, yield error event and return
    # 2. Call rag_pipeline.stream(request.query, request.filters)
    # 3. Yield each token as a "token" SSE event
    # 4. After stream ends, yield "citations" event
    # 5. Yield "done" event
    # 6. Log conversation to Postgres
    yield sse_event({"type": "error", "detail": "TODO: implement stream_rag_response"})


async def stream_agent_response(request: ChatRequest, trace_id: str):
    """
    Generator for a LangGraph multi-agent query.

    Additional event types beyond RAG:
        {"type": "agent_step", "node": "orchestrator", "output": "..."}
        {"type": "tool_call",  "tool": "rag_search",   "query": "..."}
    """
    # TODO:
    # 1. Run input guardrails
    # 2. Invoke agent graph: graph.astream({"query": request.query, "trace_id": trace_id})
    # 3. Yield intermediate step events so frontend can show agent progress
    # 4. Yield final answer tokens, citations, done
    yield sse_event({"type": "error", "detail": "TODO: implement stream_agent_response"})


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

    # Non-streaming fallback (used by eval framework)
    # TODO: implement non-streaming path
    raise HTTPException(status_code=501, detail="Non-streaming not yet implemented")
