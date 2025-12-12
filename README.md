
## Submission

**Streamlit Dashboard**: http://34.231.244.167:8501/

📹 **Project Video & Documentation**: https://drive.google.com/file/d/1kc15DQe6K-SGFtAdy-NVkq5jvs4O1do6/view?usp=sharing

🔗 **GitHub Repository**: [https://github.com/Team-01-DAMG-7245/ai-research-assistant](https://github.com/Team-01-DAMG-7245/ai-research-assistant)

📚 **Codelabs Documentation**: [View on Codelabs](https://codelabs-preview.appspot.com/?file_id=11Ld5n0n5nFOdt7d9RANhEeWbkU21C62pQ-NjZHFW_to/edit?tab=t.0#0)

# AI Research Assistant

test CD

An AI-powered research assistant that automates the process of discovering, analyzing, and synthesizing research papers from arXiv. Built with multi-agent workflows, vector search, and RAG (Retrieval-Augmented Generation) capabilities.

## Key Capabilities

- 🔍 **Semantic Search**: Find relevant papers using Pinecone vector database
- 🤖 **Multi-Agent Workflow**: Automated research synthesis using LangGraph agents
- 📊 **Citation Validation**: Automatic verification of citations and confidence scoring
- 👤 **Human-in-the-Loop**: Interactive review for quality assurance
- 📄 **Report Generation**: Generate comprehensive research reports in PDF, Markdown, or JSON
- 💰 **Cost Tracking**: Monitor API usage and costs in real-time

---

## Table of Contents

- [Quick Command Reference](#quick-command-reference)
- [Milestones](#milestones)
- [Features](#features)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Multi-Agent Workflow](#multi-agent-workflow)
- [Performance Metrics](#performance-metrics)
- [Architecture Overview](#architecture-overview)
- [API Reference](#api-reference)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

---

## Quick Command Reference

```bash
# Setup
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
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

- ✅ **M5**: Cloud Deployment & Testing (Mostly Complete)
  - ✅ Docker deployment setup and configuration
  - ✅ Comprehensive deployment documentation
    - ✅ EC2 deployment guide (EC2_DEPLOYMENT.md)
    - ✅ Docker deployment guide (DOCKER.md)
  - ✅ Production Docker configuration (docker-compose.prod.yml)
  - ✅ Unit tests for core functions
    - ✅ PDF processing and text extraction (test_m1.py, test_m2.py)
    - ✅ Citation extraction and validation (test_agents.py)
    - ✅ API endpoints and middleware (test_api.py)
    - ✅ OpenAI client and cost tracking (test_openai_client.py)
  - ✅ Integration tests for complete workflow
    - ✅ Full workflow integration tests (test_api.py)
    - ✅ Agent workflow testing (test_agents.py)
  - ✅ Set up GitHub Actions CI/CD pipeline (`.github/workflows/ci.yml`)
  - ✅ Production deployment validation script (`scripts/validate_production_deployment.py`)
  - ✅ Extensive query testing script (`scripts/test_queries.py`)
  
  **To Complete M5:**
  
  1. **GitHub Actions CI/CD**: 
     - Workflow file is ready at `.github/workflows/ci.yml`
     - Push to GitHub to trigger the pipeline automatically
     - Configure GitHub repository secrets if needed (API keys for integration tests)
  
  2. **Production Validation**: 
     ```bash
     # On your EC2 instance or from a machine that can access it
     python scripts/validate_production_deployment.py --api-url http://YOUR-EC2-IP:8000 --streamlit-url http://YOUR-EC2-IP:8501
     ```
  
  3. **Query Testing**: 
     ```bash
     # Test with all 15 sample queries (submit only)
     python scripts/test_queries.py --api-url http://localhost:8000
     
     # Test and wait for completion (takes longer)
     python scripts/test_queries.py --api-url http://localhost:8000 --wait
     
     # Test with fewer queries
     python scripts/test_queries.py --api-url http://localhost:8000 --num-queries 5
     ```

- 📋 **M6**: Final Polish & Documentation (In Progress)
  - ✅ Comprehensive testing and bug fixes
  - ✅ Optimize performance and token usage
  - ✅ Create user documentation and README
  - 📋 Prepare demo video showcasing key features
  - 📋 Write final project report
  - 📋 Presentation preparation and rehearsal

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

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

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

**Simple Commands:**

```bash
# Build services
docker compose build

# Start API and Streamlit
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

**Service Access:**
- API: http://localhost:8000
- Streamlit: http://localhost:8501

See [DOCKER.md](DOCKER.md) for detailed Docker instructions and production deployment.

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

# Production validation and query testing
python scripts/validate_production_deployment.py --api-url http://localhost:8000
python scripts/test_queries.py --api-url http://localhost:8000 --num-queries 5
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

```
ai-research-assistant/
├── src/                    # Core application code
│   ├── agents/            # Multi-agent workflow (Search, Synthesis, Validation, HITL)
│   ├── api/               # FastAPI backend and endpoints
│   ├── pipelines/         # Data ingestion pipelines
│   └── utils/             # Utilities (PDF processing, Pinecone RAG, cost tracking)
├── scripts/               # Utility scripts for ingestion, setup, and testing
├── tests/                 # Test suites
├── data/                  # Local data storage (tasks.db, logs)
├── docs/                  # Documentation
├── docker-compose.yml     # Docker Compose configuration
├── Dockerfile.api         # API service Dockerfile
├── Dockerfile.streamlit   # Streamlit service Dockerfile
└── requirements.txt       # Python dependencies
```

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

## Architecture Overview

The AI Research Assistant uses a multi-agent architecture built with LangGraph:

1. **Data Ingestion** → arXiv papers are fetched, processed, and stored in S3
2. **Vector Indexing** → Text chunks are embedded and indexed in Pinecone
3. **Multi-Agent Workflow** → Search → Synthesis → Validation → HITL Review
4. **API Layer** → FastAPI provides REST endpoints for workflow execution
5. **Web Interface** → Streamlit offers interactive UI for queries and reports

See [docs/AGENTS.md](docs/AGENTS.md) for detailed agent documentation.

## API Reference

**Base URL**: `http://localhost:8000`  
**Interactive Docs**: `http://localhost:8000/docs`

**Rate Limits** (per IP): `/api/v1/research` (5/min), `/api/v1/status` (30/min), `/api/v1/report` (10/min)

**Response Codes**: 200 OK, 201 Created, 400 Bad Request, 404 Not Found, 409 Conflict, 422 Validation Error, 429 Too Many Requests, 500 Internal Server Error

## Troubleshooting

### Port Already in Use
```bash
# Linux/Mac
lsof -i :8000
kill -9 <PID>

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Database Errors
```bash
# Reset database (will be recreated on next API start)
rm data/tasks.db
```

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Environment Variables
```bash
# Verify environment variables are loaded
python -c "import os; print('OPENAI_API_KEY:', bool(os.getenv('OPENAI_API_KEY')))"
```

### API Issues
```bash
# Check API health
curl http://localhost:8000/health

# Check task status
curl "http://localhost:8000/api/v1/status/{task_id}"

# View API logs
docker compose logs api  # If using Docker
# Or check: src/logs/*.log
```

### Docker Issues
See [DOCKER.md](DOCKER.md) troubleshooting section for Docker-specific issues.

### EC2 Deployment Issues
See [EC2_DEPLOYMENT.md](EC2_DEPLOYMENT.md) troubleshooting section for deployment issues.

## Testing the CI/CD Pipeline

The project includes a GitHub Actions CI/CD pipeline that runs automatically on pushes and PRs. See [.github/workflows/TESTING.md](.github/workflows/TESTING.md) for detailed testing instructions.

**Quick test:**
```bash
# Test locally (simulates CI/CD checks)
./scripts/test_ci_locally.sh

# Or push to GitHub to trigger the workflow
git push origin main
# Then check the "Actions" tab on GitHub
```

## Development

### Code Quality
```bash
# Code formatting
pip install black isort
black src/ tests/
isort src/ tests/

# Type checking
pip install mypy
mypy src/

# Linting
pip install flake8 pylint
flake8 src/ tests/
pylint src/
```

### Contributing
1. Create a feature branch
2. Make your changes
3. Run tests: `pytest tests/ -v`
4. Ensure code passes linting and type checking
5. Submit a pull request

## Production Deployment

### AWS EC2 Deployment 🖥️
- **[EC2_DEPLOYMENT.md](EC2_DEPLOYMENT.md)** - Step-by-step guide for deploying on AWS EC2
- ✅ **Pros**: Full control, works with current code (SQLite, local files), no code changes needed
- ⚠️ **Cons**: Requires setup (security groups, VPC, SSH), always running costs
- **Best for**: High traffic, need stateful services, want minimal code changes

### Docker Deployment
- **[DOCKER.md](DOCKER.md)** - Detailed Docker deployment instructions including production configuration

### Manual Deployment

```bash
# Production environment variables
export APP_ENV=production DEBUG=false
export TASK_DB_PATH=/var/lib/ai-research/tasks.db

# Run with Gunicorn
pip install gunicorn
gunicorn src.api.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support & Documentation

- **API Documentation**: Interactive docs available at `http://localhost:8000/docs` when API is running
- **Agent Documentation**: See [docs/AGENTS.md](docs/AGENTS.md) for detailed agent implementation
- **Docker Guide**: See [DOCKER.md](DOCKER.md) for Docker deployment instructions
- **EC2 Deployment**: See [EC2_DEPLOYMENT.md](EC2_DEPLOYMENT.md) for AWS deployment guide
