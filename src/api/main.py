"""
FastAPI Main Application
"""

import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .middleware import (
    setup_cors_middleware,
    setup_rate_limit_middleware,
    setup_error_handler_middleware,
)
from .endpoints import research, status, report, review
from .task_manager import get_task_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Research Assistant API",
    description="API for AI-powered research report generation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Setup middleware
setup_cors_middleware(app)
setup_rate_limit_middleware(app)
setup_error_handler_middleware(app)

# Include routers
app.include_router(research.router)
app.include_router(status.router)
app.include_router(report.router)
app.include_router(review.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "AI Research Assistant API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ai-research-assistant-api"}


@app.get("/api/v1/health")
async def detailed_health_check():
    """Detailed health check with service status"""
    health_status = {
        "status": "healthy",
        "service": "ai-research-assistant-api",
        "checks": {},
    }

    # Check database
    try:
        task_manager = get_task_manager()
        # Try a simple query
        task_manager._init_database()
        health_status["checks"]["database"] = "ok"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check environment variables
    required_vars = ["OPENAI_API_KEY", "PINECONE_API_KEY", "S3_BUCKET_NAME"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        health_status["checks"]["environment"] = f"missing: {', '.join(missing_vars)}"
        health_status["status"] = "degraded"
    else:
        health_status["checks"]["environment"] = "ok"

    return health_status


@app.get("/api/v1/debug/{task_id}")
async def debug_task(task_id: str):
    """
    Debug endpoint to get detailed task information

    Useful for troubleshooting and development
    """
    import uuid

    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id format")

    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {
        "task": task,
        "raw_status": task.get("status"),
        "parsed_status": task.get("status"),
        "has_report": bool(task.get("report")),
        "num_sources": len(task.get("sources", [])),
        "needs_hitl": task.get("needs_hitl", False),
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting AI Research Assistant API...")

    # Initialize task manager
    task_manager = get_task_manager()
    logger.info("Task manager initialized")

    logger.info("API startup complete")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down AI Research Assistant API...")


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 8000))

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
