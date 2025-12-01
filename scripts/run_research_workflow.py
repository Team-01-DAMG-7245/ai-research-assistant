"""
Run the complete research agent workflow.

This script executes the full research pipeline from user query to final report,
saving results to S3 and providing progress updates.

Usage:
    python scripts/run_research_workflow.py "What are recent advances in transformers?"
    
    Or run without arguments to be prompted for a query:
    python scripts/run_research_workflow.py
"""

import argparse
import json
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.workflow import compiled_workflow
from src.agents.state import ResearchState
from src.utils.s3_client import S3Client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def save_report_to_s3(
    report: str,
    task_id: str,
    user_query: str,
    metadata: Dict[str, Any]
) -> str:
    """
    Save final report to S3 gold/ layer.

    Args:
        report: Final report text.
        task_id: Task identifier.
        user_query: Original user query.
        metadata: Additional metadata to include.

    Returns:
        S3 key where the report was saved, or empty string if failed.
    """
    if not report:
        logger.warning("No report to save to S3")
        return ""

    try:
        s3_client = S3Client()
        bucket = s3_client.bucket
        
        if not bucket:
            logger.error("S3_BUCKET_NAME environment variable not set")
            return ""

        # Create report data structure
        report_data = {
            "task_id": task_id,
            "user_query": user_query,
            "report": report,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat(),
        }

        # Convert to JSON
        report_json = json.dumps(report_data, indent=2, ensure_ascii=False)

        # Create S3 key: gold/reports/{task_id}.json
        s3_key = f"gold/reports/{task_id}.json"

        # Write to temporary file first, then upload
        temp_file = Path(project_root) / "temp" / f"{task_id}_report.json"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(report_json)

        # Upload to S3
        success = s3_client.upload_file(str(temp_file), s3_key)
        
        # Clean up temp file
        temp_file.unlink(missing_ok=True)

        if success:
            logger.info(f"Report saved to s3://{bucket}/{s3_key}")
            return s3_key
        else:
            logger.error(f"Failed to save report to S3")
            return ""

    except Exception as exc:
        logger.exception(f"Error saving report to S3: {exc}")
        return ""


