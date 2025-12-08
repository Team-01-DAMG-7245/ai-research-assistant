"""
Complete Data Pipeline Orchestrator

Runs the full pipeline from arXiv ingestion to Pinecone embedding:
1. Ingest papers from arXiv
2. Process PDFs into chunks
3. Generate embeddings and upload to Pinecone

Usage:
    python scripts/run_full_pipeline.py --max-papers 100
"""

import sys
import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_command(script_path, args=None, description=""):
    """
    Run a script and return success status.
    
    Args:
        script_path: Path to the script to run
        args: List of additional arguments
        description: Description of what this step does
    
    Returns:
        bool: True if successful, False otherwise
    """
    if description:
        logger.info(f"\n{'='*70}")
        logger.info(f"{description}")
        logger.info(f"{'='*70}\n")
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            cwd=Path(__file__).parent.parent,
            capture_output=False  # Show output in real-time
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running {script_path}: {e}")
        return False
    except KeyboardInterrupt:
        logger.warning("\nPipeline interrupted by user")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run complete data pipeline: ingestion → processing → embedding"
    )
    parser.add_argument(
        '--max-papers',
        type=int,
        default=100,
        help='Maximum number of papers to ingest (default: 100)'
    )
    parser.add_argument(
        '--skip-ingestion',
        action='store_true',
        help='Skip ingestion step (use existing papers in S3)'
    )
    parser.add_argument(
        '--skip-processing',
        action='store_true',
        help='Skip processing step (use existing chunks in S3)'
    )
    parser.add_argument(
        '--skip-embedding',
        action='store_true',
        help='Skip embedding step'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompts'
    )
    
    args = parser.parse_args()
    
    # Project root
    project_root = Path(__file__).parent.parent
    scripts_dir = project_root / "scripts"
    
    # Ensure data and logs directories exist
    (project_root / "data").mkdir(exist_ok=True)
    (project_root / "logs").mkdir(exist_ok=True)
    
    logger.info("\n" + "="*70)
    logger.info("AI RESEARCH ASSISTANT - FULL PIPELINE")
    logger.info("="*70)
    logger.info(f"Max papers: {args.max_papers}")
    logger.info(f"Skip ingestion: {args.skip_ingestion}")
    logger.info(f"Skip processing: {args.skip_processing}")
    logger.info(f"Skip embedding: {args.skip_embedding}")
    logger.info("="*70)
    
    # Confirm before starting (unless --yes flag)
    if not args.yes:
        try:
            confirm = input("\nProceed with full pipeline? (y/n): ").strip().lower()
            if confirm != 'y':
                logger.info("Cancelled.")
                return
        except (EOFError, KeyboardInterrupt):
            logger.info("\nCancelled.")
            return
    
    start_time = datetime.now()
    steps_completed = []
    steps_failed = []
    
    # Step 1: Ingestion
    if not args.skip_ingestion:
        ingestion_args = ['--max-papers', str(args.max_papers)]
        if args.yes:
            ingestion_args.append('--yes')
        
        success = run_command(
            scripts_dir / "ingest_arxiv_papers.py",
            args=ingestion_args,
            description="STEP 1: INGESTING PAPERS FROM ARXIV"
        )
        
        if success:
            steps_completed.append("Ingestion")
        else:
            steps_failed.append("Ingestion")
            logger.error("Ingestion failed. Stopping pipeline.")
            return
    else:
        logger.info("\n⏭️  Skipping ingestion step")
        steps_completed.append("Ingestion (skipped)")
    
    # Step 2: Processing
    if not args.skip_processing:
        success = run_command(
            scripts_dir / "process_all_paper.py",
            description="STEP 2: PROCESSING PDFS INTO CHUNKS"
        )
        
        if success:
            steps_completed.append("Processing")
        else:
            steps_failed.append("Processing")
            logger.error("Processing failed. Stopping pipeline.")
            return
    else:
        logger.info("\n⏭️  Skipping processing step")
        steps_completed.append("Processing (skipped)")
    
    # Step 3: Embedding
    if not args.skip_embedding:
        success = run_command(
            scripts_dir / "embed_chunks_to_pinecone.py",
            description="STEP 3: GENERATING EMBEDDINGS AND UPLOADING TO PINECONE"
        )
        
        if success:
            steps_completed.append("Embedding")
        else:
            steps_failed.append("Embedding")
            logger.error("Embedding failed.")
    else:
        logger.info("\n⏭️  Skipping embedding step")
        steps_completed.append("Embedding (skipped)")
    
    # Final summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info("\n" + "="*70)
    logger.info("PIPELINE COMPLETE")
    logger.info("="*70)
    logger.info(f"Duration: {duration}")
    logger.info(f"Steps completed: {', '.join(steps_completed)}")
    if steps_failed:
        logger.warning(f"Steps failed: {', '.join(steps_failed)}")
    logger.info("="*70)
    
    if not steps_failed:
        logger.info("\n✅ All pipeline steps completed successfully!")
        logger.info("\nNext steps:")
        logger.info("  1. Start the API server: python src/api/main.py")
        logger.info("  2. Test the API: curl http://localhost:8000/health")
    else:
        logger.error("\n❌ Pipeline completed with errors. Please check logs above.")


if __name__ == "__main__":
    main()
