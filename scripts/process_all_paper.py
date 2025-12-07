"""
Process all downloaded papers into chunks with parallel processing (10 workers)
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tqdm import tqdm
import json
import logging
from datetime import datetime
from multiprocessing import Pool, Manager
from functools import partial
from src.utils.s3_client import S3Client
from src.utils.pdf_processor import PDFProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Number of worker processes
NUM_WORKERS = 10


def process_single_paper(args):
    """
    Process a single paper - designed for multiprocessing
    
    Args:
        args: Tuple of (arxiv_id, temp_dir)
    
    Returns:
        Tuple of (arxiv_id, success, num_chunks, error_message)
    """
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
            extract_tables=False,  # Skip tables for speed
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


def main():
    logger.info("="*70)
    logger.info("PROCESSING PAPERS INTO CHUNKS (Parallel Processing)")
    logger.info("="*70)
    logger.info(f"Using {NUM_WORKERS} worker processes\n")
    
    s3 = S3Client()
    
    # Get all PDFs from S3
    logger.info("📂 Finding papers in S3...")
    all_objects = s3.list_objects('raw/papers/')
    pdf_keys = [o for o in all_objects if o.endswith('.pdf')]
    arxiv_ids = [Path(k).stem for k in pdf_keys]
    
    logger.info(f"Found {len(arxiv_ids)} papers to process\n")
    
    if not arxiv_ids:
        logger.warning("No papers found to process")
        return
    
    # Create temp directory for this run
    temp_dir = Path("./temp/processing")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare arguments for multiprocessing
    args_list = [(arxiv_id, str(temp_dir)) for arxiv_id in arxiv_ids]
    
    # Process papers in parallel
    successful = 0
    failed = 0
    total_chunks = 0
    
    logger.info(f"Starting parallel processing with {NUM_WORKERS} workers...")
    
    with Pool(processes=NUM_WORKERS) as pool:
        # Use imap for progress tracking
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
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("PROCESSING COMPLETE")
    logger.info("="*70)
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total chunks: {total_chunks:,}")
    logger.info(f"Average chunks per paper: {total_chunks/successful:.1f}" if successful > 0 else "N/A")
    logger.info("="*70)
    
    summary = {
        'successful': successful,
        'failed': failed,
        'total_chunks': total_chunks,
        'num_workers': NUM_WORKERS,
        'timestamp': datetime.now().isoformat()
    }
    
    with open('data/processing_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"\n✅ Summary saved to: data/processing_summary.json")


if __name__ == "__main__":
    main()