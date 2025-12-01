"""
FastAPI Application for AI Research Assistant

Main FastAPI application with middleware, health checks, and configuration.
"""

import os
import sys
import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import uvicorn

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / ".env")

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

class Settings:
    """Application settings loaded from environment variables."""
    
    # App configuration
    APP_TITLE: str = "AI Research Assistant API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Multi-agent RAG system for automated research report generation"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # API configuration
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = os.getenv("API_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("API_PORT", "8000"))
    
    # CORS configuration
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    CORS_ALLOW_METHODS: list = os.getenv("CORS_ALLOW_METHODS", "*").split(",")
    CORS_ALLOW_HEADERS: list = os.getenv("CORS_ALLOW_HEADERS", "*").split(",")
    
    # Service configurations
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    PINECONE_API_KEY: Optional[str] = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX_NAME: Optional[str] = os.getenv("PINECONE_INDEX_NAME")
    PINECONE_ENVIRONMENT: Optional[str] = os.getenv("PINECONE_ENVIRONMENT")
    S3_BUCKET_NAME: Optional[str] = os.getenv("S3_BUCKET_NAME")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required settings are present."""
        required_settings = [
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),
            ("PINECONE_API_KEY", cls.PINECONE_API_KEY),
            ("PINECONE_INDEX_NAME", cls.PINECONE_INDEX_NAME),
            ("S3_BUCKET_NAME", cls.S3_BUCKET_NAME),
        ]
        
        missing = [name for name, value in required_settings if not value]
        if missing:
            logger.warning(f"Missing required settings: {', '.join(missing)}")
            if cls.APP_ENV == "production":
                return False
        return True


settings = Settings()


# ============================================================================
# Middleware
# ============================================================================

class RequestIDMiddleware:
    """Middleware to add a unique request ID to each request."""
    
    async def __call__(self, request: Request, call_next):
        """Add request ID to request and response headers."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class JSONLoggingMiddleware:
    """Middleware to log requests and responses in JSON format."""
    
    async def __call__(self, request: Request, call_next):
        """Log request and response details."""
        start_time = datetime.now()
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Log request
        logger.info(
            "Request received",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
            }
        )
        
        try:
            response = await call_next(request)
            process_time = (datetime.now() - start_time).total_seconds()
            
            # Log response
            logger.info(
                "Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": process_time,
                }
            )
            
            response.headers["X-Process-Time"] = str(process_time)
            return response
            
        except Exception as e:
            process_time = (datetime.now() - start_time).total_seconds()
            logger.error(
                "Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "process_time": process_time,
                },
                exc_info=True,
            )
            raise


class ErrorHandlingMiddleware:
    """Middleware to handle and format errors consistently."""
    
    async def __call__(self, request: Request, call_next):
        """Catch exceptions and return formatted error responses."""
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            request_id = getattr(request.state, "request_id", "unknown")
            
            logger.error(
                "Unhandled exception",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            
            # Return formatted error response
            error_detail = {
                "error": "Internal server error",
                "message": str(e) if settings.DEBUG else "An unexpected error occurred",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
            }
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_detail,
            )


# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events for the FastAPI application.
    
    Args:
        app: FastAPI application instance.
    """
    # Startup
    logger.info("=" * 70)
    logger.info("Starting AI Research Assistant API")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    logger.info("=" * 70)
    
    # Validate settings
    if not settings.validate():
        logger.error("Required settings validation failed!")
        if settings.APP_ENV == "production":
            raise RuntimeError("Required settings are missing in production mode")
    
    # Initialize service connections
    try:
        logger.info("Initializing service connections...")
        
        # Test OpenAI connection
        if settings.OPENAI_API_KEY:
            try:
                from src.utils.openai_client import OpenAIClient
                client = OpenAIClient()
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.warning(f"OpenAI client initialization failed: {e}")
        
        # Test Pinecone connection
        if settings.PINECONE_API_KEY and settings.PINECONE_INDEX_NAME:
            try:
                from src.utils.pinecone_rag import _get_pinecone_index
                index = _get_pinecone_index()
                logger.info("Pinecone index initialized successfully")
            except Exception as e:
                logger.warning(f"Pinecone initialization failed: {e}")
        
        # Test S3 connection
        if settings.S3_BUCKET_NAME:
            try:
                from src.utils.s3_client import S3Client
                s3_client = S3Client()
                logger.info("S3 client initialized successfully")
            except Exception as e:
                logger.warning(f"S3 client initialization failed: {e}")
        
        logger.info("Service connections initialized")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        if settings.APP_ENV == "production":
            raise
    
    logger.info("API startup complete")
    logger.info("=" * 70)
    
    yield
    
    # Shutdown
    logger.info("=" * 70)
    logger.info("Shutting down AI Research Assistant API")
    logger.info("Cleaning up resources...")
    
    # Cleanup can be added here if needed
    # For example: close database connections, clear caches, etc.
    
    logger.info("Shutdown complete")
    logger.info("=" * 70)


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
    openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
    lifespan=lifespan,
)

# Add middleware (order matters - last added is first executed)
# RequestIDMiddleware must be first so request_id is available to other middleware
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(JSONLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)  # This runs first (last added)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns:
        Dictionary with status and timestamp.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": settings.APP_TITLE,
        "version": settings.APP_VERSION,
    }


@app.get(f"{settings.API_V1_PREFIX}/health", tags=["Health"])
async def health_check_v1() -> Dict[str, Any]:
    """
    Versioned health check endpoint.
    
    Returns:
        Dictionary with status, timestamp, and service information.
    """
    # Check service connectivity
    services_status = {
        "openai": False,
        "pinecone": False,
        "s3": False,
    }
    
    # Check OpenAI
    if settings.OPENAI_API_KEY:
        try:
            from src.utils.openai_client import OpenAIClient
            client = OpenAIClient()
            services_status["openai"] = True
        except Exception:
            pass
    
    # Check Pinecone
    if settings.PINECONE_API_KEY and settings.PINECONE_INDEX_NAME:
        try:
            from src.utils.pinecone_rag import _get_pinecone_index
            index = _get_pinecone_index()
            services_status["pinecone"] = True
        except Exception:
            pass
    
    # Check S3
    if settings.S3_BUCKET_NAME:
        try:
            from src.utils.s3_client import S3Client
            s3_client = S3Client()
            services_status["s3"] = True
        except Exception:
            pass
    
    overall_status = "healthy" if all(services_status.values()) else "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "service": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "services": services_status,
    }


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    """
    Root endpoint providing API information.
    
    Returns:
        Dictionary with API information and available endpoints.
    """
    return {
        "service": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "description": settings.APP_DESCRIPTION,
        "environment": settings.APP_ENV,
        "endpoints": {
            "health": "/health",
            "health_v1": f"{settings.API_V1_PREFIX}/health",
            "docs": "/docs" if settings.APP_ENV != "production" else "disabled",
            "openapi": "/openapi.json" if settings.APP_ENV != "production" else "disabled",
        },
    }


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """
    Main entry point for running the FastAPI application.
    
    This function starts the Uvicorn server with the configured settings.
    """
    uvicorn.run(
        "src.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG and settings.APP_ENV == "development",
        log_level="info" if not settings.DEBUG else "debug",
    )


if __name__ == "__main__":
    main()

