"""
Airflow DAG for Daily arXiv Paper Ingestion and Processing

This DAG runs daily to:
1. Fetch and ingest up to 100 papers from arXiv → S3
2. Process PDFs into text chunks → S3
3. Generate embeddings and upload to Pinecone

Schedule: Daily at 2:00 AM UTC
Max Papers: 100
Categories: cs.AI, cs.LG, cs.CL
"""

from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to Python path
# Works both in Docker (/opt/airflow) and local development
if Path("/opt/airflow").exists():
    project_root = Path("/opt/airflow")  # Docker
else:
    project_root = Path(__file__).parent.parent  # Local
sys.path.insert(0, str(project_root))

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import subprocess
import os

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_ingestion(**context):
    """
    Run the arXiv paper ingestion pipeline
    """
    # Import here to speed up DAG parsing
    from src.pipelines.ingestion import ArxivIngestion
    
    # Use Airflow's task logger
    task_logger = context.get('task_instance').log if 'task_instance' in context else logger
    
    task_logger.info("=" * 70)
    task_logger.info("Starting Daily arXiv Ingestion")
    task_logger.info("=" * 70)
    
    # Configuration
    max_papers = 100
    categories = ["cs.AI", "cs.LG", "cs.CL"]
    
    task_logger.info(f"Max papers: {max_papers}")
    task_logger.info(f"Categories: {', '.join(categories)}")
    
    try:
        # Initialize and run ingestion
        ingestion = ArxivIngestion()
        papers = ingestion.fetch_papers(categories=categories, max_results=max_papers)
        task_logger.info(f"✅ Fetched {len(papers)} papers")
        
        # Process with progress tracking
        task_logger.info("Processing and uploading papers to S3...")
        success_count = 0
        failed_count = 0
        
        for i, paper in enumerate(papers, 1):
            arxiv_id = paper["arxiv_id"]
            task_logger.info(f"[{i}/{len(papers)}] Processing: {arxiv_id}")
            
            pdf_path = ingestion.download_pdf(paper)
            if pdf_path:
                if ingestion.upload_to_s3(paper, pdf_path):
                    success_count += 1
                    task_logger.info(f"  ✅ Uploaded ({success_count}/{len(papers)} successful)")
                else:
                    failed_count += 1
                    task_logger.warning(f"  ❌ Upload failed ({failed_count} failed)")
            else:
                failed_count += 1
                task_logger.warning(f"  ❌ Download failed ({failed_count} failed)")
            
            if i % 10 == 0:
                task_logger.info(f"📊 Progress: {i}/{len(papers)} | ✅ {success_count} | ❌ {failed_count}")
        
        summary = {
            "total_fetched": len(papers),
            "successfully_uploaded": success_count,
            "failed": failed_count,
            "timestamp": datetime.now().isoformat(),
        }
        
        task_logger.info("=" * 70)
        task_logger.info("Ingestion Complete")
        task_logger.info(f"Total: {summary['total_fetched']}")
        task_logger.info(f"Successful: {summary['successfully_uploaded']}")
        task_logger.info(f"Failed: {summary['failed']}")
        task_logger.info("=" * 70)
        
        return summary
        
    except Exception as e:
        task_logger.error(f"Error during ingestion: {e}", exc_info=True)
        raise


def run_processing(**context):
    """
    Process PDFs from S3 into text chunks and upload chunks to S3
    """
    task_logger = context.get('task_instance').log if 'task_instance' in context else logger
    
    task_logger.info("=" * 70)
    task_logger.info("Starting PDF Processing")
    task_logger.info("=" * 70)
    
    try:
        # First, get count of papers to process
        from src.utils.s3_client import S3Client
        s3 = S3Client()
        all_objects = s3.list_objects('raw/papers/')
        pdf_keys = [o for o in all_objects if o.endswith('.pdf')]
        total_papers = len(pdf_keys)
        
        task_logger.info(f"Found {total_papers} papers to process")
        task_logger.info("=" * 70)
        
        script_path = project_root / "scripts" / "process_all_paper.py"
        task_logger.info(f"Running: python {script_path}")
        
        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env={**os.environ, 'TQDM_DISABLE': '1'}  # Disable tqdm progress bars for cleaner logs
        )
        
        # Track progress manually
        processed_count = 0
        successful_count = 0
        failed_count = 0
        
        # Stream output line by line
        for line in iter(process.stdout.readline, ''):
            if line:
                line = line.strip()
                if line:
                    # Parse tqdm output or other progress indicators
                    if 'Processing papers' in line or '%' in line:
                        # Try to extract progress from tqdm-like output
                        if '/' in line:
                            parts = line.split('/')
                            if len(parts) >= 2:
                                try:
                                    current = int(parts[0].split()[-1])
                                    total = int(parts[1].split()[0])
                                    processed_count = current
                                    task_logger.info(f"📊 Processing: {current}/{total} papers ({current*100//total if total > 0 else 0}%)")
                                except:
                                    task_logger.info(f"📊 {line}")
                            else:
                                task_logger.info(f"📊 {line}")
                        else:
                            task_logger.info(f"📊 {line}")
                    elif 'Successful:' in line:
                        try:
                            successful_count = int(line.split(':')[1].strip())
                            task_logger.info(f"✅ {line}")
                        except:
                            task_logger.info(f"✅ {line}")
                    elif 'Failed:' in line:
                        try:
                            failed_count = int(line.split(':')[1].strip())
                            task_logger.info(f"❌ {line}")
                        except:
                            task_logger.info(f"❌ {line}")
                    elif 'PROCESSING COMPLETE' in line or 'COMPLETE' in line:
                        task_logger.info(f"✅ {line}")
                    elif 'Error' in line or 'Failed' in line or '❌' in line:
                        task_logger.error(f"❌ {line}")
                    elif '✅' in line or 'Success' in line:
                        task_logger.info(f"✅ {line}")
                    else:
                        task_logger.info(line)
        
        process.wait()
        
        if process.returncode == 0:
            task_logger.info("=" * 70)
            task_logger.info("✅ Processing completed successfully")
            if total_papers > 0:
                task_logger.info(f"📊 Final: {processed_count}/{total_papers} papers processed")
            task_logger.info("=" * 70)
            return {"status": "success", "processed": processed_count, "total": total_papers}
        else:
            task_logger.error("=" * 70)
            task_logger.error(f"❌ Processing failed with return code: {process.returncode}")
            task_logger.error("=" * 70)
            raise Exception(f"Processing failed with return code {process.returncode}")
            
    except Exception as e:
        task_logger.error(f"Error during processing: {e}", exc_info=True)
        raise


