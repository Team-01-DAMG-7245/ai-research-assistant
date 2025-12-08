# src/api/endpoints/review.py
"""
HITL Review endpoints for the AI Research Assistant API
"""

from fastapi import APIRouter, HTTPException
from typing import Dict
from datetime import datetime
from pydantic import BaseModel

from src.api.task_manager import get_task_manager, TaskStatus

router = APIRouter(prefix="/api/v1", tags=["Review"])

class ReviewRequest(BaseModel):
    """Simple review request model"""
    action: str  # "approve" or "reject"
    task_id: str
    rejection_reason: str = None

@router.post("/review/{task_id}")
async def submit_review(task_id: str, request: ReviewRequest) -> Dict:
    """
    Submit a human-in-the-loop review for a task.
    
    Args:
        task_id: Task ID
        request: Review request with action and optional reason
    
    Returns:
        Review result
    """
    task_manager = get_task_manager()
    task_status_data = task_manager.get_task_status(task_id)
    
    if not task_status_data:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    # Check if task is in reviewable state
    current_status = task_status_data.get("status", "").lower()
    if current_status != "pending_review":
        raise HTTPException(
            status_code=400, 
            detail=f"Task is not pending review. Current status: {current_status}"
        )
    
    # Process review action
    if request.action == "approve":
        task_manager.approve_task(task_id)
        return {
            "task_id": task_id,
            "action": "approved",
            "message": "Report approved successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    elif request.action == "reject":
        if not request.rejection_reason:
            raise HTTPException(status_code=400, detail="Rejection reason is required")
        
        task_manager.reject_task(task_id, request.rejection_reason)
        return {
            "task_id": task_id,
            "action": "rejected",
            "reason": request.rejection_reason,
            "message": "Report rejected",
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")
    
    raise HTTPException(status_code=500, detail="Failed to process review")