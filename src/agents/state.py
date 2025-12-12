"""
Agent state definitions for the research workflow.

This module defines the shared state object used by LangGraph-style
agent workflows in the AI Research Assistant project.
"""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class ResearchState(TypedDict, total=False):
    """
    Typed state container for the research agent graph.

    This mirrors the information passed between nodes/agents in a
    LangGraph-style workflow. All fields are optional at the type
    level to allow for incremental construction of the state, but
    most will be populated as the workflow progresses.

    Fields:
        task_id: Unique identifier for the current research task or session.

        user_query: The original natural language question or request
            provided by the user.

        search_queries: List of search query strings derived from the
            user query (e.g., for web, arXiv, or vector store search).

        search_results: List of raw search result objects (e.g., from
            web search APIs, vector search, or internal indexes). Each
            item is typically a dictionary with fields like title, url,
            snippet, score, and metadata.

        retrieved_chunks: List of knowledge chunks retrieved from vector
            search (e.g., Pinecone + S3), typically already normalized
            for downstream use. Each item generally includes fields such
            as text/content, title, url, doc_id, and any other metadata
            needed for citations.

        report_draft: Draft answer or report produced by the generation
            agent before validation or refinement.

        validation_result: Structured output produced by a validation
            or critique agent. This may include flags for correctness,
            completeness, policy issues, and any suggested edits.

        confidence_score: Overall numeric confidence score (0.0–1.0)
            reflecting how confident the system is in the current draft
            or final answer.

        needs_hitl: Boolean flag indicating whether the answer should be
            escalated for Human‑In‑The‑Loop (HITL) review before being
            presented to the user.

        final_report: Final answer or report that is ready to be returned
            to the user (possibly after validation, refinement, or HITL).

        error: Optional error message in case any node/agent in the graph
            encounters a failure. This can be used for debugging, logging,
            or graceful degradation.

        current_agent: Name or identifier of the agent currently handling
            the state (e.g., "planner", "search", "retriever",
            "report_writer", "validator").

        regeneration_count: Number of times the report has been regenerated
            due to rejection. Used to prevent infinite loops.
    """

    task_id: str
    user_query: str
    search_queries: List[str]
    search_results: List[Dict]
    retrieved_chunks: List[Dict]
    report_draft: str
    validation_result: Dict
    confidence_score: float
    needs_hitl: bool
    final_report: str
    error: Optional[str]
    current_agent: str
    regeneration_count: int


__all__ = ["ResearchState"]
