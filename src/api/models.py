"""
Pydantic models for AI Research Assistant API

This module contains all request and response models used by the API endpoints.
"""

import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# ============================================================================
# Enums
# ============================================================================

class ResearchDepth(str, Enum):
    """Research depth levels."""
    QUICK = "quick"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


class TaskStatus(str, Enum):
    """Task status values."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"


class HITLAction(str, Enum):
    """Human-in-the-loop review actions."""
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


# ============================================================================
# Request Models
# ============================================================================

class ResearchRequest(BaseModel):
    """
    Request model for initiating a research task.
    
    Attributes:
        query: Research query string (10-500 characters)
        depth: Research depth level (default: standard)
        user_id: Optional user identifier
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "What are the latest developments in quantum computing?",
                "depth": "standard",
                "user_id": "user_12345"
            }
        }
    )
    
    query: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Research query string (10-500 characters)",
        examples=["What are the latest developments in quantum computing?"]
    )
    depth: ResearchDepth = Field(
        default=ResearchDepth.STANDARD,
        description="Research depth level: quick, standard, or comprehensive",
        examples=["standard"]
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user identifier for tracking",
        examples=["user_12345"]
    )
    
    @field_validator("query")
    @classmethod
    def validate_query_content(cls, v: str) -> str:
        """
        Validate query for malicious content (HTML tags, scripts, etc.).
        
        Args:
            v: Query string to validate
            
        Returns:
            Validated query string
            
        Raises:
            ValueError: If query contains potentially malicious content
        """
        if not v or not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        
        # Check for HTML tags
        html_pattern = re.compile(r'<[^>]+>', re.IGNORECASE)
        if html_pattern.search(v):
            raise ValueError("Query cannot contain HTML tags")
        
        # Check for script tags and javascript
        script_patterns = [
            r'<script[^>]*>',
            r'javascript:',
            r'on\w+\s*=',
            r'data:text/html',
        ]
        for pattern in script_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Query cannot contain script tags or JavaScript code")
        
        # Check for SQL injection patterns (basic)
        sql_patterns = [
            r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)',
            r'(\b(UNION|OR|AND)\s+\d+\s*=\s*\d+)',
        ]
        for pattern in sql_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Query contains potentially malicious SQL patterns")
        
        return v.strip()


class HITLReviewRequest(BaseModel):
    """
    Request model for human-in-the-loop review actions.
    
    Attributes:
        task_id: Task identifier
        action: Review action (approve, edit, or reject)
        edited_report: Optional edited report text (required if action is 'edit')
        rejection_reason: Optional rejection reason (required if action is 'reject')
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "action": "approve",
                "edited_report": None,
                "rejection_reason": None
            }
        }
    )
    
    task_id: str = Field(
        ...,
        description="Task identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    action: HITLAction = Field(
        ...,
        description="Review action: approve, edit, or reject",
        examples=["approve"]
    )
    edited_report: Optional[str] = Field(
        default=None,
        description="Edited report text (required if action is 'edit')",
        examples=[None]
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Rejection reason (required if action is 'reject')",
        examples=[None]
    )
    
    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        """Validate task_id is a valid UUID format."""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError("task_id must be a valid UUID")
    
    @model_validator(mode='after')
    def validate_action_requirements(self):
        """Validate that required fields are provided based on action."""
        if self.action == HITLAction.EDIT and not self.edited_report:
            raise ValueError("edited_report is required when action is 'edit'")
        if self.action == HITLAction.REJECT and not self.rejection_reason:
            raise ValueError("rejection_reason is required when action is 'reject'")
        return self


# ============================================================================
# Response Models
# ============================================================================

class ResearchResponse(BaseModel):
    """
    Response model for research task creation.
    
    Attributes:
        task_id: Unique task identifier (UUID)
        status: Task status
        message: Status message
        created_at: Task creation timestamp
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "queued",
                "message": "Research task created successfully",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )
    
    task_id: str = Field(
        ...,
        description="Unique task identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    status: str = Field(
        ...,
        description="Current task status",
        examples=["queued"]
    )
    message: str = Field(
        ...,
        description="Status message",
        examples=["Research task created successfully"]
    )
    created_at: datetime = Field(
        ...,
        description="Task creation timestamp",
        examples=[datetime.now()]
    )


