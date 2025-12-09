"""
Helper functions for Airflow DAG tasks

This module provides Python functions that wrap your existing pipeline scripts
to work as Airflow tasks. It contains three main functions:

1. check_dependencies_task():
   - Verifies all required environment variables are set (OpenAI, Pinecone, AWS keys)
   - Checks that all Python dependencies can be imported
   - Runs as the first task to catch configuration issues early

2. run_ingestion_task():
   - Fetches papers from arXiv API based on categories and max_papers limit
   - Downloads PDFs and uploads them to S3 bronze layer
   - Wraps the functionality from scripts/ingest_arxiv_papers.py
   - Returns summary with success/failure counts

3. run_processing_task():
   - Processes all PDFs in S3 into text chunks
   - Uses parallel processing (10 workers) for efficiency
   - Uploads chunks to S3 silver layer
   - Wraps the functionality from scripts/process_all_paper.py
   - Returns summary with chunk counts

4. run_embedding_task():
   - Downloads processed chunks from S3
   - Generates embeddings using OpenAI's text-embedding-3-small model
   - Uploads vectors to Pinecone with metadata
   - Wraps the functionality from scripts/embed_chunks_to_pinecone.py
   - Returns summary with vector counts

These functions are called by the DAG defined in arxiv_ingestion_dag.py.
They handle logging, error handling, and return status dictionaries that
Airflow can track and display in its UI.
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies_task(**context) -> Dict[str, Any]:
    """
    Check that all required environment variables and dependencies are available.
    
    Returns:
        dict: Status of dependency checks
    """
    logger.info("=" * 70)
    logger.info("CHECKING DEPENDENCIES")
    logger.info("=" * 70)
    
    required_vars = [
        'OPENAI_API_KEY',
        'PINECONE_API_KEY',
        'PINECONE_INDEX_NAME',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'S3_BUCKET_NAME',
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
            logger.error(f"Missing environment variable: {var}")
        else:
            # Mask sensitive values
            masked = value[:4] + "..." if len(value) > 4 else "***"
            logger.info(f"✓ {var}: {masked}")
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Check Python imports
    try:
        from src.pipelines.ingestion import ArxivIngestion
        from src.utils.s3_client import S3Client
        from src.utils.pdf_processor import PDFProcessor
        from src.utils.openai_client import OpenAIClient
        from pinecone import Pinecone
        logger.info("✓ All Python dependencies available")
    except ImportError as e:
        error_msg = f"Missing Python dependency: {e}"
        logger.error(error_msg)
        raise ImportError(error_msg)
    
    logger.info("=" * 70)
    logger.info("ALL DEPENDENCIES CHECKED SUCCESSFULLY")
    logger.info("=" * 70)
    
    return {
        'status': 'success',
        'missing_vars': [],
        'checks_passed': True
    }


def run_ingestion_task(max_papers: int = 100, categories: list = None, **context) -> Dict[str, Any]:
    """
    Run arXiv paper ingestion.
    
    Args:
        max_papers: Maximum number of papers to ingest
        categories: List of arXiv categories (default: ['cs.AI', 'cs.LG', 'cs.CL'])
        **context: Airflow context
    
    Returns:
        dict: Ingestion summary
    """
    logger.info("=" * 70)
    logger.info("TASK: INGEST ARXIV PAPERS")
    logger.info("=" * 70)
    logger.info(f"Max papers: {max_papers}")
    logger.info(f"Categories: {categories or ['cs.AI', 'cs.LG', 'cs.CL']}")
    
    if categories is None:
        categories = ['cs.AI', 'cs.LG', 'cs.CL']
    
    try:
        from src.pipelines.ingestion import ArxivIngestion
        
        ingestion = ArxivIngestion()
        
        # Fetch metadata
        logger.info("Fetching paper metadata...")
        papers = ingestion.fetch_papers(
            categories=categories,
            max_results=max_papers
        )
        
        logger.info(f"Found {len(papers)} papers")
        
        # Download and upload papers
        successful = 0
        failed = 0
        
        import time
        from tqdm import tqdm
        
        for paper in tqdm(papers, desc="Processing papers"):
            try:
                pdf_path = ingestion.download_pdf(paper)
                
                if pdf_path:
                    if ingestion.upload_to_s3(paper, pdf_path):
                        successful += 1
                    else:
                        failed += 1
                else:
                    failed += 1
                
                # Be nice to arXiv servers
                time.sleep(0.5)
            
            except Exception as e:
                logger.error(f"Error processing {paper.get('arxiv_id', 'unknown')}: {e}")
                failed += 1
        
        summary = {
            'total': len(papers),
            'successful': successful,
            'failed': failed,
            'success_rate': f"{successful/len(papers)*100:.1f}%" if papers else "0%"
        }
        
        logger.info("=" * 70)
        logger.info("INGESTION COMPLETE")
        logger.info(f"Total: {summary['total']}")
        logger.info(f"Successful: {summary['successful']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info(f"Success rate: {summary['success_rate']}")
        logger.info("=" * 70)
        
        # Save summary to data directory
        import json
        from datetime import datetime
        summary['timestamp'] = datetime.now().isoformat()
        summary_path = project_root / 'data' / 'ingestion_summary.json'
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Summary saved to: {summary_path}")
        
        return summary
        
    except Exception as e:
        logger.error(f"Ingestion task failed: {e}", exc_info=True)
        raise


def run_processing_task(**context) -> Dict[str, Any]:
    """
    Process all PDFs in S3 into text chunks.
    
    Args:
        **context: Airflow context
    
    Returns:
        dict: Processing summary
    """
    logger.info("=" * 70)
    logger.info("TASK: PROCESS PDFS INTO CHUNKS")
    logger.info("=" * 70)
    
    try:
        from src.utils.s3_client import S3Client
        from src.utils.pdf_processor import PDFProcessor
        from multiprocessing import Pool
        from tqdm import tqdm
        import json
        from datetime import datetime
        
        NUM_WORKERS = 10
        
        def process_single_paper(args):
            """Process a single paper - designed for multiprocessing"""
            arxiv_id, temp_dir = args
            
            try:
                s3 = S3Client()
                processor = PDFProcessor(chunk_size=512, overlap=50)
                
                # Download PDF from S3
                pdf_s3_key = f"raw/papers/{arxiv_id}.pdf"
                local_pdf = str(Path(temp_dir) / f"{arxiv_id}.pdf")
                Path(local_pdf).parent.mkdir(parents=True, exist_ok=True)
                
                if not s3.download_file(pdf_s3_key, local_pdf):
                    return (arxiv_id, False, 0, "Failed to download PDF")
                
                # Process
                result = processor.process_pdf(
                    local_pdf,
                    extract_tables=False,
                    create_chunks=True,
                    save_intermediates=False
                )
                
                if result['success']:
                    # Upload chunks to S3
                    chunks_data = {
                        'arxiv_id': arxiv_id,
                        'num_chunks': result['chunks']['num_chunks'],
                        'chunks': result['chunks'].get('chunks', [])
                    }
                    
                    chunks_file = str(Path(temp_dir) / f"{arxiv_id}_chunks.json")
                    with open(chunks_file, 'w') as f:
                        json.dump(chunks_data, f)
                    
                    chunks_s3_key = f"processed/text_chunks/{arxiv_id}.json"
                    if s3.upload_file(chunks_file, chunks_s3_key):
                        num_chunks = result['chunks']['num_chunks']
                        
                        # Cleanup
                        Path(local_pdf).unlink(missing_ok=True)
                        Path(chunks_file).unlink(missing_ok=True)
                        
                        return (arxiv_id, True, num_chunks, None)
                    else:
                        return (arxiv_id, False, 0, "Failed to upload chunks")
                else:
                    return (arxiv_id, False, 0, "PDF processing failed")
            
            except Exception as e:
                logger.error(f"Error processing {arxiv_id}: {e}")
                return (arxiv_id, False, 0, str(e))
        
        s3 = S3Client()
        
        # Get all PDFs from S3
        logger.info("Finding papers in S3...")
        all_objects = s3.list_objects('raw/papers/')
        pdf_keys = [o for o in all_objects if o.endswith('.pdf')]
        arxiv_ids = [Path(k).stem for k in pdf_keys]
        
        logger.info(f"Found {len(arxiv_ids)} papers to process")
        
        if not arxiv_ids:
            logger.warning("No papers found to process")
            return {
                'successful': 0,
                'failed': 0,
                'total_chunks': 0,
                'num_workers': NUM_WORKERS
            }
        
        # Create temp directory
        temp_dir = project_root / "temp" / "processing"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare arguments for multiprocessing
        args_list = [(arxiv_id, str(temp_dir)) for arxiv_id in arxiv_ids]
        
        # Process papers in parallel
        successful = 0
        failed = 0
        total_chunks = 0
        
        logger.info(f"Starting parallel processing with {NUM_WORKERS} workers...")
        
        with Pool(processes=NUM_WORKERS) as pool:
            results = list(tqdm(
                pool.imap(process_single_paper, args_list),
                total=len(arxiv_ids),
                desc="Processing papers"
            ))
        
        # Process results
        for arxiv_id, success, num_chunks, error in results:
            if success:
                successful += 1
                total_chunks += num_chunks
            else:
                failed += 1
                if error:
                    logger.debug(f"Failed {arxiv_id}: {error}")
        
        # Cleanup temp directory
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {e}")
        
        summary = {
            'successful': successful,
            'failed': failed,
            'total_chunks': total_chunks,
            'num_workers': NUM_WORKERS,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("=" * 70)
        logger.info("PROCESSING COMPLETE")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Total chunks: {total_chunks:,}")
        logger.info(f"Average chunks per paper: {total_chunks/successful:.1f}" if successful > 0 else "N/A")
        logger.info("=" * 70)
        
        # Save summary
        summary_path = project_root / 'data' / 'processing_summary.json'
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"Summary saved to: {summary_path}")
        
        return summary
        
    except Exception as e:
        logger.error(f"Processing task failed: {e}", exc_info=True)
        raise


def run_embedding_task(**context) -> Dict[str, Any]:
    """
    Generate embeddings for processed chunks and upload to Pinecone.
    
    Args:
        **context: Airflow context
    
    Returns:
        dict: Embedding summary
    """
    logger.info("=" * 70)
    logger.info("TASK: GENERATE EMBEDDINGS AND UPLOAD TO PINECONE")
    logger.info("=" * 70)
    
    try:
        from src.utils.s3_client import S3Client
        from src.utils.openai_client import OpenAIClient
        from pinecone import Pinecone
        from tqdm import tqdm
        from datetime import datetime
        import json
        
        # Validate env vars
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME")
        
        if not pinecone_api_key:
            raise ValueError("PINECONE_API_KEY environment variable is not set")
        if not index_name:
            raise ValueError("PINECONE_INDEX_NAME environment variable is not set")
        
        # Initialize clients
        s3_client = S3Client()
        openai_client = OpenAIClient()
        pc = Pinecone(api_key=pinecone_api_key)
        index = pc.Index(index_name)
        
        # List all processed chunk files in S3
        logger.info("Listing processed chunk files from S3...")
        keys = s3_client.list_objects(prefix="processed/text_chunks/")
        json_keys = [k for k in keys if k.endswith(".json")]
        logger.info(f"Found {len(json_keys)} processed chunk JSON files")
        
        total_vectors = 0
        
        def _extract_texts_from_chunks(chunks):
            """Extract text content from chunks"""
            texts = []
            for chunk in chunks:
                if isinstance(chunk, str):
                    text = chunk.strip()
                elif isinstance(chunk, dict):
                    text = chunk.get("text") or chunk.get("content") or ""
                    text = str(text).strip()
                else:
                    text = str(chunk).strip()
                
                if text:
                    texts.append(text)
            return texts
        
        for key in tqdm(json_keys, desc="Embedding chunk files"):
            try:
                local_path = project_root / "temp" / Path(key).name
                local_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Download JSON from S3
                ok = s3_client.download_file(key, str(local_path))
                if not ok:
                    logger.error(f"Failed to download {key} from S3")
                    continue
                
                with local_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                
                arxiv_id = data.get("arxiv_id") or Path(key).stem
                chunks = data.get("chunks", [])
                if not isinstance(chunks, list) or not chunks:
                    logger.warning(f"No chunks found in {key}")
                    local_path.unlink(missing_ok=True)
                    continue
                
                texts = _extract_texts_from_chunks(chunks)
                if not texts:
                    logger.warning(f"No non-empty texts found in {key}")
                    local_path.unlink(missing_ok=True)
                    continue
                
                # Create embeddings
                emb_resp = openai_client.create_embedding(
                    texts,
                    model="text-embedding-3-small",
                )
                embeddings = emb_resp["embeddings"]
                
                if len(embeddings) != len(texts):
                    logger.warning(
                        f"Embedding count ({len(embeddings)}) does not match text count ({len(texts)}) for {key}"
                    )
                
                # Build vectors with metadata
                vectors = []
                for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                    if isinstance(chunk, str):
                        text_content = chunk
                        chunk_id = f"{arxiv_id}-{i}"
                        title = arxiv_id
                    elif isinstance(chunk, dict):
                        chunk_id = chunk.get("chunk_id") or chunk.get("id") or f"{arxiv_id}-{i}"
                        text_content = chunk.get("text") or chunk.get("content", "")
                        title = chunk.get("title") or arxiv_id
                    else:
                        text_content = str(chunk)
                        chunk_id = f"{arxiv_id}-{i}"
                        title = arxiv_id
                    
                    arxiv_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                    
                    metadata = {
                        "doc_id": str(arxiv_id),
                        "chunk_id": str(chunk_id),
                        "text": str(text_content)[:40000],
                        "title": str(title),
                        "url": str(arxiv_url),
                    }
                    vectors.append((str(chunk_id), emb, metadata))
                
                if not vectors:
                    logger.warning(f"No vectors built for {key}")
                    local_path.unlink(missing_ok=True)
                    continue
                
                # Upsert into Pinecone
                namespace = "research_papers"
                batch_size = 1000
                
                for i in range(0, len(vectors), batch_size):
                    batch = vectors[i:i + batch_size]
                    try:
                        index.upsert(vectors=batch, namespace=namespace)
                        total_vectors += len(batch)
                    except Exception as batch_exc:
                        logger.error(f"Failed to upsert batch from {key}: {batch_exc}")
                        raise
                
                logger.info(f"Upserted {len(vectors)} vectors from {key} into namespace '{namespace}'")
                
                # Cleanup
                local_path.unlink(missing_ok=True)
            
            except Exception as exc:
                logger.exception(f"Failed to embed/upload chunks from {key}: {exc}")
                try:
                    local_path.unlink(missing_ok=True)
                except Exception:
                    pass
        
        summary = {
            'total_vectors': total_vectors,
            'index_name': index_name,
            'namespace': 'research_papers',
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("=" * 70)
        logger.info("EMBEDDING COMPLETE")
        logger.info(f"Total vectors upserted into '{index_name}': {total_vectors}")
        logger.info("=" * 70)
        
        return summary
        
    except Exception as e:
        logger.error(f"Embedding task failed: {e}", exc_info=True)
        raise
