# AI Research Assistant

AI-powered research assistant for ingesting and processing arXiv papers with vector search capabilities.

## Features

- **arXiv Paper Ingestion**: Automated fetching and processing of research papers
- **PDF Processing**: Text extraction and table extraction
- **Vector Search**: Pinecone integration for semantic search
- **AWS Integration**: S3 storage and processing pipeline
- **Airflow Orchestration**: Automated workflow management

## Quick Start

1. Set up virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   Or use the automated installation script:
   ```bash
   python scripts/install_requirements.py
   ```

3. Set up environment variables (AWS credentials, Pinecone API key)

4. Set up S3 bucket:
   ```bash
   python scripts/setup_s3.py
   ```

5. Ingest papers:
   ```bash
   # With command-line arguments
   python scripts/ingest_arxiv_papers.py --max-papers 500
   
   # Or run interactively (will prompt for number of papers and categories)
   python scripts/ingest_arxiv_papers.py
   ```

## Project Structure

- `src/` - Core application code (pipelines, agents, utils, API)
- `scripts/` - Utility scripts for ingestion and setup
- `tests/` - Test suites
- `pinecone/` - Pinecone configuration and agent documentation

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

#### Interactive Test (with HITL review)

```python
from src.agents.search_agent import search_agent_node
from src.agents.synthesis_agent import synthesis_agent_node
from src.agents.validation_agent import validation_agent_node
from src.agents.hitl_review import hitl_review_node
from src.agents.state import ResearchState

# Initialize state
state: ResearchState = {
    'task_id': 'my_research_task',
    'user_query': 'What are the latest advances in transformer architectures?'
}

# Run pipeline
state = search_agent_node(state)
state = synthesis_agent_node(state)
state = validation_agent_node(state)
state = hitl_review_node(state)  # Will prompt for review if needed

# Access final report
final_report = state.get('final_report', '')
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