"""
Task Manager for handling research tasks in SQLite database
"""

import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path
from threading import Lock

from .models import TaskStatus

logger = logging.getLogger(__name__)

# Thread-safe lock for database operations
_db_lock = Lock()

# Singleton instance
_task_manager: Optional['TaskManager'] = None


def get_task_manager() -> 'TaskManager':
    """Get or create the singleton TaskManager instance"""
    global _task_manager
    if _task_manager is None:
        db_path = os.getenv('TASK_DB_PATH', 'data/tasks.db')
        _task_manager = TaskManager(db_path=db_path)
    return _task_manager


def set_task_manager(manager: 'TaskManager'):
    """Set the singleton TaskManager instance (for testing)"""
    global _task_manager
    _task_manager = manager


class TaskManager:
    """Manages research tasks in SQLite database"""
    
    def __init__(self, db_path: str = 'data/tasks.db'):
        """
        Initialize TaskManager
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info(f"TaskManager initialized with database: {db_path}")
    
    def _init_database(self):
        """Initialize database schema"""
        with _db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='tasks'
            ''')
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                # Create new table with full schema
                cursor.execute('''
                    CREATE TABLE tasks (
                        task_id TEXT PRIMARY KEY,
                        query TEXT NOT NULL,
                        user_id TEXT,
                        status TEXT NOT NULL,
                        progress REAL DEFAULT 0.0,
                        message TEXT,
                        report TEXT,
                        sources TEXT,  -- JSON string
                        confidence_score REAL,
                        needs_hitl INTEGER DEFAULT 0,
                        error TEXT,
                        metadata TEXT,  -- JSON string
                        created_at TEXT NOT NULL,
                        updated_at TEXT
                    )
                ''')
                
                # Create index on status for faster queries
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)
                ''')
            else:
                # Table exists - check and add missing columns
                cursor.execute('PRAGMA table_info(tasks)')
                columns = {row[1] for row in cursor.fetchall()}
                
                # Add missing columns (in order of dependency)
                if 'message' not in columns:
                    cursor.execute('ALTER TABLE tasks ADD COLUMN message TEXT')
                
                if 'progress' not in columns:
                    cursor.execute('ALTER TABLE tasks ADD COLUMN progress REAL DEFAULT 0.0')
                
                if 'report' not in columns:
                    cursor.execute('ALTER TABLE tasks ADD COLUMN report TEXT')
                
                if 'sources' not in columns:
                    cursor.execute('ALTER TABLE tasks ADD COLUMN sources TEXT')
                
                if 'confidence_score' not in columns:
                    cursor.execute('ALTER TABLE tasks ADD COLUMN confidence_score REAL')
                
                if 'needs_hitl' not in columns:
                    cursor.execute('ALTER TABLE tasks ADD COLUMN needs_hitl INTEGER DEFAULT 0')
                
                if 'error' not in columns:
                    cursor.execute('ALTER TABLE tasks ADD COLUMN error TEXT')
                
                if 'metadata' not in columns:
                    cursor.execute('ALTER TABLE tasks ADD COLUMN metadata TEXT')
                
                if 'updated_at' not in columns:
                    cursor.execute('ALTER TABLE tasks ADD COLUMN updated_at TEXT')
                
                # Create index if it doesn't exist
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)
                ''')
            
            conn.commit()
            conn.close()
    
    def create_task(
        self,
        query: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new research task
        
        Args:
            query: Research query
            user_id: Optional user identifier
            metadata: Optional metadata dictionary
            
        Returns:
            Task ID (UUID string)
        """
        import uuid
        task_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        with _db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO tasks (
                    task_id, query, user_id, status, progress, message,
                    created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_id,
                query,
                user_id,
                TaskStatus.QUEUED.value,
                0.0,
                "Task created and queued",
                now,
                now,  # Set updated_at to same as created_at initially
                json.dumps(metadata or {})
            ))
            
            conn.commit()
            conn.close()
        
        logger.info(f"Created task {task_id} for query: {query[:50]}...")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task by ID
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task dictionary or None if not found
        """
        with _db_lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row is None:
                return None
            
            task = dict(row)
            # Parse JSON fields
            if task.get('sources'):
                task['sources'] = json.loads(task['sources'])
            else:
                task['sources'] = []
            
            if task.get('metadata'):
                task['metadata'] = json.loads(task['metadata'])
            else:
                task['metadata'] = {}
            
            # Convert boolean
            task['needs_hitl'] = bool(task.get('needs_hitl', 0))
            
            return task
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: Optional[float] = None,
        message: Optional[str] = None
    ):
        """
        Update task status
        
        Args:
            task_id: Task identifier
            status: New status
            progress: Optional progress (0-100)
            message: Optional status message
        """
        now = datetime.utcnow().isoformat()
        
        updates = ['status = ?', 'updated_at = ?']
        values = [status.value, now]
        
        if progress is not None:
            updates.append('progress = ?')
            values.append(progress)
        
        if message is not None:
            updates.append('message = ?')
            values.append(message)
        
        values.append(task_id)
        
        with _db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                f'UPDATE tasks SET {", ".join(updates)} WHERE task_id = ?',
                values
            )
            
            conn.commit()
            conn.close()
        
        logger.info(f"Updated task {task_id} status to {status.value}")
    
    def store_task_result(
        self,
        task_id: str,
        report: str,
        sources: List[Dict[str, Any]],
        confidence: float,
        needs_hitl: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Store task result
        
        Args:
            task_id: Task identifier
            report: Generated report
            sources: List of source dictionaries
            confidence: Confidence score (0-1)
            needs_hitl: Whether HITL review is needed
            metadata: Optional metadata
        """
        now = datetime.utcnow().isoformat()
        status = TaskStatus.PENDING_REVIEW if needs_hitl else TaskStatus.COMPLETED
        
        with _db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE tasks SET
                    status = ?,
                    report = ?,
                    sources = ?,
                    confidence_score = ?,
                    needs_hitl = ?,
                    metadata = ?,
                    progress = 100.0,
                    message = ?,
                    updated_at = ?
                WHERE task_id = ?
            ''', (
                status.value,
                report,
                json.dumps(sources),
                confidence,
                1 if needs_hitl else 0,
                json.dumps(metadata or {}),
                "Report generated successfully",
                now,
                task_id
            ))
            
            conn.commit()
            conn.close()
        
        logger.info(f"Stored result for task {task_id}, needs_hitl={needs_hitl}")
    
    def mark_task_failed(self, task_id: str, error_message: str):
        """
        Mark task as failed
        
        Args:
            task_id: Task identifier
            error_message: Error message
        """
        now = datetime.utcnow().isoformat()
        
        with _db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE tasks SET
                    status = ?,
                    error = ?,
                    message = ?,
                    updated_at = ?
                WHERE task_id = ?
            ''', (
                TaskStatus.FAILED.value,
                error_message,
                "Task failed",
                now,
                task_id
            ))
            
            conn.commit()
            conn.close()
        
        logger.error(f"Marked task {task_id} as failed: {error_message}")
    
    def approve_review(self, task_id: str) -> bool:
        """
        Approve a task in HITL review
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if successful, False if task not found or not pending review
        """
        task = self.get_task(task_id)
        if not task or task['status'] != TaskStatus.PENDING_REVIEW.value:
            return False
        
        now = datetime.utcnow().isoformat()
        
        with _db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE tasks SET
                    status = ?,
                    needs_hitl = 0,
                    message = ?,
                    updated_at = ?
                WHERE task_id = ?
            ''', (
                TaskStatus.COMPLETED.value,
                "Report approved",
                now,
                task_id
            ))
            
            conn.commit()
            conn.close()
        
        logger.info(f"Approved review for task {task_id}")
        return True
    
    def edit_review(self, task_id: str, edited_report: str) -> bool:
        """
        Edit a task report during HITL review
        
        Args:
            task_id: Task identifier
            edited_report: Edited report content
            
        Returns:
            True if successful, False if task not found or not pending review
        """
        task = self.get_task(task_id)
        if not task or task['status'] != TaskStatus.PENDING_REVIEW.value:
            return False
        
        now = datetime.utcnow().isoformat()
        
        with _db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE tasks SET
                    report = ?,
                    needs_hitl = 0,
                    status = ?,
                    message = ?,
                    updated_at = ?
                WHERE task_id = ?
            ''', (
                edited_report,
                TaskStatus.COMPLETED.value,
                "Report edited and approved",
                now,
                task_id
            ))
            
            conn.commit()
            conn.close()
        
        logger.info(f"Edited report for task {task_id}")
        return True
    
    def reject_review(self, task_id: str, rejection_reason: str) -> Tuple[bool, Optional[str]]:
        """
        Reject a task report during HITL review and prepare for regeneration
        
        Args:
            task_id: Task identifier
            rejection_reason: Reason for rejection
            
        Returns:
            Tuple of (success: bool, original_query: Optional[str])
            Returns the original query if successful, None otherwise
        """
        task = self.get_task(task_id)
        if not task or task['status'] != TaskStatus.PENDING_REVIEW.value:
            return (False, None)
        
        original_query = task.get('query', '')
        if not original_query:
            logger.error(f"Cannot reject task {task_id}: original query not found")
            return (False, None)
        
        now = datetime.utcnow().isoformat()
        
        # Get existing metadata and add rejection info
        existing_metadata = task.get('metadata', {})
        if isinstance(existing_metadata, str):
            try:
                existing_metadata = json.loads(existing_metadata)
            except:
                existing_metadata = {}
        elif not isinstance(existing_metadata, dict):
            existing_metadata = {}
        
        # Track rejection history
        rejection_history = existing_metadata.get('rejection_history', [])
        rejection_history.append({
            'reason': rejection_reason,
            'timestamp': now,
            'attempt': len(rejection_history) + 1
        })
        existing_metadata['rejection_history'] = rejection_history
        existing_metadata['last_rejection_reason'] = rejection_reason
        
        with _db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Reset status to PROCESSING, clear error, keep query
            cursor.execute('''
                UPDATE tasks SET
                    status = ?,
                    error = NULL,
                    message = ?,
                    progress = ?,
                    report = NULL,
                    updated_at = ?,
                    metadata = ?
                WHERE task_id = ?
            ''', (
                TaskStatus.PROCESSING.value,
                "Report rejected. Regenerating...",
                10.0,  # Reset progress to start
                now,
                json.dumps(existing_metadata),
                task_id
            ))
            
            conn.commit()
            conn.close()
        
        logger.info(f"Rejected report for task {task_id}: {rejection_reason}. Preparing for regeneration.")
        return (True, original_query)
