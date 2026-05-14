"""Feedback endpoint — captures thumbs up/down from the frontend."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["feedback"])


class FeedbackRequest(BaseModel):
    trace_id: str
    rating: int        # 1 = thumbs up, -1 = thumbs down
    comment: str | None = None


@router.post("/feedback", status_code=201)
async def submit_feedback(body: FeedbackRequest):
    """
    Store user feedback for a conversation.
    TODO: write to Postgres feedback table.
    """
    # TODO: INSERT INTO feedback (trace_id, rating, comment) VALUES (...)
    return {"status": "received", "trace_id": body.trace_id}
