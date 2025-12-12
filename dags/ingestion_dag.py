"""
Airflow DAG for arXiv paper ingestion pipeline.

This DAG:
1. Queries arXiv API for new papers published in last 24 hours
2. Downloads PDFs from arXiv
3. Uploads PDFs to S3 bronze layer
4. Stores metadata in SQLite database
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
from airflow.utils.dates import days_ago
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta
import logging
import os
import tempfile

# Import common utilities
import sys
sys.path.append(os.path.dirname(__file__))
from common import arxiv_utils, s3_utils

logger = logging.getLogger(__name__)

# Default arguments
default_args = {
    'owner': 'research-team',
    'depends_on_past': False,
    'email': os.getenv('AIRFLOW_EMAIL', 'admin@example.com'),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
}

# DAG definition
dag = DAG(
    'arxiv_ingestion',
    default_args=default_args,
    description='Collects new research papers from arXiv API',
    schedule_interval='@daily',  # Runs at midnight
    start_date=days_ago(1),
    catchup=False,
    tags=['ingestion', 'arxiv', 'research'],
)


def check_new_papers_task(**context):
    """Task to query arXiv API for new papers."""
    try:
        logger.info("Querying arXiv API for new papers...")
        
        # Query arXiv for papers from last 24 hours
        papers = arxiv_utils.query_arxiv_papers(
            categories=['cs.AI', 'cs.LG', 'cs.CL', 'cs.CV'],
            hours_back=24,
            max_results=100
        )
        
        logger.info(f"Found {len(papers)} new papers")
        
        # Return paper IDs and metadata via XCom
        return {
            'papers': papers,
            'paper_ids': [p['arxiv_id'] for p in papers],
            'count': len(papers)
        }
        
    except Exception as e:
        logger.error(f"Error in check_new_papers_task: {e}", exc_info=True)
        raise


def download_pdfs_task(**context):
    """Task to download PDFs from arXiv."""
    try:
        # Get paper data from previous task
        ti = context['ti']
        papers_data = ti.xcom_pull(task_ids='check_new_papers_task')
        
        if not papers_data or 'papers' not in papers_data:
            logger.warning("No papers found from previous task")
            return {'downloaded_files': [], 'count': 0}
        
        papers = papers_data['papers']
        logger.info(f"Downloading {len(papers)} PDFs...")
        
        downloaded_files = []
        temp_dir = tempfile.mkdtemp()
        
        for paper in papers:
            arxiv_id = paper['arxiv_id']
            pdf_path = os.path.join(temp_dir, f"{arxiv_id}.pdf")
            
            try:
                # Download with retry logic
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        downloaded_path = arxiv_utils.download_arxiv_pdf(
                            arxiv_id=arxiv_id,
                            output_path=pdf_path,
                            delay=3.0  # Rate limiting
                        )
                        downloaded_files.append({
                            'arxiv_id': arxiv_id,
                            'local_path': downloaded_path,
                            'paper_metadata': paper
                        })
                        logger.info(f"Downloaded PDF for {arxiv_id}")
                        break
                    except Exception as e:
                        if attempt < max_attempts - 1:
                            logger.warning(f"Attempt {attempt + 1} failed for {arxiv_id}: {e}. Retrying...")
                            continue
                        else:
                            logger.error(f"Failed to download {arxiv_id} after {max_attempts} attempts: {e}")
                            
            except Exception as e:
                logger.error(f"Error downloading PDF for {arxiv_id}: {e}", exc_info=True)
                continue
        
        logger.info(f"Successfully downloaded {len(downloaded_files)} PDFs")
        
        # Store temp_dir in XCom for cleanup
        return {
            'downloaded_files': downloaded_files,
            'temp_dir': temp_dir,
            'count': len(downloaded_files)
        }
        
    except Exception as e:
        logger.error(f"Error in download_pdfs_task: {e}", exc_info=True)
        raise


def upload_to_s3_bronze_task(**context):
    """Task to upload PDFs to S3 bronze layer."""
    try:
        # Get downloaded files from previous task
        ti = context['ti']
        download_data = ti.xcom_pull(task_ids='download_pdfs_task')
        
        if not download_data or 'downloaded_files' not in download_data:
            logger.warning("No downloaded files found from previous task")
            return {'uploaded_count': 0}
        
        downloaded_files = download_data['downloaded_files']
        bucket = os.getenv('S3_BUCKET_NAME', 'research-data')
        db_path = os.getenv('TASK_DB_PATH', 'data/tasks.db')
        
        logger.info(f"Uploading {len(downloaded_files)} PDFs to S3 bronze layer...")
        
        uploaded_count = 0
        
        for file_info in downloaded_files:
            arxiv_id = file_info['arxiv_id']
            local_path = file_info['local_path']
            paper_metadata = file_info['paper_metadata']
            
            try:
                # Upload to S3 bronze layer
                s3_key = f"bronze/papers/{arxiv_id}.pdf"
                s3_utils.upload_file_to_s3(
                    local_path=local_path,
                    bucket=bucket,
                    s3_key=s3_key,
                    metadata={
                        'title': paper_metadata.get('title', ''),
                        'authors': ', '.join(paper_metadata.get('authors', [])),
                        'published': paper_metadata.get('published', ''),
                    }
                )
                
                # Store metadata in SQLite
                s3_utils.insert_document(
                    db_path=db_path,
                    doc_id=arxiv_id,
                    url=paper_metadata.get('pdf_url', ''),
                    doc_type='arxiv',
                    status='raw'
                )
                
                uploaded_count += 1
                logger.info(f"Uploaded {arxiv_id} to S3 and stored metadata")
                
            except Exception as e:
                logger.error(f"Error uploading {arxiv_id}: {e}", exc_info=True)
                continue
        
        # Cleanup temp directory
        temp_dir = download_data.get('temp_dir')
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
        
        logger.info(f"Successfully uploaded {uploaded_count}/{len(downloaded_files)} PDFs")
        
        return {'uploaded_count': uploaded_count}
        
    except Exception as e:
        logger.error(f"Error in upload_to_s3_bronze_task: {e}", exc_info=True)
        raise


# Define tasks
check_new_papers = PythonOperator(
    task_id='check_new_papers_task',
    python_callable=check_new_papers_task,
    dag=dag,
)

download_pdfs = PythonOperator(
    task_id='download_pdfs_task',
    python_callable=download_pdfs_task,
    dag=dag,
)

upload_to_s3_bronze = PythonOperator(
    task_id='upload_to_s3_bronze_task',
    python_callable=upload_to_s3_bronze_task,
    dag=dag,
)

# Define task dependencies
check_new_papers >> download_pdfs >> upload_to_s3_bronze
