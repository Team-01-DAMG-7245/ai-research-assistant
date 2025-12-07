"""
Review API Endpoint for HITL (Human-In-The-Loop) review
"""

import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Path, status

from ..models import ReviewRequest, ReviewResponse, TaskStatus, ErrorResponse
from ..task_manager import get_task_manager
from ..workflow_executor import get_workflow_executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["review"])


@router.post("/review/{task_id}", response_model=ReviewResponse)
async def submit_review(
    task_id: str = Path(..., description="Task identifier (UUID)"),
    request: ReviewRequest = ...
):
    """
    Submit HITL review action (approve, edit, or reject)
    """
    # Validate task_id matches request
    if task_id != request.task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="task_id in path does not match task_id in request body"
        )
    
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
    
    # Check if task is pending review
    task_status = TaskStatus(task['status'])
    if task_status != TaskStatus.PENDING_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task {task_id} is not pending review. Current status: {task_status.value}"
        )
    
    # Process review action
    try:
        workflow_executor = get_workflow_executor()
        result = await workflow_executor.process_hitl_review(
            task_id=task_id,
            action=request.action.value,
            edited_report=request.edited_report,
            rejection_reason=request.rejection_reason
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to process review action")
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing review for task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing review: {str(e)}"
        )
    
    # Get updated task for message
    updated_task = task_manager.get_task(task_id)
    message_map = {
        "approve": "Report approved successfully",
        "edit": "Report edited and approved successfully",
        "reject": "Report rejected"
    }
    message = message_map.get(request.action.value, "Review action processed")
    
    logger.info(f"Review action {request.action.value} completed for task {task_id}")
    
    return ReviewResponse(
        task_id=task_id,
        message=message,
        action=request.action,
        updated_at=datetime.utcnow()
    )
