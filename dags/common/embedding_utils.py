"""
Utilities for generating embeddings
"""

import logging
import os
import time
from typing import List, Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


def get_openai_client():
    """Get OpenAI client using environment variable."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return OpenAI(api_key=api_key)


def generate_embeddings_batch(
    texts: List[str],
    model: str = 'text-embedding-3-small',
    max_retries: int = 3
) -> List[List[float]]:
    """
    Generate embeddings for a batch of texts.
    
    Args:
        texts: List of text strings
        model: OpenAI embedding model
        max_retries: Maximum retry attempts
    
    Returns:
        List of embedding vectors
    """
    client = get_openai_client()
    
    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model=model,
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            logger.info(f"Generated {len(embeddings)} embeddings")
            
            return embeddings
            
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"Error generating embeddings (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to generate embeddings after {max_retries} attempts: {e}", exc_info=True)
                raise
    
    return []


def check_pinecone_chunks_exist(
    chunk_ids: List[str],
    index_name: str
) -> List[str]:
    """
    Check which chunk IDs already exist in Pinecone.
    
    Args:
        chunk_ids: List of chunk IDs to check
        index_name: Pinecone index name
    
    Returns:
        List of chunk IDs that exist in Pinecone
    """
    try:
        import pinecone
        
        api_key = os.getenv('PINECONE_API_KEY')
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable not set")
        
        pc = pinecone.Pinecone(api_key=api_key)
        index = pc.Index(index_name)
        
        # Fetch existing IDs (Pinecone fetch can handle up to 1000 IDs)
        existing_ids = []
        batch_size = 100
        
        for i in range(0, len(chunk_ids), batch_size):
            batch = chunk_ids[i:i + batch_size]
            try:
                fetch_response = index.fetch(ids=batch)
                existing_ids.extend(list(fetch_response['vectors'].keys()))
            except Exception as e:
                logger.warning(f"Error checking batch in Pinecone: {e}")
        
        logger.info(f"Found {len(existing_ids)} existing chunks in Pinecone")
        return existing_ids
        
    except Exception as e:
        logger.error(f"Error checking Pinecone chunks: {e}", exc_info=True)
        return []


def upsert_to_pinecone(
    vectors: List[Dict[str, Any]],
    index_name: str,
    batch_size: int = 100
) -> int:
    """
    Upsert vectors to Pinecone index.
    
    Args:
        vectors: List of vector dictionaries with 'id', 'values', 'metadata'
        index_name: Pinecone index name
        batch_size: Batch size for upserting
    
    Returns:
        Number of vectors upserted
    """
    try:
        import pinecone
        
        api_key = os.getenv('PINECONE_API_KEY')
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable not set")
        
        pc = pinecone.Pinecone(api_key=api_key)
        index = pc.Index(index_name)
        
        total_upserted = 0
        
        # Upsert in batches
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            try:
                index.upsert(vectors=batch)
                total_upserted += len(batch)
                logger.info(f"Upserted batch {i//batch_size + 1}: {len(batch)} vectors")
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error upserting batch: {e}", exc_info=True)
        
        logger.info(f"Total vectors upserted: {total_upserted}")
        return total_upserted
        
    except Exception as e:
        logger.error(f"Error upserting to Pinecone: {e}", exc_info=True)
        raise
