"""
Utilities for S3 operations
"""

import logging
import os
import json
import sqlite3
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_s3_client():
    """Get S3 client using environment variables."""
    return boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )


def upload_file_to_s3(
    local_path: str,
    bucket: str,
    s3_key: str,
    metadata: Dict[str, str] = None
) -> bool:
    """
    Upload a file to S3.
    
    Args:
        local_path: Local file path
        bucket: S3 bucket name
        s3_key: S3 object key
        metadata: Optional metadata dict
    
    Returns:
        True if successful
    """
    try:
        s3_client = get_s3_client()
        
        extra_args = {}
        if metadata:
            extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
        
        s3_client.upload_file(
            local_path,
            bucket,
            s3_key,
            ExtraArgs=extra_args
        )
        
        logger.info(f"Uploaded {local_path} to s3://{bucket}/{s3_key}")
        return True
        
    except ClientError as e:
        logger.error(f"Error uploading to S3: {e}", exc_info=True)
        raise


def list_s3_objects(bucket: str, prefix: str) -> List[str]:
    """
    List all objects in S3 with given prefix.
    
    Args:
        bucket: S3 bucket name
        prefix: Prefix to filter objects
    
    Returns:
        List of S3 keys
    """
    try:
        s3_client = get_s3_client()
        paginator = s3_client.get_paginator('list_objects_v2')
        
        keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            if 'Contents' in page:
                keys.extend([obj['Key'] for obj in page['Contents']])
        
        logger.info(f"Found {len(keys)} objects with prefix {prefix}")
        return keys
        
    except ClientError as e:
        logger.error(f"Error listing S3 objects: {e}", exc_info=True)
        raise


def download_from_s3(bucket: str, s3_key: str, local_path: str) -> str:
    """
    Download a file from S3.
    
    Args:
        bucket: S3 bucket name
        s3_key: S3 object key
        local_path: Local path to save file
    
    Returns:
        Path to downloaded file
    """
    try:
        s3_client = get_s3_client()
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        s3_client.download_file(bucket, s3_key, local_path)
        logger.info(f"Downloaded s3://{bucket}/{s3_key} to {local_path}")
        
        return local_path
        
    except ClientError as e:
        logger.error(f"Error downloading from S3: {e}", exc_info=True)
        raise


def save_chunk_to_s3(
    chunk_data: Dict[str, Any],
    bucket: str,
    doc_id: str,
    chunk_id: int
) -> str:
    """
    Save a chunk as JSON to S3 silver layer.
    
    Args:
        chunk_data: Chunk data dictionary
        bucket: S3 bucket name
        doc_id: Document ID
        chunk_id: Chunk ID
    
    Returns:
        S3 key of uploaded chunk
    """
    import tempfile
    
    try:
        s3_key = f"silver/chunks/{doc_id}_chunk_{chunk_id}.json"
        
        # Write to temp file first
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(chunk_data, f, indent=2)
            temp_path = f.name
        
        upload_file_to_s3(temp_path, bucket, s3_key)
        os.unlink(temp_path)  # Clean up temp file
        
        logger.info(f"Saved chunk to s3://{bucket}/{s3_key}")
        return s3_key
        
    except Exception as e:
        logger.error(f"Error saving chunk to S3: {e}", exc_info=True)
        raise


def update_document_status(
    db_path: str,
    doc_id: str,
    status: str
) -> None:
    """
    Update document status in SQLite.
    
    Args:
        db_path: Path to SQLite database
        doc_id: Document ID
        status: New status
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE documents SET status = ? WHERE doc_id = ?",
            (status, doc_id)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated document {doc_id} status to {status}")
        
    except Exception as e:
        logger.error(f"Error updating document status: {e}", exc_info=True)
        raise


def insert_document(
    db_path: str,
    doc_id: str,
    url: str,
    doc_type: str = 'arxiv',
    status: str = 'raw'
) -> None:
    """
    Insert document record into SQLite.
    
    Args:
        db_path: Path to SQLite database
        doc_id: Document ID
        url: Document URL
        doc_type: Document type
        status: Initial status
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                type TEXT,
                status TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute(
            "INSERT OR REPLACE INTO documents (doc_id, url, type, status) VALUES (?, ?, ?, ?)",
            (doc_id, url, doc_type, status)
        )
        
        conn.commit()
        conn.close()
        
        logger.info(f"Inserted document {doc_id} into database")
        
    except Exception as e:
        logger.error(f"Error inserting document: {e}", exc_info=True)
        raise


def get_unprocessed_documents(db_path: str) -> List[str]:
    """
    Get list of unprocessed document IDs.
    
    Args:
        db_path: Path to SQLite database
    
    Returns:
        List of document IDs with status='raw'
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT doc_id FROM documents WHERE status = 'raw'")
        results = cursor.fetchall()
        conn.close()
        
        doc_ids = [row[0] for row in results]
        logger.info(f"Found {len(doc_ids)} unprocessed documents")
        
        return doc_ids
        
    except Exception as e:
        logger.error(f"Error getting unprocessed documents: {e}", exc_info=True)
        raise
