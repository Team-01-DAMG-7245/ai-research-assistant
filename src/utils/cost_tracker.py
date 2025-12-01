"""
Cost Tracking Module

Tracks all OpenAI API calls with detailed information including operation type,
timestamps, tokens, and costs. Stores logs in JSON format for analysis.
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)

# Thread-safe lock for file operations
_file_lock = threading.Lock()

# Default log file path
# cost_tracker.py is in src/utils/, so go up 2 levels to project root
_DEFAULT_LOG_FILE = Path(__file__).parent.parent.parent / "logs" / "cost_tracking.json"


@dataclass
class APICallRecord:
    """Record of a single API call."""
    timestamp: str
    task_id: Optional[str]
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    operation: str
    method: str  # "chat_completion" or "create_embedding"
    duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class CostTracker:
    """
    Thread-safe cost tracker for OpenAI API calls.
    
    Tracks all API calls with operation types and stores them in JSON format.
    """
    
    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize cost tracker.
        
        Args:
            log_file: Path to JSON log file. Defaults to logs/cost_tracking.json
        """
        self.log_file = log_file or _DEFAULT_LOG_FILE
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self._records: List[APICallRecord] = []
        self._current_task_id: Optional[str] = None
        self._lock = threading.Lock()
        
        # Load existing records
        self._load_records()
    
    def set_task_id(self, task_id: str):
        """
        Set the current task ID for subsequent API calls.
        
        Args:
            task_id: Task identifier
        """
        with self._lock:
            self._current_task_id = task_id
    
    def clear_task_id(self):
        """Clear the current task ID."""
        with self._lock:
            self._current_task_id = None
    
    def log_api_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        operation: str,
        cost: float = 0.0,
        method: str = "chat_completion",
        duration: float = 0.0
    ):
        """
        Log an API call with all details.
        
        Args:
            model: Model name used
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            operation: Operation type (query_expansion, synthesis, validation, embedding)
            cost: Estimated cost in USD
            method: API method name (chat_completion or create_embedding)
            duration: Duration of API call in seconds
        """
        record = APICallRecord(
            timestamp=datetime.now().isoformat(),
            task_id=self._current_task_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost=cost,
            operation=operation,
            method=method,
            duration=duration
        )
        
        with self._lock:
            self._records.append(record)
            self._save_records()
    
    def _load_records(self):
        """Load existing records from JSON file."""
        if not self.log_file.exists():
            return
        
        try:
            with _file_lock:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._records = [
                        APICallRecord(**record) for record in data.get("records", [])
                    ]
            logger.info(f"Loaded {len(self._records)} existing cost records")
        except Exception as exc:
            logger.warning(f"Failed to load cost records: {exc}")
            self._records = []
    
    def _save_records(self):
        """Save records to JSON file."""
        try:
            with _file_lock:
                data = {
                    "last_updated": datetime.now().isoformat(),
                    "total_records": len(self._records),
                    "records": [record.to_dict() for record in self._records]
                }
                
                # Write atomically using temp file
                temp_file = self.log_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Replace original file
                temp_file.replace(self.log_file)
        except Exception as exc:
            logger.error(f"Failed to save cost records: {exc}")
    
    def get_total_cost(self) -> float:
        """
        Get total cost across all API calls.
        
        Returns:
            Total cost in USD
        """
        with self._lock:
            return sum(record.cost for record in self._records)
    
    def get_cost_by_operation(self) -> Dict[str, float]:
        """
        Get cost breakdown by operation type.
        
        Returns:
            Dictionary mapping operation to total cost
        """
        with self._lock:
            costs = defaultdict(float)
            for record in self._records:
                costs[record.operation] += record.cost
            return dict(costs)
    
    def get_cost_by_model(self) -> Dict[str, float]:
        """
        Get cost breakdown by model.
        
        Returns:
            Dictionary mapping model to total cost
        """
        with self._lock:
            costs = defaultdict(float)
            for record in self._records:
                costs[record.model] += record.cost
            return dict(costs)
    
    def get_query_cost(self, task_id: str) -> float:
        """
        Get total cost for a specific task/query.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Total cost for the task in USD
        """
        with self._lock:
            return sum(
                record.cost for record in self._records
                if record.task_id == task_id
            )
    
    def get_task_records(self, task_id: str) -> List[APICallRecord]:
        """
        Get all API call records for a specific task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            List of API call records
        """
        with self._lock:
            return [
                record for record in self._records
                if record.task_id == task_id
            ]
    
    def get_summary_statistics(self) -> Dict[str, Any]:
        """
        Get summary statistics for all API calls.
        
        Returns:
            Dictionary with summary statistics
        """
        with self._lock:
            if not self._records:
                return {
                    "total_calls": 0,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "cost_by_operation": {},
                    "cost_by_model": {},
                }
            
            total_tokens = sum(record.total_tokens for record in self._records)
            total_duration = sum(record.duration for record in self._records)
            
            # Count calls by operation
            calls_by_operation = defaultdict(int)
            for record in self._records:
                calls_by_operation[record.operation] += 1
            
            # Count calls by model
            calls_by_model = defaultdict(int)
            for record in self._records:
                calls_by_model[record.model] += 1
            
            return {
                "total_calls": len(self._records),
                "total_cost": self.get_total_cost(),
                "total_tokens": total_tokens,
                "total_prompt_tokens": sum(r.prompt_tokens for r in self._records),
                "total_completion_tokens": sum(r.completion_tokens for r in self._records),
                "total_duration_seconds": total_duration,
                "average_cost_per_call": self.get_total_cost() / len(self._records) if self._records else 0.0,
                "cost_by_operation": self.get_cost_by_operation(),
                "cost_by_model": self.get_cost_by_model(),
                "calls_by_operation": dict(calls_by_operation),
                "calls_by_model": dict(calls_by_model),
            }
    
    def save_cost_report(self, filepath: Optional[Path] = None):
        """
        Save a detailed cost report to a file.
        
        Args:
            filepath: Path to save report. Defaults to logs/cost_report.json
        """
        if filepath is None:
            filepath = Path(__file__).parent.parent.parent / "logs" / "cost_report.json"
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": self.get_summary_statistics(),
            "records": [record.to_dict() for record in self._records]
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Cost report saved to {filepath}")
        except Exception as exc:
            logger.error(f"Failed to save cost report: {exc}")
            raise
    
    def clear_records(self):
        """Clear all records (use with caution)."""
        with self._lock:
            self._records = []
            self._save_records()
            logger.info("All cost records cleared")


