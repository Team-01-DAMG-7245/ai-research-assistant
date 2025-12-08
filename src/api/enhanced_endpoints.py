# src/api/enhanced_endpoints.py
"""
Enhanced API Endpoints for M4
Author: Kundana Pooskur
Date: December 2025
Purpose: Advanced features for real-time updates, batch processing, and analytics
"""

from fastapi import APIRouter, WebSocket, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio
import json
from datetime import datetime
import requests

# Create router for your endpoints
router = APIRouter(prefix="/api/v2", tags=["Enhanced Features"])

# ============ MODELS ============
class BatchResearchRequest(BaseModel):
    queries: List[str]
    priority: str = "medium"
    user_email: Optional[str] = None

class EnhancedReviewRequest(BaseModel):
    approved: bool
    confidence_override: Optional[float] = None
    comments: str = ""
    edited_sections: Optional[Dict[str, str]] = None

class SessionCreateRequest(BaseModel):
    user_email: str
    user_name: Optional[str] = None

# Store sessions in memory (use Redis in production)
sessions = {}
active_websockets = {}

# ============ 1. WEBSOCKET FOR REAL-TIME UPDATES ============
@router.websocket("/ws/{task_id}")
async def websocket_research_updates(websocket: WebSocket, task_id: str):
    """
    Real-time progress updates via WebSocket
    Author: Kundana Pooskur
    Purpose: Frontend can show live progress without polling
    """
    await websocket.accept()
    active_websockets[task_id] = websocket
    
    try:
        while True:
            # Get current status from main API
            try:
                response = requests.get(f"http://localhost:8000/api/v1/status/{task_id}")
                if response.status_code == 200:
                    status_data = response.json()
                    
                    # Map status to progress percentage
                    progress_map = {
                        "pending": 0,
                        "searching": 20,
                        "synthesizing": 50,
                        "validating": 80,
                        "completed": 100,
                        "failed": -1
                    }
                    
                    # Send update to frontend
                    await websocket.send_json({
                        "task_id": task_id,
                        "status": status_data.get("status", "unknown"),
                        "progress": progress_map.get(status_data.get("status", "pending"), 0),
                        "message": f"Task is {status_data.get('status', 'processing')}...",
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Stop if completed or failed
                    if status_data.get("status") in ["completed", "failed"]:
                        await websocket.send_json({
                            "task_id": task_id,
                            "status": status_data.get("status"),
                            "progress": 100 if status_data.get("status") == "completed" else -1,
                            "message": "Task completed!" if status_data.get("status") == "completed" else "Task failed",
                            "final": True
                        })
                        break
            except Exception as e:
                await websocket.send_json({
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                
            await asyncio.sleep(2)  # Update every 2 seconds
            
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        del active_websockets[task_id]
        await websocket.close()

# ============ 2. BATCH PROCESSING ============
@router.post("/research/batch")
async def submit_batch_research(request: BatchResearchRequest):
    """
    Process multiple research queries at once
    Author: Kundana Pooskur
    Purpose: Efficiency for processing multiple questions
    """
    batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    task_ids = []
    failed_queries = []
    
    for query in request.queries:
        try:
            response = requests.post(
                "http://localhost:8000/api/v1/research",
                json={
                    "query": query,
                    "depth": "standard",
                    "user_id": request.user_email or "batch_user"
                }
            )
            if response.status_code == 200:
                task_data = response.json()
                task_ids.append({
                    "query": query[:50] + "..." if len(query) > 50 else query,
                    "task_id": task_data.get("task_id")
                })
            else:
                failed_queries.append(query)
        except Exception as e:
            failed_queries.append(query)
    
    return {
        "batch_id": batch_id,
        "total_queries": len(request.queries),
        "submitted": len(task_ids),
        "failed": len(failed_queries),
        "task_ids": task_ids,
        "failed_queries": failed_queries,
        "priority": request.priority,
        "submitted_at": datetime.now().isoformat()
    }

# ============ 3. STREAMING RESPONSE ============
@router.get("/report/stream/{task_id}")
async def stream_report(task_id: str):
    """
    Stream report as it's being generated
    Author: Kundana Pooskur
    Purpose: Better UX for long reports
    """
    async def generate():
        try:
            # Get report from main API
            response = requests.get(f"http://localhost:8000/api/v1/report/{task_id}")
            
            if response.status_code == 200:
                report_data = response.json()
                report_text = report_data.get("report", "")
                
                # Send metadata first
                yield f"data: {json.dumps({'type': 'metadata', 'task_id': task_id, 'total_length': len(report_text)})}\n\n"
                
                # Stream report in chunks
                chunk_size = 100
                for i in range(0, len(report_text), chunk_size):
                    chunk = report_text[i:i+chunk_size]
                    progress = min(100, int((i + chunk_size) / len(report_text) * 100))
                    
                    yield f"data: {json.dumps({'type': 'content', 'chunk': chunk, 'progress': progress})}\n\n"
                    await asyncio.sleep(0.05)  # Small delay for streaming effect
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'complete', 'message': 'Report streaming completed'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Report not found'})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

# ============ 4. ANALYTICS DASHBOARD ============
@router.get("/analytics/dashboard")
async def get_analytics():
    """
    Get analytics and metrics for dashboard
    Author: Kundana Pooskur
    Purpose: Show statistics in Streamlit dashboard
    """
    try:
        from src.api.task_manager import get_task_manager
        task_manager = get_task_manager()
        analytics_data = task_manager.get_analytics_data()
        
        # Add some additional computed fields for compatibility
        summary = analytics_data.get("summary", {})
        performance = analytics_data.get("performance", {})
        
        # Format success rate as percentage
        success_rate = performance.get("success_rate", 0.0)
        
        # Get status breakdown for display
        status_breakdown = analytics_data.get("status_breakdown", {})
        
        # Build response with real data
        response = {
            "summary": {
                "total_queries": summary.get("total_queries", 0),
                "queries_today": summary.get("queries_today", 0),
                "queries_this_week": summary.get("queries_this_week", 0),
                "active_users": summary.get("active_users", 0)
            },
            "performance": {
                "success_rate": success_rate,
                "hitl_trigger_rate": performance.get("hitl_trigger_rate", 0.0),
                "average_confidence": performance.get("average_confidence", 0.0)
            },
            "status_breakdown": status_breakdown,
            "confidence_distribution": analytics_data.get("confidence_distribution", {
                "high": {"count": 0, "range": "0.8-1.0", "percentage": 0.0},
                "medium": {"count": 0, "range": "0.6-0.8", "percentage": 0.0},
                "low": {"count": 0, "range": "0.0-0.6", "percentage": 0.0}
            }),
            "average_sources_per_report": analytics_data.get("average_sources_per_report", 0),
            "daily_usage": analytics_data.get("daily_usage", [])
        }
        
        return response
    except Exception as e:
        # Fallback to sample data if database query fails
        print(f"Error getting analytics: {e}")
        return {
            "summary": {
                "total_queries": 0,
                "queries_today": 0,
                "queries_this_week": 0,
                "active_users": 0
            },
            "performance": {
                "success_rate": 0.0,
                "hitl_trigger_rate": 0.0,
                "average_confidence": 0.0
            },
            "status_breakdown": {},
            "confidence_distribution": {
                "high": {"count": 0, "range": "0.8-1.0", "percentage": 0.0},
                "medium": {"count": 0, "range": "0.6-0.8", "percentage": 0.0},
                "low": {"count": 0, "range": "0.0-0.6", "percentage": 0.0}
            },
            "average_sources_per_report": 0,
            "daily_usage": []
        }

# ============ 5. EXPORT FORMATS ============
@router.get("/export/{task_id}")
async def export_report(task_id: str, format: str = "json"):
    """
    Export report in different formats
    Author: Kundana Pooskur
    Purpose: Users can download reports as PDF, Markdown, HTML, or JSON
    """
    try:
        # Get report from main API
        response = requests.get(f"http://localhost:8000/api/v1/report/{task_id}")
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Report not found")
        
        report_data = response.json()
        report_content = report_data.get("report", "")
        
        if format == "markdown":
            # Convert to Markdown
            markdown = f"# Research Report\n\n"
            markdown += f"**Task ID**: `{task_id}`\n\n"
            markdown += f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            markdown += f"**Status**: {report_data.get('status', 'Completed')}\n\n"
            markdown += "---\n\n"
            markdown += report_content
            markdown += "\n\n---\n\n"
            markdown += f"*Generated by AI Research Assistant - Kundana Pooskur*\n"
            
            return {
                "format": "markdown",
                "content": markdown,
                "filename": f"report_{task_id}.md",
                "size": len(markdown)
            }
        
        elif format == "html":
            # Convert to HTML with styling
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Research Report - {task_id}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                    h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
                    .metadata {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                    .content {{ line-height: 1.6; }}
                    .footer {{ margin-top: 50px; text-align: center; color: #666; font-size: 0.9em; }}
                </style>
            </head>
            <body>
                <h1>Research Report</h1>
                <div class="metadata">
                    <p><strong>Task ID:</strong> {task_id}</p>
                    <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p><strong>Status:</strong> Completed</p>
                </div>
                <div class="content">
                    {report_content.replace(chr(10), '<br>')}
                </div>
                <div class="footer">
                    <p>Generated by AI Research Assistant - Enhanced by Kundana Pooskur</p>
                </div>
            </body>
            </html>
            """
            return {
                "format": "html",
                "content": html,
                "filename": f"report_{task_id}.html",
                "size": len(html)
            }
        
        else:  # JSON default
            return {
                "format": "json",
                "content": report_data,
                "filename": f"report_{task_id}.json",
                "size": len(json.dumps(report_data))
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ 6. SESSION MANAGEMENT ============
@router.post("/session/create")
async def create_session(request: SessionCreateRequest):
    """
    Create user session for tracking
    Author: Kundana Pooskur
    Purpose: Track user's research history
    """
    session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(sessions)}"
    sessions[session_id] = {
        "session_id": session_id,
        "user_email": request.user_email,
        "user_name": request.user_name,
        "created_at": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat(),
        "queries": [],
        "total_queries": 0,
        "total_reports": 0
    }
    return sessions[session_id]

@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str):
    """
    Get user's research history
    Author: Kundana Pooskur
    Purpose: Show past queries in dashboard
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    session["last_active"] = datetime.now().isoformat()
    
    return session

@router.post("/session/{session_id}/add_query")
async def add_query_to_session(session_id: str, query: str, task_id: str):
    """
    Add query to session history
    Author: Kundana Pooskur
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    sessions[session_id]["queries"].append({
        "query": query,
        "task_id": task_id,
        "timestamp": datetime.now().isoformat()
    })
    sessions[session_id]["total_queries"] += 1
    sessions[session_id]["last_active"] = datetime.now().isoformat()
    
    return {"status": "added", "total_queries": sessions[session_id]["total_queries"]}

# ============ 7. ENHANCED REVIEW ============
@router.post("/review/enhanced/{task_id}")
async def enhanced_review(task_id: str, request: EnhancedReviewRequest):
    """
    Enhanced HITL review with detailed feedback
    Author: Kundana Pooskur
    Purpose: More detailed review process with editing capabilities
    """
    review_id = f"review_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    review_data = {
        "review_id": review_id,
        "task_id": task_id,
        "reviewed_at": datetime.now().isoformat(),
        "approved": request.approved,
        "reviewer_confidence": request.confidence_override,
        "comments": request.comments,
        "edited_sections": request.edited_sections or {},
        "changes_made": len(request.edited_sections) if request.edited_sections else 0
    }
    
    # Call original review endpoint
    try:
        action = "approve" if request.approved else "reject"
        response = requests.post(
            f"http://localhost:8000/api/v1/review/{task_id}",
            json={"action": action, "task_id": task_id}
        )
        
        review_data["original_response"] = response.json() if response.status_code == 200 else None
        review_data["status"] = "success" if response.status_code == 200 else "failed"
    except Exception as e:
        review_data["status"] = "error"
        review_data["error"] = str(e)
    
    return review_data

# ============ 8. SEARCH SUGGESTIONS ============
@router.get("/suggestions")
async def get_search_suggestions(query: str):
    """
    Get query suggestions based on partial input
    Author: Kundana Pooskur
    Purpose: Help users formulate better research queries
    """
    # Comprehensive suggestion database
    all_suggestions = [
        # Machine Learning
        "What are the latest advances in transformer architectures for NLP?",
        "How does RAG compare to fine-tuning for domain-specific LLMs?",
        "What are the best practices for prompt engineering in GPT-4?",
        "Explain attention mechanisms in neural networks",
        "What are the applications of reinforcement learning in robotics?",
        
        # Computer Vision
        "How do Vision Transformers compare to CNNs for image classification?",
        "What are the latest developments in object detection algorithms?",
        "Explain CLIP and its applications in multimodal learning",
        
        # Quantum Computing
        "What are the applications of quantum computing in cryptography?",
        "How does quantum supremacy impact current computing paradigms?",
        "What are the challenges in building scalable quantum computers?",
        
        # NLP
        "What are the limitations of current LLMs?",
        "How do multilingual models handle code-switching?",
        "What are the ethical considerations in deploying LLMs?",
        
        # General AI
        "What are the current approaches to achieving AGI?",
        "How does federated learning preserve privacy?",
        "What are the environmental impacts of training large models?"
    ]
    
    # Filter suggestions based on query
    query_lower = query.lower()
    filtered = [s for s in all_suggestions if query_lower in s.lower()]
    
    # If no exact matches, find partial matches
    if not filtered:
        words = query_lower.split()
        filtered = [s for s in all_suggestions if any(word in s.lower() for word in words)]
    
    return {
        "query": query,
        "suggestions": filtered[:5],
        "total_matches": len(filtered)
    }

# ============ 9. SYSTEM STATUS ============
@router.get("/system/status")
async def get_system_status():
    """
    Get overall system status
    Author: Kundana Pooskur
    Purpose: Monitor system health and performance
    """
    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(sessions),
        "active_websockets": len(active_websockets),
        "api_version": "2.0.0",
        "enhanced_by": "Kundana Pooskur",
        "features": [
            "WebSocket Real-time Updates",
            "Batch Processing",
            "Stream Reports",
            "Analytics Dashboard",
            "Multiple Export Formats",
            "Session Management",
            "Enhanced Review",
            "Search Suggestions"
        ]
    }