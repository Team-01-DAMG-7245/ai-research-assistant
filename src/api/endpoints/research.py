"""
Research API Endpoint
"""

import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse

from ..models import ResearchRequest, ResearchResponse, TaskStatus, ErrorResponse
from ..task_manager import get_task_manager
from ..workflow_executor import get_workflow_executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["research"])


@router.post("/research", response_model=ResearchResponse, status_code=status.HTTP_201_CREATED)
async def submit_research(
    request: ResearchRequest,
    background_tasks: BackgroundTasks
):
    """
    Submit a research query for processing
    
    Returns task_id immediately and processes in background
    """
    task_manager = get_task_manager()
    
    try:
        # Create task
        task_id = task_manager.create_task(
            query=request.query,
            user_id=request.user_id,
            metadata={
                "depth": request.depth.value,
                "submitted_at": datetime.utcnow().isoformat()
            }
        )
        
        # Add background task to execute workflow
        workflow_executor = get_workflow_executor()
        background_tasks.add_task(
            workflow_executor.execute_research_workflow,
            task_id=task_id,
            query=request.query,
            user_id=request.user_id
        )
        
        logger.info(f"Created research task {task_id} for query: {request.query[:50]}...")
        
        return ResearchResponse(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            message="Research task created and queued for processing",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.exception(f"Error creating research task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create research task: {str(e)}"
        )
