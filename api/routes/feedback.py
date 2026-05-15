"""Feedback endpoint — captures thumbs up/down from the frontend."""
from __future__ import annotations

import logging
import os

import asyncpg
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["feedback"])

_DB_URL = os.getenv("DATABASE_URL", "postgresql://raguser:ragpass@localhost:5432/ragdb")


class FeedbackRequest(BaseModel):
    trace_id: str
    rating: int        # 1 = thumbs up, -1 = thumbs down
    comment: str | None = None


@router.post("/feedback", status_code=201)
async def submit_feedback(body: FeedbackRequest):
    """Store user feedback for a conversation in Postgres."""
    conn = None
    try:
        conn = await asyncpg.connect(_DB_URL, timeout=5.0)
        await conn.execute(
            "INSERT INTO feedback (trace_id, rating, comment) VALUES ($1, $2, $3)",
            body.trace_id,
            body.rating,
            body.comment,
        )
    except Exception as e:
        logger.warning("Failed to persist feedback for trace %s: %s", body.trace_id, e)
    finally:
        if conn is not None:
            await conn.close()
    return {"status": "received", "trace_id": body.trace_id}
