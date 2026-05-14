"""
Module 3 — Rate Limiting
Sliding window rate limiter backed by Redis.
Limits: requests per minute + tokens per day per user.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse


def get_user_id(request: Request) -> str:
    """Extract user identifier from API key header for per-user rate limiting."""
    return request.headers.get("X-API-Key", get_remote_address(request))


limiter = Limiter(key_func=get_user_id)


def setup_rate_limiter(app: FastAPI) -> None:
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "detail": str(exc.detail),
                "retry_after": "60s",
            },
        )


# Usage in route handlers:
#
#   from api.middleware.ratelimit import limiter
#
#   @router.post("/chat")
#   @limiter.limit("20/minute")        # 20 requests per minute per user
#   async def chat(request: Request, ...):
#       ...
#
# TODO: add a token-based daily budget limiter using Redis directly
# (slowapi only handles request counts, not token counts)
