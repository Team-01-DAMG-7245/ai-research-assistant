"""
Pytest tests for research agent nodes.

Tests for search_agent, synthesis_agent, validation_agent, and workflow integration.
"""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.state import ResearchState
from src.agents.search_agent import search_agent_node
from src.agents.synthesis_agent import synthesis_agent_node
from src.agents.validation_agent import validation_agent_node, verify_citations
from src.agents.workflow import compiled_workflow


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def sample_state() -> ResearchState:
    """Create a sample initial state for testing."""
    return {
        "task_id": "test_task_123",
        "user_query": "What are the latest advances in transformer architectures?",
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


@pytest.fixture
def mock_openai_search_response() -> Dict[str, Any]:
    """Mock OpenAI response for search query generation."""
    return {
        "content": json.dumps(
            {
                "queries": [
                    "overview of transformer architectures",
                    "recent transformer model improvements",
                    "transformer architecture innovations 2023",
                    "comparison of transformer models",
                    "applications of transformer architectures",
                ]
            }
        ),
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        "cost": 0.0001,
    }


@pytest.fixture
def mock_pinecone_results() -> List[Dict[str, Any]]:
    """Mock Pinecone search results."""
    return [
        {
            "id": "chunk-1",
            "chunk_id": "doc1-chunk1",
            "doc_id": "doc1",
            "score": 0.85,
            "text": "Transformer architectures use self-attention mechanisms...",
            "title": "Paper 1",
            "url": "https://example.com/paper1",
            "metadata": {
                "chunk_id": "doc1-chunk1",
                "doc_id": "doc1",
                "text": "Transformer architectures use self-attention mechanisms...",
                "title": "Paper 1",
            },
        },
        {
            "id": "chunk-2",
            "chunk_id": "doc2-chunk1",
            "doc_id": "doc2",
            "score": 0.82,
            "text": "Recent improvements in transformers include...",
            "title": "Paper 2",
            "url": "https://example.com/paper2",
            "metadata": {
                "chunk_id": "doc2-chunk1",
                "doc_id": "doc2",
                "text": "Recent improvements in transformers include...",
                "title": "Paper 2",
            },
        },
        {
            "id": "chunk-3",
            "chunk_id": "doc3-chunk1",
            "doc_id": "doc3",
            "score": 0.78,
            "text": "The attention mechanism allows models to...",
            "title": "Paper 3",
            "url": "https://example.com/paper3",
            "metadata": {
                "chunk_id": "doc3-chunk1",
                "doc_id": "doc3",
                "text": "The attention mechanism allows models to...",
                "title": "Paper 3",
            },
        },
    ]


@pytest.fixture
def mock_s3_chunks() -> List[Dict[str, Any]]:
    """Mock S3 chunk data."""
    return [
        {
            "chunk_id": "doc1-chunk1",
            "doc_id": "doc1",
            "text": "Transformer architectures use self-attention mechanisms to process sequences efficiently.",
            "title": "Paper 1",
            "url": "https://example.com/paper1",
        },
        {
            "chunk_id": "doc2-chunk1",
            "doc_id": "doc2",
            "text": "Recent improvements in transformers include better positional encodings and efficient attention variants.",
            "title": "Paper 2",
            "url": "https://example.com/paper2",
        },
    ]


@pytest.fixture
def mock_synthesis_response() -> Dict[str, Any]:
    """Mock OpenAI response for synthesis agent."""
    report_text = """# Research Report

## Overview
This report discusses transformer architectures [Source 1] and their recent improvements [Source 2].

## Key Findings
1. Transformers use attention mechanisms [Source 1]
2. Recent improvements include better encodings [Source 2]
3. These models have shown significant performance gains [Source 1]

## Analysis
The findings suggest that transformer architectures continue to evolve [Source 2].

## Conclusion
In summary, transformers represent a significant advancement [Source 1]."""

    return {
        "content": report_text,
        "usage": {
            "prompt_tokens": 5000,
            "completion_tokens": 1200,
            "total_tokens": 6200,
        },
        "cost": 0.05,
    }


@pytest.fixture
def mock_validation_response() -> Dict[str, Any]:
    """Mock OpenAI response for validation agent."""
    return {
        "content": json.dumps(
            {
                "valid": True,
                "confidence": 0.85,
                "issues": [],
                "citation_coverage": 0.95,
                "unsupported_claims": [],
            }
        ),
        "usage": {
            "prompt_tokens": 6000,
            "completion_tokens": 100,
            "total_tokens": 6100,
        },
        "cost": 0.04,
    }


# ============================================================================
# SEARCH AGENT TESTS
# ============================================================================


@patch("src.agents.search_agent.OpenAIClient")
@patch("src.agents.search_agent.semantic_search")
def test_search_agent(
    mock_semantic_search,
    mock_openai_client,
    sample_state: ResearchState,
    mock_openai_search_response: Dict[str, Any],
    mock_pinecone_results: List[Dict[str, Any]],
):
    """Test search_agent_node with mocked dependencies."""
    # Setup mocks
    mock_client_instance = Mock()
    mock_client_instance.chat_completion.return_value = mock_openai_search_response
    mock_openai_client.return_value = mock_client_instance

    # Mock semantic_search to return results for each query
    mock_semantic_search.return_value = mock_pinecone_results[
        :2
    ]  # Return 2 results per query

    # Run search agent
    result_state = search_agent_node(sample_state)

    # Verify results
    assert (
        result_state["current_agent"] == "search_agent"
    )  # search_agent sets this value
    assert "search_queries" in result_state
    assert len(result_state["search_queries"]) >= 3
    assert len(result_state["search_queries"]) <= 5
    assert "search_results" in result_state
    assert len(result_state["search_results"]) > 0
    assert result_state.get("error") is None

    # Verify OpenAI was called
    mock_client_instance.chat_completion.assert_called_once()

    # Verify semantic_search was called for each query
    assert mock_semantic_search.call_count == len(result_state["search_queries"])


@patch("src.agents.search_agent.OpenAIClient")
@patch("src.agents.search_agent.semantic_search")
def test_search_agent_empty_query(
    mock_semantic_search, mock_openai_client, sample_state: ResearchState
):
    """Test search_agent_node with empty user_query."""
    sample_state["user_query"] = ""

    result_state = search_agent_node(sample_state)

    assert result_state.get("error") is not None
    assert (
        "search_queries" not in result_state
        or len(result_state.get("search_queries", [])) == 0
    )


# ============================================================================
# SYNTHESIS AGENT TESTS
# ============================================================================


@patch("src.agents.synthesis_agent.OpenAIClient")
@patch("src.agents.synthesis_agent.retrieve_full_chunks")
@patch("src.agents.synthesis_agent.semantic_search")
def test_synthesis_agent(
    mock_semantic_search,
    mock_retrieve_chunks,
    mock_openai_client,
    sample_state: ResearchState,
    mock_pinecone_results: List[Dict[str, Any]],
    mock_s3_chunks: List[Dict[str, Any]],
    mock_synthesis_response: Dict[str, Any],
):
    """Test synthesis_agent_node with mocked dependencies."""
    # Setup state with search results
    sample_state["search_results"] = mock_pinecone_results

    # Setup mocks
    mock_semantic_search.return_value = mock_pinecone_results
    mock_retrieve_chunks.return_value = mock_s3_chunks

    mock_client_instance = Mock()
    mock_client_instance.chat_completion.return_value = mock_synthesis_response
    mock_openai_client.return_value = mock_client_instance

    # Run synthesis agent
    result_state = synthesis_agent_node(sample_state)

    # Verify results
    assert result_state["current_agent"] == "synthesis"
    assert "report_draft" in result_state
    assert len(result_state["report_draft"]) > 0

    # Check report contains citations
    report = result_state["report_draft"]
    assert "[Source" in report or "[source" in report.lower()

    # Check word count (should be 1000+ words for full report, but our mock is shorter)
    word_count = len(report.split())
    assert word_count > 0

    # Verify sources
    assert "retrieved_chunks" in result_state
    assert "source_count" in result_state
    assert result_state["source_count"] > 0
    assert result_state.get("error") is None

    # Verify OpenAI was called
    mock_client_instance.chat_completion.assert_called_once()


@patch("src.agents.synthesis_agent.OpenAIClient")
@patch("src.agents.synthesis_agent.retrieve_full_chunks")
@patch("src.agents.synthesis_agent.semantic_search")
def test_synthesis_agent_no_sources(
    mock_semantic_search,
    mock_retrieve_chunks,
    mock_openai_client,
    sample_state: ResearchState,
):
    """Test synthesis_agent_node with no sources."""
    sample_state["search_results"] = []
    mock_semantic_search.return_value = []
    mock_retrieve_chunks.return_value = []

    result_state = synthesis_agent_node(sample_state)

    assert result_state.get("error") is not None
    assert result_state.get("report_draft", "") == ""


# ============================================================================
# VALIDATION AGENT TESTS
# ============================================================================


def test_verify_citations():
    """Test verify_citations helper function."""
    report = (
        "This is a claim [Source 1]. Another claim [Source 2]. Invalid [Source 10]."
    )
    num_sources = 5

    invalid = verify_citations(report, num_sources)

    assert 10 in invalid
    assert 1 not in invalid
    assert 2 not in invalid


def test_verify_citations_all_valid():
    """Test verify_citations with all valid citations."""
    report = "Claim 1 [Source 1]. Claim 2 [Source 2]. Claim 3 [Source 3]."
    num_sources = 5

    invalid = verify_citations(report, num_sources)

    assert len(invalid) == 0


@patch("src.agents.validation_agent.OpenAIClient")
def test_validation_agent_high_confidence(
    mock_openai_client,
    sample_state: ResearchState,
    mock_validation_response: Dict[str, Any],
):
    """Test validation_agent_node with high confidence report."""
    # Setup state with report
    sample_state[
        "report_draft"
    ] = "This is a well-cited report [Source 1] [Source 2] [Source 3]."
    sample_state["retrieved_chunks"] = [
        {"text": "Content 1", "doc_id": "doc1"},
        {"text": "Content 2", "doc_id": "doc2"},
        {"text": "Content 3", "doc_id": "doc3"},
    ]

    # Mock high confidence response
    mock_validation_response["content"] = json.dumps(
        {
            "valid": True,
            "confidence": 0.90,
            "issues": [],
            "citation_coverage": 1.0,
            "unsupported_claims": [],
        }
    )

    mock_client_instance = Mock()
    mock_client_instance.chat_completion.return_value = mock_validation_response
    mock_openai_client.return_value = mock_client_instance

    # Run validation agent
    result_state = validation_agent_node(sample_state)

    # Verify results
    assert result_state["current_agent"] == "validation"
    assert "validation_result" in result_state
    assert "confidence_score" in result_state
    assert result_state["confidence_score"] > 0.7
    assert result_state["needs_hitl"] is False
    assert result_state.get("error") is None


@patch("src.agents.validation_agent.OpenAIClient")
def test_validation_agent_low_confidence(
    mock_openai_client,
    sample_state: ResearchState,
    mock_validation_response: Dict[str, Any],
):
    """Test validation_agent_node with low confidence report."""
    # Setup state with report
    sample_state["report_draft"] = "This report has some claims without citations."
    sample_state["retrieved_chunks"] = [{"text": "Content 1", "doc_id": "doc1"}]

    # Mock low confidence response
    mock_validation_response["content"] = json.dumps(
        {
            "valid": False,
            "confidence": 0.60,
            "issues": ["Missing citations", "Unsupported claims"],
            "citation_coverage": 0.50,
            "unsupported_claims": ["Claim 1", "Claim 2", "Claim 3"],
        }
    )

    mock_client_instance = Mock()
    mock_client_instance.chat_completion.return_value = mock_validation_response
    mock_openai_client.return_value = mock_client_instance

    # Run validation agent
    result_state = validation_agent_node(sample_state)

    # Verify results
    assert result_state["current_agent"] == "validation"
    assert "confidence_score" in result_state
    assert result_state["confidence_score"] < 0.7
    assert result_state["needs_hitl"] is True
    assert len(result_state["validation_result"].get("unsupported_claims", [])) >= 3


@patch("src.agents.validation_agent.OpenAIClient")
def test_validation_agent_with_invalid_citations(
    mock_openai_client,
    sample_state: ResearchState,
    mock_validation_response: Dict[str, Any],
):
    """Test validation_agent_node with invalid citations."""
    # Setup state with report containing invalid citations
    sample_state["report_draft"] = "Claim [Source 1]. Invalid [Source 10]."
    sample_state["retrieved_chunks"] = [{"text": "Content 1", "doc_id": "doc1"}]

    mock_validation_response["content"] = json.dumps(
        {
            "valid": False,
            "confidence": 0.80,
            "issues": ["Invalid citations"],
            "citation_coverage": 0.90,
            "unsupported_claims": [],
        }
    )

    mock_client_instance = Mock()
    mock_client_instance.chat_completion.return_value = mock_validation_response
    mock_openai_client.return_value = mock_client_instance

    # Run validation agent
    result_state = validation_agent_node(sample_state)

    # Verify confidence is reduced due to invalid citations
    assert result_state["confidence_score"] < 0.80  # Should be reduced by 0.3
    assert len(result_state["validation_result"].get("invalid_citations", [])) > 0


# ============================================================================
# WORKFLOW INTEGRATION TESTS
# ============================================================================


@patch("src.agents.search_agent.OpenAIClient")
@patch("src.agents.search_agent.semantic_search")
@patch("src.agents.synthesis_agent.OpenAIClient")
@patch("src.agents.synthesis_agent.retrieve_full_chunks")
@patch("src.agents.synthesis_agent.semantic_search")
@patch("src.agents.validation_agent.OpenAIClient")
def test_workflow_integration(
    mock_val_openai,
    mock_syn_semantic_search,
    mock_syn_retrieve_chunks,
    mock_syn_openai,
    mock_search_semantic_search,
    mock_search_openai,
    sample_state: ResearchState,
    mock_openai_search_response: Dict[str, Any],
    mock_pinecone_results: List[Dict[str, Any]],
    mock_s3_chunks: List[Dict[str, Any]],
    mock_synthesis_response: Dict[str, Any],
    mock_validation_response: Dict[str, Any],
):
    """Test full workflow integration with all agents."""
    # Setup search agent mocks
    mock_search_client = Mock()
    mock_search_client.chat_completion.return_value = mock_openai_search_response
    mock_search_openai.return_value = mock_search_client
    mock_search_semantic_search.return_value = mock_pinecone_results[:2]

    # Setup synthesis agent mocks
    mock_syn_semantic_search.return_value = mock_pinecone_results
    mock_syn_retrieve_chunks.return_value = mock_s3_chunks
    mock_syn_client = Mock()
    mock_syn_client.chat_completion.return_value = mock_synthesis_response
    mock_syn_openai.return_value = mock_syn_client

    # Setup validation agent mocks
    mock_val_client = Mock()
    mock_val_client.chat_completion.return_value = mock_validation_response
    mock_val_openai.return_value = mock_val_client

    # Run workflow
    final_state = compiled_workflow.invoke(sample_state)

    # Verify workflow completed
    assert final_state is not None
    assert "search_queries" in final_state
    assert "search_results" in final_state
    assert "report_draft" in final_state
    assert "validation_result" in final_state
    assert "confidence_score" in final_state

    # Verify state transitions
    assert len(final_state["search_queries"]) > 0
    assert len(final_state["search_results"]) > 0
    assert len(final_state["report_draft"]) > 0
    assert final_state["confidence_score"] >= 0.0
    assert final_state["confidence_score"] <= 1.0

    # Verify final_report is set (either from HITL or set_final_report node)
    # Note: This depends on needs_hitl flag
    if not final_state.get("needs_hitl", False):
        assert "final_report" in final_state
        assert len(final_state.get("final_report", "")) > 0


@patch("src.agents.search_agent.OpenAIClient")
@patch("src.agents.search_agent.semantic_search")
def test_workflow_error_handling(
    mock_semantic_search, mock_openai_client, sample_state: ResearchState
):
    """Test workflow error handling when search fails."""
    # Mock OpenAI to raise an error
    mock_client = Mock()
    mock_client.chat_completion.side_effect = Exception("API Error")
    mock_openai_client.return_value = mock_client

    # Run workflow - should handle error gracefully
    final_state = compiled_workflow.invoke(sample_state)

    # Verify error is captured
    assert final_state is not None
    # Error should be in state or handled by the agent
    assert (
        final_state.get("error") is not None
        or len(final_state.get("search_results", [])) == 0
    )


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================


def test_verify_citations_empty_report():
    """Test verify_citations with empty report."""
    invalid = verify_citations("", 5)
    assert len(invalid) == 0


def test_verify_citations_no_citations():
    """Test verify_citations with no citations."""
    report = "This report has no citations at all."
    invalid = verify_citations(report, 5)
    assert len(invalid) == 0


def test_verify_citations_out_of_range():
    """Test verify_citations with citations out of range."""
    report = "Claim [Source 0]. Another [Source 6]."
    num_sources = 5

    invalid = verify_citations(report, num_sources)

    assert 0 in invalid  # Below range
    assert 6 in invalid  # Above range
