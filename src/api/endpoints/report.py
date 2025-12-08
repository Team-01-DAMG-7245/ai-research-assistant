"""
Report API Endpoint
"""

import logging
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Path, Query, status
from fastapi.responses import Response

from src.utils.pdf_generator import markdown_to_pdf
from ..models import ReportResponse, TaskStatus, ErrorResponse, SourceInfo
from ..task_manager import get_task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["report"])


@router.get("/report/{task_id}")
async def get_report(
    task_id: str = Path(..., description="Task identifier (UUID)"),
    format: str = Query("json", regex="^(json|markdown|pdf)$", description="Response format")
):
    """
    Get the research report for a completed task
    
    Supports JSON, Markdown, and PDF formats
    - json: Returns structured JSON response
    - markdown: Returns plain markdown text
    - pdf: Returns PDF file with formatted report
    """
    # Validate UUID format
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid task_id format. Must be a valid UUID."
        )
    
    task_manager = get_task_manager()
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    # Check if task is completed
    task_status = TaskStatus(task['status'])
    if task_status == TaskStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task {task_id} failed: {task.get('error', 'Unknown error')}"
        )
    
    if task_status not in [TaskStatus.COMPLETED, TaskStatus.PENDING_REVIEW]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task {task_id} is not completed. Current status: {task_status.value}"
        )
    
    # Check if report exists
    report = task.get('report')
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found for task {task_id}"
        )
    
    # Parse sources - handle both list and empty cases
    sources_data = task.get('sources', [])
    if not isinstance(sources_data, list):
        sources_data = []
    
    sources = []
    for i, s in enumerate(sources_data, 1):
        try:
            sources.append(SourceInfo(
                source_id=s.get('source_id', i) if isinstance(s, dict) else i,
                title=s.get('title', 'Unknown') if isinstance(s, dict) else str(s),
                url=s.get('url', '') if isinstance(s, dict) else '',
                relevance_score=float(s.get('relevance_score', 0.0)) if isinstance(s, dict) else 0.0
            ))
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Error parsing source {i}: {e}, skipping")
            continue
    
    # Parse created_at - handle different datetime formats
    try:
        created_at_value = task.get('created_at')
        
        # Handle None or empty
        if not created_at_value:
            created_at = datetime.utcnow()
        elif isinstance(created_at_value, datetime):
            # Already a datetime object
            created_at = created_at_value
        elif isinstance(created_at_value, str):
            # String - try to parse
            try:
                # Try ISO format first (most common)
                if 'T' in created_at_value or '+' in created_at_value or 'Z' in created_at_value:
                    # ISO format with timezone
                    created_at_str = created_at_value.replace('Z', '+00:00')
                    created_at = datetime.fromisoformat(created_at_str)
                elif ' ' in created_at_value and ':' in created_at_value:
                    # SQLite TIMESTAMP format: "YYYY-MM-DD HH:MM:SS.microseconds"
                    # Convert to ISO format by replacing space with T
                    iso_str = created_at_value.replace(' ', 'T', 1)
                    created_at = datetime.fromisoformat(iso_str)
                else:
                    # Try simple ISO format without timezone
                    created_at = datetime.fromisoformat(created_at_value)
            except (ValueError, AttributeError) as e:
                # Fallback to current time if parsing fails
                logger.warning(f"Could not parse created_at '{created_at_value}': {e}, using current time")
                created_at = datetime.utcnow()
        else:
            # Unknown type, use current time
            logger.warning(f"Unexpected created_at type: {type(created_at_value)}, using current time")
            created_at = datetime.utcnow()
    except Exception as e:
        logger.exception(f"Error parsing created_at: {e}, using current time")
        created_at = datetime.utcnow()
    
    # Format sources as markdown section
    def format_sources_markdown(sources_list) -> str:
        """Format sources list as markdown references section"""
        if not sources_list:
            return ""
        
        md = "\n\n---\n\n## References\n\n"
        for idx, source in enumerate(sources_list, 1):
            # Get source_id, title, and url from SourceInfo object
            source_id = getattr(source, 'source_id', None) or idx
            title = getattr(source, 'title', 'Unknown') or 'Unknown'
            url = getattr(source, 'url', '') or ''
            
            # Format as numbered list with link if URL available
            if url:
                md += f"{source_id}. [{title}]({url})\n"
            else:
                md += f"{source_id}. {title}\n"
        
        return md
    
    # Append sources to report content for markdown and PDF formats
    sources_markdown = format_sources_markdown(sources)
    report_with_sources = report + sources_markdown
    
    # Return in requested format
    if format == "markdown":
        return Response(
            content=report_with_sources,
            media_type="text/markdown; charset=utf-8"
        )
    elif format == "pdf":
        # Generate PDF from markdown report
        try:
            # Extract title from report (first line or first heading)
            title = "Research Report"
            report_lines = report.split('\n')
            for line in report_lines[:5]:  # Check first 5 lines
                line_stripped = line.strip()
                if line_stripped.startswith('# '):
                    title = line_stripped[2:].strip()
                    break
                elif line_stripped and not line_stripped.startswith('#'):
                    # Use first non-empty line as potential title
                    if len(line_stripped) < 100:  # Reasonable title length
                        title = line_stripped
                        break
            
            # Prepare metadata for PDF
            metadata = {
                'task_id': task_id,
                'confidence_score': float(task.get('confidence_score', 0.0)),
                'source_count': len(sources),
                'created_at': created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if created_at else None
            }
            
            # Generate PDF bytes (with sources included in markdown)
            pdf_bytes = markdown_to_pdf(
                markdown_content=report_with_sources,
                title=title,
                metadata=metadata
            )
            
            # Return PDF as response
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="research_report_{task_id}.pdf"'
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating PDF for task {task_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate PDF: {str(e)}"
            )
    else:  # json (default)
        return ReportResponse(
            task_id=task_id,
            report=report,
            sources=sources,
            confidence_score=float(task.get('confidence_score', 0.0)),
            needs_hitl=bool(task.get('needs_hitl', False)),
            created_at=created_at,
            metadata=task.get('metadata', {})
        )
