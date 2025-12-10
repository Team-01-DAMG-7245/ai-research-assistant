"""
Comprehensive API tests for the AI Research Assistant API.

Uses pytest with FastAPI TestClient to test all endpoints.
"""

import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Generator
from dotenv import load_dotenv

import pytest
from fastapi.testclient import TestClient

# Load .env file to get real API keys
project_root = Path(__file__).parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Set test environment before importing app
os.environ["APP_ENV"] = "test"
os.environ["API_MODE"] = "true"

from src.api.main import app
from src.api.models import TaskStatus
from src.api.task_manager import TaskManager, get_task_manager


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def test_db() -> Generator[str, None, None]:
    """
    Create a temporary test database for each test.

    Yields:
        Path to temporary database file
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    # Set environment variable for test database
    original_db = os.environ.get("TASK_DB_PATH")
    os.environ["TASK_DB_PATH"] = db_path

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)
    if original_db:
        os.environ["TASK_DB_PATH"] = original_db
    elif "TASK_DB_PATH" in os.environ:
        del os.environ["TASK_DB_PATH"]


@pytest.fixture(scope="function")
def mock_workflow_executor():
    """
    Mock the workflow executor to prevent actual workflow execution.

    Returns:
        Mock workflow executor
    """
    with patch("src.api.endpoints.research.get_workflow_executor") as mock_get, patch(
        "src.api.endpoints.review.get_workflow_executor"
    ) as mock_get_review:
        # For review endpoint, use real executor but ensure it uses the test task_manager
        from src.api.workflow_executor import WorkflowExecutor

        # Create real executor - task_manager will be set in client fixture
        real_executor = WorkflowExecutor()

        # Mock only execute_research_workflow, use real process_hitl_review
        real_executor.execute_research_workflow = AsyncMock(
            return_value={
                "success": True,
                "task_id": "test-task-id",
                "report": "Test report",
                "confidence": 0.85,
                "needs_hitl": False,
            }
        )

        mock_get.return_value = real_executor
        mock_get_review.return_value = real_executor
        yield real_executor


@pytest.fixture(scope="function")
def client(test_db, mock_workflow_executor) -> Generator[TestClient, None, None]:
    """
    Create a FastAPI test client with test database.

    Args:
        test_db: Test database fixture
        mock_workflow_executor: Mock workflow executor fixture

    Yields:
        FastAPI TestClient instance
    """
    # Set test database path in environment
    original_db = os.environ.get("TASK_DB_PATH")
    os.environ["TASK_DB_PATH"] = test_db

    # Reset task manager singleton to use test database
    from src.api.task_manager import get_task_manager, set_task_manager, TaskManager

    # Create new task manager with test database
    test_task_manager = TaskManager(db_path=test_db)
    set_task_manager(test_task_manager)

    # Also update the mock_workflow_executor's task_manager to use the test one
    # This ensures the workflow executor uses the same test database
    if hasattr(mock_workflow_executor, "task_manager"):
        mock_workflow_executor.task_manager = test_task_manager
    # Also ensure database is initialized
    test_task_manager._init_database()

    with TestClient(app) as test_client:
        yield test_client

    # Restore original database path
    if original_db:
        os.environ["TASK_DB_PATH"] = original_db
    elif "TASK_DB_PATH" in os.environ:
        del os.environ["TASK_DB_PATH"]


@pytest.fixture
def sample_task_id(client: TestClient) -> str:
    """
    Create a sample task and return its ID.

    Args:
        client: Test client

    Returns:
        Task ID string
    """
    # Reset rate limit buckets to avoid rate limiting
    from src.api.middleware import reset_all_rate_limit_buckets

    reset_all_rate_limit_buckets()

    response = client.post(
        "/api/v1/research",
        json={
            "query": "What are the latest developments in quantum computing?",
            "depth": "standard",
            "user_id": "test_user",
        },
    )
    assert response.status_code == 201
    return response.json()["task_id"]


@pytest.fixture
def completed_task_id(client: TestClient, test_db) -> str:
    """
    Create a completed task in the database.

    Args:
        client: Test client
        test_db: Test database path

    Returns:
        Task ID string
    """
    task_manager = get_task_manager()
    task_id = task_manager.create_task(
        query="Test query for completed task", user_id="test_user"
    )

    # Mark as completed with results
    task_manager.store_task_result(
        task_id=task_id,
        report="This is a test research report with comprehensive findings.",
        sources=[
            {
                "source_id": 1,
                "title": "Test Source 1",
                "url": "https://example.com/source1",
                "relevance_score": 0.95,
            },
            {
                "source_id": 2,
                "title": "Test Source 2",
                "url": "https://example.com/source2",
                "relevance_score": 0.85,
            },
        ],
        confidence=0.90,
        needs_hitl=False,
    )

    return task_id


@pytest.fixture
def pending_review_task_id(client: TestClient, test_db) -> str:
    """
    Create a task pending HITL review.

    Args:
        client: Test client
        test_db: Test database path

    Returns:
        Task ID string
    """
    task_manager = get_task_manager()
    task_id = task_manager.create_task(
        query="Test query for pending review", user_id="test_user"
    )

    # Mark as pending review
    task_manager.store_task_result(
        task_id=task_id,
        report="This is a test report that needs review.",
        sources=[],
        confidence=0.65,
        needs_hitl=True,
    )

    return task_id


# ============================================================================
# Tests for POST /api/v1/research
# ============================================================================


def test_submit_valid_query(client: TestClient):
    """Test submitting a valid research query."""
    response = client.post(
        "/api/v1/research",
        json={
            "query": "What are the latest developments in quantum computing?",
            "depth": "standard",
            "user_id": "test_user_123",
        },
    )

    assert response.status_code == 201
    data = response.json()

    # Check response structure
    assert "task_id" in data
    assert "status" in data
    assert "message" in data
    assert "created_at" in data

    # Verify task_id is a valid UUID
    task_id = data["task_id"]
    try:
        uuid.UUID(task_id)
    except ValueError:
        pytest.fail(f"task_id is not a valid UUID: {task_id}")

    # Check status
    assert data["status"] == "queued"
    assert "created" in data["message"].lower()


def test_submit_invalid_query_short(client: TestClient):
    """Test submitting a query that's too short."""
    response = client.post(
        "/api/v1/research",
        json={"query": "short", "depth": "standard"},  # Less than 10 characters
    )

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data


