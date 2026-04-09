import html
import time
from collections import defaultdict

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


# Simple in-memory rate limiter (good enough for single-process)
_rate_store = defaultdict(list)

def is_rate_limited(key, limit=60, window=60):
    now = time.time()
    timestamps = _rate_store[key]
    # remove old entries
    _rate_store[key] = [t for t in timestamps if now - t < window]
    if len(_rate_store[key]) >= limit:
        return True
    _rate_store[key].append(now)
    return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit public/auth endpoints more strictly."""

    AUTH_PATHS = {"/api/auth/login", "/api/auth/register"}
    PORTAL_PREFIX = "/api/portal"
    WIDGET_PREFIX = "/api/widget"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        ip = request.client.host if request.client else "unknown"

        # strict limit for auth endpoints: 10 req/min per IP
        if path in self.AUTH_PATHS:
            if is_rate_limited(f"auth:{ip}", limit=10, window=60):
                return JSONResponse({"detail": "Too many requests"}, status_code=429)

        # moderate limit for portal/widget: 30 req/min per IP
        elif path.startswith(self.PORTAL_PREFIX) or path.startswith(self.WIDGET_PREFIX):
            if is_rate_limited(f"public:{ip}", limit=30, window=60):
                return JSONResponse({"detail": "Too many requests"}, status_code=429)

        return await call_next(request)


def sanitize(text):
    """Escape HTML to prevent XSS when rendering user content."""
    if not text:
        return text
    return html.escape(str(text))
