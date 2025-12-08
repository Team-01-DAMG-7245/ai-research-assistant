"""
Task Queue for Background Job Processing

Manages asynchronous execution of research workflows and HITL reviews.
Uses asyncio for non-blocking operations and proper error handling.
"""

import asyncio
import logging
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List

from src.agents.state import ResearchState
from src.api.task_manager import TaskManager, TaskStatus, get_task_manager
from src.utils.s3_client import S3Client

logger = logging.getLogger(__name__)

# Lazy import of compiled_workflow to avoid executing during module import
def _get_compiled_workflow():
    """Lazy import of compiled_workflow to avoid execution during module import."""
    from src.agents.workflow import compiled_workflow
    return compiled_workflow


# ============================================================================
# Workflow Executor
# ============================================================================

class WorkflowExecutor:
    """
    Executes research workflows asynchronously with progress tracking.
    
    Handles workflow execution, progress updates, error handling, and HITL reviews.
    """
    
    def __init__(
        self,
        task_manager: Optional[TaskManager] = None,
        max_workers: int = 4
    ):
        """
        Initialize WorkflowExecutor.
        
        Args:
            task_manager: TaskManager instance (default: get_task_manager())
            max_workers: Maximum number of concurrent workflow executions
        """
        self.task_manager = task_manager or get_task_manager()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"WorkflowExecutor initialized with {max_workers} workers")
    
    async def execute_research_workflow(
        self,
        task_id: str,
        query: str,
        depth: str = "standard"
    ) -> Dict[str, Any]:
        """
        Execute research workflow asynchronously with progress tracking.
        
        Args:
            task_id: Task identifier
            query: Research query string
            depth: Research depth level (quick, standard, comprehensive)
        
        Returns:
            Dictionary with execution result and final state
        """
        logger.info(f"Starting workflow execution for task {task_id} | query: {query[:50]}...")
        
        # Update status to PROCESSING
        self.task_manager.update_task_progress(
            task_id=task_id,
            status=TaskStatus.PROCESSING,
            current_agent="search",
            progress=0
        )
        
        # Initialize ResearchState
        initial_state: ResearchState = {
            "task_id": task_id,
            "user_query": query,
            "current_agent": "search",
            "search_queries": [],
            "search_results": [],
            "retrieved_chunks": [],
            "report_draft": "",
            "validation_result": {},
            "confidence_score": 0.0,
            "needs_hitl": False,
            "final_report": "",
            "error": None,
        }
        
        try:
            # Set API mode environment variable for HITL review agent
            os.environ["API_MODE"] = "true"
            
            # Run workflow in thread pool (since compiled_workflow.invoke is synchronous)
            logger.info(f"Executing workflow in thread pool for task {task_id}")
            final_state = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self._execute_workflow_with_progress,
                task_id,
                initial_state
            )
            logger.info(f"Workflow execution completed for task {task_id}")
            
            # Check for errors in final state
            error = final_state.get("error")
            if error:
                logger.error(
                    f"Workflow completed with error for task {task_id}: {error} | "
                    f"report_draft: {len(final_state.get('report_draft', ''))} chars | "
                    f"final_report: {len(final_state.get('final_report', ''))} chars"
                )
                self.task_manager.mark_task_failed(task_id, error)
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": error,
                    "state": final_state
                }
            
            # Extract final report and metadata
            # Try final_report first, then report_draft as fallback
            final_report = final_state.get("final_report", "")
            if not final_report:
                # Fallback to report_draft if final_report is empty
                report_draft = final_state.get("report_draft", "")
                if report_draft:
                    logger.warning(
                        f"No final_report, using report_draft for task {task_id} | "
                        f"draft length: {len(report_draft)}"
                    )
                    final_report = report_draft
                else:
                    error_msg = "No final report or report_draft generated"
                    logger.error(
                        f"{error_msg} for task {task_id} | "
                        f"state keys: {list(final_state.keys())}"
                    )
                    self.task_manager.mark_task_failed(task_id, error_msg)
                    return {
                        "success": False,
                        "task_id": task_id,
                        "error": error_msg,
                        "state": final_state
                    }
            
            # Extract sources from retrieved_chunks
            sources = self._extract_sources(final_state)
            
            # Store final result
            confidence = final_state.get("confidence_score", 0.0)
            needs_hitl = final_state.get("needs_hitl", False)
            
            self.task_manager.store_task_result(
                task_id=task_id,
                report=final_report,
                sources=sources,
                confidence=confidence,
                needs_hitl=needs_hitl
            )
            
            logger.info(
                f"Workflow completed successfully for task {task_id} | "
                f"confidence: {confidence:.2f} | needs_hitl: {needs_hitl}"
            )
            
            return {
                "success": True,
                "task_id": task_id,
                "state": final_state,
                "report": final_report,
                "confidence": confidence,
                "needs_hitl": needs_hitl
            }
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            error_traceback = traceback.format_exc()
            
            logger.error(
                f"Exception in workflow execution for task {task_id}",
                exc_info=True,
                extra={
                    "task_id": task_id,
                    "error": str(e),
                    "traceback": error_traceback
                }
            )
            
            # Mark task as failed
            self.task_manager.mark_task_failed(task_id, error_msg)
            
            return {
                "success": False,
                "task_id": task_id,
                "error": error_msg,
                "traceback": error_traceback
            }
    
    def _execute_workflow_with_progress(
        self,
        task_id: str,
        initial_state: ResearchState
    ) -> ResearchState:
        """
        Execute workflow synchronously with progress tracking.
        
        This method runs in a thread pool executor to avoid blocking the event loop.
        It tracks agent transitions and updates task progress.
        
        Args:
            task_id: Task identifier
            initial_state: Initial ResearchState
        
        Returns:
            Final ResearchState after workflow execution
        """
        previous_agent = None
        
        try:
            # Use stream_events if available, otherwise use invoke
            # For now, we'll use invoke and track manually
            # In the future, we could use stream_events for real-time progress
            
            # Set API mode for non-interactive execution
            os.environ["API_MODE"] = "true"
            
            # Get compiled workflow (lazy import)
            compiled_workflow = _get_compiled_workflow()
            
            logger.info(f"Invoking workflow for task {task_id}")
            logger.debug(f"Initial state keys: {list(initial_state.keys())}")
            
            # Execute workflow
            final_state = compiled_workflow.invoke(initial_state)
            
            logger.info(f"Workflow invocation completed for task {task_id}")
            logger.debug(f"Final state keys: {list(final_state.keys())}")
            logger.debug(f"Final state report_draft length: {len(final_state.get('report_draft', ''))}")
            logger.debug(f"Final state final_report length: {len(final_state.get('final_report', ''))}")
            logger.debug(f"Final state error: {final_state.get('error')}")
            
            # Track agent transitions (workflow nodes)
            # The workflow goes: search -> synthesis -> validation -> (hitl_review or set_final_report)
            agents_sequence = ["search", "synthesis", "validation"]
            
            # Update progress for each agent transition
            # Note: We can't intercept during execution easily, so we update after
            # In a production system, you might want to use stream_events or callbacks
            
            # For now, we'll update progress based on final state
            current_agent = final_state.get("current_agent", "unknown")
            
            # Determine progress based on workflow completion
            if current_agent in ["hitl_review", "set_final_report"]:
                progress = 100
            elif current_agent == "validation":
                progress = 75
            elif current_agent == "synthesis":
                progress = 50
            elif current_agent == "search":
                progress = 25
            else:
                progress = 0
            
            # Update progress
            self.task_manager.update_task_progress(
                task_id=task_id,
                status=TaskStatus.PROCESSING,
                current_agent=current_agent,
                progress=progress
            )
            
            logger.info(
                f"Workflow step completed for task {task_id} | "
                f"agent: {current_agent} | progress: {progress}%"
            )
            
            return final_state
            
        except Exception as e:
            logger.error(
                f"Error in workflow execution for task {task_id}",
                exc_info=True
            )
            # Return state with error
            error_state = dict(initial_state)
            error_state["error"] = str(e)
            return error_state
    
    def _extract_sources(self, state: ResearchState) -> List[Dict[str, Any]]:
        """
        Extract source information from ResearchState.
        
        Args:
            state: ResearchState with search results and retrieved chunks
        
        Returns:
            List of source dictionaries with source_id, title, url, relevance_score
        """
        sources = []
        source_id = 1
        
        # Extract from retrieved_chunks (preferred - already processed)
        retrieved_chunks = state.get("retrieved_chunks", [])
        for chunk in retrieved_chunks:
            if isinstance(chunk, dict):
                source = {
                    "source_id": source_id,
                    "title": chunk.get("title", chunk.get("metadata", {}).get("title", "Unknown")),
                    "url": chunk.get("url", chunk.get("metadata", {}).get("url", "")),
                    "relevance_score": chunk.get("score", chunk.get("relevance_score", 0.0))
                }
                sources.append(source)
                source_id += 1
        
        # Fallback to search_results if no retrieved_chunks
        if not sources:
            search_results = state.get("search_results", [])
            for result in search_results:
                if isinstance(result, dict):
                    source = {
                        "source_id": source_id,
                        "title": result.get("title", "Unknown"),
                        "url": result.get("url", ""),
                        "relevance_score": result.get("score", result.get("relevance_score", 0.0))
                    }
                    sources.append(source)
                    source_id += 1
        
        return sources
    
    async def process_hitl_review(
        self,
        task_id: str,
        action: str,
        edited_report: Optional[str] = None,
        rejection_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process human-in-the-loop review decision.
        
        Args:
            task_id: Task identifier
            action: Review action (approve, edit, reject)
            edited_report: Edited report text (required if action is 'edit')
            rejection_reason: Rejection reason (required if action is 'reject')
        
        Returns:
            Dictionary with processing result
        """
        logger.info(f"Processing HITL review for task {task_id} | action: {action}")
        
        try:
            # Get task result
            task_result = self.task_manager.get_task_result(task_id)
            if not task_result:
                error_msg = f"Task result not found for task {task_id}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": error_msg
                }
            
            # Check if task is in PENDING_REVIEW status
            task_status = self.task_manager.get_task_status(task_id)
            if not task_status or task_status["status"] != TaskStatus.PENDING_REVIEW:
                error_msg = f"Task {task_id} is not in PENDING_REVIEW status"
                logger.error(error_msg)
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": error_msg
                }
            
            # Process action
            if action == "approve":
                # Approve the existing report
                success = self.task_manager.approve_task(task_id)
                if success:
                    logger.info(f"Task {task_id} approved")
                    return {
                        "success": True,
                        "task_id": task_id,
                        "action": "approve",
                        "message": "Task approved successfully"
                    }
                else:
                    error_msg = f"Failed to approve task {task_id}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "task_id": task_id,
                        "error": error_msg
                    }
            
            elif action == "edit":
                if not edited_report:
                    error_msg = "edited_report is required for 'edit' action"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "task_id": task_id,
                        "error": error_msg
                    }
                
                # Update report and approve
                success = self.task_manager.update_task_report(task_id, edited_report)
                if success:
                    # Approve the edited report
                    approve_success = self.task_manager.approve_task(task_id)
                    if approve_success:
                        logger.info(f"Task {task_id} edited and approved")
                        return {
                            "success": True,
                            "task_id": task_id,
                            "action": "edit",
                            "message": "Report edited and approved successfully"
                        }
                    else:
                        error_msg = f"Failed to approve edited task {task_id}"
                        logger.error(error_msg)
                        return {
                            "success": False,
                            "task_id": task_id,
                            "error": error_msg
                        }
                else:
                    error_msg = f"Failed to update report for task {task_id}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "task_id": task_id,
                        "error": error_msg
                    }
            
            elif action == "reject":
                if not rejection_reason:
                    error_msg = "rejection_reason is required for 'reject' action"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "task_id": task_id,
                        "error": error_msg
                    }
                
                # Mark task as failed with rejection reason
                success = self.task_manager.mark_task_failed(task_id, f"Rejected: {rejection_reason}")
                if success:
                    logger.info(f"Task {task_id} rejected: {rejection_reason}")
                    return {
                        "success": True,
                        "task_id": task_id,
                        "action": "reject",
                        "message": "Task rejected successfully"
                    }
                else:
                    error_msg = f"Failed to reject task {task_id}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "task_id": task_id,
                        "error": error_msg
                    }
            
            else:
                error_msg = f"Invalid action: {action}. Must be 'approve', 'edit', or 'reject'"
                logger.error(error_msg)
                return {
                    "success": False,
                    "task_id": task_id,
                    "error": error_msg
                }
        
        except Exception as e:
            error_msg = f"Error processing HITL review: {str(e)}"
            error_traceback = traceback.format_exc()
            
            logger.error(
                f"Exception in HITL review processing for task {task_id}",
                exc_info=True,
                extra={
                    "task_id": task_id,
                    "action": action,
                    "error": str(e),
                    "traceback": error_traceback
                }
            )
            
            return {
                "success": False,
                "task_id": task_id,
                "error": error_msg,
                "traceback": error_traceback
            }
    
    def shutdown(self):
        """Shutdown executor and cleanup resources."""
        logger.info("Shutting down WorkflowExecutor")
        self.executor.shutdown(wait=True)


# ============================================================================
# Singleton Instance
# ============================================================================

_workflow_executor: Optional[WorkflowExecutor] = None


def get_workflow_executor() -> WorkflowExecutor:
    """
    Get or create global WorkflowExecutor instance.
    
    Returns:
        WorkflowExecutor instance
    """
    global _workflow_executor
    if _workflow_executor is None:
        _workflow_executor = WorkflowExecutor()
    return _workflow_executor


def set_workflow_executor(executor: WorkflowExecutor):
    """
    Set global WorkflowExecutor instance (useful for testing).
    
    Args:
        executor: WorkflowExecutor instance
    """
    global _workflow_executor
    _workflow_executor = executor