# Global cost tracker instance
_global_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """
    Get the global cost tracker instance.
    
    Returns:
        Global CostTracker instance
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CostTracker()
    return _global_tracker


def log_api_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    operation: str,
    cost: float = 0.0,
    method: str = "chat_completion",
    duration: float = 0.0
):
    """
    Convenience function to log an API call using the global tracker.
    
    Args:
        model: Model name used
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        operation: Operation type
        cost: Estimated cost in USD
        method: API method name
        duration: Duration of API call in seconds
    """
    get_cost_tracker().log_api_call(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        operation=operation,
        cost=cost,
        method=method,
        duration=duration
    )


def get_total_cost() -> float:
    """Get total cost across all API calls."""
    return get_cost_tracker().get_total_cost()


def get_cost_by_operation() -> Dict[str, float]:
    """Get cost breakdown by operation type."""
    return get_cost_tracker().get_cost_by_operation()


def get_query_cost(task_id: str) -> float:
    """Get total cost for a specific task/query."""
    return get_cost_tracker().get_query_cost(task_id)


def save_cost_report(filepath: Optional[Path] = None):
    """Save a detailed cost report to a file."""
    get_cost_tracker().save_cost_report(filepath)


__all__ = [
    "CostTracker",
    "APICallRecord",
    "get_cost_tracker",
    "log_api_call",
    "get_total_cost",
    "get_cost_by_operation",
    "get_query_cost",
    "save_cost_report",
]

