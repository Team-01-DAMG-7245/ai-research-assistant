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
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..utils.openai_client import OpenAIClient
from ..utils.pinecone_rag import semantic_search
from .prompts import format_search_agent_prompt
from .state import ResearchState


logger = logging.getLogger(__name__)

# Ensure search agent logs are also written to a file for later inspection
_LOGS_PATH = Path(__file__).parent.parent / "logs"
_LOGS_PATH.mkdir(exist_ok=True)
_LOG_FILE = _LOGS_PATH / "search_agent.log"

if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(_LOG_FILE) for h in logger.handlers):
    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


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
    new_state: ResearchState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "search_agent"

    user_query = state.get("user_query")  # type: ignore[assignment]
    if not user_query or not isinstance(user_query, str) or not user_query.strip():
        msg = "search_agent_node: 'user_query' is missing or empty in state"
        logger.error(msg)
        new_state["error"] = msg
        new_state.setdefault("search_queries", [])
        new_state.setdefault("search_results", [])
        return new_state

    try:
        logger.info("Search agent started for task_id=%s", state.get("task_id"))

        # 1) Generate search queries with GPT-4o Mini
        client = OpenAIClient()
        prompt = format_search_agent_prompt(user_query)
        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]

        logger.info("Calling OpenAI search agent model to generate search queries")
        llm_response = client.chat_completion(
            messages=messages,
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=500,
            operation="query_expansion",
        )

        raw_content = llm_response.get("content", "")
        logger.debug("Raw LLM search-agent response: %s", raw_content)

        queries = _parse_search_queries(raw_content)
        logger.info("Generated %d search queries from LLM", len(queries))

        # 2) Run semantic search for each query
        results_by_query: List[Tuple[str, List[Dict[str, Any]]]] = []
        for q in queries:
            try:
                logger.info("Running semantic search for query: %s", q)
                results = semantic_search(q, top_k=10)
                logger.info("Got %d results for query", len(results))
                results_by_query.append((q, results))
            except Exception as exc:
                logger.exception("Semantic search failed for query '%s': %s", q, exc)
                # Continue with other queries instead of failing the whole node
                continue

        # 3) Combine, deduplicate, and rank results
        combined_results: List[Dict[str, Any]] = []
        if results_by_query:
            deduped = _deduplicate_and_rank(results_by_query)
            combined_results = deduped[:20]

            logger.info(
                "Combined %d queries into %d unique results (top 20 returned)",
                len(results_by_query),
                len(combined_results),
            )

            # Log detailed results to file for debugging / audit
            for i, result in enumerate(combined_results, start=1):
                logger.info(
                    "Result %d | doc_id=%s | score=%.4f | title=%s | origin_query=%s",
                    i,
                    result.get("doc_id"),
                    float(result.get("score") or 0.0),
                    (result.get("title") or "")[:200],
                    result.get("origin_query"),
                )
        else:
            logger.warning("No search results were obtained for any query")

        # 4) Update state
        new_state["search_queries"] = queries
        new_state["search_results"] = combined_results
        new_state["error"] = None

        return new_state

    except Exception as exc:
        logger.exception("search_agent_node encountered an error: %s", exc)
        new_state["error"] = f"search_agent_node_error: {exc}"
        # Ensure we always have these keys present
        new_state.setdefault("search_queries", [])
        new_state.setdefault("search_results", [])
        return new_state


__all__ = ["search_agent_node"]


