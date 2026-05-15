"""
Module 3 — Rate Limiting
Sliding window rate limiter backed by Redis.
Limits: requests per minute + tokens per day per user.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import redis.asyncio
from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


DAILY_TOKEN_LIMIT = int(os.getenv("DAILY_TOKEN_LIMIT", "100000"))
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE", "20"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def get_user_id(request: Request) -> str:
    """Extract user identifier from API key header for per-user rate limiting."""
    return request.headers.get("X-API-Key", get_remote_address(request))


limiter = Limiter(key_func=get_user_id)

_redis_client: redis.asyncio.Redis | None = None


async def _get_redis() -> redis.asyncio.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.asyncio.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _token_key(user_id: str) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"token_budget:{user_id}:{date_str}"


async def get_token_usage(user_id: str) -> int:
    """Return how many tokens user has used today. Returns 0 if Redis unavailable."""
    try:
        client = await _get_redis()
        value = await client.get(_token_key(user_id))
        return int(value) if value is not None else 0
    except Exception:
        return 0


async def check_token_budget(user_id: str) -> tuple[bool, int]:
    """
    Returns (allowed, current_usage).
    allowed=True if usage < DAILY_TOKEN_LIMIT. Fails open if Redis is down.
    """
    try:
        usage = await get_token_usage(user_id)
        return usage < DAILY_TOKEN_LIMIT, usage
    except Exception:
        return True, 0


async def record_tokens(user_id: str, tokens_used: int) -> int:
    """
    Increment the user's token counter. Returns new total.
    Creates key with TTL=86400 on first use. Fails silently if Redis unavailable.
    """
    try:
        client = await _get_redis()
        key = _token_key(user_id)
        new_total = await client.incrby(key, tokens_used)
        await client.expire(key, 86400)
        return new_total
    except Exception:
        return 0


class TokenBudgetMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id = get_user_id(request)

        try:
            allowed, current_usage = await check_token_budget(user_id)
        except Exception:
            allowed, current_usage = True, 0

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Daily token budget exceeded",
                    "detail": f"You have used {current_usage} of {DAILY_TOKEN_LIMIT} tokens today.",
                    "current_usage": current_usage,
                    "limit": DAILY_TOKEN_LIMIT,
                    "retry_after": "tomorrow",
                },
            )

        response = await call_next(request)

        # Don't mutate headers on streaming SSE responses — they're already sent.
        if "text/event-stream" not in response.headers.get("content-type", ""):
            response.headers["X-Daily-Tokens-Used"] = str(current_usage)
            response.headers["X-Daily-Token-Limit"] = str(DAILY_TOKEN_LIMIT)
        return response


async def close_redis() -> None:
    """Close the Redis connection pool. Call from FastAPI lifespan shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def setup_rate_limiter(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_middleware(TokenBudgetMiddleware)

    @app.on_event("shutdown")
    async def _shutdown_redis():
        await close_redis()

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
