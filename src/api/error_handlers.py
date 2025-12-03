"""
Error Handlers and Custom Exceptions for the AI Research Assistant API.

This module provides:
- Custom exception classes for different error types
- Global exception handlers for FastAPI
- Request validation middleware
- Optional error tracking integration (Sentry)
"""

import logging
import re
import traceback
from datetime import datetime
from typing import Callable, Optional
from uuid import UUID

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.models import ErrorResponse

logger = logging.getLogger(__name__)

# ============================================================================
# Custom Exception Classes
# ============================================================================


class TaskNotFoundException(Exception):
    """Raised when a task is not found in the database."""
    
    def __init__(self, task_id: str, message: Optional[str] = None):
        self.task_id = task_id
        self.message = message or f"Task not found: {task_id}"
        super().__init__(self.message)


class TaskNotCompletedException(Exception):
    """Raised when attempting to access a task that is not yet completed."""
    
    def __init__(self, task_id: str, current_status: str, message: Optional[str] = None):
        self.task_id = task_id
        self.current_status = current_status
        self.message = message or f"Task {task_id} is not completed. Current status: {current_status}"
        super().__init__(self.message)


class ValidationException(Exception):
    """Raised when request validation fails."""
    
    def __init__(self, field: str, message: str, value: Optional[str] = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(self.message)


class WorkflowException(Exception):
    """Raised when workflow execution fails."""
    
    def __init__(self, task_id: str, error: str, stage: Optional[str] = None):
        self.task_id = task_id
        self.error = error
        self.stage = stage
        message = f"Workflow failed for task {task_id}"
        if stage:
            message += f" at stage: {stage}"
        message += f". Error: {error}"
        super().__init__(message)


class RateLimitException(Exception):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, limit: int, window: str, retry_after: Optional[int] = None):
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        message = f"Rate limit exceeded: {limit} requests per {window}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message)


