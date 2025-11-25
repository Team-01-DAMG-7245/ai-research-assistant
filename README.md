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