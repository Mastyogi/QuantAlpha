"""
FastAPI Middleware Stack
========================
Production-grade middleware for the trading bot API.

Middleware (applied in order):
  1. SecurityHeadersMiddleware — CSP, HSTS, X-Frame-Options
  2. CORSMiddleware            — Controlled cross-origin access
  3. RateLimitMiddleware       — Per-IP rate limiting
  4. APIKeyMiddleware          — Optional API key auth for /api/* routes
  5. RequestLoggingMiddleware  — Structured request/response logging
  6. MetricsMiddleware         — Prometheus request counters + latency
"""
from __future__ import annotations

import time
import hashlib
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Optional

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ── Security Headers ──────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    HEADERS = {
        "X-Content-Type-Options":    "nosniff",
        "X-Frame-Options":           "DENY",
        "X-XSS-Protection":          "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy":           "strict-origin-when-cross-origin",
        "Permissions-Policy":        "geolocation=(), microphone=(), camera=()",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        for header, value in self.HEADERS.items():
            response.headers[header] = value
        return response


# ── Rate Limiting ─────────────────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP sliding window rate limiter.
    Defaults: 60 requests/minute per IP.
    Tighter limit on /api/* routes: 30 requests/minute.
    """

    def __init__(
        self,
        app: ASGIApp,
        default_limit: int = 60,
        api_limit: int = 30,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.default_limit  = default_limit
        self.api_limit      = api_limit
        self.window         = window_seconds
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ("/health", "/metrics"):
            return await call_next(request)

        client_ip  = self._get_client_ip(request)
        is_api     = request.url.path.startswith("/api")
        limit      = self.api_limit if is_api else self.default_limit
        bucket_key = f"{client_ip}:{request.url.path.split('/')[1]}"

        now     = time.monotonic()
        bucket  = self._buckets[bucket_key]

        # Remove requests outside the window
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = int(self.window - (now - bucket[0]))
            logger.warning(f"Rate limit exceeded: {client_ip} on {request.url.path}")
            return JSONResponse(
                status_code = 429,
                content     = {"error": "Rate limit exceeded", "retry_after": retry_after},
                headers     = {"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"]     = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(limit - len(bucket))
        response.headers["X-RateLimit-Reset"]     = str(int(now + self.window))
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract real IP, respecting X-Forwarded-For (from nginx)."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# ── API Key Authentication ────────────────────────────────────────────────────

class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Optional API key auth for /api/* routes.
    Set API_KEY env var to enable. If not set, skip auth.
    """

    PUBLIC_PATHS = {"/health", "/metrics", "/docs", "/openapi.json"}

    def __init__(self, app: ASGIApp, api_key: Optional[str] = None):
        super().__init__(app)
        self._api_key = api_key
        if api_key:
            # Store hashed key for comparison
            self._key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        else:
            self._key_hash = None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip if API key not configured
        if not self._api_key:
            return await call_next(request)

        # Skip public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Only enforce on /api/* routes
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        # Check key in header or query param
        provided = (
            request.headers.get("X-API-Key")
            or request.query_params.get("api_key")
        )

        if not provided:
            return JSONResponse(
                status_code = 401,
                content     = {"error": "API key required. Pass X-API-Key header."},
            )

        provided_hash = hashlib.sha256(provided.encode()).hexdigest()
        if provided_hash != self._key_hash:
            logger.warning(f"Invalid API key attempt from {request.client}")
            return JSONResponse(
                status_code = 403,
                content     = {"error": "Invalid API key"},
            )

        return await call_next(request)


# ── Request Logging ───────────────────────────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Structured logging of all API requests with latency."""

    SKIP_PATHS = {"/health", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start   = time.monotonic()
        method  = request.method
        path    = request.url.path
        client  = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
            latency_ms = (time.monotonic() - start) * 1000
            logger.info(
                f"API {method} {path} → {response.status_code} "
                f"({latency_ms:.1f}ms) [{client}]"
            )
            response.headers["X-Response-Time"] = f"{latency_ms:.1f}ms"
            return response

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            logger.error(f"API {method} {path} → 500 ({latency_ms:.1f}ms): {e}")
            return JSONResponse(
                status_code = 500,
                content     = {"error": "Internal server error"},
            )


# ── Metrics Middleware ────────────────────────────────────────────────────────

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Collect Prometheus metrics: request count, latency histogram.
    Metrics exposed at GET /metrics.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._request_counts: Dict[str, int]   = defaultdict(int)
        self._latencies: Dict[str, list]        = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start    = time.monotonic()
        path     = request.url.path
        method   = request.method

        response = await call_next(request)

        latency  = (time.monotonic() - start) * 1000
        key      = f"{method}:{path}:{response.status_code}"
        self._request_counts[key] += 1
        lats = self._latencies[path]
        lats.append(latency)
        if len(lats) > 1000:  # Keep last 1000 per path
            self._latencies[path] = lats[-1000:]

        return response

    def get_metrics(self) -> dict:
        metrics = {}
        for key, count in self._request_counts.items():
            metrics[f"requests_total_{key}"] = count
        for path, lats in self._latencies.items():
            if lats:
                metrics[f"latency_p99_{path}"] = sorted(lats)[int(len(lats) * 0.99)]
                metrics[f"latency_avg_{path}"] = sum(lats) / len(lats)
        return metrics


# ── Setup Helper ──────────────────────────────────────────────────────────────

def setup_middleware(app, api_key: Optional[str] = None, allowed_origins: Optional[list] = None):
    """
    Apply all middleware to a FastAPI app.
    Call this in your app factory: setup_middleware(app)
    """
    origins = allowed_origins or [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins     = origins,
        allow_credentials = True,
        allow_methods     = ["GET", "POST", "OPTIONS"],
        allow_headers     = ["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    if api_key:
        app.add_middleware(APIKeyMiddleware, api_key=api_key)

    logger.info("API middleware stack configured")
    return app
