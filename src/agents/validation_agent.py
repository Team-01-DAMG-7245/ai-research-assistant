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
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from ..utils.openai_client import OpenAIClient
from .prompts import VALIDATION_AGENT_PROMPT, format_validation_agent_prompt
from .state import ResearchState


logger = logging.getLogger(__name__)

# Ensure validation agent logs are also written to a file for later inspection
_LOGS_PATH = Path(__file__).parent.parent / "logs"
_LOGS_PATH.mkdir(exist_ok=True)
_LOG_FILE = _LOGS_PATH / "validation_agent.log"

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
    new_state = dict(state)
    new_state["current_agent"] = "validation"

    try:
        report_draft = state.get("report_draft", "")
        retrieved_chunks = state.get("retrieved_chunks", [])

        if not report_draft:
            error_msg = "report_draft is required in state for validation agent"
            logger.error(error_msg)
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

        task_id = state.get("task_id", "unknown")
        logger.info("Validation agent started for task_id=%s", task_id)

        num_sources = len(retrieved_chunks)
        if num_sources == 0:
            logger.warning("No retrieved_chunks found in state, using search_results count")
            search_results = state.get("search_results", [])
            num_sources = len(search_results)

        # 1) Verify citations
        logger.info("Verifying citations in report (num_sources=%d)", num_sources)
        invalid_citations = verify_citations(report_draft, num_sources)
        logger.info("Found %d invalid citations", len(invalid_citations))

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
        logger.info("Calling OpenAI validation agent model")
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
                operation="validation",
            )

            response_text = llm_response.get("content", "").strip()
            usage = llm_response.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            cost = llm_response.get("cost", 0.0)

            logger.info(
                "Validation API call: %d tokens, cost: $%.6f",
                total_tokens,
                cost,
            )

        except Exception as exc:
            logger.exception("OpenAI API call failed: %s", exc)
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
        try:
            validation_result = _parse_validation_response(response_text)
            logger.info("Parsed validation result: valid=%s, confidence=%.2f",
                       validation_result.get("valid"),
                       validation_result.get("confidence"))
        except Exception as exc:
            logger.exception("Failed to parse validation response: %s", exc)
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

        logger.info(
            "Validation completed: confidence=%.2f, needs_hitl=%s, invalid_citations=%d, unsupported_claims=%d",
            confidence_score,
            needs_hitl,
            len(invalid_citations),
            len(unsupported_claims),
        )

        # Log to file
        logger.info(
            "Validation result | task_id=%s | confidence=%.2f | needs_hitl=%s | invalid_citations=%d | unsupported_claims=%d",
            task_id,
            confidence_score,
            needs_hitl,
            len(invalid_citations),
            len(unsupported_claims),
        )

        return new_state

    except Exception as exc:
        logger.exception("validation_agent_node encountered an error: %s", exc)
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

