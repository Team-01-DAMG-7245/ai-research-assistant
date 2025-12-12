"""
Airflow DAG for generating embeddings and upserting to Pinecone.

This DAG:
1. Lists new chunks from S3 silver layer that need embeddings
2. Generates embeddings using OpenAI API
3. Upserts embeddings to Pinecone vector database
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import logging
import os
import json

# Import common utilities
import sys
sys.path.append(os.path.dirname(__file__))
from common import s3_utils, embedding_utils

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
    'generate_embeddings',
    default_args=default_args,
    description='Generates embeddings and upserts to Pinecone',
    schedule_interval=None,  # Triggered by processing_dag completion
    start_date=days_ago(1),
    catchup=False,
    tags=['embeddings', 'pinecone', 'openai'],
)


def list_new_chunks_task(**context):
    """Task to list chunks needing embeddings."""
    try:
        bucket = os.getenv('S3_BUCKET_NAME', 'research-data')
        index_name = os.getenv('PINECONE_INDEX_NAME', 'research-papers')
        
        logger.info("Listing new chunks from S3 silver layer...")
        
        # List all chunks in S3 silver layer
        all_chunk_keys = s3_utils.list_s3_objects(bucket, 'silver/chunks/')
        
        # Extract chunk IDs from S3 keys
        chunk_ids = []
        for key in all_chunk_keys:
            # Extract chunk ID from key like "silver/chunks/doc_id_chunk_0.json"
            if key.endswith('.json'):
                chunk_id = key.split('/')[-1].replace('.json', '')
                chunk_ids.append(chunk_id)
        
        logger.info(f"Found {len(chunk_ids)} total chunks in S3")
        
        # Check which chunks already exist in Pinecone
        existing_ids = embedding_utils.check_pinecone_chunks_exist(
            chunk_ids=chunk_ids,
            index_name=index_name
        )
        
        # Filter to only new chunks
        existing_set = set(existing_ids)
        new_chunk_keys = [
            key for key, chunk_id in zip(all_chunk_keys, chunk_ids)
            if chunk_id not in existing_set
        ]
        
        logger.info(f"Found {len(new_chunk_keys)} new chunks needing embeddings")
        
        return {
            's3_keys': new_chunk_keys,
            'chunk_ids': [key.split('/')[-1].replace('.json', '') for key in new_chunk_keys],
            'count': len(new_chunk_keys)
        }
        
    except Exception as e:
        logger.error(f"Error in list_new_chunks_task: {e}", exc_info=True)
        raise


def generate_embeddings_batch_task(**context):
    """Task to generate embeddings in batches."""
    try:
        # Get chunk keys from previous task
        ti = context['ti']
        list_data = ti.xcom_pull(task_ids='list_new_chunks_task')
        
        if not list_data or 's3_keys' not in list_data:
            logger.warning("No new chunks found")
            return {'embeddings': [], 'count': 0}
        
        s3_keys = list_data['s3_keys']
        bucket = os.getenv('S3_BUCKET_NAME', 'research-data')
        batch_size = 100
        
        logger.info(f"Generating embeddings for {len(s3_keys)} chunks in batches of {batch_size}...")
        
        all_embeddings_data = []
        
        # Process in batches
        for i in range(0, len(s3_keys), batch_size):
            batch_keys = s3_keys[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: {len(batch_keys)} chunks")
            
            # Load chunks from S3
            texts = []
            chunk_metadata = []
            
            for s3_key in batch_keys:
                try:
                    # Download chunk from S3
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        temp_path = f.name
                    
                    s3_utils.download_from_s3(bucket, s3_key, temp_path)
                    
                    # Load chunk data
                    with open(temp_path, 'r') as f:
                        chunk_data = json.load(f)
                    
                    text = chunk_data.get('text', '')
                    texts.append(text)
                    chunk_metadata.append({
                        'chunk_id': chunk_data.get('doc_id', '') + '_chunk_' + str(chunk_data.get('chunk_id', 0)),
                        'doc_id': chunk_data.get('doc_id', ''),
                        'chunk_index': chunk_data.get('chunk_id', 0),
                        'metadata': chunk_data.get('metadata', {}),
                        's3_key': s3_key
                    })
                    
                    # Clean up temp file
                    os.unlink(temp_path)
                    
                except Exception as e:
                    logger.error(f"Error loading chunk {s3_key}: {e}", exc_info=True)
                    continue
            
            if not texts:
                logger.warning(f"No texts loaded for batch {i//batch_size + 1}")
                continue
            
            # Generate embeddings
            try:
                embeddings = embedding_utils.generate_embeddings_batch(
                    texts=texts,
                    model='text-embedding-3-small',
                    max_retries=3
                )
                
                # Combine embeddings with metadata
                for emb, meta in zip(embeddings, chunk_metadata):
                    all_embeddings_data.append({
                        'chunk_id': meta['chunk_id'],
                        'embedding': emb,
                        'doc_id': meta['doc_id'],
                        'chunk_index': meta['chunk_index'],
                        'metadata': meta['metadata'],
                        's3_key': meta['s3_key']
                    })
                
                logger.info(f"Generated {len(embeddings)} embeddings for batch {i//batch_size + 1}")
                
            except Exception as e:
                logger.error(f"Error generating embeddings for batch: {e}", exc_info=True)
                continue
        
        logger.info(f"Total embeddings generated: {len(all_embeddings_data)}")
        
        return {
            'embeddings': all_embeddings_data,
            'count': len(all_embeddings_data)
        }
        
    except Exception as e:
        logger.error(f"Error in generate_embeddings_batch_task: {e}", exc_info=True)
        raise


def upsert_to_pinecone_task(**context):
    """Task to upsert embeddings to Pinecone."""
    try:
        # Get embeddings from previous task
        ti = context['ti']
        embedding_data = ti.xcom_pull(task_ids='generate_embeddings_batch_task')
        
        if not embedding_data or 'embeddings' not in embedding_data:
            logger.warning("No embeddings found")
            return {'upserted_count': 0}
        
        embeddings_list = embedding_data['embeddings']
        index_name = os.getenv('PINECONE_INDEX_NAME', 'research-papers')
        
        logger.info(f"Upserting {len(embeddings_list)} vectors to Pinecone...")
        
        # Format vectors for Pinecone
        vectors = []
        for emb_data in embeddings_list:
            chunk_id = emb_data['chunk_id']
            embedding = emb_data['embedding']
            metadata = emb_data['metadata']
            
            # Prepare Pinecone vector format
            vector = {
                'id': chunk_id,
                'values': embedding,
                'metadata': {
                    'text': emb_data.get('metadata', {}).get('text', '')[:500],  # First 500 chars
                    'doc_id': emb_data['doc_id'],
                    'chunk_index': emb_data['chunk_index'],
                    'title': metadata.get('title', ''),
                    'url': metadata.get('url', ''),
                }
            }
            vectors.append(vector)
        
        # Upsert to Pinecone
        upserted_count = embedding_utils.upsert_to_pinecone(
            vectors=vectors,
            index_name=index_name,
            batch_size=100
        )
        
        logger.info(f"Successfully upserted {upserted_count} vectors to Pinecone")
        
        return {
            'upserted_count': upserted_count
        }
        
    except Exception as e:
        logger.error(f"Error in upsert_to_pinecone_task: {e}", exc_info=True)
        raise


# Sensor to wait for processing_dag completion
wait_for_processing = ExternalTaskSensor(
    task_id='wait_for_processing_dag',
    external_dag_id='document_processing',
    external_task_id='upload_chunks_to_s3_silver_task',
    timeout=7200,  # 2 hour timeout
    poke_interval=600,  # Check every 10 minutes
    dag=dag,
)

# Define tasks
list_new_chunks = PythonOperator(
    task_id='list_new_chunks_task',
    python_callable=list_new_chunks_task,
    dag=dag,
)

generate_embeddings_batch = PythonOperator(
    task_id='generate_embeddings_batch_task',
    python_callable=generate_embeddings_batch_task,
    dag=dag,
)

upsert_to_pinecone = PythonOperator(
    task_id='upsert_to_pinecone_task',
    python_callable=upsert_to_pinecone_task,
    dag=dag,
)

# Define task dependencies
wait_for_processing >> list_new_chunks >> generate_embeddings_batch >> upsert_to_pinecone
