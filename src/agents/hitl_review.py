"""
Human-In-The-Loop (HITL) review node for the research workflow.

This module defines a LangGraph-style node function that:
  - Checks if human review is needed (needs_hitl flag)
  - Displays report draft and validation issues to the user
  - Prompts for user action: Approve, Edit, or Reject
  - Updates state based on user decision
  - Logs review decisions

Note: This is a console-based implementation for testing.
A Streamlit UI will be built in M4 for production use.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict

from ..utils.logger import (
    get_agent_logger,
    log_state_transition,
    log_performance_metrics,
    log_error_with_context,
)
from .state import ResearchState


logger = get_agent_logger("hitl_review")


def _display_report_summary(report_draft: str, max_preview: int = 1000) -> None:
    """
    Display a preview of the report draft to the console.

    Args:
        report_draft: The report text to display.
        max_preview: Maximum number of characters to display in preview.
    """
    print("\n" + "=" * 70)
    print("REPORT DRAFT PREVIEW")
    print("=" * 70)
    
    if len(report_draft) > max_preview:
        print(report_draft[:max_preview])
        print(f"\n... (truncated, full report is {len(report_draft)} characters)")
    else:
        print(report_draft)
    
    print("=" * 70)


def _display_validation_info(validation_result: Dict[str, Any], confidence_score: float) -> None:
    """
    Display validation information to the console.

    Args:
        validation_result: Validation result dictionary.
        confidence_score: Final confidence score.
    """
    print("\n" + "=" * 70)
    print("VALIDATION INFORMATION")
    print("=" * 70)
    
    print(f"Confidence Score: {confidence_score:.2f}")
    print(f"Valid: {validation_result.get('valid', False)}")
    print(f"Citation Coverage: {validation_result.get('citation_coverage', 0.0):.2f}")
    
    invalid_citations = validation_result.get('invalid_citations', [])
    if invalid_citations:
        print(f"Invalid Citations: {invalid_citations}")
    else:
        print("Invalid Citations: None")
    
    unsupported_claims = validation_result.get('unsupported_claims', [])
    if unsupported_claims:
        print(f"Unsupported Claims: {len(unsupported_claims)}")
        for i, claim in enumerate(unsupported_claims[:3], 1):  # Show first 3
            print(f"  {i}. {claim[:100]}..." if len(claim) > 100 else f"  {i}. {claim}")
    
    issues = validation_result.get('issues', [])
    if issues:
        print(f"\nIssues Found ({len(issues)}):")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    
    print("=" * 70)


def _is_interactive_mode() -> bool:
    """
    Check if running in interactive mode (TTY available).
    
    Returns:
        True if running interactively, False if in API/background mode
    """
    # Check environment variable for API mode FIRST (takes precedence)
    if os.getenv("API_MODE", "").lower() in ["true", "1", "yes"]:
        return False
    # Check if stdin is a TTY (interactive terminal)
    # In background/thread pool execution, stdin is typically not a TTY
    if hasattr(sys.stdin, 'isatty'):
        try:
            return sys.stdin.isatty()
        except (AttributeError, OSError):
            # If stdin is not available or not a TTY, assume non-interactive
            return False
    # Default to non-interactive if we can't determine
    return False


def _prompt_user_action() -> str:
    """
    Prompt user for review action.
    
    In non-interactive mode (API), automatically approves the report.

    Returns:
        User's choice: 'approve', 'edit', or 'reject'.
    """
    # Check if running in interactive mode
    if not _is_interactive_mode():
        logger.info("Non-interactive mode detected (API mode). Auto-approving report.")
        return 'approve'
    
    print("\n" + "=" * 70)
    print("HUMAN REVIEW REQUIRED")
    print("=" * 70)
    print("Please review the report and choose an action:")
    print("  [A]pprove - Accept the report as-is")
    print("  [E]dit   - Provide an edited version")
    print("  [R]eject - Reject the report (will trigger regeneration)")
    print("=" * 70)
    
    while True:
        try:
            choice = input("\nEnter your choice (A/E/R): ").strip().upper()
            if choice in ['A', 'APPROVE']:
                return 'approve'
            elif choice in ['E', 'EDIT']:
                return 'edit'
            elif choice in ['R', 'REJECT']:
                return 'reject'
            else:
                print("Invalid choice. Please enter A, E, or R.")
        except (EOFError, KeyboardInterrupt):
            print("\n\nReview cancelled by user.")
            return 'reject'  # Default to reject if cancelled


def _prompt_edited_report() -> str:
    """
    Prompt user to provide an edited version of the report.

    Returns:
        Edited report text.
    """
    print("\n" + "=" * 70)
    print("PROVIDE EDITED REPORT")
    print("=" * 70)
    print("Enter your edited report below.")
    print("Press Enter on a new line, then Ctrl+Z (Windows) or Ctrl+D (Unix) to finish.")
    print("=" * 70)
    
    try:
        lines = []
        while True:
            try:
                line = input()
                lines.append(line)
            except EOFError:
                break
        
        edited_report = "\n".join(lines).strip()
        
        if not edited_report:
            print("Warning: Empty report provided. Using original draft.")
            return None
        
        return edited_report
    except (EOFError, KeyboardInterrupt):
        print("\n\nEdit cancelled. Using original draft.")
        return None


def hitl_review_node(state: ResearchState) -> ResearchState:
    """
    Human-In-The-Loop review node for the research workflow.

    This function:
      1. Checks if needs_hitl is False, skips review if so
      2. If needs_hitl is True:
         - Displays report_draft to console
         - Displays validation issues and confidence_score
         - Prompts user for action: [A]pprove, [E]dit, [R]eject
         - Updates state based on user decision
      3. Logs review decision

    Args:
        state: ResearchState containing report_draft, validation_result, etc.

    Returns:
        Updated ResearchState with final_report or error based on user decision.
    """
    start_time = time.time()
    task_id = state.get("task_id", "unknown")
    
    # Check API mode early and log it
    is_interactive = _is_interactive_mode()
    api_mode_env = os.getenv("API_MODE", "not set")
    logger.info("=" * 70)
    logger.info("HITL REVIEW - Entry | task_id=%s | interactive_mode=%s | API_MODE=%s", 
                task_id, is_interactive, api_mode_env)
    logger.debug("Input state keys: %s", list(state.keys()))
    
    new_state = dict(state)
    new_state["current_agent"] = "hitl_review"

    try:
        needs_hitl = state.get("needs_hitl", False)
        confidence_score = state.get("confidence_score", 0.0)

        # 1) Check if review is needed
        if not needs_hitl:
            logger.info("HITL review skipped | task_id=%s | needs_hitl=False | confidence=%.2f", 
                       task_id, confidence_score)
            # If no review needed, set final_report to report_draft
            report_draft = state.get("report_draft", "")
            if report_draft:
                new_state["final_report"] = report_draft
                logger.info("Set final_report to report_draft (no review needed)")
            log_state_transition(
                logger,
                from_state="validation",
                to_state="hitl_review",
                task_id=task_id,
                action="skipped",
            )
            return new_state

        logger.info("HITL review started | task_id=%s | confidence=%.2f", task_id, confidence_score)

        # 2) Check for errors from previous stages first
        previous_error = state.get("error")
        if previous_error:
            logger.warning(
                "Previous error detected in state, skipping HITL review | task_id=%s | error=%s",
                task_id, previous_error
            )
            # In non-interactive mode, propagate the error
            if not _is_interactive_mode():
                new_state["final_report"] = ""
                new_state["error"] = previous_error
                return new_state
        
        # 3) Extract required information
        report_draft = state.get("report_draft", "")
        validation_result = state.get("validation_result", {})
        confidence_score = state.get("confidence_score", 0.0)

        # If report_draft is missing or empty, try to use final_report or any other report field
        if not report_draft or (isinstance(report_draft, str) and len(report_draft.strip()) == 0):
            # Try to get final_report as fallback
            final_report = state.get("final_report", "")
            if final_report:
                logger.warning(
                    "report_draft missing, using final_report | task_id=%s",
                    task_id
                )
                report_draft = final_report
            else:
                # Try to find any report-like field in the state
                for key in ["report", "synthesis_report", "draft_report"]:
                    potential_report = state.get(key, "")
                    if potential_report and isinstance(potential_report, str) and len(potential_report) > 0:
                        logger.warning(
                            "report_draft missing, using %s | task_id=%s",
                            key, task_id
                        )
                        report_draft = potential_report
                        break
                
                # If still no report found
                if not report_draft:
                    # In non-interactive mode, this indicates a synthesis failure
                    if not _is_interactive_mode():
                        error_msg = "Synthesis agent failed to generate report_draft. Cannot proceed with HITL review."
                        logger.error(
                            "No report found in state for HITL review in API mode | task_id=%s | state_keys=%s | error=%s",
                            task_id, list(state.keys()), error_msg
                        )
                        # Set error to indicate synthesis failure
                        new_state["error"] = error_msg
                        new_state["final_report"] = ""
                        return new_state
                    else:
                        error_msg = "report_draft is required for HITL review"
                        log_error_with_context(logger, ValueError(error_msg), "hitl_review_node", task_id=task_id)
                        new_state["error"] = error_msg
                        return new_state

        logger.info(
            "Review information | report_length=%d chars | word_count=%d | confidence=%.2f",
            len(report_draft),
            len(report_draft.split()),
            confidence_score,
        )

        # 3) Display report and validation info (only in interactive mode)
        if _is_interactive_mode():
            _display_report_summary(report_draft)
            _display_validation_info(validation_result, confidence_score)
        else:
            logger.info("Skipping display (non-interactive mode)")

        # 4) Prompt user for action (or auto-approve in API mode)
        if _is_interactive_mode():
            logger.info("Waiting for user input...")
        else:
            logger.info("Non-interactive mode: auto-approving report")
        action = _prompt_user_action()
        logger.info("User action received: %s", action)

        # 5) Handle user action
        if action == 'approve':
            new_state["final_report"] = report_draft
            new_state["error"] = None
            logger.info(
                "HITL review: APPROVED | task_id=%s | confidence=%.2f",
                task_id,
                confidence_score,
            )
            print("\n[APPROVED] Report approved. Final report set to draft version.")

        elif action == 'edit':
            edited_report = _prompt_edited_report()
            if edited_report:
                new_state["final_report"] = edited_report
                new_state["error"] = None
                logger.info(
                    "HITL review: EDITED | task_id=%s | original_length=%d | edited_length=%d",
                    task_id,
                    len(report_draft),
                    len(edited_report),
                )
                print(f"\n[EDITED] Report edited. Final report updated ({len(edited_report)} characters).")
            else:
                # User cancelled edit, use original draft
                new_state["final_report"] = report_draft
                new_state["error"] = None
                logger.info(
                    "HITL review: EDIT CANCELLED, using original | task_id=%s",
                    task_id,
                )
                print("\n[EDIT CANCELLED] Using original draft as final report.")

        elif action == 'reject':
            new_state["final_report"] = ""
            new_state["error"] = "Report rejected by human reviewer. Regeneration required."
            # Increment regeneration count
            current_count = state.get("regeneration_count", 0)
            new_state["regeneration_count"] = current_count + 1
            # Clear previous results to allow fresh regeneration
            new_state["search_results"] = []
            new_state["retrieved_chunks"] = []
            new_state["report_draft"] = ""
            new_state["validation_result"] = {}
            logger.info(
                "HITL review: REJECTED | task_id=%s | confidence=%.2f | regeneration_count=%d",
                task_id,
                confidence_score,
                new_state["regeneration_count"],
            )
            print(f"\n[REJECTED] Report rejected. Will regenerate (attempt {new_state['regeneration_count']}).")

        else:
            # Should not happen, but handle gracefully
            logger.warning("Unexpected action in HITL review: %s", action)
            new_state["final_report"] = report_draft
            new_state["error"] = None

        total_duration = time.time() - start_time
        log_performance_metrics(
            logger,
            operation="hitl_review_complete",
            duration=total_duration,
            task_id=task_id,
            action=action,
            confidence_score=confidence_score,
        )
        
        log_state_transition(
            logger,
            from_state="validation",
            to_state="hitl_review",
            task_id=task_id,
            action=action,
            confidence_score=confidence_score,
        )
        
        logger.info("HITL REVIEW - Exit | task_id=%s | action=%s | duration=%.2fs", 
                   task_id, action, total_duration)
        logger.info("=" * 70)

        return new_state

    except Exception as exc:
        total_duration = time.time() - start_time
        log_error_with_context(
            logger,
            exc,
            "hitl_review_node",
            task_id=task_id,
            duration=total_duration,
        )
        new_state["error"] = f"hitl_review_node_error: {exc}"
        # On error, default to using report_draft as final_report
        new_state.setdefault("final_report", state.get("report_draft", ""))
        return new_state


__all__ = ["hitl_review_node"]

