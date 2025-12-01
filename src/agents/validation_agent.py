"""
Validation agent node for the research workflow.

This module defines a LangGraph-style node function that:
  - Validates citations in the report draft
  - Calls GPT-4o Mini to analyze report quality
  - Calculates confidence score based on validation results
  - Determines if human-in-the-loop (HITL) review is needed
  - Updates the shared ResearchState with validation results
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List

from ..utils.openai_client import OpenAIClient
from ..utils.logger import (
    get_agent_logger,
    log_state_transition,
    log_api_call,
    log_performance_metrics,
    log_error_with_context,
)
from .prompts import VALIDATION_AGENT_PROMPT, format_validation_agent_prompt
from .state import ResearchState


logger = get_agent_logger("validation_agent")


def verify_citations(report: str, num_sources: int) -> List[int]:
    """
    Extract all [Source N] citations from report and check if N is within valid range.

    Args:
        report: Report text containing [Source N] citations.
        num_sources: Total number of available sources (valid range is [1, num_sources]).

    Returns:
        List of invalid citation numbers (citations outside the valid range).
    """
    if not report or not num_sources:
        return []

    # Extract all citation numbers using regex
    pattern = r'\[Source\s+(\d+)\]'
    matches = re.findall(pattern, report, re.IGNORECASE)
    citation_numbers = [int(m) for m in matches]

    # Find citations outside valid range [1, num_sources]
    invalid_citations = [
        n for n in citation_numbers if n < 1 or n > num_sources
    ]

    if invalid_citations:
        logger.warning(
            "Found %d invalid citations: %s (valid range: 1-%d)",
            len(invalid_citations),
            invalid_citations,
            num_sources,
        )

    return invalid_citations


def _parse_validation_response(response_text: str) -> Dict[str, Any]:
    """
    Parse the LLM validation response as JSON.

    The expected format is:
        {
            "valid": true/false,
            "confidence": 0.0-1.0,
            "issues": ["issue1", "issue2", ...],
            "citation_coverage": 0.0-1.0,
            "unsupported_claims": ["claim1", "claim2", ...]
        }

    Args:
        response_text: Raw text returned by the LLM.

    Returns:
        Parsed validation result dictionary.

    Raises:
        ValueError: If JSON parsing fails or response is invalid.
    """
    # Try to extract JSON from the response (in case there's extra text)
    response_text = response_text.strip()

    # Look for JSON object in the response
    json_start = response_text.find("{")
    json_end = response_text.rfind("}") + 1

    if json_start == -1 or json_end == 0:
        raise ValueError("No JSON object found in validation response")

    json_str = response_text[json_start:json_end]

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse validation JSON: %s", exc)
        logger.debug("Response text: %s", response_text)
        raise ValueError(f"Invalid JSON in validation response: {exc}") from exc

    # Validate required fields
    required_fields = ["valid", "confidence"]
    for field in required_fields:
        if field not in result:
            raise ValueError(f"Missing required field '{field}' in validation response")

    # Ensure optional fields have defaults
    result.setdefault("issues", [])
    result.setdefault("citation_coverage", 0.0)
    result.setdefault("unsupported_claims", [])

    # Validate confidence score range
    confidence = float(result.get("confidence", 0.0))
    if confidence < 0.0 or confidence > 1.0:
        logger.warning("Confidence score out of range [0.0, 1.0]: %f, clamping", confidence)
        result["confidence"] = max(0.0, min(1.0, confidence))

    return result


def _calculate_confidence_score(
    llm_confidence: float,
    invalid_citations: List[int],
    unsupported_claims: List[str],
    has_contradictions: bool,
) -> float:
    """
    Calculate final confidence score with deductions.

    Args:
        llm_confidence: Base confidence score from LLM (0.0-1.0).
        invalid_citations: List of invalid citation numbers.
        unsupported_claims: List of claims without citations.
        has_contradictions: Whether contradictions were found.

    Returns:
        Final confidence score (0.0-1.0).
    """
    confidence = float(llm_confidence)

    # Deduct 0.3 if invalid citations found
    if invalid_citations:
        confidence -= 0.3
        logger.info("Deducting 0.3 for invalid citations: %s", invalid_citations)

    # Deduct 0.2 if 3+ missing citations
    if len(unsupported_claims) >= 3:
        confidence -= 0.2
        logger.info("Deducting 0.2 for %d unsupported claims", len(unsupported_claims))

    # Deduct 0.3 if contradictions found
    if has_contradictions:
        confidence -= 0.3
        logger.info("Deducting 0.3 for contradictions found")

    # Clamp to [0.0, 1.0]
    confidence = max(0.0, min(1.0, confidence))

    return confidence


def validation_agent_node(state: ResearchState) -> ResearchState:
    """
    Validation agent node that validates the research report.

    This function:
      1. Extracts report_draft and retrieved_chunks from state
      2. Verifies citations using verify_citations() helper
      3. Calls GPT-4o Mini with VALIDATION_AGENT_PROMPT
      4. Parses JSON response with validation results
      5. Calculates confidence_score with deductions
      6. Determines needs_hitl flag (confidence_score < 0.7)
      7. Updates state with validation_result, confidence_score, and needs_hitl

    Args:
        state: ResearchState containing report_draft and retrieved_chunks.

    Returns:
        Updated ResearchState with validation results.
    """
    start_time = time.time()
    task_id = state.get("task_id", "unknown")
    
    logger.info("=" * 70)
    logger.info("VALIDATION AGENT - Entry | task_id=%s", task_id)
    logger.debug("Input state keys: %s", list(state.keys()))
    
    new_state = dict(state)
    new_state["current_agent"] = "validation"

    try:
        report_draft = state.get("report_draft", "")
        retrieved_chunks = state.get("retrieved_chunks", [])

        if not report_draft:
            error_msg = "report_draft is required in state for validation agent"
            log_error_with_context(logger, ValueError(error_msg), "validation_agent_node", task_id=task_id)
            new_state["error"] = error_msg
            new_state["validation_result"] = {
                "valid": False,
                "confidence": 0.0,
                "issues": [error_msg],
                "citation_coverage": 0.0,
                "unsupported_claims": [],
            }
            new_state["confidence_score"] = 0.0
            new_state["needs_hitl"] = True
            return new_state

        logger.info("Validating report | report_length=%d chars | word_count=%d", 
                   len(report_draft), len(report_draft.split()))

        num_sources = len(retrieved_chunks)
        if num_sources == 0:
            logger.warning("No retrieved_chunks found in state, using search_results count")
            search_results = state.get("search_results", [])
            num_sources = len(search_results)

        # 1) Verify citations
        citation_start_time = time.time()
        logger.info("Verifying citations in report | num_sources=%d", num_sources)
        invalid_citations = verify_citations(report_draft, num_sources)
        citation_duration = time.time() - citation_start_time
        logger.info(
            "Citation verification completed | invalid_citations=%d | duration=%.2fs",
            len(invalid_citations),
            citation_duration,
        )
        if invalid_citations:
            logger.warning("Invalid citations found: %s", invalid_citations)

        # 2) Format sources for validation prompt
        # Use retrieved_chunks if available, otherwise use search_results
        sources = retrieved_chunks if retrieved_chunks else state.get("search_results", [])
        
        # Format sources as list of dicts with 'content' key for the prompt formatter
        source_dicts = []
        for chunk in sources:
            source_dicts.append({
                "content": chunk.get("text", "") or chunk.get("content", ""),
                "title": chunk.get("title", ""),
                "doc_id": chunk.get("doc_id", ""),
            })

        # 3) Call GPT-4o Mini with VALIDATION_AGENT_PROMPT
        validation_start_time = time.time()
        logger.info("Calling OpenAI API for validation | model=gpt-4o-mini | temperature=0.1")
        openai_client = OpenAIClient()

        prompt = format_validation_agent_prompt(
            report=report_draft,
            sources=source_dicts
        )

        messages = [{"role": "user", "content": prompt}]

        try:
            llm_response = openai_client.chat_completion(
                messages=messages,
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"},
                operation="validation",
                task_id=task_id,
            )

            validation_duration = time.time() - validation_start_time
            response_text = llm_response.get("content", "").strip()
            usage = llm_response.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            cost = llm_response.get("cost", 0.0)

            log_api_call(
                logger,
                operation="validation",
                model="gpt-4o-mini",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration=validation_duration,
                cost=cost,
                task_id=task_id,
            )

        except Exception as exc:
            log_error_with_context(logger, exc, "openai_validation", task_id=task_id)
            new_state["error"] = f"validation_agent_openai_error: {exc}"
            new_state["validation_result"] = {
                "valid": False,
                "confidence": 0.0,
                "issues": [f"API call failed: {exc}"],
                "citation_coverage": 0.0,
                "unsupported_claims": [],
            }
            new_state["confidence_score"] = 0.0
            new_state["needs_hitl"] = True
            return new_state

        # 4) Parse JSON response
        parse_start_time = time.time()
        try:
            validation_result = _parse_validation_response(response_text)
            parse_duration = time.time() - parse_start_time
            logger.info(
                "Validation response parsed | valid=%s | llm_confidence=%.2f | duration=%.2fs",
                validation_result.get("valid"),
                validation_result.get("confidence"),
                parse_duration,
            )
        except Exception as exc:
            log_error_with_context(logger, exc, "parse_validation_response", task_id=task_id)
            new_state["error"] = f"validation_agent_parse_error: {exc}"
            new_state["validation_result"] = {
                "valid": False,
                "confidence": 0.0,
                "issues": [f"Failed to parse response: {exc}"],
                "citation_coverage": 0.0,
                "unsupported_claims": [],
            }
            new_state["confidence_score"] = 0.0
            new_state["needs_hitl"] = True
            return new_state

        # 5) Calculate confidence score with deductions
        confidence_start_time = time.time()
        unsupported_claims = validation_result.get("unsupported_claims", [])
        # Check if contradictions are mentioned in issues
        issues = validation_result.get("issues", [])
        has_contradictions = any(
            "contradict" in issue.lower() or "inconsistent" in issue.lower()
            for issue in issues
        )

        llm_confidence = float(validation_result.get("confidence", 0.0))
        confidence_score = _calculate_confidence_score(
            llm_confidence=llm_confidence,
            invalid_citations=invalid_citations,
            unsupported_claims=unsupported_claims,
            has_contradictions=has_contradictions,
        )
        confidence_duration = time.time() - confidence_start_time

        # 6) Determine needs_hitl
        needs_hitl = confidence_score < 0.7

        # Add citation verification results to validation_result
        validation_result["invalid_citations"] = invalid_citations
        validation_result["has_contradictions"] = has_contradictions
        validation_result["final_confidence"] = confidence_score

        # 7) Update state
        new_state["validation_result"] = validation_result
        new_state["confidence_score"] = confidence_score
        new_state["needs_hitl"] = needs_hitl
        new_state["error"] = None

        total_duration = time.time() - start_time
        log_performance_metrics(
            logger,
            operation="validation_agent_complete",
            duration=total_duration,
            task_id=task_id,
            confidence_score=confidence_score,
            needs_hitl=needs_hitl,
            invalid_citations=len(invalid_citations),
            unsupported_claims=len(unsupported_claims),
            citation_duration=citation_duration,
            validation_duration=validation_duration,
        )
        
        log_state_transition(
            logger,
            from_state="synthesis",
            to_state="validation",
            task_id=task_id,
            confidence_score=confidence_score,
            needs_hitl=needs_hitl,
        )
        
        logger.info(
            "VALIDATION AGENT - Exit | task_id=%s | confidence=%.2f | needs_hitl=%s | duration=%.2fs",
            task_id,
            confidence_score,
            needs_hitl,
            total_duration,
        )
        logger.info("=" * 70)

        return new_state

    except Exception as exc:
        total_duration = time.time() - start_time
        log_error_with_context(
            logger,
            exc,
            "validation_agent_node",
            task_id=task_id,
            duration=total_duration,
        )
        new_state["error"] = f"validation_agent_node_error: {exc}"
        # Ensure we always have these keys present
        new_state.setdefault("validation_result", {
            "valid": False,
            "confidence": 0.0,
            "issues": [str(exc)],
            "citation_coverage": 0.0,
            "unsupported_claims": [],
        })
        new_state.setdefault("confidence_score", 0.0)
        new_state.setdefault("needs_hitl", True)
        return new_state


__all__ = ["validation_agent_node", "verify_citations"]

