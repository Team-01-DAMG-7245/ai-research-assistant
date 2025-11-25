# AI Research Assistant

AI-powered research assistant for ingesting and processing arXiv papers with vector search capabilities.

## Features

- **arXiv Paper Ingestion**: Automated fetching and processing of research papers
- **PDF Processing**: Text extraction, layout detection, and table extraction
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

3. Install detectron2 (must be installed AFTER torch/torchvision):
   ```bash
   pip install 'git+https://github.com/facebookresearch/detectron2.git'
   ```

4. Download PubLayNet model:
   - Download from: https://huggingface.co/nlpconnect/PubLayNet-faster_rcnn_R_50_FPN_3x/tree/d4cebcc544ac0c9899748e1023e2f3ccda8ca70e
   - Copy the files into your root directory

5. Set up environment variables (AWS credentials, Pinecone API key)

6. Set up S3 bucket:
   ```bash
   python scripts/setup_s3.py
   ```

7. Ingest papers:
   ```bash
   python scripts/ingest_arxiv_papers.py --max-papers 500
   ```

## Project Structure

- `src/` - Core application code (pipelines, agents, utils, API)
- `scripts/` - Utility scripts for ingestion and setup
- `tests/` - Test suites
- `pinecone/` - Pinecone configuration and agent documentation