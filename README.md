# AI Research Assistant

AI-powered research assistant for ingesting and processing arXiv papers with vector search capabilities.

## Quick Command Reference

```bash
# Setup
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Start API Server
python src/api/main.py

# Start Streamlit Web Interface
streamlit run streamlit_app.py

# Docker (Alternative)
docker compose build                    # Build API + Streamlit
docker compose up -d                    # Start API + Streamlit
docker compose logs -f                  # View logs
docker compose down                     # Stop services

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

- ✅ **M4**: API Development & Streamlit Interface (Complete)
  - ✅ FastAPI backend with async request handling
  - ✅ Background task processing
  - ✅ RESTful API endpoints (/api/research, /api/status, /api/report, /api/review)
  - ✅ HITL review interface via API
  - ✅ CORS and rate limiting middleware
  - ✅ SQLite task management
  - ✅ PDF and Markdown report export formats
  - ✅ Streamlit web interface
    - ✅ Interactive query input
    - ✅ Real-time workflow visualization
    - ✅ Report preview and editing
    - ✅ HITL review interface
    - ✅ Cost dashboard
  - ✅ Docker containerization
    - ✅ Docker Compose setup for local development
    - ✅ Multi-container orchestration (API + Streamlit)
    - ✅ Production Docker configuration

- 📋 **M5**: Cloud Deployment & Testing (In Progress)
  - ✅ Docker deployment setup
  - 📋 Deploy FastAPI and Streamlit on AWS EC2
  - 📋 Configure production environment and environment variables
  - 📋 Write unit tests for core functions (chunking, citation extraction, validation)
  - 📋 Implement integration tests for complete workflow
  - 📋 Set up GitHub Actions CI/CD pipeline
  - 📋 Test with 10-15 sample queries across different topics

- 📋 **M6**: Final Polish & Documentation (Planned)
  - Comprehensive testing and bug fixes
  - Optimize performance and token usage
  - Create user documentation and README
  - Prepare demo video showcasing key features
  - Write final project report
  - Presentation preparation and rehearsal

## Features

- **arXiv Paper Ingestion**: Automated fetching and processing of research papers
- **PDF Processing**: Text extraction and table extraction
- **Vector Search**: Pinecone integration for semantic search
- **AWS Integration**: S3 storage and processing pipeline
- **Multi-Agent RAG Workflow**: LangGraph-based research report generation
- **Citation Validation**: Automated citation checking and quality assurance
- **Human-in-the-Loop (HITL)**: Interactive review for low-confidence reports
- **Cost Tracking**: Comprehensive API usage and cost monitoring

## Quick Start

### 1. Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac: venv\Scripts\activate (Windows)

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env  # Edit with your API keys

# Setup S3 bucket
python scripts/setup_s3.py

# Setup Pinecone index
python scripts/list_pinecone_indexes.py        # List existing indexes
python scripts/create_pinecone_index.py      # Create new index (if needed)
```

**Required environment variables** (in `.env`):
- `OPENAI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `AWS_REGION`

### 2. Data Pipeline

```bash
# Run complete pipeline (recommended)
python scripts/run_full_pipeline.py --max-papers 100

# Or run steps individually:
python scripts/ingest_arxiv_papers.py --max-papers 100  # Step 1: Ingest
python scripts/process_all_paper.py                     # Step 2: Process
python scripts/embed_chunks_to_pinecone.py             # Step 3: Embed
```

### 3. Start API Server

```bash
python src/api/main.py
```

API available at:
- **Base URL**: `http://localhost:8000`
- **Interactive Docs**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

### 3a. Start Streamlit Web Interface (Optional)

```bash
streamlit run streamlit_app.py
```

Streamlit interface available at:
- **Web UI**: `http://localhost:8501`
- Features: Query submission, real-time status tracking, report preview, HITL review, cost dashboard

### 3b. Docker Deployment (Alternative)

**Using Docker Compose Profiles:**

The project uses Docker Compose profiles to selectively start services:

**Default (API + Streamlit):**
```bash
# Build and start API and Streamlit
docker compose build
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

**Service Access:**
- API: http://localhost:8000
- Streamlit: http://localhost:8501

**Quick Reference:**
- `docker compose up` - Starts API and Streamlit
- `docker compose build` - Builds API and Streamlit images

See [DOCKER.md](DOCKER.md) for detailed Docker instructions.

### 4. API Usage

```bash
# Submit research query
curl -X POST "http://localhost:8000/api/v1/research" \
  -H "Content-Type: application/json" \
  -d '{"query": "Your research question", "depth": "standard"}'

# Check status
curl "http://localhost:8000/api/v1/status/{task_id}"

# Get report (JSON, Markdown, or PDF)
curl "http://localhost:8000/api/v1/report/{task_id}?format=json"
curl "http://localhost:8000/api/v1/report/{task_id}?format=pdf" --output report.pdf

# HITL review
curl -X POST "http://localhost:8000/api/v1/review/{task_id}" \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "task_id": "{task_id}"}'
```

### 5. Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Test individual components
pytest tests/test_api.py -v                    # API tests
python test_search_results.py                  # Search agent
python test_synthesis_agent.py                 # Synthesis agent
python test_validation_agent.py                # Validation agent
python test_hitl_review.py                     # Full pipeline test
python scripts/run_research_workflow.py        # Command-line workflow
```

