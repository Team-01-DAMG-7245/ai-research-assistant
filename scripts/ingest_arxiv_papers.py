"""
Production arXiv Paper Ingestion
Fetches 500 papers with progress tracking

Usage:
    python scripts/ingest_arxiv_papers.py --max-papers 500
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import json
import time
from datetime import datetime
from tqdm import tqdm
import logging
from src.pipelines.ingestion import ArxivIngestion

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

Path('logs').mkdir(exist_ok=True)
Path('data').mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-papers', type=int, default=None)
    parser.add_argument('--categories', nargs='+', default=None)
    args = parser.parse_args()
    
    # Interactive mode if arguments not provided
    if args.max_papers is None:
        print("\n" + "="*70)
        print("arXiv Paper Ingestion for aiRA Research Assistant")
        print("="*70)
        print("\nRecommended paper counts:")
        print("  - 100 papers: ~15-20 min (good for quick testing)")
        print("  - 200 papers: ~30-40 min (balanced)")
        print("  - 500 papers: ~2-3 hours (substantial dataset)")
        print("  - 1000 papers: ~4-6 hours (large dataset)")
        print("  - 5000 papers: ~8-12 hours (full proposal target)")
        
        while True:
            try:
                max_papers = int(input("\nHow many papers do you want to ingest? "))
                if max_papers > 0:
                    break
                print("Please enter a positive number")
            except ValueError:
                print("Please enter a valid number")
    else:
        max_papers = args.max_papers
    
    if args.categories is None:
        print("\nDefault categories: cs.AI, cs.LG, cs.CL")
        use_default = input("Use default categories? (y/n): ").strip().lower()
        
        if use_default == 'y':
            categories = ['cs.AI', 'cs.LG', 'cs.CL']
        else:
            print("\nAvailable CS categories:")
            print("  cs.AI  - Artificial Intelligence")
            print("  cs.LG  - Machine Learning")
            print("  cs.CL  - Computation and Language")
            print("  cs.CV  - Computer Vision")
            print("  cs.NE  - Neural and Evolutionary Computing")
            cats = input("Enter categories (space-separated): ").strip().split()
            categories = cats if cats else ['cs.AI', 'cs.LG', 'cs.CL']
    else:
        categories = args.categories
    
    # Estimate time
    est_minutes = max_papers * 0.15  # ~9 seconds per paper
    
    print("\n" + "="*70)
    print("STARTING INGESTION")
    print("="*70)
    print(f"Papers to fetch: {max_papers}")
    print(f"Categories: {', '.join(categories)}")
    print(f"Estimated time: ~{est_minutes:.0f} minutes")
    print("="*70)
    
    # Confirm
    confirm = input("\nProceed? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Cancelled.")
        return
    
    print()
    
    # Run ingestion
    logger.info("="*70)
    logger.info(f"Starting ingestion: {max_papers} papers")
    logger.info(f"Categories: {categories}")
    logger.info("="*70)
    
    ingestion = ArxivIngestion()
    
    # Fetch metadata
    logger.info(f"\n📚 Fetching metadata...")
    papers = ingestion.fetch_papers(
        categories=categories,
        max_results=max_papers
    )
    
    logger.info(f"Found {len(papers)} papers\n")
    
    # Download and upload with progress bar
    successful = 0
    failed = 0
    
    for paper in tqdm(papers, desc="Processing papers"):
        try:
            # Download
            pdf_path = ingestion.download_pdf(paper)
            
            if pdf_path:
                # Upload to S3
                if ingestion.upload_to_s3(paper, pdf_path):
                    successful += 1
                else:
                    failed += 1
            else:
                failed += 1
            
            # Be nice to arXiv servers
            time.sleep(0.5)
        
        except Exception as e:
            logger.error(f"Error: {e}")
            failed += 1
    
    # Summary
    summary = {
        'total': len(papers),
        'successful': successful,
        'failed': failed,
        'success_rate': f"{successful/len(papers)*100:.1f}%",
        'timestamp': datetime.now().isoformat()
    }
    
    logger.info("\n" + "="*70)
    logger.info("INGESTION COMPLETE")
    logger.info("="*70)
    logger.info(f"Total: {summary['total']}")
    logger.info(f"Successful: {summary['successful']}")
    logger.info(f"Failed: {summary['failed']}")
    logger.info(f"Success rate: {summary['success_rate']}")
    logger.info("="*70)
    
    # Save summary
    with open('data/ingestion_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✅ Summary saved to: data/ingestion_summary.json")
    print(f"\n🎉 M2 Ingestion Complete! Next: Run processing script")
    print(f"   python scripts/process_all_papers.py")


if __name__ == "__main__":
    main()