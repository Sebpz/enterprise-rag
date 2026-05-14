"""
Module 3 — API Key Auth Middleware
Validates X-API-Key header on all non-public routes.
"""
from __future__ import annotations

import os

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Routes that don't require auth
PUBLIC_PATHS = {"/health", "/metrics", "/docs", "/redoc", "/openapi.json"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        valid_key = os.getenv("DEV_API_KEY", "dev-key-local")

        if not api_key or api_key != valid_key:
            return Response(
                content='{"error": "Invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)