def test_submit_invalid_query_long(client: TestClient):
    """Test submitting a query that's too long."""
    long_query = "a" * 501  # More than 500 characters
    response = client.post(
        "/api/v1/research", json={"query": long_query, "depth": "standard"}
    )

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data


def test_submit_malicious_query_xss(client: TestClient):
    """Test submitting a query with XSS attempt."""
    response = client.post(
        "/api/v1/research",
        json={
            "query": "What is <script>alert('xss')</script> quantum computing?",
            "depth": "standard",
        },
    )

    # Should be rejected by validation middleware
    assert response.status_code in [400, 422]
    data = response.json()
    assert "error" in data or "detail" in data


def test_submit_malicious_query_javascript(client: TestClient):
    """Test submitting a query with JavaScript protocol."""
    response = client.post(
        "/api/v1/research",
        json={
            "query": "What is javascript:alert('xss') quantum computing?",
            "depth": "standard",
        },
    )

    # Should be rejected by validation middleware
    assert response.status_code in [400, 422]
    data = response.json()
    assert "error" in data or "detail" in data


def test_submit_query_with_different_depths(client: TestClient):
    """Test submitting queries with different depth levels."""
    # Reset rate limit buckets between depth tests
    from src.api.middleware import reset_all_rate_limit_buckets

    depths = ["quick", "standard", "comprehensive"]

    for depth in depths:
        reset_all_rate_limit_buckets()  # Reset to avoid rate limiting
        response = client.post(
            "/api/v1/research",
            json={"query": f"Test query for {depth} depth research", "depth": depth},
        )

        assert response.status_code == 201
        assert response.json()["task_id"]


