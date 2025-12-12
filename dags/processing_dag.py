"""
Airflow DAG for document processing pipeline.

This DAG:
1. Lists unprocessed papers from SQLite
2. Extracts text from PDFs in parallel
3. Chunks text into 512-token segments
4. Uploads chunks to S3 silver layer
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import logging
import os

# Import common utilities
import sys
sys.path.append(os.path.dirname(__file__))
from common import s3_utils, processing_utils

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
    'document_processing',
    default_args=default_args,
    description='Processes raw PDFs into text chunks',
    schedule_interval=None,  # Triggered by ingestion_dag completion
    start_date=days_ago(1),
    catchup=False,
    tags=['processing', 'pdf', 'chunking'],
)


def list_unprocessed_papers_task(**context):
    """Task to list unprocessed papers."""
    try:
        db_path = os.getenv('TASK_DB_PATH', 'data/tasks.db')
        bucket = os.getenv('S3_BUCKET_NAME', 'research-data')
        
        logger.info("Listing unprocessed papers...")
        
        # Get unprocessed document IDs from SQLite
        doc_ids = s3_utils.get_unprocessed_documents(db_path)
        
        # List S3 bronze files
        bronze_keys = s3_utils.list_s3_objects(bucket, 'bronze/papers/')
        
        # Filter to only unprocessed documents
        unprocessed_keys = [
            key for key in bronze_keys
            if any(doc_id in key for doc_id in doc_ids)
        ]
        
        logger.info(f"Found {len(unprocessed_keys)} unprocessed papers")
        
        return {
            's3_keys': unprocessed_keys,
            'doc_ids': doc_ids,
            'count': len(unprocessed_keys)
        }
        
    except Exception as e:
        logger.error(f"Error in list_unprocessed_papers_task: {e}", exc_info=True)
        raise


def extract_text_parallel_task(**context):
    """Task to extract text from PDFs in parallel."""
    try:
        # Get S3 keys from previous task
        ti = context['ti']
        list_data = ti.xcom_pull(task_ids='list_unprocessed_papers_task')
        
        if not list_data or 's3_keys' not in list_data:
            logger.warning("No unprocessed papers found")
            return {'extracted_texts': [], 'count': 0}
        
        s3_keys = list_data['s3_keys']
        bucket = os.getenv('S3_BUCKET_NAME', 'research-data')
        num_workers = int(os.getenv('PROCESSING_WORKERS', '10'))
        
        logger.info(f"Extracting text from {len(s3_keys)} PDFs using {num_workers} workers...")
        
        # Process PDFs in parallel
        results = processing_utils.process_pdfs_parallel(
            s3_keys=s3_keys,
            bucket=bucket,
            num_workers=num_workers
        )
        
        # Filter successful extractions
        extracted_texts = [
            {
                'doc_id': r['doc_id'],
                'text': r['text'],
                's3_key': next((k for k in s3_keys if r['doc_id'] in k), None)
            }
            for r in results if r['success']
        ]
        
        logger.info(f"Successfully extracted text from {len(extracted_texts)} PDFs")
        
        return {
            'extracted_texts': extracted_texts,
            'count': len(extracted_texts)
        }
        
    except Exception as e:
        logger.error(f"Error in extract_text_parallel_task: {e}", exc_info=True)
        raise


def chunk_text_task(**context):
    """Task to chunk extracted text."""
    try:
        # Get extracted texts from previous task
        ti = context['ti']
        extract_data = ti.xcom_pull(task_ids='extract_text_parallel_task')
        
        if not extract_data or 'extracted_texts' not in extract_data:
            logger.warning("No extracted texts found")
            return {'chunks': [], 'count': 0}
        
        extracted_texts = extract_data['extracted_texts']
        chunk_size = int(os.getenv('CHUNK_SIZE', '512'))
        overlap = int(os.getenv('CHUNK_OVERLAP', '50'))
        
        logger.info(f"Chunking {len(extracted_texts)} documents...")
        
        all_chunks = []
        
        for doc_data in extracted_texts:
            doc_id = doc_data['doc_id']
            text = doc_data['text']
            s3_key = doc_data['s3_key']
            
            if not text.strip():
                logger.warning(f"No text extracted for {doc_id}")
                continue
            
            # Chunk the text
            chunks = processing_utils.chunk_text(
                text=text,
                chunk_size=chunk_size,
                overlap=overlap
            )
            
            # Add metadata to each chunk
            for idx, chunk in enumerate(chunks):
                chunk_data = {
                    'doc_id': doc_id,
                    'chunk_id': idx,
                    'chunk_index': idx,
                    'text': chunk['text'],
                    'token_count': chunk['token_count'],
                    'metadata': {
                        'title': doc_id,  # Could be enhanced with actual title
                        'url': f"https://arxiv.org/pdf/{doc_id}.pdf",
                        's3_key': s3_key,
                    }
                }
                all_chunks.append(chunk_data)
            
            logger.info(f"Created {len(chunks)} chunks for {doc_id}")
        
        logger.info(f"Total chunks created: {len(all_chunks)}")
        
        return {
            'chunks': all_chunks,
            'count': len(all_chunks)
        }
        
    except Exception as e:
        logger.error(f"Error in chunk_text_task: {e}", exc_info=True)
        raise


def upload_chunks_to_s3_silver_task(**context):
    """Task to upload chunks to S3 silver layer."""
    try:
        # Get chunks from previous task
        ti = context['ti']
        chunk_data = ti.xcom_pull(task_ids='chunk_text_task')
        
        if not chunk_data or 'chunks' not in chunk_data:
            logger.warning("No chunks found")
            return {'uploaded_count': 0}
        
        chunks = chunk_data['chunks']
        bucket = os.getenv('S3_BUCKET_NAME', 'research-data')
        db_path = os.getenv('TASK_DB_PATH', 'data/tasks.db')
        
        logger.info(f"Uploading {len(chunks)} chunks to S3 silver layer...")
        
        uploaded_count = 0
        processed_doc_ids = set()
        
        for chunk in chunks:
            doc_id = chunk['doc_id']
            chunk_id = chunk['chunk_id']
            
            try:
                # Upload chunk to S3
                s3_utils.save_chunk_to_s3(
                    chunk_data=chunk,
                    bucket=bucket,
                    doc_id=doc_id,
                    chunk_id=chunk_id
                )
                
                uploaded_count += 1
                processed_doc_ids.add(doc_id)
                
            except Exception as e:
                logger.error(f"Error uploading chunk {doc_id}_chunk_{chunk_id}: {e}", exc_info=True)
                continue
        
        # Update document status to 'processed'
        for doc_id in processed_doc_ids:
            try:
                s3_utils.update_document_status(
                    db_path=db_path,
                    doc_id=doc_id,
                    status='processed'
                )
            except Exception as e:
                logger.error(f"Error updating status for {doc_id}: {e}", exc_info=True)
        
        logger.info(f"Successfully uploaded {uploaded_count} chunks and updated {len(processed_doc_ids)} documents")
        
        return {
            'uploaded_count': uploaded_count,
            'processed_docs': len(processed_doc_ids)
        }
        
    except Exception as e:
        logger.error(f"Error in upload_chunks_to_s3_silver_task: {e}", exc_info=True)
        raise


# Sensor to wait for ingestion_dag completion
wait_for_ingestion = ExternalTaskSensor(
    task_id='wait_for_ingestion_dag',
    external_dag_id='arxiv_ingestion',
    external_task_id='upload_to_s3_bronze_task',
    timeout=3600,  # 1 hour timeout
    poke_interval=300,  # Check every 5 minutes
    dag=dag,
)

# Define tasks
list_unprocessed = PythonOperator(
    task_id='list_unprocessed_papers_task',
    python_callable=list_unprocessed_papers_task,
    dag=dag,
)

extract_text_parallel = PythonOperator(
    task_id='extract_text_parallel_task',
    python_callable=extract_text_parallel_task,
    dag=dag,
)

chunk_text = PythonOperator(
    task_id='chunk_text_task',
    python_callable=chunk_text_task,
    dag=dag,
)

upload_chunks_to_s3_silver = PythonOperator(
    task_id='upload_chunks_to_s3_silver_task',
    python_callable=upload_chunks_to_s3_silver_task,
    dag=dag,
)

# Define task dependencies
wait_for_ingestion >> list_unprocessed >> extract_text_parallel >> chunk_text >> upload_chunks_to_s3_silver
