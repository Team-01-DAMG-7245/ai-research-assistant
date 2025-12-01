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