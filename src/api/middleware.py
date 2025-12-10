"""
FastAPI Middleware for CORS, rate limiting, and error handling
"""

import os
import time
import logging
from collections import defaultdict
from typing import Callable
from fastapi import Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Rate limit storage (in-memory, per IP)
_rate_limit_buckets: dict = defaultdict(lambda: {"count": 0, "reset_time": 0})


def reset_all_rate_limit_buckets():
    """Reset all rate limit buckets (for testing)"""
    global _rate_limit_buckets
    _rate_limit_buckets.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        # Per-endpoint limits
        self.endpoint_limits = {
            "/api/v1/research": 5,  # 5 requests per minute
            "/api/v1/status": 30,  # 30 requests per minute
            "/api/v1/report": 10,  # 10 requests per minute
            "/api/v1/review": 20,  # 20 requests per minute
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limits before processing request"""
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Get limit for this endpoint (default to general limit)
        limit = self.endpoint_limits.get(path, self.requests_per_minute)

        # Get or create bucket for this IP
        bucket = _rate_limit_buckets[f"{client_ip}:{path}"]
        current_time = time.time()

        # Reset if time window expired
        if current_time >= bucket["reset_time"]:
            bucket["count"] = 0
            bucket["reset_time"] = current_time + 60  # 1 minute window

        # Check if limit exceeded
        if bucket["count"] >= limit:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Maximum {limit} requests per minute for this endpoint",
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(int(bucket["reset_time"] - current_time)),
                },
            )

        # Increment counter
        bucket["count"] += 1

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(limit - bucket["count"])

        return response


def get_cors_middleware_config():
    """Get CORS middleware configuration"""
    import os

    app_env = os.getenv("APP_ENV", "development")

    if app_env == "production":
        # In production, specify allowed origins
        allowed_origins = os.getenv("CORS_ORIGINS", "").split(",")
        if not allowed_origins or allowed_origins == [""]:
            allowed_origins = ["https://yourdomain.com"]
    else:
        # In development, allow all origins
        allowed_origins = ["*"]

    return {
        "allow_origins": allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


def setup_cors_middleware(app):
    """Setup CORS middleware on FastAPI app"""
    config = get_cors_middleware_config()
    app.add_middleware(CORSMiddleware, **config)
    logger.info(
        f"CORS middleware configured for environment: {os.getenv('APP_ENV', 'development')}"
    )


def setup_rate_limit_middleware(app):
    """Setup rate limiting middleware on FastAPI app"""
    app.add_middleware(RateLimitMiddleware)
    logger.info("Rate limiting middleware configured")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handling middleware"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle errors globally"""
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.exception(f"Unhandled error in {request.url.path}: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal server error",
                    "detail": str(e)
                    if os.getenv("DEBUG") == "true"
                    else "An unexpected error occurred",
                },
            )


def setup_error_handler_middleware(app):
    """Setup error handling middleware on FastAPI app"""
    app.add_middleware(ErrorHandlerMiddleware)
    logger.info("Error handling middleware configured")