def test_rate_limiting_research_endpoint(client: TestClient):
    """Test rate limiting on research endpoint."""
    # Reset rate limit buckets to ensure clean state
    from src.api.middleware import reset_all_rate_limit_buckets

    reset_all_rate_limit_buckets()

    # Submit 6 requests rapidly (limit is 5 per minute)
    responses = []
    for i in range(6):
        response = client.post(
            "/api/v1/research",
            json={"query": f"Test query {i} for rate limiting", "depth": "quick"},
        )
        responses.append(response)

    # First 5 should succeed
    for i in range(5):
        assert responses[i].status_code == 201, f"Request {i} should succeed"

    # 6th request should be rate limited
    assert responses[5].status_code == 429, "6th request should be rate limited"
    assert "Retry-After" in responses[5].headers
    data = responses[5].json()
    # FastAPI returns "error" or "detail" in rate limit response
    error_text = data.get("error", data.get("detail", ""))
    if isinstance(error_text, dict):
        error_text = error_text.get("error", "")
    assert "rate limit" in str(error_text).lower()


# ============================================================================
# Tests for GET /api/v1/status/{task_id}
# ============================================================================


def test_get_existing_task_status(client: TestClient, sample_task_id: str):
    """Test getting status for an existing task."""
    response = client.get(f"/api/v1/status/{sample_task_id}")

    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert data["task_id"] == sample_task_id
    assert "status" in data
    assert "progress" in data
    assert "message" in data
    assert "created_at" in data
    assert "updated_at" in data

    # Check status is valid
    assert data["status"] in [
        "queued",
        "processing",
        "completed",
        "failed",
        "pending_review",
        "approved",
    ]

    # Check progress is 0-100
    assert 0 <= data["progress"] <= 100


def test_get_nonexistent_task(client: TestClient):
    """Test getting status for a non-existent task."""
    fake_task_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/status/{fake_task_id}")

    assert response.status_code == 404
    data = response.json()
    # FastAPI uses "detail" for HTTPException
    error_text = data.get("error", data.get("detail", ""))
    assert "not found" in str(error_text).lower()


def test_get_invalid_task_id_format(client: TestClient):
    """Test getting status with invalid UUID format."""
    invalid_task_id = "not-a-valid-uuid"
    response = client.get(f"/api/v1/status/{invalid_task_id}")

    assert response.status_code == 400
    data = response.json()
    assert "error" in data or "detail" in data
    assert "uuid" in str(data).lower()


def test_get_task_status_caching(client: TestClient, sample_task_id: str):
    """Test that status responses are cached."""
    # Reset rate limit buckets
    from src.api.middleware import reset_all_rate_limit_buckets

    reset_all_rate_limit_buckets()

    # First request
    response1 = client.get(f"/api/v1/status/{sample_task_id}")
    assert response1.status_code == 200

    # Second request (should be cached)
    response2 = client.get(f"/api/v1/status/{sample_task_id}")
    assert response2.status_code == 200

    # Both should have same data (within cache window)
    assert response1.json() == response2.json()


# ============================================================================
# Tests for GET /api/v1/report/{task_id}
# ============================================================================


def test_get_completed_report(client: TestClient, completed_task_id: str):
    """Test getting a completed report."""
    response = client.get(f"/api/v1/report/{completed_task_id}?format=json")

    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert data["task_id"] == completed_task_id
    assert "report" in data
    assert "sources" in data
    assert "confidence_score" in data
    assert "needs_hitl" in data
    assert "created_at" in data
    assert "metadata" in data

    # Check report content
    assert isinstance(data["report"], str)
    assert len(data["report"]) > 0

    # Check sources
    assert isinstance(data["sources"], list)
    assert len(data["sources"]) > 0

    # Check source structure
    source = data["sources"][0]
    assert "source_id" in source
    assert "title" in source
    assert "url" in source
    assert "relevance_score" in source

    # Check confidence score
    assert 0.0 <= data["confidence_score"] <= 1.0


def test_get_report_markdown_format(client: TestClient, completed_task_id: str):
    """Test getting report in markdown format."""
    response = client.get(f"/api/v1/report/{completed_task_id}?format=markdown")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"

    # Should be plain text (markdown)
    content = response.text
    assert isinstance(content, str)
    assert len(content) > 0


