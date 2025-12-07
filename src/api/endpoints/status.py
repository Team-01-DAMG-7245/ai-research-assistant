"""
Status API Endpoint
"""

import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Path, status

from ..models import StatusResponse, TaskStatus, ErrorResponse
from ..task_manager import get_task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["status"])


@router.get("/status/{task_id}", response_model=StatusResponse)
async def get_task_status(
    task_id: str = Path(..., description="Task identifier (UUID)")
):
    """
    Get the status of a research task
    """
    # Validate UUID format
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id format. Must be a valid UUID."
        )
    
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    # Parse datetime strings
    created_at = datetime.fromisoformat(task['created_at'])
    updated_at = None
    if task.get('updated_at'):
        updated_at = datetime.fromisoformat(task['updated_at'])
    
    return StatusResponse(
        task_id=task_id,
        status=TaskStatus(task['status']),
        progress=task.get('progress'),
        message=task.get('message'),
        created_at=created_at,
        updated_at=updated_at,
        error=task.get('error')
    )
