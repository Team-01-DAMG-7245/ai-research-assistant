"""
Research API Endpoints

Handles research query submission and processing.
"""

import hashlib
import logging
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, Union

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, Response

from src.api.models import ResearchRequest, ResearchResponse, ReportResponse, Source, StatusResponse
from src.api.task_manager import get_task_manager, TaskStatus
from src.api.task_queue import get_workflow_executor

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["Research"])

# Rate limiting storage (in-memory, thread-safe with locks)
# In production, consider using Redis or similar for distributed rate limiting
_rate_limit_store: Dict[str, list] = defaultdict(list)
_rate_limit_lock = threading.Lock()  # Thread-safe lock for rate limiting

# Rate limiting configuration
MAX_REQUESTS_PER_MINUTE = 5
RATE_LIMIT_WINDOW_SECONDS = 60

# Status caching configuration
_status_cache: Dict[str, Tuple[StatusResponse, float]] = {}
_status_cache_lock = threading.Lock()
STATUS_CACHE_TTL_SECONDS = 2  # Cache status for 2 seconds


def _get_rate_limit_key(request: Request, user_id: str = None) -> str:
    """
    Generate rate limit key from user_id or IP address.
    
    Args:
        request: FastAPI Request object
        user_id: Optional user identifier
    
    Returns:
        Rate limit key string
    """
    if user_id:
        return f"user:{user_id}"
    
    # Use IP address as fallback
    client_ip = request.client.host if request.client else "unknown"
    # Handle forwarded IPs (e.g., from proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    
    return f"ip:{client_ip}"


def _check_rate_limit(key: str) -> Tuple[bool, int]:
    """
    Check if request is within rate limit.
    
    Thread-safe rate limiting check.
    
    Args:
        key: Rate limit key (user_id or IP)
    
    Returns:
        Tuple of (is_allowed, remaining_requests)
    """
    now = time.time()
    
    with _rate_limit_lock:
        # Clean old entries (older than 1 minute)
        _rate_limit_store[key] = [
            timestamp for timestamp in _rate_limit_store[key]
            if now - timestamp < RATE_LIMIT_WINDOW_SECONDS
        ]
        
        # Check if limit exceeded
        request_count = len(_rate_limit_store[key])
        
        if request_count >= MAX_REQUESTS_PER_MINUTE:
            remaining = 0
            return False, remaining
        
        # Add current request timestamp
        _rate_limit_store[key].append(now)
        remaining = MAX_REQUESTS_PER_MINUTE - request_count - 1
        
        return True, remaining


def _hash_query(query: str) -> str:
    """
    Generate hash of query for logging (privacy-preserving).
    
    Args:
        query: Query string
    
    Returns:
        SHA256 hash of query (first 16 characters)
    """
    return hashlib.sha256(query.encode()).hexdigest()[:16]


def _validate_task_id(task_id: str) -> bool:
    """
    Validate task_id is a valid UUID format.
    
    Args:
        task_id: Task identifier string
    
    Returns:
        True if valid UUID, False otherwise
    """
    try:
        uuid.UUID(task_id)
        return True
    except (ValueError, AttributeError):
        return False


def _get_status_message(task_status: str, current_agent: Optional[str], error_message: Optional[str] = None) -> str:
    """
    Map internal status to user-friendly message.
    
    Args:
        task_status: Internal task status
        current_agent: Currently executing agent (if processing)
        error_message: Error message (if failed)
    
    Returns:
        User-friendly status message
    """
    if task_status == TaskStatus.QUEUED:
        return "Your research task is queued for processing"
    
    elif task_status == TaskStatus.PROCESSING:
        if current_agent == "search" or current_agent == "search_agent":
            return "Searching for relevant papers and sources..."
        elif current_agent == "synthesis" or current_agent == "synthesis_agent":
            return "Generating research report from sources..."
        elif current_agent == "validation" or current_agent == "validation_agent":
            return "Validating citations and report quality..."
        elif current_agent == "hitl_review":
            return "Awaiting human review..."
        else:
            return "Processing your research request..."
    
    elif task_status == TaskStatus.PENDING_REVIEW:
        return "Report ready for human review"
    
    elif task_status == TaskStatus.COMPLETED:
        return "Research report completed successfully"
    
    elif task_status == TaskStatus.APPROVED:
        return "Research report approved and ready"
    
    elif task_status == TaskStatus.FAILED:
        if error_message:
            return f"Task failed: {error_message}"
        return "Task failed during processing"
    
    else:
        return f"Status: {task_status}"