### 6. Additional Commands

```bash
# View logs
cat src/logs/*.log
cat logs/cost_tracking.json

# Health check
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health

# Reset database
rm data/tasks.db  # Will be recreated on next API start
```

## Project Structure

- `src/` - Core application code (pipelines, agents, utils, API)
- `scripts/` - Utility scripts for ingestion and setup
- `tests/` - Test suites
- `pinecone/` - Pinecone configuration and agent documentation

## RAG Utilities

The `src/utils/pinecone_rag.py` module provides:
- `query_to_embedding()`: Converts queries to embeddings
- `semantic_search()`: Searches Pinecone index
- `retrieve_full_chunks()`: Loads full chunk content from S3
- `prepare_context()`: Formats chunks for LLM prompts

## Multi-Agent Workflow

The system uses a LangGraph-based workflow: **Search → Synthesis → Validation → HITL Review**

### Agents

1. **Search Agent**: Expands queries, performs semantic search in Pinecone, returns top 20 results
2. **Synthesis Agent**: Generates 1200-1500 word reports with citations from 20-30 sources
3. **Validation Agent**: Validates citations, calculates confidence scores (0.0-1.0), flags low-confidence reports
4. **HITL Review**: Human review for reports with confidence < 0.7

### Usage

```bash
# Command-line workflow
python scripts/run_research_workflow.py "Your research question"

# Programmatic usage
from src.agents.workflow import compiled_workflow
from src.agents.state import ResearchState
final_state = compiled_workflow.invoke(initial_state)
```

See `src/agents/` for detailed agent implementations.

## Performance Metrics

- **Query Time**: 35-50 seconds (Search: 8-12s, Synthesis: 20-30s, Validation: 3-5s)
- **Cost per Report**: $0.002 - $0.004 (~$0.30-0.40/month for 100 reports)
- **Token Usage**: ~2,000-3,500 tokens per report
- **Citation Accuracy**: 95-100% coverage, <2% invalid citations
- **Quality**: 0.75-0.90 average confidence, 15-25% HITL trigger rate
- **Report Length**: 1,200-1,500 words with 18-25 sources

## Current Status & Next Steps

### M4: API Development & Streamlit Interface (Complete)

**Completed:**
- ✅ FastAPI backend with full REST API
- ✅ Background task processing
- ✅ HITL review via API
- ✅ Report export (PDF, Markdown)
- ✅ Streamlit web interface
  - ✅ Interactive query input
  - ✅ Real-time workflow visualization
  - ✅ Report preview and editing
  - ✅ HITL review interface
  - ✅ Cost dashboard
- ✅ Docker containerization
  - ✅ Docker Compose for local development
  - ✅ Production Docker configuration

### M5: Cloud Deployment & Testing (In Progress)

**Deliverable:** Production-ready system deployed on AWS with automated testing

**Completed:**
- ✅ Docker deployment setup

**In Progress:**
- 📋 Deploy FastAPI and Streamlit on AWS EC2
- 📋 Configure production environment and environment variables
- 📋 Write unit tests for core functions (chunking, citation extraction, validation)
- 📋 Implement integration tests for complete workflow
- 📋 Set up GitHub Actions CI/CD pipeline
- 📋 Test with 10-15 sample queries across different topics

### M6: Final Polish & Documentation (Planned)

**Deliverable:** Complete project ready for submission with documentation and demo

- Comprehensive testing and bug fixes
- Optimize performance and token usage
- Create user documentation and README
- Prepare demo video showcasing key features
- Write final project report
- Presentation preparation and rehearsal

## API Reference

**Base URL**: `http://localhost:8000`  
**Interactive Docs**: `http://localhost:8000/docs`

**Rate Limits** (per IP): `/api/v1/research` (5/min), `/api/v1/status` (30/min), `/api/v1/report` (10/min)

**Response Codes**: 200 OK, 201 Created, 400 Bad Request, 404 Not Found, 409 Conflict, 422 Validation Error, 429 Too Many Requests, 500 Internal Server Error

## Troubleshooting

```bash
# Port already in use
lsof -i :8000  # Linux/Mac: netstat -ano | findstr :8000 (Windows)

# Database errors - reset database
rm data/tasks.db  # Will be recreated on next API start

# Import errors - reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check task status/debug
curl "http://localhost:8000/api/v1/debug/{task_id}"

# Verify environment variables
python -c "import os; print('OPENAI_API_KEY:', bool(os.getenv('OPENAI_API_KEY')))"
```

## Development

```bash
# Code formatting
pip install black isort && black src/ tests/ && isort src/ tests/

# Type checking
pip install mypy && mypy src/

# Linting
pip install flake8 pylint && flake8 src/ tests/ && pylint src/
```

## Production Deployment

See [DOCKER.md](DOCKER.md) for detailed Docker deployment instructions including production setup and EC2 deployment.

### Manual Deployment

```bash
# Production environment variables
export APP_ENV=production DEBUG=false
export TASK_DB_PATH=/var/lib/ai-research/tasks.db

# Run with Gunicorn
pip install gunicorn
gunicorn src.api.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120
```