class StatusResponse(BaseModel):
    """
    Response model for task status queries.
    
    Attributes:
        task_id: Task identifier
        status: Current task status (queued, processing, completed, failed)
        current_agent: Currently executing agent (if processing)
        progress: Progress percentage (0-100)
        message: Status message
        created_at: Task creation timestamp
        updated_at: Last update timestamp
        estimated_completion: Estimated completion time (if available)
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "processing",
                "current_agent": "synthesis",
                "progress": 65,
                "message": "Synthesizing research findings",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:35:00Z",
                "estimated_completion": "2024-01-15T10:40:00Z"
            }
        }
    )
    
    task_id: str = Field(
        ...,
        description="Task identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    status: TaskStatus = Field(
        ...,
        description="Current task status",
        examples=[TaskStatus.PROCESSING]
    )
    current_agent: Optional[str] = Field(
        default=None,
        description="Currently executing agent (search, synthesis, validation, hitl)",
        examples=["synthesis"]
    )
    progress: int = Field(
        ...,
        ge=0,
        le=100,
        description="Progress percentage (0-100)",
        examples=[65]
    )
    message: str = Field(
        ...,
        description="Status message",
        examples=["Synthesizing research findings"]
    )
    created_at: datetime = Field(
        ...,
        description="Task creation timestamp",
        examples=[datetime.now()]
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
        examples=[datetime.now()]
    )
    estimated_completion: Optional[datetime] = Field(
        default=None,
        description="Estimated completion time (if available)",
        examples=[datetime.now()]
    )


class Source(BaseModel):
    """
    Nested model for research source information.
    
    Attributes:
        source_id: Unique source identifier
        title: Source title
        url: Source URL
        relevance_score: Relevance score (0.0-1.0)
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_id": 1,
                "title": "Quantum Computing Advances in 2024",
                "url": "https://example.com/quantum-computing-2024",
                "relevance_score": 0.95
            }
        }
    )
    
    source_id: int = Field(
        ...,
        description="Unique source identifier",
        examples=[1]
    )
    title: str = Field(
        ...,
        description="Source title",
        examples=["Quantum Computing Advances in 2024"]
    )
    url: str = Field(
        ...,
        description="Source URL",
        examples=["https://example.com/quantum-computing-2024"]
    )
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Relevance score (0.0-1.0)",
        examples=[0.95]
    )


class ReportResponse(BaseModel):
    """
    Response model for completed research reports.
    
    Attributes:
        task_id: Task identifier
        status: Task status
        report: Generated report text
        sources: List of research sources
        confidence_score: Confidence score (0.0-1.0)
        needs_hitl: Whether human review is needed
        created_at: Task creation timestamp
        metadata: Additional metadata dictionary
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "report": "This report summarizes the latest developments...",
                "sources": [
                    {
                        "source_id": 1,
                        "title": "Quantum Computing Advances in 2024",
                        "url": "https://example.com/quantum-computing-2024",
                        "relevance_score": 0.95
                    }
                ],
                "confidence_score": 0.87,
                "needs_hitl": False,
                "created_at": "2024-01-15T10:30:00Z",
                "metadata": {
                    "total_sources": 10,
                    "processing_time": 120.5
                }
            }
        }
    )
    
    task_id: str = Field(
        ...,
        description="Task identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    status: str = Field(
        ...,
        description="Task status",
        examples=["completed"]
    )
    report: str = Field(
        ...,
        description="Generated report text",
        examples=["This report summarizes the latest developments..."]
    )
    sources: List[Source] = Field(
        ...,
        description="List of research sources",
        examples=[[]]
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0)",
        examples=[0.87]
    )
    needs_hitl: bool = Field(
        ...,
        description="Whether human-in-the-loop review is needed",
        examples=[False]
    )
    created_at: datetime = Field(
        ...,
        description="Task creation timestamp",
        examples=[datetime.now()]
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata dictionary",
        examples=[{"total_sources": 10, "processing_time": 120.5}]
    )


class ErrorResponse(BaseModel):
    """
    Standard error response model.
    
    Attributes:
        error: Error type or code
        detail: Detailed error message
        timestamp: Error timestamp
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "ValidationError",
                "detail": "Query must be between 10 and 500 characters",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
    )
    
    error: str = Field(
        ...,
        description="Error type or code",
        examples=["ValidationError"]
    )
    detail: str = Field(
        ...,
        description="Detailed error message",
        examples=["Query must be between 10 and 500 characters"]
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Error timestamp",
        examples=[datetime.now()]
    )

