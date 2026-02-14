"""
Rimuru Crypto Empire — Security Middleware
==========================================
API Key authentication, rate limiting, CORS, and request logging
for all microservices.

Every inbound request must carry:
    X-Rimuru-Key: <RIMURU_API_KEY>

Health endpoints are exempt (for Docker healthchecks and Prometheus).
Inter-service calls must also pass the key.
"""

import os
import time
import hashlib
import hmac
import logging
from collections import defaultdict
from typing import Optional, Set

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("rimuru.security")

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

RIMURU_API_KEY = os.getenv("RIMURU_API_KEY", "")
RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "120"))  # requests per minute
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# Paths that skip auth (healthchecks, metrics for Prometheus)
PUBLIC_PATHS: Set[str] = {
    "/health",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
}


# ─────────────────────────────────────────────
# API KEY AUTH MIDDLEWARE
# ─────────────────────────────────────────────

class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Validates X-Rimuru-Key header on every request.
    Skips public paths (health, metrics).
    Uses constant-time comparison to prevent timing attacks.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")

        # Allow public endpoints without auth
        if path in PUBLIC_PATHS or path == "":
            return await call_next(request)

        # If no API key is configured, deny everything (fail-closed)
        if not RIMURU_API_KEY:
            logger.error("RIMURU_API_KEY not set — blocking request to %s", path)
            return JSONResponse(
                status_code=503,
                content={"error": "service not configured — API key missing"}
            )

        # Extract and validate the key
        provided_key = request.headers.get("X-Rimuru-Key", "")
        if not provided_key:
            logger.warning("Unauthenticated request to %s from %s",
                           path, request.client.host if request.client else "unknown")
            return JSONResponse(
                status_code=401,
                content={"error": "missing X-Rimuru-Key header"}
            )

        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(provided_key, RIMURU_API_KEY):
            logger.warning("Invalid API key for %s from %s",
                           path, request.client.host if request.client else "unknown")
            return JSONResponse(
                status_code=403,
                content={"error": "invalid API key"}
            )

        return await call_next(request)


# ─────────────────────────────────────────────
# RATE LIMITER MIDDLEWARE
# ─────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP rate limiting using a sliding window.
    Returns 429 Too Many Requests when exceeded.
    """

    def __init__(self, app, max_rpm: int = 120):
        super().__init__(app)
        self.max_rpm = max_rpm
        self.requests: dict = defaultdict(list)  # ip -> [timestamps]

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")

        # Don't rate-limit health checks
        if path in PUBLIC_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60.0

        # Clean old entries and add current
        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if t > window_start
        ]
        self.requests[client_ip].append(now)

        if len(self.requests[client_ip]) > self.max_rpm:
            logger.warning("Rate limit exceeded for %s on %s (%d rpm)",
                           client_ip, path, len(self.requests[client_ip]))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate limit exceeded",
                    "limit": self.max_rpm,
                    "retry_after_seconds": 60
                },
                headers={"Retry-After": "60"}
            )

        return await call_next(request)


# ─────────────────────────────────────────────
# REQUEST LOGGING MIDDLEWARE
# ─────────────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs all non-health requests with timing."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")

        if path in PUBLIC_PATHS:
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000

        client_ip = request.client.host if request.client else "unknown"
        logger.info("%s %s %s → %d (%.1fms)",
                    client_ip, request.method, path,
                    response.status_code, duration_ms)

        return response


# ─────────────────────────────────────────────
# APPLY ALL SECURITY TO A FASTAPI APP
# ─────────────────────────────────────────────

def secure_app(app: FastAPI) -> FastAPI:
    """
    Call this once on each FastAPI app to apply:
      1. CORS restrictions
      2. API key authentication
      3. Rate limiting
      4. Request logging

    Usage:
        from shared.security import secure_app
        app = FastAPI(title="My Service")
        secure_app(app)
    """

    # 1. CORS — restrict to known origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["X-Rimuru-Key", "Content-Type"],
    )

    # 2. Request logging (outermost — runs first)
    app.add_middleware(RequestLoggingMiddleware)

    # 3. Rate limiting
    app.add_middleware(RateLimitMiddleware, max_rpm=RATE_LIMIT_RPM)

    # 4. API key auth (innermost — runs last, closest to route)
    app.add_middleware(APIKeyAuthMiddleware)

    logger.info("Security middleware applied — auth=%s, rate_limit=%d rpm, cors=%s",
                "ENABLED" if RIMURU_API_KEY else "DISABLED",
                RATE_LIMIT_RPM,
                ALLOWED_ORIGINS)

    return app


# ─────────────────────────────────────────────
# HELPER: Add auth header to inter-service calls
# ─────────────────────────────────────────────

def get_auth_headers() -> dict:
    """Returns headers dict with the API key for inter-service calls."""
    if RIMURU_API_KEY:
        return {"X-Rimuru-Key": RIMURU_API_KEY}
    return {}


def authenticated_request(url: str, data: Optional[dict] = None,
                          method: str = "GET", timeout: int = 15) -> dict:
    """
    Make an authenticated HTTP request to another Rimuru service.
    Automatically injects X-Rimuru-Key header.
    """
    import json as _json
    from urllib.request import Request, urlopen

    headers = {"Content-Type": "application/json"}
    headers.update(get_auth_headers())

    if data is not None:
        body = _json.dumps(data).encode()
        req = Request(url, data=body, headers=headers, method=method or "POST")
    else:
        req = Request(url, headers=headers, method=method)

    try:
        with urlopen(req, timeout=timeout) as resp:
            return _json.loads(resp.read().decode())
    except Exception as e:
        logger.error("Service call failed: %s %s — %s", method, url, e)
        raise
