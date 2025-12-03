"""
HITL Review API Endpoints

Handles human-in-the-loop review submissions for flagged reports.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from src.api.models import HITLReviewRequest, HITLAction
from src.api.task_manager import get_task_manager, TaskStatus
from src.api.task_queue import get_workflow_executor

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["Review"])


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


@router.post("/review/{task_id}")
async def submit_hitl_review(
    task_id: str,
    review: HITLReviewRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Submit human review decision for flagged reports.
    
    Available actions:
    - approve: Accept report as-is
    - edit: Approve with modifications
    - reject: Reject and optionally regenerate
    
    Args:
        task_id: UUID of the task under review
        review: Review decision and optional content
        background_tasks: For async processing
    
    Returns:
        Success message with task_id and action
    
    Raises:
        HTTPException(404): Task not found
        HTTPException(400): Invalid task_id or action
        HTTPException(409): Task not pending review
        HTTPException(500): Server error
    """
    try:
        # Validate task_id format
        if not _validate_task_id(task_id):
            logger.warning(f"Invalid task_id format: {task_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid task_id format",
                    "message": "task_id must be a valid UUID"
                }
            )
        
        # Ensure task_id in review matches path parameter
        if review.task_id != task_id:
            logger.warning(
                f"Task ID mismatch | path: {task_id} | body: {review.task_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Task ID mismatch",
                    "message": "task_id in request body must match path parameter"
                }
            )
        
        # Validate action
        if review.action not in [HITLAction.APPROVE, HITLAction.EDIT, HITLAction.REJECT]:
            logger.warning(f"Invalid action: {review.action}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid action",
                    "message": "action must be one of: approve, edit, reject"
                }
            )
        
        # Get task manager
        task_manager = get_task_manager()
        
        # Check task status
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
        
        task_status = task_status_data["status"]
        
        # Verify task is in PENDING_REVIEW status
        if task_status != TaskStatus.PENDING_REVIEW:
            logger.warning(
                f"Task not pending review | task_id: {task_id} | status: {task_status}"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Task not pending review",
                    "message": f"Task is not in PENDING_REVIEW status. Current status: {task_status}",
                    "current_status": task_status
                }
            )
        
        # Validate action-specific requirements
        action_str = review.action.value if hasattr(review.action, 'value') else str(review.action)
        
        if action_str == "edit":
            if not review.edited_report or not review.edited_report.strip():
                logger.warning(f"Edit action requires edited_report | task_id: {task_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Missing edited_report",
                        "message": "edited_report is required when action is 'edit'"
                    }
                )
            
            # Basic validation of edited content
            if len(review.edited_report.strip()) < 10:
                logger.warning(f"Edited report too short | task_id: {task_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid edited_report",
                        "message": "edited_report must be at least 10 characters"
                    }
                )
        
        elif action_str == "reject":
            if not review.rejection_reason or not review.rejection_reason.strip():
                logger.warning(f"Reject action requires rejection_reason | task_id: {task_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Missing rejection_reason",
                        "message": "rejection_reason is required when action is 'reject'"
                    }
                )
        
        # Get workflow executor
        workflow_executor = get_workflow_executor()
        
        # Extract reviewer information (if available from request context)
        # For now, we'll use the task's user_id if available
        reviewer_id = task_status_data.get("user_id", "unknown")
        
        # Log review decision
        logger.info(
            f"HITL review submitted | "
            f"task_id: {task_id} | "
            f"action: {action_str} | "
            f"reviewer: {reviewer_id} | "
            f"timestamp: {datetime.utcnow().isoformat()}"
        )
        
        # Queue background task for processing
        try:
            background_tasks.add_task(
                workflow_executor.process_hitl_review,
                task_id,
                action_str,
                review.edited_report,
                review.rejection_reason
            )
        except Exception as e:
            logger.error(
                f"Failed to queue HITL review task | task_id: {task_id} | error: {str(e)}",
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Task queuing failed",
                    "message": "Failed to queue review task for processing. Please try again."
                }
            )
        
        # Return immediate response
        response = {
            "message": "Review submitted successfully",
            "task_id": task_id,
            "action": action_str,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(
            f"HITL review queued successfully | "
            f"task_id: {task_id} | "
            f"action: {action_str}"
        )
        
        return response
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        logger.error(
            f"Unexpected error in submit_hitl_review | "
            f"task_id: {task_id} | "
            f"error: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "An unexpected error occurred while processing your review."
            }
        )

