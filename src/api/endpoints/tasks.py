# src/api/endpoints/tasks.py
"""
Tasks endpoint for listing and managing research tasks
Compatible with existing research.py
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Optional, Any
from datetime import datetime
from src.api.task_manager import get_task_manager

router = APIRouter(prefix="/api/v1", tags=["Tasks"])

@router.get("/tasks")
async def get_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
) -> Dict[str, Any]:
    """
    Get all tasks from the database
    
    Args:
        status: Optional status filter
        limit: Maximum number of tasks to return
        offset: Number of tasks to skip
    
    Returns:
        Dictionary containing tasks list and pagination info
    """
    try:
        task_manager = get_task_manager()
        
        # Get all tasks from database
        all_tasks = task_manager.get_all_tasks(status=status, limit=limit, offset=offset)
        
        # Return in the format expected by the frontend
        return {
            "tasks": all_tasks,
            "total": len(all_tasks),
            "count": len(all_tasks),
            "limit": limit,
            "offset": offset,
            "has_more": len(all_tasks) == limit if limit else False,
            "status_filter": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tasks: {str(e)}")

@router.get("/tasks/{task_id}")
async def get_task_by_id(task_id: str) -> Dict:
    """
    Get a specific task by ID
    
    Args:
        task_id: Task ID
    
    Returns:
        Task details
    """
    try:
        task_manager = get_task_manager()
        
        # Get task status
        task_status = task_manager.get_task_status(task_id)
        
        if not task_status:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
        # Get task result if available
        task_result = task_manager.get_task_result(task_id)
        
        # Combine status and result
        task_data = {**task_status}
        if task_result:
            task_data.update({
                "report": task_result.get("report"),
                "sources": task_result.get("sources"),
                "confidence_score": task_result.get("confidence_score"),
                "needs_hitl": task_result.get("needs_hitl"),
                "s3_url": task_result.get("s3_url")
            })
        
        return task_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching task: {str(e)}")