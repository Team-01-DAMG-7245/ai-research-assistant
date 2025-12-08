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

import time
from typing import Any, Dict, List, Set

from ..utils.openai_client import OpenAIClient
from ..utils.pinecone_rag import (
    semantic_search,
    retrieve_full_chunks,
    prepare_context,
)
from ..utils.logger import (
    get_agent_logger,
    log_state_transition,
    log_api_call,
    log_performance_metrics,
    log_error_with_context,
)
from .prompts import SYNTHESIS_AGENT_SYSTEM_PROMPT, SYNTHESIS_AGENT_USER_PROMPT
from .state import ResearchState


logger = get_agent_logger("synthesis_agent")


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
    start_time = time.time()
    task_id = state.get("task_id", "unknown")
    
    logger.info("=" * 70)
    logger.info("SYNTHESIS AGENT - Entry | task_id=%s", task_id)
    logger.debug("Input state keys: %s", list(state.keys()))
    
    new_state = dict(state)
    new_state["current_agent"] = "synthesis"

    try:
        user_query = state.get("user_query", "")
        if not user_query:
            error_msg = "user_query is required in state for synthesis agent"
            log_error_with_context(logger, ValueError(error_msg), "synthesis_agent_node", task_id=task_id)
            new_state["error"] = error_msg
            return new_state

        logger.info("Processing user query: %s", user_query[:100])

        # 1) Search Pinecone for top-15 semantically relevant chunks
        # (increased from 10 to ensure we have enough sources after deduplication)
        pinecone_start_time = time.time()
        logger.info("Searching Pinecone for top-15 chunks using user_query")
        try:
            pinecone_results = semantic_search(
                user_query, top_k=15, namespace="research_papers", task_id=task_id
            )
            pinecone_duration = time.time() - pinecone_start_time
            logger.info(
                "Pinecone search completed | results=%d | duration=%.2fs",
                len(pinecone_results),
                pinecone_duration,
            )
        except Exception as exc:
            log_error_with_context(logger, exc, "pinecone_search", task_id=task_id)
            pinecone_results = []

        # 2) Extract chunk_ids and retrieve full chunks from S3
        s3_start_time = time.time()
        chunk_ids: List[str] = []
        for result in pinecone_results:
            # chunk_id is now included in semantic_search results
            chunk_id = result.get("chunk_id") or result.get("id", "")
            if chunk_id:
                chunk_ids.append(str(chunk_id))

        logger.info("Retrieving %d full chunks from S3", len(chunk_ids))
        try:
            pinecone_chunks = retrieve_full_chunks(chunk_ids) if chunk_ids else []
            s3_duration = time.time() - s3_start_time
            logger.info(
                "S3 retrieval completed | retrieved=%d/%d | duration=%.2fs",
                len(pinecone_chunks),
                len(chunk_ids),
                s3_duration,
            )
            if len(pinecone_chunks) < len(chunk_ids):
                logger.warning(
                    "Some chunks missing from S3 | requested=%d | retrieved=%d",
                    len(chunk_ids),
                    len(pinecone_chunks),
                )
            
            # Merge URL and other metadata from Pinecone results into retrieved chunks
            # Create a lookup map from chunk_id to Pinecone result
            pinecone_result_map = {result.get("chunk_id") or result.get("id", ""): result 
                                  for result in pinecone_results}
            
            for chunk in pinecone_chunks:
                chunk_id = chunk.get("chunk_id") or chunk.get("doc_id", "")
                if chunk_id in pinecone_result_map:
                    result = pinecone_result_map[chunk_id]
                    # Preserve URL from Pinecone metadata if available
                    if "url" not in chunk or not chunk.get("url"):
                        chunk["url"] = result.get("url", "")
                    # Preserve title if not in chunk
                    if "title" not in chunk or not chunk.get("title"):
                        chunk["title"] = result.get("title", "")
                    # Preserve doc_id if not in chunk
                    if "doc_id" not in chunk or not chunk.get("doc_id"):
                        chunk["doc_id"] = result.get("doc_id", "")
                    # Preserve score from Pinecone
                    if "score" not in chunk:
                        chunk["score"] = result.get("score", 0.0)
        except Exception as exc:
            log_error_with_context(logger, exc, "s3_retrieval", task_id=task_id, chunk_count=len(chunk_ids))
            pinecone_chunks = []

        # 3) Combine Pinecone chunks with search_results from Search Agent
        combine_start_time = time.time()
        search_results = state.get("search_results", [])
        logger.info(
            "Combining sources | pinecone_chunks=%d | search_results=%d",
            len(pinecone_chunks),
            len(search_results),
        )
        all_sources = _combine_sources(pinecone_chunks, search_results)
        combine_duration = time.time() - combine_start_time

        if not all_sources:
            error_msg = "No sources available for synthesis (no Pinecone chunks or search results)"
            logger.warning(error_msg)
            new_state["error"] = error_msg
            new_state["retrieved_chunks"] = []
            new_state["source_count"] = 0
            new_state["report_draft"] = ""
            return new_state

        # Check if we have minimum sources (5 recommended for good citations)
        min_sources = 5
        if len(all_sources) < min_sources:
            logger.warning(
                "Only %d sources available for synthesis (recommended minimum: %d) | task_id=%s",
                len(all_sources),
                min_sources,
                task_id
            )
        
        # Limit to ~20-30 sources as specified
        max_sources = 30
        if len(all_sources) > max_sources:
            logger.info("Limiting sources from %d to %d", len(all_sources), max_sources)
            all_sources = all_sources[:max_sources]

        logger.info(
            "Source combination completed | unique_sources=%d | duration=%.2fs",
            len(all_sources),
            combine_duration,
        )

        # 4) Format sources using prepare_context()
        context_start_time = time.time()
        context_text = prepare_context(all_sources)
        context_duration = time.time() - context_start_time
        logger.info(
            "Context preparation completed | sources=%d | context_length=%d chars | duration=%.2fs",
            len(all_sources),
            len(context_text),
            context_duration,
        )

        # 5) Call GPT-4o Mini with SYNTHESIS_AGENT_PROMPT
        synthesis_start_time = time.time()
        logger.info("Calling OpenAI API for report generation | model=gpt-4o-mini | temperature=0.3")
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
                operation="synthesis",
                task_id=task_id,
            )

            synthesis_duration = time.time() - synthesis_start_time
            report_draft = llm_response.get("content", "").strip()
            usage = llm_response.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            cost = llm_response.get("cost", 0.0)
            word_count = len(report_draft.split())

            log_api_call(
                logger,
                operation="synthesis",
                model="gpt-4o-mini",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration=synthesis_duration,
                cost=cost,
                task_id=task_id,
            )

            logger.info(
                "Report generated | words=%d | tokens=%d (prompt: %d, completion: %d) | cost=$%.6f",
                word_count,
                total_tokens,
                prompt_tokens,
                completion_tokens,
                cost,
            )

        except Exception as exc:
            log_error_with_context(logger, exc, "openai_synthesis", task_id=task_id)
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

        total_duration = time.time() - start_time
        log_performance_metrics(
            logger,
            operation="synthesis_agent_complete",
            duration=total_duration,
            task_id=task_id,
            sources_used=len(all_sources),
            word_count=word_count,
            pinecone_duration=pinecone_duration,
            s3_duration=s3_duration,
            synthesis_duration=synthesis_duration,
        )
        
        log_state_transition(
            logger,
            from_state="search_agent",
            to_state="synthesis",
            task_id=task_id,
            sources=len(all_sources),
            word_count=word_count,
        )
        
        logger.info("SYNTHESIS AGENT - Exit | task_id=%s | duration=%.2fs", task_id, total_duration)
        logger.info("=" * 70)

        return new_state

    except Exception as exc:
        total_duration = time.time() - start_time
        log_error_with_context(
            logger,
            exc,
            "synthesis_agent_node",
            task_id=task_id,
            duration=total_duration,
        )
        new_state["error"] = f"synthesis_agent_node_error: {exc}"
        # Ensure we always have these keys present
        new_state.setdefault("retrieved_chunks", [])
        new_state.setdefault("source_count", 0)
        new_state.setdefault("report_draft", "")
        return new_state


__all__ = ["synthesis_agent_node"]