def run_embedding(**context):
    """
    Generate embeddings and upload to Pinecone
    """
    task_logger = context.get('task_instance').log if 'task_instance' in context else logger
    
    task_logger.info("=" * 70)
    task_logger.info("Starting Embedding Generation")
    task_logger.info("=" * 70)
    
    try:
        # First, get count of chunks to embed
        from src.utils.s3_client import S3Client
        s3 = S3Client()
        all_objects = s3.list_objects('processed/text_chunks/')
        chunk_files = [o for o in all_objects if o.endswith('.json')]
        total_chunks = len(chunk_files)
        
        task_logger.info(f"Found {total_chunks} chunk files to embed")
        task_logger.info("=" * 70)
        
        script_path = project_root / "scripts" / "embed_chunks_to_pinecone.py"
        task_logger.info(f"Running: python {script_path}")
        
        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env={**os.environ, 'TQDM_DISABLE': '1'}  # Disable tqdm progress bars for cleaner logs
        )
        
        # Track progress manually
        embedded_count = 0
        upserted_count = 0
        
        # Stream output line by line
        for line in iter(process.stdout.readline, ''):
            if line:
                line = line.strip()
                if line:
                    # Parse progress indicators
                    if 'Processing' in line and ('/' in line or '%' in line):
                        # Try to extract progress
                        if '/' in line:
                            parts = line.split('/')
                            if len(parts) >= 2:
                                try:
                                    current = int(parts[0].split()[-1])
                                    total = int(parts[1].split()[0])
                                    embedded_count = current
                                    task_logger.info(f"📊 Embedding: {current}/{total} chunks ({current*100//total if total > 0 else 0}%)")
                                except:
                                    task_logger.info(f"📊 {line}")
                            else:
                                task_logger.info(f"📊 {line}")
                        else:
                            task_logger.info(f"📊 {line}")
                    elif 'Upserted' in line or 'upserted' in line:
                        try:
                            # Extract number from "Upserted X vectors"
                            import re
                            nums = re.findall(r'\d+', line)
                            if nums:
                                upserted_count = int(nums[-1])
                                task_logger.info(f"📊 {line}")
                            else:
                                task_logger.info(f"📊 {line}")
                        except:
                            task_logger.info(f"📊 {line}")
                    elif 'Complete' in line or 'COMPLETE' in line:
                        task_logger.info(f"✅ {line}")
                    elif 'Error' in line or 'Failed' in line or '❌' in line:
                        task_logger.error(f"❌ {line}")
                    elif '✅' in line or 'Success' in line:
                        task_logger.info(f"✅ {line}")
                    else:
                        task_logger.info(line)
        
        process.wait()
        
        if process.returncode == 0:
            task_logger.info("=" * 70)
            task_logger.info("✅ Embedding completed successfully")
            if total_chunks > 0:
                task_logger.info(f"📊 Final: {embedded_count}/{total_chunks} chunks embedded")
            task_logger.info("=" * 70)
            return {"status": "success", "embedded": embedded_count, "total": total_chunks}
        else:
            task_logger.error("=" * 70)
            task_logger.error(f"❌ Embedding failed with return code: {process.returncode}")
            task_logger.error("=" * 70)
            raise Exception(f"Embedding failed with return code {process.returncode}")
            
    except Exception as e:
        task_logger.error(f"Error during embedding: {e}", exc_info=True)
        raise


# Default arguments
default_args = {
    'owner': 'ai-research-assistant',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'start_date': days_ago(1),
}

# Create the DAG
dag = DAG(
    'arxiv_daily_ingestion',
    default_args=default_args,
    description='Daily arXiv paper ingestion → processing → embedding (max 100 papers)',
    schedule_interval='0 2 * * *',  # Daily at 2:00 AM UTC
    catchup=False,
    tags=['ingestion', 'arxiv', 'daily', 's3', 'pinecone'],
    max_active_runs=1,
)

# Create tasks
ingestion_task = PythonOperator(
    task_id='ingest_arxiv_papers',
    python_callable=run_ingestion,
    dag=dag,
    provide_context=True,
    execution_timeout=timedelta(hours=1),
)

processing_task = PythonOperator(
    task_id='process_pdfs_to_chunks',
    python_callable=run_processing,
    dag=dag,
    provide_context=True,
    execution_timeout=timedelta(hours=2),
)

embedding_task = PythonOperator(
    task_id='embed_and_upload_to_pinecone',
    python_callable=run_embedding,
    dag=dag,
    provide_context=True,
    execution_timeout=timedelta(hours=1),
)

# Set task dependencies: ingestion → processing → embedding
ingestion_task >> processing_task >> embedding_task
