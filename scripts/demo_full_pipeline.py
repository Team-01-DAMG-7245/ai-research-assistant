"""
Full Pipeline Demonstration Script

Demonstrates the complete M1-M3 pipeline working together:
- Data ingestion (S3 bronze/silver layers)
- Vector search (Pinecone)
- LangGraph workflow (Search → Synthesis → Validation → HITL)
- Final report generation and storage (S3 gold layer)

Usage:
    python scripts/demo_full_pipeline.py
"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to import rich for colorful output, fallback to basic output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Note: Install 'rich' for better output: pip install rich")

from src.agents.workflow import compiled_workflow
from src.agents.state import ResearchState
from src.utils.s3_client import S3Client
from src.utils.pinecone_rag import semantic_search
from src.utils.cost_tracker import get_cost_tracker, get_query_cost

# Setup logging (reduce verbosity for demo)
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and errors
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize console if rich is available (with encoding error handling)
if RICH_AVAILABLE:
    try:
        console = Console(force_terminal=True, legacy_windows=False)
    except Exception:
        # Fallback to basic console if there are encoding issues
        console = None
        RICH_AVAILABLE = False
else:
    console = None


def sanitize_text(text: str) -> str:
    """Sanitize text to remove problematic Unicode characters for Windows console."""
    if not text:
        return ""
    # Replace common problematic Unicode characters
    replacements = {
        '\u221a': 'sqrt',
        '\u2212': '-',
        '\u2013': '-',
        '\u2014': '--',
        '\u2018': "'",
        '\u2019': "'",
        '\u201c': '"',
        '\u201d': '"',
    }
    result = text
    for unicode_char, replacement in replacements.items():
        result = result.replace(unicode_char, replacement)
    # Remove any remaining problematic characters by encoding/decoding
    try:
        # Try to encode to cp1252 (Windows console encoding)
        result.encode('cp1252', errors='strict')
        return result
    except UnicodeEncodeError:
        # Fallback: encode with errors='ignore' to remove problematic chars
        return result.encode('cp1252', errors='ignore').decode('cp1252', errors='ignore')


def print_header(text: str):
    """Print a header with styling."""
    if console:
        console.print(f"\n{'='*70}", style="bold blue")
        console.print(f"{text}", style="bold white")
        console.print(f"{'='*70}", style="bold blue")
    else:
        print(f"\n{'='*70}")
        print(f"{text}")
        print(f"{'='*70}")


def print_section(text: str):
    """Print a section header."""
    if console:
        console.print(f"\n[bold cyan]{text}[/bold cyan]")
    else:
        print(f"\n{text}")


def print_success(text: str):
    """Print success message."""
    if console:
        console.print(f"[green][OK][/green] {text}")
    else:
        print(f"[OK] {text}")


def print_info(text: str):
    """Print info message."""
    if console:
        console.print(f"[blue][INFO][/blue] {text}")
    else:
        print(f"[INFO] {text}")


def print_warning(text: str):
    """Print warning message."""
    if console:
        console.print(f"[yellow][WARN][/yellow] {text}")
    else:
        print(f"[WARN] {text}")


def show_s3_bronze_papers(s3_client: S3Client, limit: int = 5):
    """Show sample papers from S3 bronze/ layer."""
    print_section("Step 1: Sample Papers in S3 Bronze Layer")
    
    try:
        bronze_keys = s3_client.list_objects(prefix="bronze/", max_keys=100)
        pdf_keys = [k for k in bronze_keys if k.endswith('.pdf')]
        
        if not pdf_keys:
            print_warning("No PDF files found in bronze/ layer")
            return []
        
        sample_keys = pdf_keys[:limit]
        
        if console:
            table = Table(title="Sample Papers in S3 Bronze Layer")
            table.add_column("Index", style="cyan")
            table.add_column("S3 Key", style="green")
            table.add_column("Paper ID", style="yellow")
            
            for i, key in enumerate(sample_keys, 1):
                paper_id = Path(key).stem
                table.add_row(str(i), key, paper_id)
            
            console.print(table)
        else:
            print(f"\nFound {len(pdf_keys)} PDF files. Showing {len(sample_keys)} samples:")
            for i, key in enumerate(sample_keys, 1):
                paper_id = Path(key).stem
                print(f"  {i}. {key} (ID: {paper_id})")
        
        return sample_keys
    except Exception as exc:
        print_warning(f"Error listing bronze papers: {exc}")
        return []


def show_s3_silver_chunks(s3_client: S3Client, limit: int = 5):
    """Show processed chunks from S3 silver/ layer."""
    print_section("Step 2: Processed Chunks in S3 Silver Layer")
    
    try:
        silver_keys = s3_client.list_objects(prefix="silver/chunks/", max_keys=100)
        
        if not silver_keys:
            print_warning("No chunk files found in silver/chunks/ layer")
            return []
        
        sample_keys = silver_keys[:limit]
        
        if console:
            table = Table(title="Sample Processed Chunks in S3 Silver Layer")
            table.add_column("Index", style="cyan")
            table.add_column("S3 Key", style="green")
            table.add_column("Chunk ID", style="yellow")
            
            for i, key in enumerate(sample_keys, 1):
                chunk_id = Path(key).stem
                table.add_row(str(i), key, chunk_id)
            
            console.print(table)
        else:
            print(f"\nFound {len(silver_keys)} chunk files. Showing {len(sample_keys)} samples:")
            for i, key in enumerate(sample_keys, 1):
                chunk_id = Path(key).stem
                print(f"  {i}. {key} (Chunk ID: {chunk_id})")
        
        return sample_keys
    except Exception as exc:
        print_warning(f"Error listing silver chunks: {exc}")
        return []


def query_pinecone_demo(query: str, top_k: int = 5):
    """Query Pinecone and display results."""
    print_section("Step 3: Querying Pinecone Vector Database")
    
    if console:
        with console.status("[bold green]Searching Pinecone..."):
            results = semantic_search(query, top_k=top_k, namespace="research_papers")
    else:
        print("Searching Pinecone...")
        results = semantic_search(query, top_k=top_k, namespace="research_papers")
    
    if not results:
        print_warning("No results found in Pinecone")
        return []
    
    if console:
        table = Table(title=f"Top {len(results)} Pinecone Search Results")
        table.add_column("Rank", style="cyan")
        table.add_column("Doc ID", style="green")
        table.add_column("Score", style="yellow", justify="right")
        table.add_column("Title", style="white")
        table.add_column("Text Preview", style="dim", max_width=50)
        
        for i, result in enumerate(results, 1):
            doc_id = result.get("doc_id", "N/A")
            score = result.get("score", 0.0)
            title = sanitize_text(result.get("title", "N/A"))
            text_preview = sanitize_text((result.get("text", "") or "")[:100] + "...")
            
            table.add_row(
                str(i),
                doc_id,
                f"{score:.4f}",
                title,
                text_preview
            )
        
        console.print(table)
    else:
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results, 1):
            doc_id = result.get("doc_id", "N/A")
            score = result.get("score", 0.0)
            title = result.get("title", "N/A")
            print(f"  {i}. {doc_id} (score: {score:.4f}) - {title}")
    
    return results


def display_search_agent_output(state: ResearchState):
    """Display search agent output."""
    print_section("Search Agent Output")
    
    queries = state.get("search_queries", [])
    results = state.get("search_results", [])
    
    if console:
        # Show queries
        queries_text = "\n".join(f"  {i}. {q}" for i, q in enumerate(queries, 1))
        console.print(Panel(queries_text, title="Generated Search Queries", border_style="green"))
        
        # Show results summary
        if results:
            table = Table(title="Search Results Summary")
            table.add_column("Rank", style="cyan")
            table.add_column("Doc ID", style="green")
            table.add_column("Score", style="yellow", justify="right")
            table.add_column("Title", style="white")
            
            for i, result in enumerate(results[:10], 1):  # Show top 10
                table.add_row(
                    str(i),
                    result.get("doc_id", "N/A"),
                    f"{result.get('score', 0.0):.4f}",
                    sanitize_text(result.get("title", "N/A")[:50])
                )
            
            console.print(table)
    else:
        print(f"\nGenerated {len(queries)} search queries:")
        for i, q in enumerate(queries, 1):
            print(f"  {i}. {q}")
        print(f"\nFound {len(results)} search results")
    
    print_success(f"Search Agent: {len(queries)} queries, {len(results)} results")


def display_synthesis_agent_output(state: ResearchState):
    """Display synthesis agent output."""
    print_section("Synthesis Agent Output")
    
    report_draft = state.get("report_draft", "")
    source_count = state.get("source_count", 0)
    word_count = len(report_draft.split()) if report_draft else 0
    
    if console:
        console.print(f"[bold]Sources Used:[/bold] {source_count}")
        console.print(f"[bold]Report Length:[/bold] {word_count} words, {len(report_draft)} characters")
        
        # Show report preview
        if report_draft:
            preview = sanitize_text(report_draft[:500] + "..." if len(report_draft) > 500 else report_draft)
            console.print(Panel(preview, title="Report Preview (first 500 chars)", border_style="blue"))
    else:
        print(f"\nSources Used: {source_count}")
        print(f"Report Length: {word_count} words, {len(report_draft)} characters")
        if report_draft:
            preview = report_draft[:500] + "..." if len(report_draft) > 500 else report_draft
            print(f"\nReport Preview:\n{preview}")
    
    print_success(f"Synthesis Agent: Generated {word_count}-word report from {source_count} sources")


def display_validation_agent_output(state: ResearchState):
    """Display validation agent output."""
    print_section("Validation Agent Output")
    
    validation_result = state.get("validation_result", {})
    confidence_score = state.get("confidence_score", 0.0)
    needs_hitl = state.get("needs_hitl", False)
    
    if console:
        # Create validation table
        table = Table(title="Validation Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Valid", str(validation_result.get("valid", False)))
        table.add_row("Confidence Score", f"{confidence_score:.2f}")
        table.add_row("Needs HITL", str(needs_hitl))
        table.add_row("Citation Coverage", f"{validation_result.get('citation_coverage', 0.0):.2f}")
        table.add_row("Invalid Citations", str(len(validation_result.get('invalid_citations', []))))
        table.add_row("Unsupported Claims", str(len(validation_result.get('unsupported_claims', []))))
        
        console.print(table)
        
        # Show issues if any
        issues = validation_result.get("issues", [])
        if issues:
            issues_text = "\n".join(f"  - {sanitize_text(str(issue))}" for issue in issues)
            console.print(Panel(issues_text, title="Issues Found", border_style="yellow"))
    else:
        print(f"\nValidation Results:")
        print(f"  Valid: {validation_result.get('valid', False)}")
        print(f"  Confidence Score: {confidence_score:.2f}")
        print(f"  Needs HITL: {needs_hitl}")
        print(f"  Citation Coverage: {validation_result.get('citation_coverage', 0.0):.2f}")
        print(f"  Invalid Citations: {len(validation_result.get('invalid_citations', []))}")
        print(f"  Unsupported Claims: {len(validation_result.get('unsupported_claims', []))}")
        
        issues = validation_result.get("issues", [])
        if issues:
            print(f"\nIssues:")
            for issue in issues:
                print(f"  • {issue}")
    
    print_success(f"Validation Agent: Confidence {confidence_score:.2f}, HITL required: {needs_hitl}")


def display_hitl_output(state: ResearchState):
    """Display HITL review output."""
    print_section("HITL Review Output")
    
    needs_hitl = state.get("needs_hitl", False)
    final_report = state.get("final_report", "")
    
    if needs_hitl:
        if console:
            console.print("[yellow]Human review was required[/yellow]")
            console.print("[green]Auto-approved for demo purposes[/green]")
        else:
            print("Human review was required")
            print("Auto-approved for demo purposes")
    else:
        if console:
            console.print("[green]No human review needed (confidence >= 0.7)[/green]")
        else:
            print("No human review needed (confidence >= 0.7)")
    
    if final_report:
        word_count = len(final_report.split())
        if console:
            console.print(f"[bold]Final Report:[/bold] {word_count} words, {len(final_report)} characters")
        else:
            print(f"Final Report: {word_count} words, {len(final_report)} characters")
    
    print_success("HITL Review: Completed")


def save_report_to_s3(
    report: str,
    task_id: str,
    user_query: str,
    metadata: Dict[str, Any],
    s3_client: S3Client
) -> str:
    """Save final report to S3 gold/ layer."""
    if not report:
        return ""
    
    try:
        bucket = s3_client.bucket
        if not bucket:
            print_warning("S3_BUCKET_NAME not set, skipping S3 save")
            return ""
        
        report_data = {
            "task_id": task_id,
            "user_query": user_query,
            "report": report,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat(),
        }
        
        report_json = json.dumps(report_data, indent=2, ensure_ascii=False)
        s3_key = f"gold/reports/{task_id}.json"
        
        # Write to temp file and upload
        temp_file = project_root / "temp" / f"{task_id}_report.json"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(report_json)
        
        success = s3_client.upload_file(str(temp_file), s3_key)
        temp_file.unlink(missing_ok=True)
        
        if success:
            return s3_key
        return ""
    except Exception as exc:
        print_warning(f"Failed to save report to S3: {exc}")
        return ""


def display_execution_metrics(
    execution_time: float,
    state: ResearchState,
    task_id: str,
    s3_key: str = ""
):
    """Display execution metrics."""
    print_section("Execution Metrics")
    
    cost_tracker = get_cost_tracker()
    task_cost = get_query_cost(task_id)
    total_cost = cost_tracker.get_total_cost()
    cost_by_operation = cost_tracker.get_cost_by_operation()
    
    if console:
        table = Table(title="Execution Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Task ID", task_id)
        table.add_row("Execution Time", f"{execution_time:.2f} seconds")
        table.add_row("Report Word Count", str(len(state.get("final_report", "").split())))
        table.add_row("Sources Used", str(state.get("source_count", 0)))
        table.add_row("Confidence Score", f"{state.get('confidence_score', 0.0):.2f}")
        table.add_row("Task Cost", f"${task_cost:.6f}")
        table.add_row("Total Cost (all tasks)", f"${total_cost:.6f}")
        
        if s3_key:
            table.add_row("S3 Location", f"s3://{S3Client().bucket}/{s3_key}")
        
        console.print(table)
        
        # Cost breakdown
        if cost_by_operation:
            cost_table = Table(title="Cost Breakdown by Operation")
            cost_table.add_column("Operation", style="cyan")
            cost_table.add_column("Cost", style="green", justify="right")
            
            for op, cost in cost_by_operation.items():
                cost_table.add_row(op, f"${cost:.6f}")
            
            console.print(cost_table)
    else:
        print(f"\nExecution Summary:")
        print(f"  Task ID: {task_id}")
        print(f"  Execution Time: {execution_time:.2f} seconds")
        print(f"  Report Word Count: {len(state.get('final_report', '').split())}")
        print(f"  Sources Used: {state.get('source_count', 0)}")
        print(f"  Confidence Score: {state.get('confidence_score', 0.0):.2f}")
        print(f"  Task Cost: ${task_cost:.6f}")
        print(f"  Total Cost (all tasks): ${total_cost:.6f}")
        if s3_key:
            print(f"  S3 Location: s3://{S3Client().bucket}/{s3_key}")
        
        if cost_by_operation:
            print(f"\nCost Breakdown by Operation:")
            for op, cost in cost_by_operation.items():
                print(f"  {op}: ${cost:.6f}")


def main():
    """Main demonstration function."""
    print_header("AI Research Assistant - Full Pipeline Demonstration")
    
    # Initialize components
    s3_client = S3Client()
    cost_tracker = get_cost_tracker()
    
    # Demo query
    demo_query = "What are attention mechanisms in transformers?"
    
    if console:
        console.print(f"[bold]Demo Query:[/bold] {demo_query}\n")
    else:
        print(f"Demo Query: {demo_query}\n")
    
    # Step 1: Show S3 bronze papers
    bronze_papers = show_s3_bronze_papers(s3_client, limit=5)
    time.sleep(0.5)  # Small delay for readability
    
    # Step 2: Show S3 silver chunks
    silver_chunks = show_s3_silver_chunks(s3_client, limit=5)
    time.sleep(0.5)
    
    # Step 3: Query Pinecone
    pinecone_results = query_pinecone_demo(demo_query, top_k=5)
    time.sleep(0.5)
    
    # Step 4: Run LangGraph workflow
    print_section("Step 4: Running LangGraph Workflow")
    
    task_id = f"demo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cost_tracker.set_task_id(task_id)
    
    initial_state: ResearchState = {
        "task_id": task_id,
        "user_query": demo_query,
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
    
    try:
        if console:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Executing workflow...", total=None)
                final_state = compiled_workflow.invoke(initial_state)
                progress.update(task, completed=True)
        else:
            print("Executing workflow...")
            final_state = compiled_workflow.invoke(initial_state)
        
        execution_time = time.time() - start_time
        
        # Auto-approve for demo if HITL was needed
        if final_state.get("needs_hitl", False) and not final_state.get("final_report"):
            final_state["final_report"] = final_state.get("report_draft", "")
            final_state["error"] = None
            if console:
                console.print("[yellow]Auto-approved report for demo (HITL skipped)[/yellow]")
            else:
                print("Auto-approved report for demo (HITL skipped)")
        
        # Display agent outputs
        display_search_agent_output(final_state)
        time.sleep(0.3)
        
        display_synthesis_agent_output(final_state)
        time.sleep(0.3)
        
        display_validation_agent_output(final_state)
        time.sleep(0.3)
        
        display_hitl_output(final_state)
        time.sleep(0.3)
        
        # Step 5: Save to S3 gold/
        print_section("Step 5: Saving Final Report to S3 Gold Layer")
        
        final_report = final_state.get("final_report", "")
        if final_report:
            metadata = {
                "confidence_score": final_state.get("confidence_score", 0.0),
                "needs_hitl": final_state.get("needs_hitl", False),
                "source_count": final_state.get("source_count", 0),
                "execution_time_seconds": execution_time,
            }
            
            s3_key = save_report_to_s3(
                report=final_report,
                task_id=task_id,
                user_query=demo_query,
                metadata=metadata,
                s3_client=s3_client
            )
            
            if s3_key:
                print_success(f"Report saved to s3://{s3_client.bucket}/{s3_key}")
            else:
                print_warning("Failed to save report to S3")
        else:
            print_warning("No final report to save")
        
        # Step 6: Display metrics
        display_execution_metrics(execution_time, final_state, task_id, s3_key if final_report else "")
        
        # Display final report
        if final_report:
            print_section("Final Report")
            if console:
                # Show full report in a scrollable panel
                sanitized_report = sanitize_text(final_report)
                console.print(Panel(sanitized_report, title="Complete Final Report", border_style="green"))
            else:
                print(f"\n{final_report}")
        
        print_header("Demo Complete!")
        
    except Exception as exc:
        print_warning(f"Workflow execution failed: {exc}")
        if console:
            console.print_exception()
        else:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

