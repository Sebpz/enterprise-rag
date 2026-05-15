"""Health check endpoints — used by Docker, load balancers, and Kubernetes probes."""
import asyncio
import os
import re
import time

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://raguser:ragpass@localhost:5432/ragdb")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "arxiv_papers")

_REQUIRED_PG_TABLES = ("conversations", "guardrail_events", "eval_runs")
_CHECK_TIMEOUT_S = 5.0


def _sanitize_url(url: str) -> str:
    """Strip credentials (user:password@) from a connection URL for safe logging."""
    return re.sub(r"://[^@]*@", "://***@", url)


class HealthResponse(BaseModel):
    status: str    # "ok" if all pass, "degraded" if any fail
    services: dict  # {name: {"status": "ok"|"error"|"timeout", "latency_ms": float, ...}}


async def _check_qdrant() -> dict:
    client = None
    start = time.perf_counter()
    try:
        from qdrant_client import AsyncQdrantClient
        client = AsyncQdrantClient(url=QDRANT_URL)
        collection = await client.get_collection(QDRANT_COLLECTION)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "ok",
            "latency_ms": latency_ms,
            "vectors_count": collection.vectors_count,
            "url": _sanitize_url(QDRANT_URL),
        }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e),
            "url": _sanitize_url(QDRANT_URL),
        }
    finally:
        if client is not None:
            await client.close()


async def _check_postgres() -> dict:
    conn = None
    start = time.perf_counter()
    try:
        import asyncpg
        conn = await asyncpg.connect(DATABASE_URL)
        tables_found = await conn.fetchval(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = ANY($1::text[])",
            list(_REQUIRED_PG_TABLES),
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "ok",
            "latency_ms": latency_ms,
            "tables_found": int(tables_found),
            "url": _sanitize_url(DATABASE_URL),
        }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e),
            "url": _sanitize_url(DATABASE_URL),
        }
    finally:
        if conn is not None:
            await conn.close()


async def _check_redis() -> dict:
    client = None
    start = time.perf_counter()
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(REDIS_URL)
        await client.ping()
        info = await client.info("server")
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "ok",
            "latency_ms": latency_ms,
            "redis_version": info.get("redis_version"),
            "url": _sanitize_url(REDIS_URL),
        }
    except Exception as e:
        return {
            "status": "error",
            "detail": str(e),
            "url": _sanitize_url(REDIS_URL),
        }
    finally:
        if client is not None:
            await client.close()


async def _timed(coro, timeout: float = _CHECK_TIMEOUT_S) -> dict:
    """Run coro with a hard timeout; returns a timeout sentinel dict on expiry."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        return {"status": "timeout", "latency_ms": round(timeout * 1000)}


@router.get("/health/live")
async def liveness():
    """
    Kubernetes liveness probe — returns 200 immediately without checking
    any external dependencies. The pod should only be restarted if this
    endpoint is unreachable, not because Qdrant or Postgres is slow.
    """
    return {"status": "ok"}


@router.get("/health", response_model=HealthResponse)
async def health():
    """
    Readiness probe. Checks all dependencies in parallel (5-second timeout
    per service). Returns status="degraded" if any service is unreachable.
    """
    qdrant_result, postgres_result, redis_result = await asyncio.gather(
        _timed(_check_qdrant()),
        _timed(_check_postgres()),
        _timed(_check_redis()),
        return_exceptions=True,
    )

    def _coerce(result) -> dict:
        if isinstance(result, Exception):
            return {"status": "error", "detail": str(result)}
        return result

    services = {
        "qdrant": _coerce(qdrant_result),
        "postgres": _coerce(postgres_result),
        "redis": _coerce(redis_result),
    }
    overall = "ok" if all(s.get("status") == "ok" for s in services.values()) else "degraded"
    return HealthResponse(status=overall, services=services)