def _calculate_estimated_completion(
    task_status: str,
    current_agent: Optional[str],
    created_at: datetime,
    updated_at: datetime
) -> Optional[datetime]:
    """
    Calculate estimated completion time based on current agent and progress.
    
    Args:
        task_status: Current task status
        current_agent: Currently executing agent
        created_at: Task creation timestamp
        updated_at: Last update timestamp
    
    Returns:
        Estimated completion datetime or None
    """
    if task_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.APPROVED]:
        return None
    
    # Average time estimates per agent (in seconds)
    agent_time_estimates = {
        "search": 30,  # 30 seconds for search
        "search_agent": 30,
        "synthesis": 60,  # 60 seconds for synthesis
        "synthesis_agent": 60,
        "validation": 20,  # 20 seconds for validation
        "validation_agent": 20,
        "hitl_review": None,  # Unknown - depends on human
    }
    
    # If in HITL review, can't estimate
    if current_agent == "hitl_review" or task_status == TaskStatus.PENDING_REVIEW:
        return None
    
    # Calculate elapsed time
    elapsed = (updated_at - created_at).total_seconds()
    
    # Estimate remaining time based on current agent
    if current_agent and current_agent in agent_time_estimates:
        remaining_estimate = agent_time_estimates.get(current_agent, 30)
    else:
        # Default estimate if agent unknown
        remaining_estimate = 30
    
    # Estimate completion
    estimated_completion = updated_at + timedelta(seconds=remaining_estimate)
    
    return estimated_completion


def _get_cached_status(task_id: str) -> Optional[StatusResponse]:
    """
    Get cached status if available and not expired.
    
    Args:
        task_id: Task identifier
    
    Returns:
        Cached StatusResponse or None if not cached/expired
    """
    with _status_cache_lock:
        if task_id in _status_cache:
            cached_response, cache_time = _status_cache[task_id]
            if time.time() - cache_time < STATUS_CACHE_TTL_SECONDS:
                return cached_response
            else:
                # Remove expired cache entry
                del _status_cache[task_id]
    return None


def _set_cached_status(task_id: str, status_response: StatusResponse):
    """
    Cache status response.
    
    Args:
        task_id: Task identifier
        status_response: StatusResponse to cache
    """
    with _status_cache_lock:
        _status_cache[task_id] = (status_response, time.time())
        
        # Clean up old cache entries (older than 1 minute)
        current_time = time.time()
        expired_keys = [
            key for key, (_, cache_time) in _status_cache.items()
            if current_time - cache_time > 60
        ]
        for key in expired_keys:
            del _status_cache[key]


@router.post("/research", response_model=ResearchResponse, status_code=status.HTTP_201_CREATED)
async def submit_research_query(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
    http_request: Request
) -> ResearchResponse:
    """
    Submit a new research query for processing.
    
    This endpoint:
    1. Validates the input query
    2. Creates a new task with unique ID
    3. Queues the task for background processing
    4. Returns task_id immediately (doesn't wait for completion)
    
    Args:
        request: ResearchRequest with query and optional parameters
        background_tasks: FastAPI background task manager
        http_request: FastAPI Request object for rate limiting
    
    Returns:
        ResearchResponse with task_id and status
    
    Raises:
        HTTPException(400): Invalid input or rate limit exceeded
        HTTPException(500): Server error
    """
    start_time = datetime.utcnow()
    query_hash = _hash_query(request.query)
    
    try:
        # Rate limiting check
        rate_limit_key = _get_rate_limit_key(http_request, request.user_id)
        is_allowed, remaining = _check_rate_limit(rate_limit_key)
        
        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded | key: {rate_limit_key} | "
                f"query_hash: {query_hash}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {MAX_REQUESTS_PER_MINUTE} requests per minute allowed",
                    "retry_after": RATE_LIMIT_WINDOW_SECONDS
                }
            )
        
        # Log request details
        logger.info(
            f"Research query submitted | "
            f"user_id: {request.user_id or 'anonymous'} | "
            f"query_hash: {query_hash} | "
            f"depth: {request.depth} | "
            f"rate_limit_remaining: {remaining}"
        )
        
        # Get task manager and workflow executor
        task_manager = get_task_manager()
        workflow_executor = get_workflow_executor()
        
        # Create task
        try:
            task_id = task_manager.create_task(
                query=request.query,
                user_id=request.user_id,
                depth=request.depth.value if hasattr(request.depth, 'value') else str(request.depth)
            )
        except Exception as e:
            logger.error(
                f"Failed to create task | query_hash: {query_hash} | error: {str(e)}",
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Task creation failed",
                    "message": "Failed to create research task. Please try again."
                }
            )
        
        # Add background task for workflow execution
        # FastAPI BackgroundTasks can handle async functions directly
        try:
            # Add the async function directly - FastAPI will handle it
            background_tasks.add_task(
                workflow_executor.execute_research_workflow,
                task_id,
                request.query,
                request.depth.value if hasattr(request.depth, 'value') else str(request.depth)
            )
            logger.info(f"Background task queued for task {task_id}")
        except Exception as e:
            logger.error(
                f"Failed to queue background task | task_id: {task_id} | error: {str(e)}",
                exc_info=True
            )
            # Mark task as failed since we couldn't queue it
            task_manager.mark_task_failed(
                task_id,
                f"Failed to queue workflow execution: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Task queuing failed",
                    "message": "Failed to queue research task for processing. Please try again."
                }
            )
        
        # Return response immediately
        response = ResearchResponse(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            message="Research task created successfully and queued for processing",
            created_at=start_time
        )
        
        logger.info(
            f"Research task created successfully | "
            f"task_id: {task_id} | "
            f"user_id: {request.user_id or 'anonymous'} | "
            f"query_hash: {query_hash}"
        )
        
        return response
    
    except HTTPException:
        # Re-raise HTTP exceptions (rate limiting, etc.)
        raise
    
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(
            f"Unexpected error in submit_research_query | "
            f"query_hash: {query_hash} | "
            f"error: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "An unexpected error occurred while processing your request."
            }
        )