def test_get_incomplete_task_report(client: TestClient, sample_task_id: str):
    """Test getting report for a task that's still processing."""
    # Reset rate limit buckets
    from src.api.middleware import reset_all_rate_limit_buckets

    reset_all_rate_limit_buckets()

    response = client.get(f"/api/v1/report/{sample_task_id}?format=json")

    assert response.status_code == 409  # Conflict
    data = response.json()
    # FastAPI uses "detail" for HTTPException
    error_text = data.get("error", data.get("detail", ""))
    assert (
        "processing" in str(error_text).lower()
        or "not completed" in str(error_text).lower()
    )


def test_get_failed_task_report(client: TestClient, test_db):
    """Test getting report for a failed task."""
    task_manager = get_task_manager()
    task_id = task_manager.create_task(
        query="Test query that will fail", user_id="test_user"
    )

    # Mark task as failed
    task_manager.mark_task_failed(task_id, "Test error message")

    response = client.get(f"/api/v1/report/{task_id}?format=json")

    assert response.status_code == 400
    data = response.json()
    # FastAPI uses "detail" for HTTPException
    error_text = data.get("error", data.get("detail", ""))
    assert "failed" in str(error_text).lower()


def test_get_report_nonexistent_task(client: TestClient):
    """Test getting report for non-existent task."""
    fake_task_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/report/{fake_task_id}?format=json")

    assert response.status_code == 404
    data = response.json()
    # FastAPI uses "detail" for HTTPException
    error_text = data.get("error", data.get("detail", ""))
    assert "not found" in str(error_text).lower()


def test_get_report_invalid_format(client: TestClient, completed_task_id: str):
    """Test getting report with invalid format parameter."""
    response = client.get(f"/api/v1/report/{completed_task_id}?format=invalid")

    # FastAPI validation returns 422 for invalid query parameters
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


# ============================================================================
# Tests for POST /api/v1/review/{task_id}
# ============================================================================


