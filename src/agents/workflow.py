"""
LangGraph workflow for the AI Research Assistant.

This module builds and compiles the complete research agent workflow,
connecting all agents (search, synthesis, validation, HITL review) into
a single executable graph.
"""

from __future__ import annotations

from typing import Literal

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    raise ImportError("LangGraph is required. Install it with: pip install langgraph")

from ..utils.logger import get_workflow_logger, log_state_transition
from .state import ResearchState
from .search_agent import search_agent_node
from .synthesis_agent import synthesis_agent_node
from .validation_agent import validation_agent_node
from .hitl_review import hitl_review_node


logger = get_workflow_logger()


def set_final_report_node(state: ResearchState) -> ResearchState:
    """
    Helper node to set final_report when HITL review is skipped.

    This ensures final_report is set to report_draft when needs_hitl is False.

    Args:
        state: Current ResearchState.

    Returns:
        Updated ResearchState with final_report set.
    """
    task_id = state.get("task_id", "unknown")
    new_state = dict(state)
    report_draft = state.get("report_draft", "")
    if report_draft and not new_state.get("final_report"):
        new_state["final_report"] = report_draft
        logger.info(
            "Set final_report to report_draft (HITL review skipped) | task_id=%s",
            task_id,
        )
        log_state_transition(
            logger,
            from_state="validation",
            to_state="set_final_report",
            task_id=task_id,
            action="auto_approve",
        )
    return new_state


def handle_max_retries_node(state: ResearchState) -> ResearchState:
    """
    Helper node to handle max regeneration retries exceeded.

    Sets a clear error message and returns state to end workflow.

    Args:
        state: Current ResearchState.

    Returns:
        Updated ResearchState with error set.
    """
    task_id = state.get("task_id", "unknown")
    regeneration_count = state.get("regeneration_count", 0)
    new_state = dict(state)
    new_state[
        "error"
    ] = f"Max regeneration attempts ({regeneration_count}) exceeded. Report could not be improved after multiple attempts."
    new_state["final_report"] = ""
    logger.error(
        "Max regenerations exceeded, ending workflow | task_id=%s | attempts=%d",
        task_id,
        regeneration_count,
    )
    log_state_transition(
        logger,
        from_state="hitl_review",
        to_state="end",
        task_id=task_id,
        action="max_retries_exceeded",
    )
    return new_state


def route_after_validation(
    state: ResearchState,
) -> Literal["hitl_review", "set_final_report"]:
    """
    Conditional routing function after validation agent.

    Routes to HITL review if needs_hitl is True, otherwise sets final_report and ends.

    Args:
        state: Current ResearchState.

    Returns:
        "hitl_review" if needs_hitl is True, "set_final_report" otherwise.
    """
    task_id = state.get("task_id", "unknown")
    needs_hitl = state.get("needs_hitl", False)
    confidence_score = state.get("confidence_score", 0.0)

    if needs_hitl:
        logger.info(
            "Routing to HITL review | task_id=%s | confidence=%.2f | needs_hitl=True | reason=confidence_below_threshold",
            task_id,
            confidence_score,
        )
        log_state_transition(
            logger,
            from_state="validation",
            to_state="hitl_review",
            task_id=task_id,
            confidence_score=confidence_score,
        )
        return "hitl_review"
    else:
        logger.info(
            "Skipping HITL review | task_id=%s | confidence=%.2f | needs_hitl=False | reason=confidence_above_threshold(>=0.7)",
            task_id,
            confidence_score,
        )
        log_state_transition(
            logger,
            from_state="validation",
            to_state="set_final_report",
            task_id=task_id,
            confidence_score=confidence_score,
        )
        return "set_final_report"


