"""
Synthesis agent node for the research workflow.

This module defines a LangGraph-style node function that:
  - Retrieves additional relevant chunks from Pinecone using the user query
  - Combines Pinecone chunks with search_results from the Search Agent
  - Formats all sources into numbered citations using prepare_context()
  - Generates a comprehensive 1200-1500 word research report using GPT-4o Mini
  - Updates the shared ResearchState with report_draft, retrieved_chunks, and source_count
  - Logs token usage and cost
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Set

from ..utils.openai_client import OpenAIClient
from ..utils.pinecone_rag import (
    semantic_search,
    retrieve_full_chunks,
    prepare_context,
)
from .prompts import SYNTHESIS_AGENT_SYSTEM_PROMPT, SYNTHESIS_AGENT_USER_PROMPT
from .state import ResearchState


logger = logging.getLogger(__name__)

# Ensure synthesis agent logs are also written to a file for later inspection
_LOGS_PATH = Path(__file__).parent.parent / "logs"
_LOGS_PATH.mkdir(exist_ok=True)
_LOG_FILE = _LOGS_PATH / "synthesis_agent.log"

if not any(
    isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(_LOG_FILE)
    for h in logger.handlers
):
    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


def _deduplicate_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate chunks by chunk_id or doc_id.

    Args:
        chunks: List of chunk dictionaries.

    Returns:
        Deduplicated list of chunks, preserving order.
    """
    seen: Set[str] = set()
    deduplicated: List[Dict[str, Any]] = []

    for chunk in chunks:
        # Use chunk_id first, fallback to doc_id
        identifier = chunk.get("chunk_id") or chunk.get("doc_id") or ""
        if identifier and identifier not in seen:
            seen.add(identifier)
            deduplicated.append(chunk)
        elif not identifier:
            # If no identifier, include it anyway (shouldn't happen in practice)
            deduplicated.append(chunk)

    return deduplicated