@router.get("/status/{task_id}", response_model=StatusResponse)
async def get_task_status(task_id: str) -> StatusResponse:
    """
    Get the current status of a research task.
    
    Returns real-time progress including:
    - Current processing status
    - Which agent is currently working
    - Progress percentage (0-100)
    - Estimated completion time
    
    Args:
        task_id: UUID of the task to check
    
    Returns:
        StatusResponse with current state
    
    Raises:
        HTTPException(404): Task not found
        HTTPException(400): Invalid task_id format
        HTTPException(500): Server error
    """
    try:
        # Validate task_id format (UUID)
        if not _validate_task_id(task_id):
            logger.warning(f"Invalid task_id format: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid task_id format",
                    "message": "task_id must be a valid UUID"
                }
            )
        
        # Check cache first
        cached_status = _get_cached_status(task_id)
        if cached_status:
            logger.debug(f"Returning cached status for task {task_id}")
            return cached_status
        
        # Get task status from database
        task_manager = get_task_manager()
        task_data = task_manager.get_task_status(task_id)
        
        if not task_data:
            logger.warning(f"Task not found: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Task not found",
                    "message": f"No task found with id: {task_id}"
                }
            )
        
        # Parse timestamps (SQLite returns strings)
        created_at_value = task_data.get("created_at")
        updated_at_value = task_data.get("updated_at")
        
        # Helper function to parse datetime
        def parse_datetime(value):
            if value is None:
                return datetime.utcnow()
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                # Try multiple formats
                formats = [
                    "%Y-%m-%d %H:%M:%S.%f",  # SQLite with microseconds
                    "%Y-%m-%d %H:%M:%S",     # SQLite without microseconds
                    "%Y-%m-%dT%H:%M:%S.%fZ", # ISO with Z
                    "%Y-%m-%dT%H:%M:%SZ",    # ISO without microseconds
                ]
                for fmt in formats:
                    try:
                        return datetime.strptime(value, fmt)
                    except (ValueError, AttributeError):
                        continue
                # Try fromisoformat as last resort
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass
            return datetime.utcnow()
        
        created_at = parse_datetime(created_at_value)
        updated_at = parse_datetime(updated_at_value)
        
        # Get status and current agent
        task_status_str = task_data.get("status", "")
        current_agent = task_data.get("current_agent")
        progress = task_data.get("progress", 0) or 0
        error_message = task_data.get("error_message")
        
        # Convert task_status string to TaskStatus enum
        # Map string values to enum values
        status_mapping = {
            "queued": TaskStatus.QUEUED,
            "processing": TaskStatus.PROCESSING,
            "completed": TaskStatus.COMPLETED,
            "failed": TaskStatus.FAILED,
            "pending_review": TaskStatus.PENDING_REVIEW,
            "approved": TaskStatus.APPROVED,
        }
        
        task_status = status_mapping.get(task_status_str.lower(), task_status_str)
        
        # Map status to user-friendly message
        status_message = _get_status_message(
            task_status_str,  # Pass string for message mapping
            current_agent,
            error_message
        )
        
        # Calculate estimated completion
        estimated_completion = _calculate_estimated_completion(
            task_status=task_status_str,  # Pass string for calculation
            current_agent=current_agent,
            created_at=created_at,
            updated_at=updated_at
        )
        
        # Use TaskStatus enum for response
        # StatusResponse expects TaskStatus enum, so we need to convert
        try:
            # Try to get the enum value from the string
            status_enum = status_mapping.get(task_status_str.lower())
            if status_enum is None:
                # If not in mapping, try direct enum creation
                status_enum = TaskStatus(task_status_str)
        except (ValueError, KeyError, AttributeError) as e:
            logger.warning(f"Could not convert status '{task_status_str}' to enum: {e}")
            # Fallback: use QUEUED as default if conversion fails
            status_enum = TaskStatus.QUEUED
        
        # Build response
        try:
            status_response = StatusResponse(
                task_id=task_id,
                status=status_enum,
                current_agent=current_agent,
                progress=progress,
                message=status_message,
                created_at=created_at,
                updated_at=updated_at,
                estimated_completion=estimated_completion
            )
        except Exception as e:
            logger.error(f"Error creating StatusResponse: {e}", exc_info=True)
            # Re-raise with more context
            raise ValueError(f"Failed to create StatusResponse: {str(e)}") from e
        
        # Cache the response
        _set_cached_status(task_id, status_response)
        
        logger.debug(
            f"Status retrieved for task {task_id} | "
            f"status: {task_status} | "
            f"progress: {progress}% | "
            f"agent: {current_agent}"
        )
        
        return status_response
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(
            f"Error retrieving task status | task_id: {task_id} | error_type: {error_type} | error: {error_msg}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": f"An error occurred while retrieving task status: {error_msg}",
                "error_type": error_type
            }
        )