# ============================================================================
# Global Exception Handlers
# ============================================================================


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    
    @app.exception_handler(TaskNotFoundException)
    async def task_not_found_handler(request: Request, exc: TaskNotFoundException):
        """Handle task not found errors."""
        logger.warning(
            f"Task not found | task_id: {exc.task_id} | path: {request.url.path}"
        )
        error_response = ErrorResponse(
            error="Task not found",
            detail=exc.message,
            timestamp=datetime.utcnow()
        )
        content = error_response.model_dump()
        if isinstance(content.get("timestamp"), datetime):
            content["timestamp"] = content["timestamp"].isoformat()
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=content
        )
    
    @app.exception_handler(TaskNotCompletedException)
    async def task_not_completed_handler(request: Request, exc: TaskNotCompletedException):
        """Handle task not completed errors."""
        logger.warning(
            f"Task not completed | task_id: {exc.task_id} | status: {exc.current_status} | path: {request.url.path}"
        )
        error_response = ErrorResponse(
            error="Task not completed",
            detail=exc.message,
            timestamp=datetime.utcnow()
        )
        content = error_response.model_dump()
        if isinstance(content.get("timestamp"), datetime):
            content["timestamp"] = content["timestamp"].isoformat()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=content
        )
    
    @app.exception_handler(ValidationException)
    async def validation_error_handler(request: Request, exc: ValidationException):
        """Handle validation errors."""
        logger.warning(
            f"Validation error | field: {exc.field} | message: {exc.message} | path: {request.url.path}"
        )
        error_response = ErrorResponse(
            error="Validation error",
            detail=f"Field '{exc.field}': {exc.message}",
            timestamp=datetime.utcnow()
        )
        content = error_response.model_dump()
        if isinstance(content.get("timestamp"), datetime):
            content["timestamp"] = content["timestamp"].isoformat()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=content
        )
    
    @app.exception_handler(WorkflowException)
    async def workflow_error_handler(request: Request, exc: WorkflowException):
        """Handle workflow execution errors."""
        logger.error(
            f"Workflow error | task_id: {exc.task_id} | stage: {exc.stage} | error: {exc.error} | path: {request.url.path}",
            exc_info=True
        )
        error_response = ErrorResponse(
            error="Workflow execution failed",
            detail=f"Task {exc.task_id} failed during workflow execution: {exc.error}",
            timestamp=datetime.utcnow()
        )
        content = error_response.model_dump()
        if isinstance(content.get("timestamp"), datetime):
            content["timestamp"] = content["timestamp"].isoformat()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=content
        )
    
    @app.exception_handler(RateLimitException)
    async def rate_limit_handler(request: Request, exc: RateLimitException):
        """Handle rate limit errors."""
        logger.warning(
            f"Rate limit exceeded | limit: {exc.limit} | window: {exc.window} | path: {request.url.path}"
        )
        headers = {}
        if exc.retry_after:
            headers["Retry-After"] = str(exc.retry_after)
        
        error_response = ErrorResponse(
            error="Rate limit exceeded",
            detail=exc.message,
            timestamp=datetime.utcnow()
        )
        content = error_response.model_dump()
        if isinstance(content.get("timestamp"), datetime):
            content["timestamp"] = content["timestamp"].isoformat()
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=content,
            headers=headers
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Catch-all handler for unexpected errors."""
        error_traceback = traceback.format_exc()
        error_type = type(exc).__name__
        error_message = str(exc)
        
        # Log full traceback for debugging
        logger.error(
            f"Unhandled exception | type: {error_type} | error: {error_message} | path: {request.url.path}",
            exc_info=True,
            extra={
                "error_type": error_type,
                "error_message": error_message,
                "path": str(request.url.path),
                "method": request.method,
                "traceback": error_traceback
            }
        )
        
        # Optional: Send to error tracking service (Sentry, etc.)
        _send_to_error_tracking(exc, request, error_traceback)
        
        # Return generic error message (don't leak internal details)
        error_response = ErrorResponse(
            error="Internal server error",
            detail="An unexpected error occurred. Please try again later or contact support if the issue persists.",
            timestamp=datetime.utcnow()
        )
        # Convert to dict and ensure datetime is serialized
        content = error_response.model_dump()
        if isinstance(content.get("timestamp"), datetime):
            content["timestamp"] = content["timestamp"].isoformat()
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=content
        )


# ============================================================================
# Request Validation Middleware
# ============================================================================


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate and sanitize incoming requests.
    
    Performs:
    - Malicious input pattern detection
    - HTML/JavaScript sanitization
    - UUID format validation
    - Request size limits
    """
    
    # Maximum request body size (10MB)
    MAX_REQUEST_SIZE = 10 * 1024 * 1024
    
    # Malicious patterns to detect
    MALICIOUS_PATTERNS = [
        (r'<script[^>]*>.*?</script>', 'Script tags detected'),
        (r'javascript:', 'JavaScript protocol detected'),
        (r'on\w+\s*=', 'Event handler attributes detected'),
        (r'<iframe[^>]*>', 'Iframe tags detected'),
        (r'<object[^>]*>', 'Object tags detected'),
        (r'<embed[^>]*>', 'Embed tags detected'),
        (r'<link[^>]*>', 'Link tags detected'),
        (r'<meta[^>]*>', 'Meta tags detected'),
        (r'<style[^>]*>.*?</style>', 'Style tags detected'),
        (r'data:text/html', 'Data URI with HTML detected'),
        (r'vbscript:', 'VBScript protocol detected'),
        (r'expression\s*\(', 'CSS expression detected'),
    ]
    
    # UUID pattern
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request through validation middleware."""
        
        # Skip validation for certain paths (health checks, docs, etc.)
        skip_paths = ['/health', '/docs', '/openapi.json', '/redoc', '/']
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        
        try:
            # 1. Check request size
            content_length = request.headers.get('content-length')
            if content_length:
                try:
                    size = int(content_length)
                    if size > self.MAX_REQUEST_SIZE:
                        logger.warning(
                            f"Request too large | size: {size} bytes | max: {self.MAX_REQUEST_SIZE} | path: {request.url.path}"
                        )
                        error_response = ErrorResponse(
                            error="Request too large",
                            detail=f"Request body exceeds maximum size of {self.MAX_REQUEST_SIZE / (1024*1024):.1f}MB",
                            timestamp=datetime.utcnow()
                        )
                        content = error_response.model_dump()
                        if isinstance(content.get("timestamp"), datetime):
                            content["timestamp"] = content["timestamp"].isoformat()
                        return JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content=content
                        )
                except ValueError:
                    pass  # Invalid content-length header, let it pass
            
            # 2. Validate UUIDs in path parameters
            path_params = request.path_params
            for param_name, param_value in path_params.items():
                if 'task_id' in param_name.lower() or 'id' in param_name.lower():
                    if not self._is_valid_uuid(param_value):
                        logger.warning(
                            f"Invalid UUID format | param: {param_name} | value: {param_value} | path: {request.url.path}"
                        )
                        error_response = ErrorResponse(
                            error="Invalid UUID format",
                            detail=f"Parameter '{param_name}' must be a valid UUID",
                            timestamp=datetime.utcnow()
                        )
                        content = error_response.model_dump()
                        if isinstance(content.get("timestamp"), datetime):
                            content["timestamp"] = content["timestamp"].isoformat()
                        return JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content=content
                        )
            
            # 3. Read and validate request body (for POST/PUT/PATCH)
            if request.method in ['POST', 'PUT', 'PATCH']:
                body = await request.body()
                
                if body:
                    # Check body size
                    if len(body) > self.MAX_REQUEST_SIZE:
                        logger.warning(
                            f"Request body too large | size: {len(body)} bytes | max: {self.MAX_REQUEST_SIZE} | path: {request.url.path}"
                        )
                        error_response = ErrorResponse(
                            error="Request body too large",
                            detail=f"Request body exceeds maximum size of {self.MAX_REQUEST_SIZE / (1024*1024):.1f}MB",
                            timestamp=datetime.utcnow()
                        )
                        content = error_response.model_dump()
                        if isinstance(content.get("timestamp"), datetime):
                            content["timestamp"] = content["timestamp"].isoformat()
                        return JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content=content
                        )
                    
                    # Check for malicious patterns in body
                    body_str = body.decode('utf-8', errors='ignore')
                    validation_error = self._validate_content(body_str)
                    if validation_error:
                        logger.warning(
                            f"Malicious content detected | error: {validation_error} | path: {request.url.path}"
                        )
                        error_response = ErrorResponse(
                            error="Invalid request content",
                            detail=f"Request contains potentially malicious content: {validation_error}",
                            timestamp=datetime.utcnow()
                        )
                        content = error_response.model_dump()
                        if isinstance(content.get("timestamp"), datetime):
                            content["timestamp"] = content["timestamp"].isoformat()
                        return JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content=content
                        )
                    
                    # Recreate request with body (since we consumed it)
                    async def receive():
                        return {'type': 'http.request', 'body': body}
                    
                    request._receive = receive
            
            # 4. Validate query parameters
            query_params = dict(request.query_params)
            for param_name, param_value in query_params.items():
                validation_error = self._validate_content(param_value)
                if validation_error:
                    logger.warning(
                        f"Malicious content in query param | param: {param_name} | error: {validation_error} | path: {request.url.path}"
                    )
                    error_response = ErrorResponse(
                        error="Invalid query parameter",
                        detail=f"Query parameter '{param_name}' contains potentially malicious content: {validation_error}",
                        timestamp=datetime.utcnow()
                    )
                    content = error_response.model_dump()
                    if isinstance(content.get("timestamp"), datetime):
                        content["timestamp"] = content["timestamp"].isoformat()
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content=content
                    )
            
            # Continue with request processing
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(
                f"Error in request validation middleware | error: {str(e)} | path: {request.url.path}",
                exc_info=True
            )
            # If validation middleware fails, let the request through
            # (fail open to avoid blocking legitimate requests)
            return await call_next(request)
    
    def _is_valid_uuid(self, value: str) -> bool:
        """Check if a string is a valid UUID."""
        if not isinstance(value, str):
            return False
        return bool(self.UUID_PATTERN.match(value))
    
    def _validate_content(self, content: str) -> Optional[str]:
        """
        Validate content for malicious patterns.
        
        Args:
            content: Content string to validate
            
        Returns:
            Error message if malicious content detected, None otherwise
        """
        if not isinstance(content, str):
            return None
        
        content_lower = content.lower()
        
        for pattern, description in self.MALICIOUS_PATTERNS:
            if re.search(pattern, content_lower, re.IGNORECASE | re.DOTALL):
                return description
        
        return None
    
    def _sanitize_html(self, content: str) -> str:
        """
        Sanitize HTML content by removing potentially dangerous tags and attributes.
        
        Note: This is a basic sanitizer. For production, consider using
        a library like bleach or html-sanitizer.
        
        Args:
            content: HTML content to sanitize
            
        Returns:
            Sanitized content
        """
        # Remove script tags and their content
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove event handlers
        content = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)
        
        # Remove dangerous tags
        dangerous_tags = ['iframe', 'object', 'embed', 'link', 'meta', 'style']
        for tag in dangerous_tags:
            content = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', content, flags=re.IGNORECASE | re.DOTALL)
            content = re.sub(rf'<{tag}[^>]*/?>', '', content, flags=re.IGNORECASE)
        
        return content


# ============================================================================
# Error Tracking Integration (Sentry)
# ============================================================================


def _send_to_error_tracking(exc: Exception, request: Request, traceback_str: str):
    """
    Send error to external error tracking service (e.g., Sentry).
    
    This is a placeholder implementation. To enable Sentry:
    1. Install: pip install sentry-sdk[fastapi]
    2. Initialize in main.py:
       import sentry_sdk
       from sentry_sdk.integrations.fastapi import FastApiIntegration
       sentry_sdk.init(
           dsn="your-sentry-dsn",
           integrations=[FastApiIntegration()],
           traces_sample_rate=1.0,
       )
    
    Args:
        exc: Exception that occurred
        request: FastAPI request object
        traceback_str: Formatted traceback string
    """
    try:
        # Check if Sentry is available
        try:
            import sentry_sdk
            if sentry_sdk.Hub.current.client:
                # Sentry is initialized, capture exception
                with sentry_sdk.push_scope() as scope:
                    scope.set_context("request", {
                        "url": str(request.url),
                        "method": request.method,
                        "path": request.url.path,
                        "query_params": dict(request.query_params),
                    })
                    scope.set_tag("error_type", type(exc).__name__)
                    sentry_sdk.capture_exception(exc)
        except ImportError:
            # Sentry not installed, skip
            pass
        except Exception as e:
            # Error tracking failed, log but don't raise
            logger.warning(f"Failed to send error to tracking service: {e}")
    except Exception:
        # Silently fail to avoid breaking the error handler
        pass


# ============================================================================
# Utility Functions
# ============================================================================


def validate_uuid(value: str, param_name: str = "id") -> UUID:
    """
    Validate and convert a string to UUID.
    
    Args:
        value: String value to validate
        param_name: Name of the parameter (for error messages)
        
    Returns:
        UUID object
        
    Raises:
        ValidationException: If value is not a valid UUID
    """
    try:
        return UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise ValidationException(
            field=param_name,
            message=f"'{value}' is not a valid UUID format",
            value=value
        )


def sanitize_input(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize user input by removing potentially dangerous content.
    
    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length (None for no limit)
        
    Returns:
        Sanitized string
        
    Raises:
        ValidationException: If input is invalid or too long
    """
    if not isinstance(value, str):
        raise ValidationException(
            field="input",
            message="Input must be a string",
            value=str(value)
        )
    
    if max_length and len(value) > max_length:
        raise ValidationException(
            field="input",
            message=f"Input exceeds maximum length of {max_length} characters",
            value=value[:100] + "..." if len(value) > 100 else value
        )
    
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Basic HTML sanitization (remove script tags, etc.)
    middleware = RequestValidationMiddleware(None)
    error = middleware._validate_content(value)
    if error:
        raise ValidationException(
            field="input",
            message=f"Input contains potentially malicious content: {error}",
            value=value[:100] + "..." if len(value) > 100 else value
        )
    
    return value


__all__ = [
    "TaskNotFoundException",
    "TaskNotCompletedException",
    "ValidationException",
    "WorkflowException",
    "RateLimitException",
    "register_exception_handlers",
    "RequestValidationMiddleware",
    "validate_uuid",
    "sanitize_input",
]

