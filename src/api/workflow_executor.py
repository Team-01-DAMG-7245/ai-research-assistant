"""
Workflow Executor for running research workflows in background
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.agents.state import ResearchState
from src.agents.workflow import compiled_workflow

from .models import TaskStatus
from .task_manager import TaskManager, get_task_manager

logger = logging.getLogger(__name__)

# Singleton instance
_workflow_executor: Optional["WorkflowExecutor"] = None


def get_workflow_executor() -> "WorkflowExecutor":
    """Get or create the singleton WorkflowExecutor instance"""
    global _workflow_executor
    if _workflow_executor is None:
        _workflow_executor = WorkflowExecutor()
    return _workflow_executor


class WorkflowExecutor:
    """Executes research workflows in background"""

    def __init__(self):
        """Initialize workflow executor"""
        self.task_manager = get_task_manager()
        logger.info("WorkflowExecutor initialized")

    async def execute_research_workflow(
        self, task_id: str, query: str, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute research workflow asynchronously

        Args:
            task_id: Task identifier
            query: Research query
            user_id: Optional user identifier

        Returns:
            Dictionary with workflow results
        """
        try:
            # Update status to processing
            self.task_manager.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                progress=10.0,
                message="Starting research workflow...",
            )

            # Initialize state
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
                "regeneration_count": 0,
            }

            # Initial progress update (agents will update their own progress)
            # This is just to show workflow has started
            self.task_manager.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                progress=10.0,
                message="Workflow started. Initializing agents...",
            )

            # Run workflow in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            final_state = await loop.run_in_executor(
                None, lambda: compiled_workflow.invoke(initial_state)
            )

            # Check for errors
            if final_state.get("error"):
                error_msg = final_state.get("error", "Unknown error")
                self.task_manager.mark_task_failed(task_id, error_msg)
                return {"success": False, "task_id": task_id, "error": error_msg}

            # Extract results
            final_report = final_state.get("final_report", "")
            report_draft = final_state.get("report_draft", "")
            confidence_score = final_state.get("confidence_score", 0.0)
            original_needs_hitl = final_state.get("needs_hitl", False)

            # If final_report exists and is not empty, HITL review was completed
            # (either approved, edited, or auto-approved), so needs_hitl should be False
            if final_report and final_report.strip():
                needs_hitl = False  # HITL review completed successfully
                report_to_store = final_report
            else:
                needs_hitl = (
                    original_needs_hitl  # Use original value if no final report
                )
                # If final_report is empty but report_draft exists, use report_draft
                # This happens when workflow ends with needs_hitl=True (pending review)
                if report_draft and report_draft.strip():
                    report_to_store = report_draft
                else:
                    report_to_store = final_report  # Fallback to empty string

            # Get sources from retrieved chunks
            retrieved_chunks = final_state.get("retrieved_chunks", [])
            sources = []

            # Include up to 20 sources (recommend at least 5 for good citation coverage)
            min_sources_recommended = 5
            max_sources = 20
            num_chunks_to_include = min(len(retrieved_chunks), max_sources)

            # Warn if we have fewer than recommended minimum
            if len(retrieved_chunks) < min_sources_recommended:
                logger.warning(
                    "Only %d sources available (recommended minimum: %d) | task_id=%s",
                    len(retrieved_chunks),
                    min_sources_recommended,
                    task_id,
                )

            for i, chunk in enumerate(retrieved_chunks[:num_chunks_to_include], 1):
                # Extract URL, with fallback to constructing from arxiv_id/doc_id
                url = chunk.get("url") or chunk.get("pdf_url", "")

                # If no URL, try to construct from arxiv_id/doc_id
                if not url:
                    arxiv_id = chunk.get("doc_id") or chunk.get("arxiv_id", "")
                    if arxiv_id:
                        # Construct arXiv PDF URL: https://arxiv.org/pdf/{arxiv_id}.pdf
                        url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

                sources.append(
                    {
                        "source_id": i,
                        "title": chunk.get("title", chunk.get("doc_id", "Unknown")),
                        "url": url,
                        "relevance_score": 1.0 - (i * 0.02),  # Decreasing relevance
                    }
                )

            # Store results in database
            self.task_manager.store_task_result(
                task_id=task_id,
                report=report_to_store,
                sources=sources,
                confidence=confidence_score,
                needs_hitl=needs_hitl,
                metadata={
                    "search_queries": final_state.get("search_queries", []),
                    "num_sources": len(retrieved_chunks),
                    "user_id": user_id,
                    "hitl_completed": not original_needs_hitl
                    or (final_report and final_report.strip()),
                    "validation_result": final_state.get("validation_result", {}),
                },
            )

            logger.info(
                f"Workflow completed for task {task_id}, confidence={confidence_score:.2f}, needs_hitl={needs_hitl}"
            )

            return {
                "success": True,
                "task_id": task_id,
                "report": report_to_store,
                "confidence": confidence_score,
                "needs_hitl": needs_hitl,
                "sources": sources,
            }

        except Exception as e:
            logger.exception(f"Error executing workflow for task {task_id}: {e}")
            self.task_manager.mark_task_failed(task_id, str(e))
            return {"success": False, "task_id": task_id, "error": str(e)}

    async def process_hitl_review(
        self,
        task_id: str,
        action: str,
        edited_report: Optional[str] = None,
        rejection_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process HITL review action

        Args:
            task_id: Task identifier
            action: Review action (approve, edit, reject)
            edited_report: Edited report (for edit action)
            rejection_reason: Rejection reason (for reject action)

        Returns:
            Dictionary with review results
        """
        # Ensure database is initialized
        self.task_manager._init_database()
        task_manager = self.task_manager

        if action == "approve":
            success = task_manager.approve_review(task_id)
            if success:
                return {"success": True, "task_id": task_id, "action": "approve"}
        elif action == "edit":
            if not edited_report:
                return {
                    "success": False,
                    "error": "edited_report is required for edit action",
                }
            success = task_manager.edit_review(task_id, edited_report)
            if success:
                return {"success": True, "task_id": task_id, "action": "edit"}
        elif action == "reject":
            if not rejection_reason:
                return {
                    "success": False,
                    "error": "rejection_reason is required for reject action",
                }
            success, original_query = task_manager.reject_review(
                task_id, rejection_reason
            )
            if success:
                # Return the original query so the caller can restart the workflow
                return {
                    "success": True,
                    "task_id": task_id,
                    "action": "reject",
                    "original_query": original_query,
                }
        else:
            return {"success": False, "error": f"Invalid action: {action}"}

        return {
            "success": False,
            "error": "Task not found or not in pending review status",
        }
