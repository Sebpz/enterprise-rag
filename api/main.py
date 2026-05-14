"""
Module 3 — FastAPI Application
Entry point for the API server.
"""
from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from api.routes import chat, feedback, health
from api.middleware.auth import APIKeyMiddleware
from api.middleware.ratelimit import setup_rate_limiter

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Enterprise RAG Platform",
    description="ArXiv research assistant — RAG + Multi-Agent",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (allow Next.js frontend) ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth middleware ────────────────────────────────────────────────────────────
app.add_middleware(APIKeyMiddleware)

# ── Rate limiting ─────────────────────────────────────────────────────────────
setup_rate_limiter(app)

# ── Request timing middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
    return response

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(chat.router,     prefix="/v1")
app.include_router(feedback.router, prefix="/v1")

# ── Prometheus metrics endpoint ───────────────────────────────────────────────
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# ── Global error handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )

@app.on_event("startup")
async def startup():
    logger.info("🚀 Enterprise RAG Platform starting up")
    # TODO: initialise Qdrant client, warm up embedding model, connect to Postgres

@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down")
    # TODO: close DB connections, flush Langfuse queue