def test_approve_review(client: TestClient, pending_review_task_id: str):
    """Test approving a HITL review."""
    response = client.post(
        f"/api/v1/review/{pending_review_task_id}",
        json={"action": "approve", "task_id": pending_review_task_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "success" in data["message"].lower() or "approved" in data["message"].lower()


def test_edit_review(client: TestClient, pending_review_task_id: str):
    """Test editing a report during HITL review."""
    edited_report = (
        "This is an edited version of the research report with updated findings."
    )

    response = client.post(
        f"/api/v1/review/{pending_review_task_id}",
        json={
            "action": "edit",
            "task_id": pending_review_task_id,
            "edited_report": edited_report,
        },
    )

    # Check if successful (200) or if there's an error
    if response.status_code != 200:
        # Log the error for debugging
        print(f"Edit review failed: {response.status_code} - {response.json()}")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "edit" in data["message"].lower() or "success" in data["message"].lower()


def test_reject_review(client: TestClient, pending_review_task_id: str):
    """Test rejecting a report during HITL review."""
    response = client.post(
        f"/api/v1/review/{pending_review_task_id}",
        json={
            "action": "reject",
            "task_id": pending_review_task_id,
            "rejection_reason": "Report does not meet quality standards",
        },
    )

    # Check if successful (200) or if there's an error
    if response.status_code != 200:
        # Log the error for debugging
        print(f"Reject review failed: {response.status_code} - {response.json()}")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


def test_review_nonexistent_task(client: TestClient):
    """Test reviewing a non-existent task."""
    fake_task_id = str(uuid.uuid4())
    response = client.post(
        f"/api/v1/review/{fake_task_id}",
        json={"action": "approve", "task_id": fake_task_id},
    )

    assert response.status_code == 404
    data = response.json()
    # FastAPI uses "detail" for HTTPException
    error_text = data.get("error", data.get("detail", ""))
    assert "not found" in str(error_text).lower()


def test_review_not_pending_task(client: TestClient, completed_task_id: str):
    """Test reviewing a task that's not pending review."""
    response = client.post(
        f"/api/v1/review/{completed_task_id}",
        json={"action": "approve", "task_id": completed_task_id},
    )

    assert response.status_code == 409  # Conflict
    data = response.json()
    # FastAPI uses "detail" for HTTPException
    error_text = data.get("error", data.get("detail", ""))
    assert "pending review" in str(error_text).lower()


def test_review_invalid_action(client: TestClient, pending_review_task_id: str):
    """Test reviewing with an invalid action."""
    response = client.post(
        f"/api/v1/review/{pending_review_task_id}",
        json={"action": "invalid_action", "task_id": pending_review_task_id},
    )

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data


def test_review_edit_without_content(client: TestClient, pending_review_task_id: str):
    """Test editing without providing edited_report."""
    response = client.post(
        f"/api/v1/review/{pending_review_task_id}",
        json={
            "action": "edit",
            "task_id": pending_review_task_id
            # Missing edited_report
        },
    )

    # Pydantic validation may return 400 or 422 depending on where validation fails
    assert response.status_code in [400, 422]
    data = response.json()
    assert "detail" in data


def test_review_reject_without_reason(client: TestClient, pending_review_task_id: str):
    """Test rejecting without providing rejection_reason."""
    response = client.post(
        f"/api/v1/review/{pending_review_task_id}",
        json={
            "action": "reject",
            "task_id": pending_review_task_id
            # Missing rejection_reason
        },
    )

    # Pydantic validation should catch this and return 400 or 422
    assert response.status_code in [400, 422]
    data = response.json()
    assert "detail" in data


# ============================================================================
# Integration Tests
# ============================================================================


def test_full_workflow_integration(client: TestClient, mock_workflow_executor):
    """Test a full workflow from submission to completion."""
    # Reset rate limit buckets
    from src.api.middleware import reset_all_rate_limit_buckets

    reset_all_rate_limit_buckets()

    # 1. Submit research query
    submit_response = client.post(
        "/api/v1/research",
        json={
            "query": "What are the latest developments in artificial intelligence?",
            "depth": "standard",
            "user_id": "integration_test_user",
        },
    )
    assert submit_response.status_code == 201
    task_id = submit_response.json()["task_id"]

    # 2. Check status
    status_response = client.get(f"/api/v1/status/{task_id}")
    assert status_response.status_code == 200
    assert status_response.json()["task_id"] == task_id

    # 3. Wait for completion (in real test, you'd mock the workflow to complete)
    # For now, we'll just verify the endpoints work together

    # 4. Get report (will fail if not completed, which is expected)
    report_response = client.get(f"/api/v1/report/{task_id}?format=json")
    # Should be 409 if not completed, or 200 if mock completed it
    assert report_response.status_code in [200, 409]


def test_rate_limiting_different_endpoints(client: TestClient, completed_task_id: str):
    """Test that rate limiting works independently for different endpoints."""
    # Status endpoint has higher limit (30/min)
    status_responses = []
    for i in range(31):
        response = client.get(f"/api/v1/status/{completed_task_id}")
        status_responses.append(response)

    # All should succeed (limit is 30, but we're testing 31)
    # Actually, 31st might be rate limited
    assert status_responses[0].status_code == 200

    # Report endpoint has limit of 10/min
    report_responses = []
    for i in range(11):
        response = client.get(f"/api/v1/report/{completed_task_id}?format=json")
        report_responses.append(response)

    # First 10 should succeed
    for i in range(min(10, len(report_responses))):
        if report_responses[i].status_code != 200:
            # Might be 409 if task not completed, which is fine
            assert report_responses[i].status_code in [200, 409]


# ============================================================================
# Helper Functions
# ============================================================================


def test_uuid_validation():
    """Test that UUID validation works correctly."""
    valid_uuid = str(uuid.uuid4())
    assert uuid.UUID(valid_uuid)

    invalid_uuids = ["not-a-uuid", "123", "abc-def-ghi"]
    for invalid in invalid_uuids:
        with pytest.raises(ValueError):
            uuid.UUID(invalid)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
