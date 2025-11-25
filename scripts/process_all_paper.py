"""
Process all downloaded papers into chunks
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tqdm import tqdm
import json
import logging
from src.utils.s3_client import S3Client
from src.utils.pdf_processor import PDFProcessor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("="*70)
    logger.info("PROCESSING PAPERS INTO CHUNKS")
    logger.info("="*70)
    
    s3 = S3Client()
    processor = PDFProcessor(chunk_size=512, overlap=50)
    
    # Get all PDFs from S3
    logger.info("\n📂 Finding papers in S3...")
    all_objects = s3.list_objects('raw/papers/')
    pdf_keys = [o for o in all_objects if o.endswith('.pdf')]
    arxiv_ids = [Path(k).stem for k in pdf_keys]
    
    logger.info(f"Found {len(arxiv_ids)} papers to process\n")
    
    successful = 0
    failed = 0
    total_chunks = 0
    
    for arxiv_id in tqdm(arxiv_ids, desc="Processing papers"):
        try:
            # Download PDF from S3
            pdf_s3_key = f"raw/papers/{arxiv_id}.pdf"
            local_pdf = f"./temp/{arxiv_id}.pdf"
            Path(local_pdf).parent.mkdir(parents=True, exist_ok=True)
            
            s3.download_file(pdf_s3_key, local_pdf)
            
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
                
                chunks_file = f"./temp/{arxiv_id}_chunks.json"
                with open(chunks_file, 'w') as f:
                    json.dump(chunks_data, f)
                
                chunks_s3_key = f"processed/text_chunks/{arxiv_id}.json"
                s3.upload_file(chunks_file, chunks_s3_key)
                
                successful += 1
                total_chunks += result['chunks']['num_chunks']
                
                # Cleanup
                Path(local_pdf).unlink(missing_ok=True)
                Path(chunks_file).unlink(missing_ok=True)
            else:
                failed += 1
        
        except Exception as e:
            logger.error(f"Error processing {arxiv_id}: {e}")
            failed += 1
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("PROCESSING COMPLETE")
    logger.info("="*70)
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total chunks: {total_chunks:,}")
    logger.info("="*70)
    
    summary = {
        'successful': successful,
        'failed': failed,
        'total_chunks': total_chunks,
        'timestamp': datetime.now().isoformat()
    }
    
    with open('data/processing_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()