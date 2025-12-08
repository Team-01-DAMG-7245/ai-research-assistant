# src/api/task_manager.py
"""
Task Manager for handling task persistence and state management
Compatible with existing research.py and task_queue.py
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import uuid
from threading import Lock
import logging

logger = logging.getLogger(__name__)

# Task status constants to match research.py
class TaskStatus:
    """Task status constants"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"

class TaskManager:
    """
    Manages tasks with SQLite persistence.
    This implementation matches what research.py expects.
    """
    
    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path
        self.lock = Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    user_id TEXT,
                    depth TEXT DEFAULT 'standard',
                    status TEXT DEFAULT 'queued',
                    current_agent TEXT,
                    progress INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Create results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_results (
                    task_id TEXT PRIMARY KEY,
                    report TEXT,
                    sources TEXT,  -- JSON string
                    confidence_score REAL DEFAULT 0.0,
                    needs_hitl BOOLEAN DEFAULT 0,
                    s3_url TEXT,
                    metadata TEXT,  -- JSON string
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)")
            
            conn.commit()
    
    def create_task(self, query: str, user_id: Optional[str] = None, depth: str = "standard") -> str:
        """Create a new task and return task_id."""
        task_id = str(uuid.uuid4())
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tasks (task_id, query, user_id, depth, status, created_at, updated_at, progress)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (task_id, query, user_id, depth, TaskStatus.QUEUED, created_at, created_at, 0))
                conn.commit()
        
        logger.info(f"Created task {task_id} for query: {query[:50]}...")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status information."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_id, query, user_id, depth, status, current_agent, 
                       progress, error_message, created_at, updated_at
                FROM tasks
                WHERE task_id = ?
            """, (task_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task result if available."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get both task info and result
            cursor.execute("""
                SELECT 
                    t.task_id,
                    t.status,
                    t.created_at as task_created_at,
                    r.report,
                    r.sources,
                    r.confidence_score,
                    r.needs_hitl,
                    r.s3_url,
                    r.metadata,
                    r.created_at
                FROM tasks t
                LEFT JOIN task_results r ON t.task_id = r.task_id
                WHERE t.task_id = ?
            """, (task_id,))
            row = cursor.fetchone()
            
            if row and row['report']:
                result = dict(row)
                # Parse JSON fields
                if result.get('sources'):
                    try:
                        result['sources'] = json.loads(result['sources'])
                    except:
                        result['sources'] = []
                if result.get('metadata'):
                    try:
                        result['metadata'] = json.loads(result['metadata'])
                    except:
                        result['metadata'] = {}
                return result
            return None
    
    def update_task_status(self, task_id: str, status: str, current_agent: Optional[str] = None, 
                          progress: Optional[int] = None, error_message: Optional[str] = None):
        """Update task status and related fields."""
        updated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build update query
                updates = ["status = ?", "updated_at = ?"]
                params = [status, updated_at]
                
                if current_agent is not None:
                    updates.append("current_agent = ?")
                    params.append(current_agent)
                
                if progress is not None:
                    updates.append("progress = ?")
                    params.append(progress)
                
                if error_message is not None:
                    updates.append("error_message = ?")
                    params.append(error_message)
                
                params.append(task_id)
                
                query = f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?"
                cursor.execute(query, params)
                conn.commit()
        
        logger.debug(f"Updated task {task_id}: status={status}, agent={current_agent}, progress={progress}")
    
    def save_task_result(self, task_id: str, report: str, sources: List[Dict], 
                        confidence_score: float, needs_hitl: bool = False, 
                        s3_url: Optional[str] = None, metadata: Optional[Dict] = None):
        """Save task result to database."""
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Convert lists/dicts to JSON
                sources_json = json.dumps(sources) if sources else "[]"
                metadata_json = json.dumps(metadata) if metadata else "{}"
                
                # Insert or replace result
                cursor.execute("""
                    INSERT OR REPLACE INTO task_results 
                    (task_id, report, sources, confidence_score, needs_hitl, s3_url, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (task_id, report, sources_json, confidence_score, 
                     1 if needs_hitl else 0, s3_url, metadata_json, created_at))
                
                # Update task status
                status = TaskStatus.PENDING_REVIEW if needs_hitl else TaskStatus.COMPLETED
                cursor.execute("""
                    UPDATE tasks 
                    SET status = ?, progress = 100, updated_at = ?
                    WHERE task_id = ?
                """, (status, created_at, task_id))
                
                conn.commit()
        
        logger.info(f"Saved result for task {task_id}: confidence={confidence_score}, needs_hitl={needs_hitl}")
    
    def mark_task_failed(self, task_id: str, error_message: str):
        """Mark a task as failed with error message."""
        self.update_task_status(task_id, TaskStatus.FAILED, error_message=error_message, progress=0)
    
    def get_all_tasks(self, status: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get all tasks with optional filtering."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if status:
                query = """
                    SELECT task_id, query, user_id, depth, status, current_agent, 
                           progress, error_message, created_at, updated_at
                    FROM tasks
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, (status, limit, offset))
            else:
                query = """
                    SELECT task_id, query, user_id, depth, status, current_agent, 
                           progress, error_message, created_at, updated_at
                    FROM tasks
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """
                cursor.execute(query, (limit, offset))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def approve_task(self, task_id: str):
        """Approve a task that was pending review."""
        self.update_task_status(task_id, TaskStatus.APPROVED, progress=100)
    
    def reject_task(self, task_id: str, reason: str):
        """Reject a task that was pending review."""
        self.update_task_status(task_id, TaskStatus.FAILED, error_message=f"Rejected: {reason}")
    
    def get_analytics_data(self) -> Dict:
        """Get analytics data for dashboard."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get total counts
            cursor.execute("SELECT COUNT(*) FROM tasks")
            total_queries = cursor.fetchone()[0]
            
            # Get status breakdown
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM tasks
                GROUP BY status
            """)
            status_breakdown = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Get today's count
            today = datetime.utcnow().strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT COUNT(*) FROM tasks
                WHERE DATE(created_at) = DATE(?)
            """, (today,))
            queries_today = cursor.fetchone()[0]
            
            # Get week's count
            week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT COUNT(*) FROM tasks
                WHERE DATE(created_at) >= DATE(?)
            """, (week_ago,))
            queries_this_week = cursor.fetchone()[0]
            
            # Calculate metrics
            completed = status_breakdown.get(TaskStatus.COMPLETED, 0) + status_breakdown.get(TaskStatus.APPROVED, 0)
            success_rate = completed / total_queries if total_queries > 0 else 0.0
            
            # Get confidence distribution from results
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN confidence_score >= 0.8 THEN 1 ELSE 0 END) as high,
                    SUM(CASE WHEN confidence_score >= 0.6 AND confidence_score < 0.8 THEN 1 ELSE 0 END) as medium,
                    SUM(CASE WHEN confidence_score < 0.6 THEN 1 ELSE 0 END) as low,
                    COUNT(*) as total,
                    AVG(confidence_score) as avg_confidence,
                    SUM(CASE WHEN needs_hitl = 1 THEN 1 ELSE 0 END) as hitl_count
                FROM task_results
            """)
            row = cursor.fetchone()
            
            high_conf = row[0] or 0
            medium_conf = row[1] or 0
            low_conf = row[2] or 0
            total_results = row[3] or 0
            avg_confidence = row[4] or 0.0
            hitl_count = row[5] or 0
            
            hitl_rate = hitl_count / total_results if total_results > 0 else 0.0
            
            return {
                "summary": {
                    "total_queries": total_queries,
                    "queries_today": queries_today,
                    "queries_this_week": queries_this_week,
                    "active_users": 0  # Would need to track this separately
                },
                "performance": {
                    "success_rate": success_rate,
                    "hitl_trigger_rate": hitl_rate,
                    "average_confidence": avg_confidence
                },
                "status_breakdown": status_breakdown,
                "confidence_distribution": {
                    "high": {
                        "count": high_conf,
                        "range": "0.8-1.0",
                        "percentage": (high_conf / total_results * 100) if total_results > 0 else 0
                    },
                    "medium": {
                        "count": medium_conf,
                        "range": "0.6-0.8",
                        "percentage": (medium_conf / total_results * 100) if total_results > 0 else 0
                    },
                    "low": {
                        "count": low_conf,
                        "range": "0.0-0.6",
                        "percentage": (low_conf / total_results * 100) if total_results > 0 else 0
                    }
                },
                "average_sources_per_report": 0,  # Would need to calculate from sources
                "daily_usage": []  # Would need to implement daily tracking
            }

# Singleton instance
_task_manager = None

def get_task_manager() -> TaskManager:
    """Get or create the task manager singleton."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager