"""
Utilities for PDF processing and text chunking
"""

import logging
import os
import json
import fitz  # PyMuPDF
from typing import List, Dict, Any
from multiprocessing import Pool
import tiktoken

logger = logging.getLogger(__name__)

# Initialize tokenizer
tokenizer = tiktoken.get_encoding("cl100k_base")


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF using PyMuPDF.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Extracted text
    """
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_parts.append(text)
        
        doc.close()
        full_text = "\n\n".join(text_parts)
        
        logger.info(f"Extracted {len(full_text)} characters from {pdf_path}")
        return full_text
        
    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path}: {e}", exc_info=True)
        return ""  # Return empty string on error


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 50
) -> List[Dict[str, Any]]:
    """
    Chunk text into token-sized segments.
    
    Args:
        text: Text to chunk
        chunk_size: Target chunk size in tokens
        overlap: Overlap size in tokens
    
    Returns:
        List of chunk dictionaries
    """
    try:
        # Tokenize text
        tokens = tokenizer.encode(text)
        
        chunks = []
        start_idx = 0
        
        while start_idx < len(tokens):
            end_idx = min(start_idx + chunk_size, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]
            
            # Decode back to text
            chunk_text = tokenizer.decode(chunk_tokens)
            
            chunks.append({
                'text': chunk_text,
                'token_count': len(chunk_tokens),
                'start_token': start_idx,
                'end_token': end_idx
            })
            
            # Move start index with overlap
            start_idx = end_idx - overlap
            if start_idx >= len(tokens):
                break
        
        logger.info(f"Created {len(chunks)} chunks from text")
        return chunks
        
    except Exception as e:
        logger.error(f"Error chunking text: {e}", exc_info=True)
        return []


def process_pdf_worker(args: tuple) -> Dict[str, Any]:
    """
    Worker function for parallel PDF processing.
    
    Args:
        args: Tuple of (s3_key, bucket, local_temp_dir, doc_id)
    
    Returns:
        Dictionary with doc_id, text, and error status
    """
    s3_key, bucket, local_temp_dir, doc_id = args
    
    try:
        from common.s3_utils import download_from_s3
        
        # Download PDF from S3
        local_pdf_path = os.path.join(local_temp_dir, f"{doc_id}.pdf")
        download_from_s3(bucket, s3_key, local_pdf_path)
        
        # Extract text
        text = extract_text_from_pdf(local_pdf_path)
        
        # Clean up local file
        if os.path.exists(local_pdf_path):
            os.unlink(local_pdf_path)
        
        return {
            'doc_id': doc_id,
            'text': text,
            'success': True,
            'error': None
        }
        
    except Exception as e:
        logger.error(f"Error processing PDF {doc_id}: {e}", exc_info=True)
        return {
            'doc_id': doc_id,
            'text': '',
            'success': False,
            'error': str(e)
        }


def process_pdfs_parallel(
    s3_keys: List[str],
    bucket: str,
    num_workers: int = 10
) -> List[Dict[str, Any]]:
    """
    Process multiple PDFs in parallel.
    
    Args:
        s3_keys: List of S3 keys to process
        bucket: S3 bucket name
        num_workers: Number of worker processes
    
    Returns:
        List of processing results
    """
    import tempfile
    
    try:
        temp_dir = tempfile.mkdtemp()
        
        # Prepare arguments for workers
        args_list = []
        for s3_key in s3_keys:
            doc_id = s3_key.split('/')[-1].replace('.pdf', '')
            args_list.append((s3_key, bucket, temp_dir, doc_id))
        
        # Process in parallel
        with Pool(processes=num_workers) as pool:
            results = pool.map(process_pdf_worker, args_list)
        
        # Clean up temp directory
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        successful = sum(1 for r in results if r['success'])
        logger.info(f"Processed {successful}/{len(results)} PDFs successfully")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in parallel PDF processing: {e}", exc_info=True)
        raise
