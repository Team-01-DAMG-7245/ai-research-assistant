"""
Search agent node for the research workflow.

This module defines a LangGraph-style node function that:
  - Expands the user's question into multiple search queries using GPT-4o Mini
  - Runs semantic search against Pinecone for each query
  - Deduplicates and ranks results
  - Updates the shared ResearchState with search queries and results
  - Logs queries and top results to a persistent log file for debugging
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple

from ..utils.openai_client import OpenAIClient
from ..utils.pinecone_rag import semantic_search
from ..utils.logger import (
    get_agent_logger,
    log_state_transition,
    log_api_call,
    log_performance_metrics,
    log_error_with_context,
)
from .prompts import format_search_agent_prompt
from .state import ResearchState

# Import task manager for status updates (only when needed)
try:
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))
    from src.api.task_manager import get_task_manager
    from src.api.models import TaskStatus
    TASK_MANAGER_AVAILABLE = True
except ImportError:
    TASK_MANAGER_AVAILABLE = False

logger = get_agent_logger("search_agent")


def _parse_search_queries(response_text: str) -> List[str]:
    """
    Parse the LLM response as JSON and extract the list of queries.

    The expected format is:
        {"queries": ["query1", "query2", ...]}

    Args:
        response_text: Raw text returned by the LLM.

    Returns:
        List of query strings.

    Raises:
        ValueError: If the JSON is invalid or does not contain a 'queries' list.
    """
    try:
        # Try direct JSON parse first
        data = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to recover by extracting the first JSON object substring
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM response is not valid JSON and could not be recovered")
        data = json.loads(response_text[start : end + 1])

    if not isinstance(data, dict) or "queries" not in data:
        raise ValueError("JSON response must contain a 'queries' field")

    queries = data["queries"]
    if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
        raise ValueError("'queries' field must be a list of strings")

    # Filter out empty / whitespace-only queries
    cleaned = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
    if not cleaned:
        raise ValueError("No valid queries found in LLM response")

    return cleaned


def _deduplicate_and_rank(results_by_query: List[Tuple[str, List[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
    """
    Deduplicate search results across queries and rank by score.

    Deduplication key preference:
      1. URL (if present)
      2. doc_id (if present)

    Args:
        results_by_query: List of (query, results) tuples where results come
            from `semantic_search`.

    Returns:
        List of unique results sorted by descending score.
    """
    best_by_key: Dict[str, Dict[str, Any]] = {}

    for query, results in results_by_query:
        for item in results:
            url = item.get("url")
            doc_id = item.get("doc_id")
            key = url or doc_id

            # If neither URL nor doc_id is available, skip dedup keying
            if not key:
                continue

            # Track the originating query for debugging/traceability
            if "origin_query" not in item:
                item["origin_query"] = query

            score = item.get("score") or 0.0

            if key not in best_by_key or (best_by_key[key].get("score") or 0.0) < score:
                best_by_key[key] = item

    # Sort by descending score
    unique_results = list(best_by_key.values())
    unique_results.sort(key=lambda r: r.get("score") or 0.0, reverse=True)

    return unique_results


def search_agent_node(state: ResearchState) -> ResearchState:
    """
    LangGraph-style node that runs the search agent.

    Steps:
      1. Extract `user_query` from the state.
      2. Use GPT-4o Mini with `SEARCH_AGENT_PROMPT` to generate 3–5 search queries.
      3. Parse the JSON response to extract queries.
      4. For each query, call Pinecone `semantic_search()` to get top-10 results.
      5. Deduplicate results by URL/doc_id.
      6. Rank by relevance score.
      7. Take the top 20 overall results.
      8. Update the state with `search_queries` and `search_results`.
      9. Handle errors gracefully and log progress.

    Args:
        state: Current `ResearchState` dictionary.

    Returns:
        Updated `ResearchState` with search information.
    """
    start_time = time.time()
    task_id = state.get("task_id", "unknown")
    
    logger.info("=" * 70)
    logger.info("SEARCH AGENT - Entry | task_id=%s", task_id)
    logger.debug("Input state keys: %s", list(state.keys()))
    
    # Update task status to show search agent is running
    if TASK_MANAGER_AVAILABLE:
        try:
            task_manager = get_task_manager()
            task_manager.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                progress=40.0,
                message="Searching for relevant papers..."
            )
            logger.info("Updated task status: Search agent running | task_id=%s", task_id)
        except Exception as e:
            logger.warning("Failed to update task status: %s", e)
    
    new_state: ResearchState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "search_agent"

    user_query = state.get("user_query")  # type: ignore[assignment]
    if not user_query or not isinstance(user_query, str) or not user_query.strip():
        msg = "search_agent_node: 'user_query' is missing or empty in state"
        log_error_with_context(logger, ValueError(msg), "search_agent_node", task_id=task_id)
        new_state["error"] = msg
        new_state.setdefault("search_queries", [])
        new_state.setdefault("search_results", [])
        return new_state

    try:
        logger.info("Processing user query: %s", user_query[:100])

        # 1) Generate search queries with GPT-4o Mini
        query_start_time = time.time()
        client = OpenAIClient()
        prompt = format_search_agent_prompt(user_query)
        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]

        logger.debug("Calling OpenAI API for query expansion | model=gpt-4o-mini | temperature=0.3")
        llm_response = client.chat_completion(
            messages=messages,
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=500,
            operation="query_expansion",
            task_id=task_id,
        )

        query_duration = time.time() - query_start_time
        raw_content = llm_response.get("content", "")
        prompt_tokens = llm_response.get("prompt_tokens", 0)
        completion_tokens = llm_response.get("completion_tokens", 0)
        cost = llm_response.get("cost", 0.0)
        
        log_api_call(
            logger,
            operation="query_expansion",
            model="gpt-4o-mini",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration=query_duration,
            cost=cost,
            task_id=task_id,
        )
        
        logger.debug("Raw LLM response length: %d characters", len(raw_content))

        queries = _parse_search_queries(raw_content)
        logger.info("Generated %d search queries: %s", len(queries), queries)

        # 2) Run semantic search for each query
        search_start_time = time.time()
        results_by_query: List[Tuple[str, List[Dict[str, Any]]]] = []
        total_results = 0
        
        for idx, q in enumerate(queries, 1):
            try:
                logger.debug("Semantic search %d/%d | query='%s'", idx, len(queries), q)
                query_search_start = time.time()
                results = semantic_search(q, top_k=10, namespace="research_papers", task_id=task_id)
                query_search_duration = time.time() - query_search_start
                
                logger.info(
                    "Semantic search completed | query='%s' | results=%d | duration=%.2fs",
                    q,
                    len(results),
                    query_search_duration,
                )
                results_by_query.append((q, results))
                total_results += len(results)
            except Exception as exc:
                log_error_with_context(
                    logger,
                    exc,
                    "semantic_search",
                    task_id=task_id,
                    query=q,
                    query_index=idx,
                )
                # Continue with other queries instead of failing the whole node
                continue

        search_duration = time.time() - search_start_time
        log_performance_metrics(
            logger,
            operation="semantic_search_all_queries",
            duration=search_duration,
            task_id=task_id,
            queries_processed=len(results_by_query),
            total_results_before_dedup=total_results,
        )

        # 3) Combine, deduplicate, and rank results
        dedup_start_time = time.time()
        combined_results: List[Dict[str, Any]] = []
        if results_by_query:
            deduped = _deduplicate_and_rank(results_by_query)
            combined_results = deduped[:20]
            dedup_duration = time.time() - dedup_start_time

            logger.info(
                "Deduplication completed | input_results=%d | unique_results=%d | "
                "final_results=%d | duration=%.2fs",
                total_results,
                len(deduped),
                len(combined_results),
                dedup_duration,
            )

            # Log top results for debugging / audit
            logger.debug("Top search results:")
            for i, result in enumerate(combined_results[:10], start=1):  # Log top 10
                logger.debug(
                    "  %d. doc_id=%s | score=%.4f | title='%s' | origin_query='%s'",
                    i,
                    result.get("doc_id", "N/A"),
                    float(result.get("score") or 0.0),
                    (result.get("title") or "N/A")[:100],
                    result.get("origin_query", "N/A"),
                )
        else:
            logger.warning("No search results obtained for any query | task_id=%s", task_id)

        # 4) Update state
        new_state["search_queries"] = queries
        new_state["search_results"] = combined_results
        new_state["error"] = None

        total_duration = time.time() - start_time
        log_performance_metrics(
            logger,
            operation="search_agent_complete",
            duration=total_duration,
            task_id=task_id,
            queries_generated=len(queries),
            final_results=len(combined_results),
        )
        
        log_state_transition(
            logger,
            from_state="entry",
            to_state="search_agent",
            task_id=task_id,
            queries=len(queries),
            results=len(combined_results),
        )
        
        logger.info("SEARCH AGENT - Exit | task_id=%s | duration=%.2fs", task_id, total_duration)
        logger.info("=" * 70)

        return new_state

    except Exception as exc:
        total_duration = time.time() - start_time
        log_error_with_context(
            logger,
            exc,
            "search_agent_node",
            task_id=task_id,
            duration=total_duration,
        )
        new_state["error"] = f"search_agent_node_error: {exc}"
        # Ensure we always have these keys present
        new_state.setdefault("search_queries", [])
        new_state.setdefault("search_results", [])
        return new_state


__all__ = ["search_agent_node"]


