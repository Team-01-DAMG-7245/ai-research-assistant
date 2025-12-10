"""
API Request and Response Models
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class TaskStatus(str, Enum):
    """Task status enumeration"""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"


class ResearchDepth(str, Enum):
    """Research depth levels"""

    QUICK = "quick"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


class ReviewAction(str, Enum):
    """HITL review actions"""

    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


# ============================================================================
# Request Models
# ============================================================================


class ResearchRequest(BaseModel):
    """Request model for submitting a research query"""

    query: str = Field(
        ..., min_length=10, max_length=500, description="Research question"
    )
    depth: ResearchDepth = Field(
        default=ResearchDepth.STANDARD, description="Research depth level"
    )
    user_id: Optional[str] = Field(
        default=None, max_length=100, description="Optional user identifier"
    )

    @validator("query")
    def validate_query_safety(cls, v):
        """Validate query doesn't contain malicious content"""
        v_lower = v.lower()
        # Check for XSS attempts
        if "<script" in v_lower or "javascript:" in v_lower:
            raise ValueError("Query contains potentially unsafe content")
        return v


class ReviewRequest(BaseModel):
    """Request model for HITL review"""

    action: ReviewAction = Field(..., description="Review action to take")
    task_id: str = Field(..., description="Task ID to review")
    edited_report: Optional[str] = Field(
        default=None, description="Edited report content (required for edit action)"
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for rejection (required for reject action)",
    )

    @validator("edited_report")
    def validate_edit_has_content(cls, v, values):
        """Validate edited_report is provided for edit action"""
        if values.get("action") == ReviewAction.EDIT and not v:
            raise ValueError("edited_report is required for edit action")
        return v

    @validator("rejection_reason")
    def validate_reject_has_reason(cls, v, values):
        """Validate rejection_reason is provided for reject action"""
        if values.get("action") == ReviewAction.REJECT and not v:
            raise ValueError("rejection_reason is required for reject action")
        return v


# ============================================================================
# Response Models
# ============================================================================


class SourceInfo(BaseModel):
    """Source information model"""

    source_id: int
    title: str
    url: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)


class ResearchResponse(BaseModel):
    """Response model for research submission"""

    task_id: str
    status: TaskStatus
    message: str
    created_at: datetime


class StatusResponse(BaseModel):
    """Response model for task status"""

    task_id: str
    status: TaskStatus
    progress: Optional[float] = Field(None, ge=0.0, le=100.0)
    message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    error: Optional[str] = None


class ReportResponse(BaseModel):
    """Response model for report retrieval"""

    task_id: str
    report: str
    sources: List[SourceInfo]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    needs_hitl: bool
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReviewResponse(BaseModel):
    """Response model for HITL review"""

    task_id: str
    message: str
    action: ReviewAction
    updated_at: datetime


class ErrorResponse(BaseModel):
    """Error response model"""

    error: str
    detail: Optional[str] = None
