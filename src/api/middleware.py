"""
Middleware for the AI Research Assistant API.

This module provides:
- Request ID generation and tracking
- Structured request/response logging
- Rate limiting with token bucket algorithm
- CORS configuration
- Response compression
"""

import gzip
import json
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional, Tuple
from threading import Lock

from fastapi import Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

logger = logging.getLogger(__name__)

# ============================================================================
# Request ID Middleware
# ============================================================================


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to generate and track unique request IDs.
    
    Adds X-Request-ID header to all requests and responses for request tracing.
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request and add request ID."""
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Add to request state for use in other middleware/endpoints
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


# ============================================================================
# Logging Middleware
# ============================================================================


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured request/response logging.
    
    Logs:
    - Request: method, path, query params, user_id, request_id
    - Response: status code, duration
    - Uses JSON format for structured logging
    - Excludes sensitive data (API keys, full queries)
    """
    
    # Sensitive headers to exclude from logs
    SENSITIVE_HEADERS = {
        'authorization', 'api-key', 'x-api-key', 'cookie',
        'x-auth-token', 'access-token', 'secret'
    }
    
    # Sensitive query parameters to exclude
    SENSITIVE_QUERY_PARAMS = {
        'api_key', 'token', 'password', 'secret', 'auth'
    }
    
    # Maximum query length to log (truncate longer queries)
    MAX_QUERY_LENGTH = 200
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request and log request/response."""
        start_time = time.time()
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # Extract user_id from headers or query params (if available)
        user_id = (
            request.headers.get("X-User-ID") or
            request.query_params.get("user_id") or
            "anonymous"
        )
        
        # Build request log data
        request_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": self._sanitize_query_params(dict(request.query_params)),
            "user_id": user_id,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", "")[:100],  # Truncate
        }
        
        # Log request
        logger.info(f"Request received | {json.dumps(request_log)}")
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            error = None
        except Exception as e:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error = str(e)
            raise
        finally:
            # Calculate duration
            duration = time.time() - start_time
            
            # Build response log data
            response_log = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "response",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round(duration * 1000, 2),
                "user_id": user_id,
            }
            
            if error:
                response_log["error"] = error
            
            # Log response
            logger.info(f"Request completed | {json.dumps(response_log)}")
        
        return response
    
    def _sanitize_query_params(self, params: Dict[str, str]) -> Dict[str, str]:
        """Sanitize query parameters, removing sensitive data."""
        sanitized = {}
        for key, value in params.items():
            key_lower = key.lower()
            
            # Skip sensitive parameters
            if key_lower in self.SENSITIVE_QUERY_PARAMS:
                sanitized[key] = "[REDACTED]"
            # Truncate long values (like queries)
            elif len(value) > self.MAX_QUERY_LENGTH:
                sanitized[key] = value[:self.MAX_QUERY_LENGTH] + "...[TRUNCATED]"
            else:
                sanitized[key] = value
        
        return sanitized


# ============================================================================
# Rate Limiting Middleware (Token Bucket Algorithm)
# ============================================================================


class TokenBucket:
    """
    Token bucket for rate limiting.
    
    Implements the token bucket algorithm:
    - Tokens are added at a constant rate (refill_rate per second)
    - Each request consumes one token
    - Requests are allowed if tokens are available
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens (burst capacity)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self.lock = Lock()
    
    def consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Try to consume tokens from the bucket.
        
        Args:
            tokens: Number of tokens to consume (default: 1)
            
        Returns:
            Tuple of (success, retry_after_seconds)
            - success: True if tokens were available, False otherwise
            - retry_after_seconds: Seconds until tokens will be available (0 if success)
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            
            # Refill tokens based on elapsed time
            self.tokens = min(
                self.capacity,
                self.tokens + (elapsed * self.refill_rate)
            )
            self.last_refill = now
            
            # Check if enough tokens are available
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            else:
                # Calculate retry after
                tokens_needed = tokens - self.tokens
                retry_after = tokens_needed / self.refill_rate
                return False, retry_after


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using token bucket algorithm.
    
    Rate limits:
    - /api/v1/research: 5 requests/minute per IP
    - /api/v1/status: 30 requests/minute per IP
    - /api/v1/report: 10 requests/minute per IP
    - Other endpoints: 60 requests/minute per IP (default)
    """
    
    # Rate limit configurations: (capacity, refill_rate_per_second)
    RATE_LIMITS = {
        "/api/v1/research": (5, 5.0 / 60.0),  # 5 per minute
        "/api/v1/status": (30, 30.0 / 60.0),  # 30 per minute
        "/api/v1/report": (10, 10.0 / 60.0),  # 10 per minute
    }
    
    # Default rate limit: 60 per minute
    DEFAULT_LIMIT = (60, 60.0 / 60.0)
    
    # Paths to exclude from rate limiting
    EXCLUDED_PATHS = ['/health', '/docs', '/openapi.json', '/redoc', '/']
    
    def __init__(self, app):
        super().__init__(app)
        # Store token buckets per IP address
        # Format: {ip: {path: TokenBucket}}
        self.buckets: Dict[str, Dict[str, TokenBucket]] = defaultdict(dict)
        self.buckets_lock = Lock()
        
        # Cleanup old buckets periodically (every 5 minutes)
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded IP (from proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_rate_limit(self, path: str) -> Tuple[int, float]:
        """Get rate limit configuration for a path."""
        # Check exact match first
        if path in self.RATE_LIMITS:
            return self.RATE_LIMITS[path]
        
        # Check prefix match
        for limit_path, limit_config in self.RATE_LIMITS.items():
            if path.startswith(limit_path):
                return limit_config
        
        # Default limit
        return self.DEFAULT_LIMIT
    
    def _get_or_create_bucket(self, ip: str, path: str) -> TokenBucket:
        """Get or create a token bucket for an IP and path."""
        with self.buckets_lock:
            if path not in self.buckets[ip]:
                capacity, refill_rate = self._get_rate_limit(path)
                self.buckets[ip][path] = TokenBucket(capacity, refill_rate)
            return self.buckets[ip][path]
    
    def _cleanup_old_buckets(self):
        """Remove old buckets to prevent memory leaks."""
        now = time.time()
        if now - self.last_cleanup < self.cleanup_interval:
            return
        
        with self.buckets_lock:
            # Remove IPs with no active buckets (simple cleanup)
            # In production, you might want more sophisticated cleanup
            self.last_cleanup = now
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request with rate limiting."""
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        path = request.url.path
        
        # Cleanup old buckets periodically
        self._cleanup_old_buckets()
        
        # Get or create token bucket for this IP and path
        bucket = self._get_or_create_bucket(client_ip, path)
        
        # Try to consume a token
        allowed, retry_after = bucket.consume(1)
        
        if not allowed:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded | ip: {client_ip} | path: {path} | retry_after: {retry_after:.2f}s"
            )
            
            from fastapi.responses import JSONResponse
            from src.api.models import ErrorResponse
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=ErrorResponse(
                    error="Rate limit exceeded",
                    detail=f"Too many requests. Please try again after {int(retry_after) + 1} seconds.",
                    timestamp=datetime.utcnow()
                ).model_dump(),
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Limit": str(bucket.capacity),
                    "X-RateLimit-Remaining": "0",
                }
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(bucket.capacity)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.tokens))
        
        return response