def route_after_hitl(
    state: ResearchState,
) -> Literal["search", "set_final_report", "handle_max_retries"]:
    """
    Conditional routing function after HITL review.

    Routes based on HITL review outcome:
    - If rejected and retry count < max: route back to search for regeneration
    - If rejected and retry count >= max: end with error
    - If approved/edited: route to set_final_report

    Args:
        state: Current ResearchState.

    Returns:
        "search" if regeneration needed, "set_final_report" if approved/edited, "end" if max retries exceeded.
    """
    task_id = state.get("task_id", "unknown")
    error = state.get("error", "")
    final_report = state.get("final_report", "")
    regeneration_count = state.get("regeneration_count", 0)
    MAX_REGENERATIONS = 2  # Maximum number of regeneration attempts

    # Check if report was rejected
    is_rejected = (
        error and "rejected" in error.lower() and "regeneration" in error.lower()
    )

    if is_rejected:
        # regeneration_count was already incremented in HITL node
        if regeneration_count <= MAX_REGENERATIONS:
            # Reset state for regeneration (clear previous results but keep query)
            logger.info(
                "Report rejected, regenerating | task_id=%s | attempt=%d/%d",
                task_id,
                regeneration_count,
                MAX_REGENERATIONS,
            )
            log_state_transition(
                logger,
                from_state="hitl_review",
                to_state="search",
                task_id=task_id,
                action="regenerate",
                regeneration_count=regeneration_count,
            )
            # Return "search" to restart the workflow
            return "search"
        else:
            # Max retries exceeded, end with error
            logger.error(
                "Max regenerations exceeded | task_id=%s | attempts=%d",
                task_id,
                regeneration_count,
            )
            return "handle_max_retries"
    elif final_report and final_report.strip():
        # Report was approved or edited, proceed to final
        logger.info(
            "HITL review completed successfully | task_id=%s",
            task_id,
        )
        log_state_transition(
            logger,
            from_state="hitl_review",
            to_state="set_final_report",
            task_id=task_id,
            action="approved_or_edited",
        )
        return "set_final_report"
    elif not final_report and not error:
        # No final_report and no error means pending review (API mode)
        # The workflow executor will handle setting status to PENDING_REVIEW
        logger.info(
            "HITL review pending (awaiting API review) | task_id=%s",
            task_id,
        )
        log_state_transition(
            logger,
            from_state="hitl_review",
            to_state="pending_review",
            task_id=task_id,
            action="pending",
        )
        # Return "end" to stop workflow - API will resume when review is submitted
        return "end"
    else:
        # Unexpected state, end with error
        logger.warning(
            "Unexpected HITL review state | task_id=%s | error=%s | final_report=%s",
            task_id,
            error,
            bool(final_report),
        )
        return "handle_max_retries"


def build_workflow() -> StateGraph:
    """
    Build the complete research agent workflow graph.

    The workflow structure:
        1. search_agent (entry point)
        2. synthesis_agent
        3. validation_agent
        4. Conditional routing:
           - If needs_hitl=True → hitl_review
           - If needs_hitl=False → set_final_report → END
        5. After HITL review, conditional routing:
           - If rejected and retries < max → search (regeneration)
           - If rejected and retries >= max → END (error)
           - If approved/edited → set_final_report → END

    Returns:
        Compiled StateGraph ready for execution.
    """
    # Create StateGraph with ResearchState schema
    workflow = StateGraph(ResearchState)

    # Add all nodes to the graph
    workflow.add_node("search", search_agent_node)
    workflow.add_node("synthesis", synthesis_agent_node)
    workflow.add_node("validation", validation_agent_node)
    workflow.add_node("hitl_review", hitl_review_node)
    workflow.add_node("set_final_report", set_final_report_node)
    workflow.add_node("handle_max_retries", handle_max_retries_node)

    # Set entry point
    workflow.set_entry_point("search")

    # Add edges
    workflow.add_edge("search", "synthesis")
    workflow.add_edge("synthesis", "validation")

    # Conditional edge: validation → hitl_review or set_final_report
    workflow.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "hitl_review": "hitl_review",
            "set_final_report": "set_final_report",
        },
    )

    # Conditional edge: hitl_review → search (regenerate) or set_final_report or END
    workflow.add_conditional_edges(
        "hitl_review",
        route_after_hitl,
        {
            "search": "search",  # Regenerate: loop back to search
            "set_final_report": "set_final_report",  # Approved/edited: proceed to final
            "handle_max_retries": "handle_max_retries",  # Max retries exceeded: handle error
            "end": END,  # Pending review: end workflow, wait for API
        },
    )

    # set_final_report and handle_max_retries go to END
    workflow.add_edge("set_final_report", END)
    workflow.add_edge("handle_max_retries", END)

    logger.info("Research agent workflow graph built successfully")
    return workflow


def compile_workflow() -> StateGraph:
    """
    Build and compile the research agent workflow.

    Returns:
        Compiled StateGraph ready for execution.
    """
    workflow = build_workflow()
    compiled = workflow.compile()
    logger.info("Research agent workflow compiled successfully")
    return compiled


# Compile the workflow at module import time
compiled_workflow = compile_workflow()


__all__ = [
    "build_workflow",
    "compile_workflow",
    "compiled_workflow",
    "route_after_validation",
    "route_after_hitl",
    "set_final_report_node",
]
