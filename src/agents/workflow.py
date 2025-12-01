"""
LangGraph workflow for the AI Research Assistant.

This module builds and compiles the complete research agent workflow,
connecting all agents (search, synthesis, validation, HITL review) into
a single executable graph.
"""

from __future__ import annotations

import logging
from typing import Literal

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    raise ImportError(
        "LangGraph is required. Install it with: pip install langgraph"
    )

from .state import ResearchState
from .search_agent import search_agent_node
from .synthesis_agent import synthesis_agent_node
from .validation_agent import validation_agent_node
from .hitl_review import hitl_review_node


logger = logging.getLogger(__name__)


def set_final_report_node(state: ResearchState) -> ResearchState:
    """
    Helper node to set final_report when HITL review is skipped.

    This ensures final_report is set to report_draft when needs_hitl is False.

    Args:
        state: Current ResearchState.

    Returns:
        Updated ResearchState with final_report set.
    """
    new_state = dict(state)
    report_draft = state.get("report_draft", "")
    if report_draft and not new_state.get("final_report"):
        new_state["final_report"] = report_draft
        logger.info("Set final_report to report_draft (HITL review skipped)")
    return new_state


def route_after_validation(state: ResearchState) -> Literal["hitl_review", "set_final_report"]:
    """
    Conditional routing function after validation agent.

    Routes to HITL review if needs_hitl is True, otherwise sets final_report and ends.

    Args:
        state: Current ResearchState.

    Returns:
        "hitl_review" if needs_hitl is True, "set_final_report" otherwise.
    """
    needs_hitl = state.get("needs_hitl", False)
    
    if needs_hitl:
        logger.info("Routing to HITL review (needs_hitl=True)")
        return "hitl_review"
    else:
        logger.info("Skipping HITL review (needs_hitl=False), setting final_report")
        return "set_final_report"


def build_workflow() -> StateGraph:
    """
    Build the complete research agent workflow graph.

    The workflow structure:
        1. search_agent (entry point)
        2. synthesis_agent
        3. validation_agent
        4. Conditional routing:
           - If needs_hitl=True → hitl_review → END
           - If needs_hitl=False → set_final_report → END

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
    
    # Both hitl_review and set_final_report go to END
    workflow.add_edge("hitl_review", END)
    workflow.add_edge("set_final_report", END)

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
    "set_final_report_node",
]