@router.get("/report/{task_id}", response_model=None)
async def get_research_report(
    task_id: str,
    format: Optional[str] = Query(default="json", description="Response format: json, markdown, or pdf")
) -> Union[ReportResponse, Response]:
    """
    Retrieve the completed research report.
    
    Returns the full report with sources and metadata.
    Only available when task status is COMPLETED or APPROVED.
    
    Args:
        task_id: UUID of the completed task
        format: Response format - json (default), markdown, or pdf
    
    Returns:
        ReportResponse with full report content (or markdown text if format=markdown)
    
    Raises:
        HTTPException(404): Task not found
        HTTPException(400): Task failed
        HTTPException(409): Task not completed yet
        HTTPException(500): Server error
    """
    try:
        # Validate task_id format (UUID)
        if not _validate_task_id(task_id):
            logger.warning(f"Invalid task_id format: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid task_id format",
                    "message": "task_id must be a valid UUID"
                }
            )
        
        # Normalize format parameter
        format_lower = format.lower() if format else "json"
        if format_lower not in ["json", "markdown", "pdf"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid format",
                    "message": "format must be one of: json, markdown, pdf"
                }
            )
        
        # Get task manager
        task_manager = get_task_manager()
        
        # Check task status first
        task_status_data = task_manager.get_task_status(task_id)
        if not task_status_data:
            logger.warning(f"Task not found: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Task not found",
                    "message": f"No task found with id: {task_id}"
                }
            )
        
        task_status_str = task_status_data.get("status", "")
        error_message = task_status_data.get("error_message")
        
        # Normalize status for comparison (handle both string and enum)
        task_status_lower = task_status_str.lower() if isinstance(task_status_str, str) else str(task_status_str).lower()
        
        # Check if task is in a valid state for report retrieval
        if task_status_lower in ["queued", "processing"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Task still processing",
                    "message": "Task is still being processed. Please check the status endpoint for updates.",
                    "status": task_status
                }
            )
        
        if task_status_lower == "pending_review":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Task pending review",
                    "message": "Task is pending human review. Report will be available after approval.",
                    "status": task_status_str
                }
            )
        
        if task_status_lower == "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Task failed",
                    "message": f"Task failed: {error_message or 'Unknown error'}",
                    "status": task_status_str
                }
            )
        
        if task_status_lower not in ["completed", "approved"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Report not available",
                    "message": f"Report is not available for task status: {task_status_str}",
                    "status": task_status_str
                }
            )
        
        # Get task result
        task_result = task_manager.get_task_result(task_id)
        if not task_result:
            logger.warning(f"Task result not found: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Report not found",
                    "message": f"Report not found for task: {task_id}"
                }
            )
        
        # Parse sources from JSON
        sources_data = task_result.get("sources", [])
        sources = []
        if isinstance(sources_data, list):
            for idx, source_data in enumerate(sources_data):
                if isinstance(source_data, dict):
                    try:
                        source = Source(
                            source_id=source_data.get("source_id", idx + 1),
                            title=source_data.get("title", "Unknown"),
                            url=source_data.get("url", ""),
                            relevance_score=float(source_data.get("relevance_score", 0.0))
                        )
                        sources.append(source)
                    except Exception as e:
                        logger.warning(f"Error parsing source {idx}: {e}")
                        # Skip invalid sources
                        continue
        
        # Parse created_at timestamp
        created_at_value = task_result.get("created_at") or task_result.get("task_created_at")
        if isinstance(created_at_value, datetime):
            created_at = created_at_value
        elif isinstance(created_at_value, str):
            try:
                created_at = datetime.fromisoformat(created_at_value.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                try:
                    created_at = datetime.strptime(created_at_value, "%Y-%m-%d %H:%M:%S.%f")
                except (ValueError, AttributeError):
                    created_at = datetime.utcnow()
        else:
            created_at = datetime.utcnow()
        
        # Get report text
        report_text = task_result.get("report", "")
        
        # Build metadata with download links
        s3_url = task_result.get("s3_url", "")
        metadata = {
            "total_sources": len(sources),
            "confidence_score": task_result.get("confidence_score", 0.0),
            "needs_hitl": task_result.get("needs_hitl", False),
            "download_links": {
                "markdown": s3_url if s3_url else None,
                "pdf": s3_url.replace(".md", ".pdf") if s3_url else None
            }
        }
        
        # Handle different formats
        if format_lower == "markdown":
            # Return just the markdown report
            logger.info(f"Returning markdown report for task {task_id}")
            return PlainTextResponse(
                content=report_text,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f'attachment; filename="report_{task_id}.md"'
                }
            )
        
        elif format_lower == "pdf":
            # For PDF, return JSON with PDF URL (or redirect if PDF exists)
            # In a real implementation, you might generate PDF on-the-fly or have it pre-generated
            pdf_url = metadata["download_links"]["pdf"]
            if pdf_url:
                # If PDF exists, could redirect here
                # For now, return JSON with PDF URL
                logger.info(f"Returning PDF link for task {task_id}")
                return Response(
                    content=f'{{"pdf_url": "{pdf_url}", "message": "PDF available at the provided URL"}}',
                    media_type="application/json"
                )
            else:
                # PDF not available, return JSON with message
                logger.info(f"PDF not available for task {task_id}, returning JSON")
                return Response(
                    content='{"error": "PDF not available", "message": "PDF version not yet generated. Markdown version available."}',
                    media_type="application/json"
                )
        
        else:  # format == "json" (default)
            # Return full ReportResponse
            report_response = ReportResponse(
                task_id=task_id,
                status=task_status_str,  # Use string status
                report=report_text,
                sources=sources,
                confidence_score=task_result.get("confidence_score", 0.0),
                needs_hitl=task_result.get("needs_hitl", False),
                created_at=created_at,
                metadata=metadata
            )
            
            logger.info(
                f"Report retrieved for task {task_id} | "
                f"status: {task_status_str} | "
                f"sources: {len(sources)} | "
                f"confidence: {task_result.get('confidence_score', 0.0):.2f}"
            )
            
            return report_response
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        logger.error(
            f"Error retrieving report | task_id: {task_id} | error: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "An error occurred while retrieving the report."
            }
        )


@router.get("/debug/{task_id}")
async def debug_task(task_id: str) -> Dict[str, Any]:
    """
    Debug endpoint to inspect task state and workflow execution details.
    
    This endpoint provides detailed information about a task for debugging purposes.
    """
    try:
        if not _validate_task_id(task_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Invalid task_id format"}
            )
        
        task_manager = get_task_manager()
        task_status = task_manager.get_task_status(task_id)
        task_result = task_manager.get_task_result(task_id)
        
        return {
            "task_id": task_id,
            "task_status": task_status,
            "task_result": task_result,
            "has_status": task_status is not None,
            "has_result": task_result is not None,
        }
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e)}
        )