def _combine_sources(
    pinecone_chunks: List[Dict[str, Any]],
    search_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Combine Pinecone chunks with search_results from Search Agent.

    Args:
        pinecone_chunks: Chunks retrieved from Pinecone and S3.
        search_results: Raw search results from the Search Agent.

    Returns:
        Combined and deduplicated list of source chunks.
    """
    combined: List[Dict[str, Any]] = []

    # Add Pinecone chunks (already have full text from S3)
    combined.extend(pinecone_chunks)

    # Convert search_results to chunk format
    # search_results typically have: doc_id, score, text, title, url, metadata
    for result in search_results:
        chunk = {
            "chunk_id": result.get("chunk_id") or result.get("doc_id", ""),
            "doc_id": result.get("doc_id", ""),
            "text": result.get("text", ""),
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "score": result.get("score", 0.0),
            "metadata": result.get("metadata", {}),
        }
        combined.append(chunk)

    # Deduplicate by chunk_id/doc_id
    deduplicated = _deduplicate_chunks(combined)

    logger.info(
        "Combined %d Pinecone chunks + %d search results = %d unique sources",
        len(pinecone_chunks),
        len(search_results),
        len(deduplicated),
    )

    return deduplicated


def synthesis_agent_node(state: ResearchState) -> ResearchState:
    """
    Synthesis agent node that generates a comprehensive research report.

    This function:
      1. Converts user_query to embedding and searches Pinecone for top-10 chunks
      2. Retrieves full chunk text from S3
      3. Combines Pinecone chunks with search_results from Search Agent
      4. Formats sources using prepare_context()
      5. Generates a 1200-1500 word report using GPT-4o Mini
      6. Updates state with report_draft, retrieved_chunks, and source_count

    Args:
        state: ResearchState containing user_query and search_results.

    Returns:
        Updated ResearchState with report_draft, retrieved_chunks, and source_count.
    """
    new_state = dict(state)
    new_state["current_agent"] = "synthesis"

    try:
        user_query = state.get("user_query", "")
        if not user_query:
            error_msg = "user_query is required in state for synthesis agent"
            logger.error(error_msg)
            new_state["error"] = error_msg
            return new_state

        task_id = state.get("task_id", "unknown")
        logger.info("Synthesis agent started for task_id=%s", task_id)

        # 1) Search Pinecone for top-10 semantically relevant chunks
        logger.info("Searching Pinecone for top-10 chunks using user_query")
        try:
            pinecone_results = semantic_search(user_query, top_k=10, namespace="research_papers")
            logger.info("Pinecone search returned %d results", len(pinecone_results))
        except Exception as exc:
            logger.exception("Pinecone search failed: %s", exc)
            pinecone_results = []

        # 2) Extract chunk_ids and retrieve full chunks from S3
        chunk_ids: List[str] = []
        for result in pinecone_results:
            # chunk_id is now included in semantic_search results
            chunk_id = result.get("chunk_id") or result.get("id", "")
            if chunk_id:
                chunk_ids.append(str(chunk_id))

        logger.info("Retrieving %d full chunks from S3", len(chunk_ids))
        try:
            pinecone_chunks = retrieve_full_chunks(chunk_ids) if chunk_ids else []
            logger.info("Retrieved %d/%d chunks from S3", len(pinecone_chunks), len(chunk_ids))
        except Exception as exc:
            logger.exception("Failed to retrieve chunks from S3: %s", exc)
            pinecone_chunks = []

        # 3) Combine Pinecone chunks with search_results from Search Agent
        search_results = state.get("search_results", [])
        all_sources = _combine_sources(pinecone_chunks, search_results)

        if not all_sources:
            error_msg = "No sources available for synthesis (no Pinecone chunks or search results)"
            logger.warning(error_msg)
            new_state["error"] = error_msg
            new_state["retrieved_chunks"] = []
            new_state["source_count"] = 0
            new_state["report_draft"] = ""
            return new_state

        # Limit to ~20-30 sources as specified
        max_sources = 30
        if len(all_sources) > max_sources:
            logger.info("Limiting sources from %d to %d", len(all_sources), max_sources)
            all_sources = all_sources[:max_sources]

        # 4) Format sources using prepare_context()
        context_text = prepare_context(all_sources)
        logger.info("Prepared context with %d sources, length=%d chars", len(all_sources), len(context_text))

        # 5) Call GPT-4o Mini with SYNTHESIS_AGENT_PROMPT
        logger.info("Calling OpenAI synthesis agent model to generate report")
        openai_client = OpenAIClient()

        # Use prepare_context() output directly in the prompt
        user_prompt = SYNTHESIS_AGENT_USER_PROMPT.format(
            topic=user_query,
            sources=context_text
        )

        messages = [
            {"role": "system", "content": SYNTHESIS_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        try:
            llm_response = openai_client.chat_completion(
                messages=messages,
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=2000,
            )

            report_draft = llm_response.get("content", "").strip()
            usage = llm_response.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            cost = llm_response.get("cost", 0.0)

            logger.info(
                "Generated report: %d words, %d tokens (prompt: %d, completion: %d), cost: $%.6f",
                len(report_draft.split()),
                total_tokens,
                prompt_tokens,
                completion_tokens,
                cost,
            )

            # Log to file
            logger.info(
                "Report generated | task_id=%s | words=%d | tokens=%d | cost=$%.6f",
                task_id,
                len(report_draft.split()),
                total_tokens,
                cost,
            )

        except Exception as exc:
            logger.exception("OpenAI API call failed: %s", exc)
            new_state["error"] = f"synthesis_agent_openai_error: {exc}"
            new_state["retrieved_chunks"] = all_sources
            new_state["source_count"] = len(all_sources)
            new_state["report_draft"] = ""
            return new_state

        # 7) Update state
        new_state["report_draft"] = report_draft
        new_state["retrieved_chunks"] = all_sources
        new_state["source_count"] = len(all_sources)
        new_state["error"] = None

        logger.info(
            "Synthesis agent completed: %d sources, %d words in report",
            len(all_sources),
            len(report_draft.split()),
        )

        return new_state

    except Exception as exc:
        logger.exception("synthesis_agent_node encountered an error: %s", exc)
        new_state["error"] = f"synthesis_agent_node_error: {exc}"
        # Ensure we always have these keys present
        new_state.setdefault("retrieved_chunks", [])
        new_state.setdefault("source_count", 0)
        new_state.setdefault("report_draft", "")
        return new_state


__all__ = ["synthesis_agent_node"]

