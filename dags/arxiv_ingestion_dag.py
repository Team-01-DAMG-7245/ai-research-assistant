"""
arXiv Paper Ingestion DAG

This DAG orchestrates the complete data ingestion pipeline:
1. Ingest papers from arXiv
2. Process PDFs into chunks
3. Generate embeddings and upload to Pinecone

Schedule: Daily at 2 AM UTC (configurable)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dags.airflow_helpers import (
    run_ingestion_task,
    run_processing_task,
    run_embedding_task,
    check_dependencies_task
)

# Default arguments for all tasks
default_args = {
    'owner': 'ai-research',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': days_ago(1),
}

# DAG definition
dag = DAG(
    'arxiv_daily_ingestion',
    default_args=default_args,
    description='Daily arXiv paper ingestion pipeline: ingest → process → embed',
    schedule_interval='0 2 * * *',  # Daily at 2 AM UTC
    catchup=False,  # Don't backfill past runs
    tags=['arxiv', 'ingestion', 'pipeline'],
    max_active_runs=1,  # Only one run at a time
)

# Task 0: Check dependencies (verify environment variables and connections)
check_deps = PythonOperator(
    task_id='check_dependencies',
    python_callable=check_dependencies_task,
    dag=dag,
)

# Task 1: Ingest papers from arXiv
ingest_papers = PythonOperator(
    task_id='ingest_arxiv_papers',
    python_callable=run_ingestion_task,
    op_kwargs={
        'max_papers': 500,  # Default: 500 papers per day
        'categories': ['cs.AI', 'cs.LG', 'cs.CL'],  # Default categories
    },
    dag=dag,
)

# Task 2: Process PDFs into chunks
process_pdfs = PythonOperator(
    task_id='process_pdfs',
    python_callable=run_processing_task,
    dag=dag,
)

# Task 3: Generate embeddings and upload to Pinecone
generate_embeddings = PythonOperator(
    task_id='generate_embeddings',
    python_callable=run_embedding_task,
    dag=dag,
)

# Set task dependencies
check_deps >> ingest_papers >> process_pdfs >> generate_embeddings
