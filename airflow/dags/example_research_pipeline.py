"""
Example DAG for AI Research Assistant Pipeline

This DAG demonstrates how to orchestrate the research pipeline using Airflow.
It includes tasks for:
1. Data ingestion from arXiv
2. PDF processing and chunking
3. Embedding generation and Pinecone indexing
4. Research report generation workflow
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Default arguments
default_args = {
    'owner': 'research-team',
    'depends_on_past': False,
    'email': ['airflow@example.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# DAG definition
dag = DAG(
    'research_pipeline',
    default_args=default_args,
    description='AI Research Assistant Data Pipeline',
    schedule_interval=timedelta(days=1),  # Run daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['research', 'ingestion', 'pipeline'],
)

# Task 1: Ingest arXiv papers
ingest_papers = BashOperator(
    task_id='ingest_arxiv_papers',
    bash_command='cd /opt/airflow && python scripts/ingest_arxiv_papers.py --max-papers 100',
    dag=dag,
)

# Task 2: Process PDFs and extract text
process_pdfs = BashOperator(
    task_id='process_pdfs',
    bash_command='cd /opt/airflow && python scripts/process_all_paper.py',
    dag=dag,
)

# Task 3: Generate embeddings and index in Pinecone
embed_and_index = BashOperator(
    task_id='embed_and_index',
    bash_command='cd /opt/airflow && python scripts/embed_chunks_to_pinecone.py',
    dag=dag,
)

# Task 4: Run full pipeline (alternative single task)
full_pipeline = BashOperator(
    task_id='run_full_pipeline',
    bash_command='cd /opt/airflow && python scripts/run_full_pipeline.py --max-papers 100',
    dag=dag,
)

# Define task dependencies
# Option 1: Sequential pipeline
ingest_papers >> process_pdfs >> embed_and_index

# Option 2: Use full pipeline (uncomment to use instead)
# full_pipeline
