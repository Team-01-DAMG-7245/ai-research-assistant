"""
Task Manager for AI Research Assistant

Manages research task state, persistence, and S3 storage.
Provides thread-safe operations for concurrent task management.
"""

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Any, Optional, List

import logging

from src.utils.s3_client import S3Client

logger = logging.getLogger(__name__)


# ============================================================================
# TaskStatus Enum
# ============================================================================

class TaskStatus:
    """Task status constants."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"


# ============================================================================
# Database Connection Manager
# ============================================================================

class DatabaseManager:
    """
    Thread-safe SQLite database manager with connection pooling.
    
    SQLite doesn't support true connection pooling, but we use:
    - Thread-local connections
    - Locks for write operations
    - Connection context manager for proper cleanup
    """
    
    def __init__(self, db_path: str):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.RLock()  # Reentrant lock for nested operations
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0  # Wait up to 30 seconds for lock
            )
            self._local.connection.row_factory = sqlite3.Row  # Return dict-like rows
            # Enable WAL mode for better concurrency
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA foreign_keys=ON")
        return self._local.connection
    
    def _init_database(self):
        """Initialize database schema."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Create tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    query TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_agent TEXT,
                    progress INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            
            # Create task_results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_results (
                    task_id TEXT PRIMARY KEY,
                    report TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    needs_hitl INTEGER NOT NULL DEFAULT 0,
                    s3_url TEXT,
                    created_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)
            
            # Create indexes for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status 
                ON tasks(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_user_id 
                ON tasks(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_created_at 
                ON tasks(created_at)
            """)
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        
        Usage:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(...)
        """
        conn = self._get_connection()
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}", exc_info=True)
            raise
        finally:
            # Don't close connection here - keep it for thread-local reuse
            pass
    
    def close_connection(self):
        """Close thread-local connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# ============================================================================
# Task Manager
# ============================================================================

class TaskManager:
    """
    Manages research task state and persistence.
    
    Thread-safe operations for creating, updating, and retrieving tasks.
    """
    
    def __init__(self, db_path: Optional[str] = None, s3_client: Optional[S3Client] = None):
        """
        Initialize TaskManager.
        
        Args:
            db_path: Path to SQLite database (default: data/tasks.db)
            s3_client: S3Client instance for storing reports (optional)
        """
        if db_path is None:
            # Default to data directory in project root
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "tasks.db")
        
        self.db_manager = DatabaseManager(db_path)
        self.s3_client = s3_client if s3_client is not None else S3Client()
        self._lock = threading.RLock()
        logger.info(f"TaskManager initialized with database: {db_path}")
    
    def create_task(self, query: str, user_id: Optional[str] = None, depth: str = "standard") -> str:
        """
        Create a new research task.
        
        Args:
            query: Research query string
            user_id: Optional user identifier
            depth: Research depth level (quick, standard, comprehensive)
        
        Returns:
            task_id: Unique task identifier (UUID)
        """
        task_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        with self._lock:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tasks (
                        task_id, user_id, query, status, 
                        current_agent, progress, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id,
                    user_id,
                    query,
                    TaskStatus.QUEUED,
                    None,
                    0,
                    now,
                    now
                ))
                conn.commit()
        
        logger.info(f"Created task {task_id} for query: {query[:50]}...")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve task status and progress information.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Dictionary with task status, progress, and current_agent,
            or None if task not found
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    task_id, user_id, query, status, current_agent, 
                    progress, error_message, created_at, updated_at
                FROM tasks
                WHERE task_id = ?
            """, (task_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                "task_id": row["task_id"],
                "user_id": row["user_id"],
                "query": row["query"],
                "status": row["status"],
                "current_agent": row["current_agent"],
                "progress": row["progress"],
                "error_message": row["error_message"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
    
    def update_task_progress(
        self,
        task_id: str,
        status: str,
        current_agent: Optional[str] = None,
        progress: int = 0,
        message: Optional[str] = None
    ) -> bool:
        """
        Update task progress and status.
        
        Args:
            task_id: Task identifier
            status: New status (must be valid TaskStatus)
            current_agent: Currently executing agent (optional)
            progress: Progress percentage (0-100)
            message: Optional status message
        
        Returns:
            True if update successful, False otherwise
        """
        if progress < 0 or progress > 100:
            raise ValueError("Progress must be between 0 and 100")
        
        now = datetime.utcnow()
        
        with self._lock:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Build update query dynamically
                updates = ["status = ?", "progress = ?", "updated_at = ?"]
                params = [status, progress, now]
                
                if current_agent is not None:
                    updates.append("current_agent = ?")
                    params.append(current_agent)
                
                if message and status == TaskStatus.FAILED:
                    updates.append("error_message = ?")
                    params.append(message)
                
                params.append(task_id)
                
                query = f"""
                    UPDATE tasks
                    SET {', '.join(updates)}
                    WHERE task_id = ?
                """
                
                cursor.execute(query, params)
                conn.commit()
                
                if cursor.rowcount == 0:
                    logger.warning(f"Task {task_id} not found for update")
                    return False
        
        logger.debug(f"Updated task {task_id}: status={status}, progress={progress}, agent={current_agent}")
        return True
    
    def store_task_result(
        self,
        task_id: str,
        report: str,
        sources: List[Dict[str, Any]],
        confidence: float,
        needs_hitl: bool = False
    ) -> bool:
        """
        Store final task result and upload report to S3.
        
        Args:
            task_id: Task identifier
            report: Generated report text
            sources: List of source dictionaries
            confidence: Confidence score (0.0-1.0)
            needs_hitl: Whether human review is needed
        
        Returns:
            True if successful, False otherwise
        """
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        
        now = datetime.utcnow()
        s3_url = None
        
        # Upload report to S3
        try:
            s3_key = f"gold/reports/{task_id}.md"
            
            # Write report to temporary file
            with NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(report)
                tmp_path = tmp_file.name
            
            # Upload to S3
            if self.s3_client.upload_file(tmp_path, s3_key):
                # Construct S3 URL (assuming standard S3 URL format)
                bucket = self.s3_client.bucket
                region = self.s3_client.region
                s3_url = f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
                logger.info(f"Uploaded report for task {task_id} to S3: {s3_url}")
            else:
                logger.warning(f"Failed to upload report for task {task_id} to S3")
            
            # Clean up temporary file
            Path(tmp_path).unlink(missing_ok=True)
            
        except Exception as e:
            logger.error(f"Error uploading report to S3 for task {task_id}: {e}", exc_info=True)
            # Continue even if S3 upload fails - we'll still store in database
        
        # Determine final status
        final_status = TaskStatus.PENDING_REVIEW if needs_hitl else TaskStatus.COMPLETED
        
        with self._lock:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Store task result
                cursor.execute("""
                    INSERT OR REPLACE INTO task_results (
                        task_id, report, sources_json, confidence_score,
                        needs_hitl, s3_url, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id,
                    report,
                    json.dumps(sources),
                    confidence,
                    1 if needs_hitl else 0,
                    s3_url,
                    now
                ))
                
                # Update task status
                cursor.execute("""
                    UPDATE tasks
                    SET status = ?, progress = 100, updated_at = ?
                    WHERE task_id = ?
                """, (final_status, now, task_id))
                
                conn.commit()
        
        logger.info(f"Stored result for task {task_id} (status: {final_status}, confidence: {confidence:.2f})")
        return True
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve final task result including report and metadata.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Dictionary with report, sources, confidence, and S3 URL,
            or None if task result not found
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    tr.task_id, tr.report, tr.sources_json, 
                    tr.confidence_score, tr.needs_hitl, tr.s3_url, tr.created_at,
                    t.status, t.query, t.created_at as task_created_at
                FROM task_results tr
                JOIN tasks t ON tr.task_id = t.task_id
                WHERE tr.task_id = ?
            """, (task_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            try:
                sources = json.loads(row["sources_json"])
            except (json.JSONDecodeError, TypeError):
                sources = []
            
            return {
                "task_id": row["task_id"],
                "report": row["report"],
                "sources": sources,
                "confidence_score": row["confidence_score"],
                "needs_hitl": bool(row["needs_hitl"]),
                "s3_url": row["s3_url"],
                "status": row["status"],
                "query": row["query"],
                "created_at": row["created_at"],
                "task_created_at": row["task_created_at"],
            }
    
    def mark_task_failed(self, task_id: str, error: str) -> bool:
        """
        Mark task as failed and store error message.
        
        Args:
            task_id: Task identifier
            error: Error message
        
        Returns:
            True if update successful, False otherwise
        """
        now = datetime.utcnow()
        
        with self._lock:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tasks
                    SET status = ?, error_message = ?, updated_at = ?
                    WHERE task_id = ?
                """, (TaskStatus.FAILED, error, now, task_id))
                conn.commit()
                
                if cursor.rowcount == 0:
                    logger.warning(f"Task {task_id} not found for failure marking")
                    return False
        
        logger.error(f"Marked task {task_id} as failed: {error}")
        return True
    
    def approve_task(self, task_id: str) -> bool:
        """
        Approve a task that was pending review.
        
        Args:
            task_id: Task identifier
        
        Returns:
            True if update successful, False otherwise
        """
        now = datetime.utcnow()
        
        with self._lock:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tasks
                    SET status = ?, updated_at = ?
                    WHERE task_id = ? AND status = ?
                """, (TaskStatus.APPROVED, now, task_id, TaskStatus.PENDING_REVIEW))
                conn.commit()
                
                if cursor.rowcount == 0:
                    logger.warning(f"Task {task_id} not found or not in PENDING_REVIEW status")
                    return False
        
        logger.info(f"Approved task {task_id}")
        return True
    
    def update_task_report(self, task_id: str, edited_report: str) -> bool:
        """
        Update task report (for HITL edit action).
        
        Args:
            task_id: Task identifier
            edited_report: Edited report text
        
        Returns:
            True if update successful, False otherwise
        """
        now = datetime.utcnow()
        
        # Re-upload to S3 if needed
        s3_url = None
        try:
            s3_key = f"gold/reports/{task_id}.md"
            
            with NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(edited_report)
                tmp_path = tmp_file.name
            
            if self.s3_client.upload_file(tmp_path, s3_key):
                bucket = self.s3_client.bucket
                region = self.s3_client.region
                s3_url = f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
            
            Path(tmp_path).unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Error uploading edited report to S3: {e}", exc_info=True)
        
        with self._lock:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Update report in task_results
                if s3_url:
                    cursor.execute("""
                        UPDATE task_results
                        SET report = ?, s3_url = ?, created_at = ?
                        WHERE task_id = ?
                    """, (edited_report, s3_url, now, task_id))
                else:
                    cursor.execute("""
                        UPDATE task_results
                        SET report = ?, created_at = ?
                        WHERE task_id = ?
                    """, (edited_report, now, task_id))
                
                # Update task timestamp
                cursor.execute("""
                    UPDATE tasks
                    SET updated_at = ?
                    WHERE task_id = ?
                """, (now, task_id))
                
                conn.commit()
                
                if cursor.rowcount == 0:
                    logger.warning(f"Task result {task_id} not found for update")
                    return False
        
        logger.info(f"Updated report for task {task_id}")
        return True
    
    def close(self):
        """Close database connections."""
        self.db_manager.close_connection()


# ============================================================================
# Singleton Instance
# ============================================================================

# Global task manager instance (can be initialized in main.py)
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """
    Get or create global TaskManager instance.
    
    Returns:
        TaskManager instance
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager


def set_task_manager(task_manager: TaskManager):
    """
    Set global TaskManager instance (useful for testing).
    
    Args:
        task_manager: TaskManager instance
    """
    global _task_manager
    _task_manager = task_manager
