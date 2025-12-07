# AI Research Assistant

AI-powered research assistant for ingesting and processing arXiv papers with vector search capabilities.

## Quick Command Reference

```bash
# Setup
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Start API Server
python src/api/main.py

# Run Tests
pytest tests/test_api.py -v

# Submit Research Query
curl -X POST "http://localhost:8000/api/v1/research" -H "Content-Type: application/json" -d '{"query": "Your research question", "depth": "standard"}'

# Check Status
curl "http://localhost:8000/api/v1/status/{task_id}"

# Get Report
curl "http://localhost:8000/api/v1/report/{task_id}?format=json"
```

See [Quick Start](#quick-start) section below for detailed instructions.

## Milestones

- ✅ **M1**: Data Ingestion Pipeline (Complete)
  - arXiv paper fetching and processing
  - S3 bronze/silver layer storage
  - PDF text and table extraction

- ✅ **M2**: Data Pipeline Development (Complete)
  - arXiv API integration for collecting Computer Science papers
  - Text extraction and chunking pipeline using PyMuPDF
  - Parallel processing with Python multiprocessing (10 workers)
  - Simple pipeline orchestrator (see `scripts/run_full_pipeline.py`)
  - S3 storage layers (bronze/silver/gold)
  - Pinecone index setup and management
  - Embedding generation with OpenAI
  - Semantic search capabilities

- ✅ **M3**: Multi-Agent RAG Workflow (Complete)
  - LangGraph-based agent orchestration
  - Search, Synthesis, Validation, and HITL agents
  - Automated report generation with citations
  - Cost tracking and performance metrics

- ✅ **M4**: API Development (Complete - Frontend handled by teammate)
  - FastAPI backend with async request handling
  - Background task processing
  - RESTful API endpoints (/api/research, /api/status, /api/report, /api/review)
  - HITL review interface via API
  - CORS and rate limiting middleware
  - SQLite task management

## Features

- **arXiv Paper Ingestion**: Automated fetching and processing of research papers
- **PDF Processing**: Text extraction and table extraction
- **Vector Search**: Pinecone integration for semantic search
- **AWS Integration**: S3 storage and processing pipeline
- **Pipeline Orchestration**: Simple Python-based pipeline management
- **Multi-Agent RAG Workflow**: LangGraph-based research report generation
- **Citation Validation**: Automated citation checking and quality assurance
- **Human-in-the-Loop (HITL)**: Interactive review for low-confidence reports
- **Cost Tracking**: Comprehensive API usage and cost monitoring

## Quick Start

### 1. Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables Configuration

Create a `.env` file in the project root:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Pinecone Configuration
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX_NAME=your_index_name

# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_bucket_name

# API Configuration (optional)
API_HOST=0.0.0.0
API_PORT=8000
APP_ENV=development
DEBUG=true

# Database Configuration (optional, defaults to data/tasks.db)
TASK_DB_PATH=data/tasks.db
```

### 3. S3 Bucket Setup

```bash
# Set up S3 bucket structure (bronze/silver/gold layers)
python scripts/setup_s3.py
```

### 4. Data Pipeline

You can run the complete pipeline (ingestion → processing → embedding) or individual steps:

```bash
# Run complete pipeline (recommended) - We are using 100 papers to save time and processing power
python scripts/run_full_pipeline.py --max-papers 100

# Or run steps individually:

# Step 1: Ingest papers from arXiv
python scripts/ingest_arxiv_papers.py --max-papers 100

# Step 2: Process PDFs and create chunks (uses 10 workers)
python scripts/process_all_paper.py

# Step 3: Generate embeddings and upload to Pinecone
python scripts/embed_chunks_to_pinecone.py
```

See `scripts/README_PIPELINE.md` for detailed pipeline documentation and scheduling options.

### 5. Run the FastAPI Server

```bash
# Start the API server
python src/api/main.py

# Or using uvicorn directly
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# With custom host/port
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

The API will be available at:
- **API Base URL**: `http://localhost:8000`
- **Interactive Docs**: `http://localhost:8000/docs`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`
- **Health Check**: `http://localhost:8000/health`

### 6. API Endpoints Usage

#### Submit Research Query

```bash
# Using curl
curl -X POST "http://localhost:8000/api/v1/research" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the latest developments in quantum computing?",
    "depth": "standard",
    "user_id": "user_12345"
  }'

# Using Python requests
python -c "
import requests
response = requests.post('http://localhost:8000/api/v1/research', json={
    'query': 'What are the latest developments in quantum computing?',
    'depth': 'standard',
    'user_id': 'user_12345'
})
print(response.json())
"
```

#### Check Task Status

```bash
# Replace {task_id} with actual task ID from submission
curl "http://localhost:8000/api/v1/status/{task_id}"

# Example
curl "http://localhost:8000/api/v1/status/d516660f-b170-4bb0-b26f-b599f51299ae"
```

#### Get Research Report

```bash
# Get report as JSON (default)
curl "http://localhost:8000/api/v1/report/{task_id}?format=json"

# Get report as Markdown
curl "http://localhost:8000/api/v1/report/{task_id}?format=markdown"

# Get report as PDF (returns URL)
curl "http://localhost:8000/api/v1/report/{task_id}?format=pdf"
```

#### Submit HITL Review

```bash
# Approve report
curl -X POST "http://localhost:8000/api/v1/review/{task_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "approve",
    "task_id": "{task_id}"
  }'

# Edit report
curl -X POST "http://localhost:8000/api/v1/review/{task_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "edit",
    "task_id": "{task_id}",
    "edited_report": "Your edited report content here..."
  }'

# Reject report
curl -X POST "http://localhost:8000/api/v1/review/{task_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reject",
    "task_id": "{task_id}",
    "rejection_reason": "Report does not meet quality standards"
  }'
```

#### Debug Endpoint

```bash
# Get detailed task information for debugging
curl "http://localhost:8000/api/v1/debug/{task_id}"
```

### 7. Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all API tests
pytest tests/test_api.py -v

# Run specific test
pytest tests/test_api.py::test_submit_valid_query -v

# Run tests with coverage
pytest tests/test_api.py --cov=src/api --cov-report=html

# Run all tests in tests directory
pytest tests/ -v

# Run tests with output
pytest tests/test_api.py -v -s
```

### 8. Run Research Workflow (Command Line)

```bash
# Run complete workflow with query as argument
python scripts/run_research_workflow.py "What are attention mechanisms in transformers?"

# Run interactively (will prompt for query)
python scripts/run_research_workflow.py

# Run full pipeline demonstration
python scripts/demo_full_pipeline.py
```

### 9. Test Individual Agents

```bash
# Test search agent
python test_search_results.py

# Test synthesis agent
python test_synthesis_agent.py

# Test validation agent
python test_validation_agent.py

# Test HITL review (full pipeline)
python test_hitl_review.py
```

### 10. Database Management

```bash
# Database is automatically created at: data/tasks.db
# To reset database, delete the file:
# On Windows:
del data\tasks.db
# On Linux/Mac:
rm data/tasks.db

# Database will be recreated on next API start
```

### 11. View Logs

```bash
# Agent logs
cat src/logs/search_agent.log
cat src/logs/synthesis_agent.log
cat src/logs/validation_agent.log
cat src/logs/hitl_review.log

# Cost tracking
cat logs/cost_tracking.json

# API logs (if configured)
# Logs are output to console when running the server
```

### 12. Health Check

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check with service status
curl http://localhost:8000/api/v1/health
```

## Complete Setup Workflow

Here's the complete sequence to get everything running:

```bash
# 1. Clone/navigate to project
cd "final project/ai-research-assistant"

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file with your API keys
# (Edit .env file with your credentials)

# 5. Set up S3 bucket
python scripts/setup_s3.py

# 6. Ingest papers (optional, for testing)
python scripts/ingest_arxiv_papers.py --max-papers 100

# 7. Start API server
python src/api/main.py

# 8. In another terminal, test the API
curl -X POST "http://localhost:8000/api/v1/research" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is machine learning?", "depth": "standard"}'

# 9. Run tests
pytest tests/test_api.py -v
```

## Project Structure

- `src/` - Core application code (pipelines, agents, utils, API)
- `scripts/` - Utility scripts for ingestion and setup
- `tests/` - Test suites
- `pinecone/` - Pinecone configuration and agent documentation

## M3: New Capabilities

### Multi-Agent RAG Workflow

The M3 milestone introduces a complete multi-agent system for generating research reports:

- **Semantic Search with Pinecone**: Intelligent query expansion and vector-based retrieval
- **GPT-4o Mini Report Generation**: High-quality, citation-rich research reports (1200-1500 words)
- **Citation Validation**: Automated verification of citation accuracy and coverage
- **HITL Workflow**: Human review integration for quality assurance
- **Cost Tracking**: Real-time monitoring of API usage and costs

### Key Improvements

- **Query Expansion**: Automatically generates 3-5 diverse search queries from user input
- **Source Deduplication**: Intelligent merging of results from multiple queries
- **Context-Aware Synthesis**: Combines 20-30 sources for comprehensive reports
- **Confidence Scoring**: Automated quality assessment (0.0-1.0 scale)
- **Automated Routing**: Conditional workflow based on confidence thresholds

## Using the RAG Utilities

The module `src/utils/pinecone_rag.py` provides helper functions for Retrieval-Augmented Generation (RAG):

- `query_to_embedding(query: str) -> List[float]`: Uses OpenAI `text-embedding-3-small` to convert a query string into a 1536‑dimensional embedding.
- `semantic_search(query: str, top_k: int = 10) -> List[Dict]`: Runs a semantic search against the configured Pinecone index and returns matches with metadata (`text`, `title`, `url`, `doc_id`, `score`).
- `retrieve_full_chunks(chunk_ids: List[str]) -> List[Dict]`: Given chunk IDs from Pinecone, loads the full chunk content and metadata from the S3 silver layer.
- `prepare_context(chunks: List[Dict]) -> str`: Formats chunks into a numbered source context string for LLM prompts.

### Example usage

Make sure the virtual environment is active and required environment variables are set (`OPENAI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, `S3_BUCKET_NAME`), then from the project root:

```bash
python -c "import sys, pathlib; sys.path.append(str(pathlib.Path('.').resolve())); from src.utils import pinecone_rag as rag; print(rag.semantic_search('test query', top_k=3))"
```

## Research Agent Pipeline

The AI Research Assistant uses a multi-agent LangGraph-style workflow to generate comprehensive research reports. The pipeline consists of four main agents that work together:

### Agent Workflow

```
User Query → Search Agent → Synthesis Agent → Validation Agent → HITL Review → Final Report
```

### 1. Search Agent (`src/agents/search_agent.py`)

**Purpose**: Expands user queries into multiple search queries and retrieves relevant sources.

**Function**: `search_agent_node(state: ResearchState) -> ResearchState`

**Features**:
- Uses GPT-4o Mini to generate 3-5 diverse search queries from the user's question
- Performs semantic search in Pinecone for each query (top-10 results per query)
- Deduplicates and ranks results by relevance score
- Returns top 20 unique results

**State Updates**:
- `search_queries`: List of generated search queries
- `search_results`: List of retrieved search results with metadata
- `current_agent`: "search"

**Logs**: `src/logs/search_agent.log`

### 2. Synthesis Agent (`src/agents/synthesis_agent.py`)

**Purpose**: Generates a comprehensive research report from retrieved sources.

**Function**: `synthesis_agent_node(state: ResearchState) -> ResearchState`

**Features**:
- Searches Pinecone for top-10 additional relevant chunks using the user query
- Retrieves full chunk text from S3
- Combines Pinecone chunks with search results (total ~20-30 sources)
- Formats sources using `prepare_context()` with numbered citations
- Generates 1200-1500 word report using GPT-4o Mini
- Includes proper [Source N] citations throughout the report

**State Updates**:
- `report_draft`: Generated research report
- `retrieved_chunks`: List of all sources used
- `source_count`: Number of sources used
- `current_agent`: "synthesis"

**Parameters**:
- Temperature: 0.3
- Max tokens: 2000

**Logs**: `src/logs/synthesis_agent.log`

### 3. Validation Agent (`src/agents/validation_agent.py`)

**Purpose**: Validates report quality and calculates confidence scores.

**Function**: `validation_agent_node(state: ResearchState) -> ResearchState`

**Features**:
- Verifies all [Source N] citations are within valid range
- Uses GPT-4o Mini to analyze report quality
- Checks citation coverage, accuracy, and identifies unsupported claims
- Calculates confidence score with deductions:
  - Base score from LLM (0.0-1.0)
  - -0.3 if invalid citations found
  - -0.2 if 3+ unsupported claims
  - -0.3 if contradictions detected
- Determines if human review is needed (`needs_hitl = confidence_score < 0.7`)

**State Updates**:
- `validation_result`: Detailed validation results (valid, confidence, issues, unsupported_claims)
- `confidence_score`: Final confidence score (0.0-1.0)
- `needs_hitl`: Boolean flag for human review requirement
- `current_agent`: "validation"

**Parameters**:
- Temperature: 0.1
- Max tokens: 800

**Helper Functions**:
- `verify_citations(report: str, num_sources: int) -> List[int]`: Returns list of invalid citation numbers

**Logs**: `src/logs/validation_agent.log`

### 4. HITL Review Agent (`src/agents/hitl_review.py`)

**Purpose**: Provides human-in-the-loop review for reports that need validation.

**Function**: `hitl_review_node(state: ResearchState) -> ResearchState`

**Features**:
- Skips review if `needs_hitl = False` (auto-approves)
- If `needs_hitl = True`:
  - Displays report draft preview (first 1000 characters)
  - Shows validation information (confidence score, issues, invalid citations)
  - Prompts user for action: [A]pprove, [E]dit, or [R]eject
  - Updates state based on user decision

**User Actions**:
- **Approve**: Sets `final_report = report_draft`
- **Edit**: Allows user to provide edited version, sets `final_report = edited_report`
- **Reject**: Sets `error` flag for regeneration, `final_report = ""`

**State Updates**:
- `final_report`: Approved/edited report (or empty if rejected)
- `error`: Error message if rejected (or None)
- `current_agent`: "hitl_review"

**Logs**: `src/logs/hitl_review.log`

**Note**: Currently uses console-based interface. Streamlit UI will be added in M4.

### Running the Full Pipeline

#### Command-Line Interface (Recommended)

Run the complete workflow with a single command:

```bash
# With query as argument
python scripts/run_research_workflow.py "What are attention mechanisms in transformers?"

# Or run interactively (will prompt for query)
python scripts/run_research_workflow.py
```

The script will:
- Generate search queries and retrieve sources
- Synthesize a comprehensive report
- Validate citations and calculate confidence
- Prompt for human review if needed (confidence < 0.7)
- Save final report to S3 gold/ layer
- Display execution metrics and costs

#### Full Pipeline Demonstration

Run the interactive demo to see all pipeline stages:

```bash
python scripts/demo_full_pipeline.py
```

This demo script shows:
- Sample papers from S3 bronze/ layer
- Processed chunks from S3 silver/ layer
- Pinecone search results
- Each agent's output with formatted tables
- Final report generation
- Complete execution metrics

#### Programmatic Usage

```python
from src.agents.workflow import compiled_workflow
from src.agents.state import ResearchState
import uuid

# Initialize state
initial_state: ResearchState = {
    "task_id": str(uuid.uuid4()),
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

# Run complete workflow
final_state = compiled_workflow.invoke(initial_state)

# Access results
print(f"Final Report: {final_state['final_report']}")
print(f"Confidence Score: {final_state['confidence_score']:.2f}")
print(f"Sources Used: {final_state.get('source_count', 0)}")
```

#### Using Test Scripts

**Full pipeline test** (includes HITL review):
```bash
python test_hitl_review.py
```

**Synthesis and validation only**:
```bash
python test_synthesis_agent.py
python test_validation_agent.py
```

**Search results inspection**:
```bash
python test_search_results.py
```

### State Structure

The `ResearchState` TypedDict contains:

- `task_id`: Unique identifier for the research task
- `user_query`: Original user question
- `search_queries`: Generated search queries
- `search_results`: Raw search results from Pinecone
- `retrieved_chunks`: Full chunk data with metadata
- `report_draft`: Generated research report
- `validation_result`: Validation analysis results
- `confidence_score`: Confidence score (0.0-1.0)
- `needs_hitl`: Whether human review is needed
- `final_report`: Final approved/edited report
- `error`: Error message if any
- `current_agent`: Current agent identifier

### Environment Variables

Required environment variables:

```bash
OPENAI_API_KEY=your_openai_key
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=your_index_name
S3_BUCKET_NAME=your_bucket_name
AWS_REGION=us-east-1
```

### Logging

All agents log to both console and file:
- Search Agent: `src/logs/search_agent.log`
- Synthesis Agent: `src/logs/synthesis_agent.log`
- Validation Agent: `src/logs/validation_agent.log`
- HITL Review: `src/logs/hitl_review.log`

Logs include:
- Agent execution status
- Token usage and costs
- Search queries and results
- Validation issues and confidence scores
- Review decisions

## Sample Output

### Generated Report Example

```
# Research Report: Attention Mechanisms in Transformers

## Introduction

Attention mechanisms have revolutionized natural language processing and 
deep learning architectures. This report examines the fundamental principles, 
recent advances, and applications of attention mechanisms in transformer models.

## Core Concepts

The attention mechanism allows models to focus on relevant parts of the input 
sequence when processing each element [Source 1]. The scaled dot-product 
attention, introduced in the original Transformer paper, computes attention 
scores as:

Attention(Q, K, V) = softmax(QK^T / √d_k) V

where Q, K, and V represent queries, keys, and values respectively [Source 2].

## Recent Advances

Recent research has explored efficient attention variants to reduce computational 
complexity. Sparse attention patterns, such as those in Longformer and BigBird, 
enable processing of longer sequences [Source 3]. Linear attention mechanisms 
have been proposed to achieve O(n) complexity instead of O(n²) [Source 4].

## Applications

Transformer-based models with attention mechanisms have achieved state-of-the-art 
results in various tasks including machine translation, text generation, and 
computer vision [Source 5]. Vision Transformers (ViTs) demonstrate that attention 
can effectively process image patches [Source 6].

## Conclusion

Attention mechanisms remain a cornerstone of modern deep learning architectures, 
with ongoing research focused on efficiency, interpretability, and scalability.

---

**Sources Used**: 20
**Confidence Score**: 0.85
**Word Count**: 1,247
```

### Execution Metrics Example

```
Execution Summary:
  Task ID: demo_20241201_125233
  Execution Time: 45.32 seconds
  Report Word Count: 1,247
  Sources Used: 20
  Confidence Score: 0.85
  Task Cost: $0.002341
  Total Cost (all tasks): $0.015623
  S3 Location: s3://my-bucket/gold/reports/demo_20241201_125233.json

Cost Breakdown by Operation:
  query_expansion: $0.000123
  embedding: $0.000045
  synthesis: $0.001892
  validation: $0.000281
```

## M3 Performance Metrics

Based on testing with various research queries:

### Average Query Performance

- **Average Query Time**: 35-50 seconds
  - Search Agent: 8-12 seconds
  - Synthesis Agent: 20-30 seconds
  - Validation Agent: 3-5 seconds
  - HITL Review: 0-5 seconds (if needed)

### Token Usage

- **Per Query Average**:
  - Query Expansion: 50-100 tokens
  - Embeddings: 7-15 tokens per query
  - Synthesis: 1,500-2,500 tokens
  - Validation: 400-800 tokens
  - **Total per Report**: ~2,000-3,500 tokens

### Cost Analysis

- **Cost per Report**: $0.002 - $0.004
  - Query Expansion: $0.0001 - $0.0002
  - Embeddings: $0.00001 - $0.00005
  - Synthesis: $0.0015 - $0.003
  - Validation: $0.0002 - $0.0005

- **Monthly Estimate** (100 reports): ~$0.30 - $0.40

### Citation Accuracy

- **Citation Coverage**: 95-100% of claims supported
- **Invalid Citations**: < 2% of total citations
- **Missing Citations**: < 5% of claims requiring support
- **Average Sources per Report**: 18-25 sources

### Quality Metrics

- **Average Confidence Score**: 0.75-0.90
- **HITL Trigger Rate**: 15-25% of reports (confidence < 0.7)
- **Report Length**: 1,200-1,500 words (target range)
- **Source Diversity**: 15-20 unique papers per report

## Next Steps: M4 Milestone

The next milestone focuses on user interface and production deployment:

### Planned Features

1. **Streamlit Web Interface**
   - Interactive query input
   - Real-time workflow visualization
   - Report preview and editing
   - HITL review interface
   - Cost dashboard

2. **Production Deployment**
   - Docker containerization
   - AWS deployment (ECS/Lambda)
   - API endpoint creation
   - Monitoring and alerting
   - Auto-scaling configuration

3. **Enhanced Features**
   - Report templates and customization
   - Export formats (PDF, Markdown, HTML)
   - Batch processing capabilities
   - User authentication and history
   - Advanced filtering and search

4. **Performance Optimization**
   - Caching strategies
   - Parallel processing
   - Response time improvements
   - Cost optimization

## API Reference

### Base URL
```
http://localhost:8000
```

### Authentication
Currently, the API does not require authentication. Rate limiting is applied per IP address.

### Rate Limits
- `/api/v1/research`: 5 requests/minute per IP
- `/api/v1/status`: 30 requests/minute per IP
- `/api/v1/report`: 10 requests/minute per IP
- Other endpoints: 60 requests/minute per IP

### Common Response Codes
- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request or task failed
- `404 Not Found`: Resource not found
- `409 Conflict`: Task not in required state
- `422 Validation Error`: Request validation failed
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Troubleshooting

### API Server Won't Start

```bash
# Check if port 8000 is already in use
# On Windows:
netstat -ano | findstr :8000
# On Linux/Mac:
lsof -i :8000

# Use a different port
uvicorn src.api.main:app --port 8001
```

### Database Errors

```bash
# Delete and recreate database
rm data/tasks.db  # Linux/Mac
del data\tasks.db  # Windows

# Database will be recreated on next API start
```

### Import Errors

```bash
# Make sure you're in the project root directory
cd "final project/ai-research-assistant"

# Verify Python path
python -c "import sys; print(sys.path)"

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Workflow Not Completing

```bash
# Check server logs for errors
# Look for error messages in the terminal where the server is running

# Check task status
curl "http://localhost:8000/api/v1/debug/{task_id}"

# Verify environment variables are set
python -c "import os; print('OPENAI_API_KEY:', bool(os.getenv('OPENAI_API_KEY')))"
```

### Rate Limiting Issues

```bash
# Check rate limit headers in response
curl -v "http://localhost:8000/api/v1/research" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "test query"}'

# Look for X-RateLimit-Limit and X-RateLimit-Remaining headers
```

## Development Commands

### Code Formatting

```bash
# Install formatting tools
pip install black isort

# Format code
black src/ tests/
isort src/ tests/
```

### Type Checking

```bash
# Install type checker
pip install mypy

# Run type checking
mypy src/
```

### Linting

```bash
# Install linter
pip install flake8 pylint

# Run linting
flake8 src/ tests/
pylint src/
```

## Production Deployment

### Environment Variables for Production

```bash
# Set production environment
export APP_ENV=production
export DEBUG=false

# Use production database
export TASK_DB_PATH=/var/lib/ai-research/tasks.db

# Configure CORS for production domain
# Edit src/api/middleware.py get_cors_middleware_config()
```

### Running with Gunicorn (Production)

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn src.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120
```

### Docker Deployment (Future)

```bash
# Build Docker image (when Dockerfile is created)
docker build -t ai-research-assistant .

# Run container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e PINECONE_API_KEY=your_key \
  ai-research-assistant
```