def track_agent_progress(state: ResearchState, previous_agent: str = None) -> str:
    """
    Track and print progress as agents complete.

    Args:
        state: Current ResearchState.
        previous_agent: Previous agent name for comparison.

    Returns:
        Current agent name.
    """
    current_agent = state.get("current_agent", "unknown")
    
    if current_agent != previous_agent:
        agent_display_names = {
            "search": "Search Agent",
            "synthesis": "Synthesis Agent",
            "validation": "Validation Agent",
            "hitl_review": "HITL Review",
            "set_final_report": "Finalizing Report",
        }
        
        display_name = agent_display_names.get(current_agent, current_agent)
        print(f"\n{'='*70}")
        print(f"✓ {display_name} completed")
        print(f"{'='*70}")
        
        # Print relevant state info
        if current_agent == "search":
            queries = state.get("search_queries", [])
            results = state.get("search_results", [])
            print(f"  Generated {len(queries)} search queries")
            print(f"  Found {len(results)} search results")
        
        elif current_agent == "synthesis":
            word_count = len(state.get("report_draft", "").split())
            source_count = state.get("source_count", 0)
            print(f"  Generated {word_count}-word report")
            print(f"  Used {source_count} sources")
        
        elif current_agent == "validation":
            confidence = state.get("confidence_score", 0.0)
            needs_hitl = state.get("needs_hitl", False)
            print(f"  Confidence Score: {confidence:.2f}")
            print(f"  Needs HITL Review: {needs_hitl}")
        
        elif current_agent == "hitl_review":
            final_report = state.get("final_report", "")
            if final_report:
                print(f"  Report approved/edited ({len(final_report)} characters)")
            else:
                print(f"  Report rejected - regeneration required")
    
    return current_agent


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Run the complete research agent workflow"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Research query/question (optional, will prompt if not provided)"
    )
    parser.add_argument(
        "--task-id",
        help="Custom task ID (default: auto-generated UUID)"
    )
    
    args = parser.parse_args()

    # Get user query
    user_query = args.query
    if not user_query:
        print("\n" + "="*70)
        print("AI Research Assistant - Workflow Runner")
        print("="*70)
        user_query = input("\nEnter your research query: ").strip()
        if not user_query:
            print("Error: Query cannot be empty")
            sys.exit(1)

    # Generate task ID
    task_id = args.task_id or str(uuid.uuid4())

    print("\n" + "="*70)
    print("Starting Research Workflow")
    print("="*70)
    print(f"Task ID: {task_id}")
    print(f"Query: {user_query}")
    print("="*70)

    # Initialize state
    initial_state: ResearchState = {
        "task_id": task_id,
        "user_query": user_query,
        "current_agent": "search",
        "search_queries": [],
        "search_results": [],
        "retrieved_chunks": [],
        "report_draft": "",
        "validation_result": {},
        "confidence_score": 0.0,
        "needs_hitl": False,
        "final_report": "",
        "error": None,
    }

    start_time = time.time()
    previous_agent = None
    error_occurred = False

    try:
        # Run workflow with progress tracking
        print("\nExecuting workflow...")
        
        # Use stream_events or invoke with callbacks if available
        # For now, we'll use invoke and track state changes
        final_state = compiled_workflow.invoke(initial_state)
        
        # Track final agent
        track_agent_progress(final_state, previous_agent)

    except Exception as exc:
        logger.exception(f"Workflow execution failed: {exc}")
        print(f"\n{'='*70}")
        print("ERROR: Workflow execution failed")
        print(f"{'='*70}")
        print(f"Error: {exc}")
        error_occurred = True
        final_state = initial_state
        final_state["error"] = str(exc)

    execution_time = time.time() - start_time

    # Check for errors
    error = final_state.get("error")
    if error:
        print(f"\n{'='*70}")
        print("Workflow completed with errors")
        print(f"{'='*70}")
        print(f"Error: {error}")
        error_occurred = True

    # Get final report
    final_report = final_state.get("final_report", "")
    
    if not final_report and not error_occurred:
        logger.warning("No final report generated")
        print("\nWarning: No final report was generated")

    # Save to S3
    if final_report:
        print(f"\n{'='*70}")
        print("Saving Report to S3")
        print(f"{'='*70}")
        
        metadata = {
            "confidence_score": final_state.get("confidence_score", 0.0),
            "needs_hitl": final_state.get("needs_hitl", False),
            "source_count": final_state.get("source_count", 0),
            "execution_time_seconds": execution_time,
        }
        
        s3_key = save_report_to_s3(
            report=final_report,
            task_id=task_id,
            user_query=user_query,
            metadata=metadata
        )
        
        if s3_key:
            print(f"✓ Report saved to S3: {s3_key}")
        else:
            print("✗ Failed to save report to S3")

    # Print final report
    if final_report:
        print(f"\n{'='*70}")
        print("FINAL REPORT")
        print(f"{'='*70}")
        print(final_report)
        print(f"{'='*70}")

    # Print summary
    print(f"\n{'='*70}")
    print("Execution Summary")
    print(f"{'='*70}")
    print(f"Task ID: {task_id}")
    print(f"Query: {user_query}")
    print(f"Execution Time: {execution_time:.2f} seconds")
    print(f"Final Report Length: {len(final_report)} characters")
    print(f"Word Count: {len(final_report.split()) if final_report else 0} words")
    print(f"Confidence Score: {final_state.get('confidence_score', 0.0):.2f}")
    print(f"Sources Used: {final_state.get('source_count', 0)}")
    print(f"Error: {error if error else 'None'}")
    
    if final_report and s3_key:
        print(f"S3 Location: s3://{S3Client().bucket}/{s3_key}")
    
    print(f"\nNote: API costs are logged per agent in:")
    print(f"  - src/logs/search_agent.log")
    print(f"  - src/logs/synthesis_agent.log")
    print(f"  - src/logs/validation_agent.log")
    
    print(f"{'='*70}\n")

    # Exit with error code if failed
    if error_occurred:
        sys.exit(1)


if __name__ == "__main__":
    main()