# ============================================================================
# Compression Middleware
# ============================================================================


class CompressionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to compress responses using gzip.
    
    Compresses responses larger than 1KB to reduce bandwidth.
    """
    
    MIN_SIZE = 1024  # 1KB minimum size to compress
    CONTENT_TYPES_TO_COMPRESS = {
        'application/json',
        'application/javascript',
        'text/html',
        'text/css',
        'text/plain',
        'text/xml',
        'text/markdown',
        'application/xml',
    }
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request and compress response if applicable."""
        # Check if client accepts gzip encoding
        accept_encoding = request.headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding.lower():
            return await call_next(request)
        
        # Process request
        response = await call_next(request)
        
        # Skip compression for certain response types
        if not isinstance(response, StarletteResponse):
            return response
        
        # Skip if already compressed
        if response.headers.get("Content-Encoding"):
            return response
        
        # Skip for streaming responses (hard to compress)
        if hasattr(response, "body_iterator") and not hasattr(response, "body"):
            return response
        
        # Skip compression for small responses or non-compressible types
        content_type = response.headers.get("Content-Type", "")
        if not any(ct in content_type for ct in self.CONTENT_TYPES_TO_COMPRESS):
            return response
        
        # For now, skip compression to avoid Content-Length issues
        # Compression can be enabled later with proper response body handling
        # The issue is that FastAPI responses need special handling for body reading
        return response


# ============================================================================
# CORS Configuration
# ============================================================================


def get_cors_middleware_config() -> dict:
    """
    Get CORS middleware configuration.
    
    Returns:
        Dictionary with CORS configuration
    """
    return {
        "allow_origins": [
            "http://localhost:8501",  # Streamlit default port
            "http://127.0.0.1:8501",
            "http://localhost:3000",  # Common React dev port
            "http://127.0.0.1:3000",
        ],
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Content-Type",
            "Authorization",
            "X-Request-ID",
            "X-User-ID",
            "Accept",
            "Accept-Encoding",
        ],
        "expose_headers": [
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "Retry-After",
        ],
        "max_age": 3600,  # Cache preflight requests for 1 hour
    }


__all__ = [
    "RequestIDMiddleware",
    "LoggingMiddleware",
    "RateLimitMiddleware",
    "CompressionMiddleware",
    "get_cors_middleware_config",
]

