"""
arXiv Paper Ingestion Pipeline
Fetches papers and uploads to S3
"""

import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import arxiv
from typing import List, Dict, Optional
import logging
import json
from datetime import datetime
from src.utils.s3_client import S3Client

logging.basicConfig(level=logging.INFO)


class ArxivIngestion:
    """Fetch papers from arXiv and store in S3"""

    def __init__(self, s3_client: Optional[S3Client] = None):
        """
        Initialize arXiv ingestion pipeline

        Args:
            s3_client: S3Client instance (creates new if None)
        """
        self.s3 = s3_client or S3Client()
        self.logger = logging.getLogger(__name__)
        self.temp_dir = Path("./data/raw")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def fetch_papers(
        self,
        categories: List[str] = None,
        max_results: int = 100,
        query: Optional[str] = None,
    ) -> List[Dict]:
        """
        Fetch papers from arXiv

        Args:
            categories: List of arXiv categories (e.g., ['cs.AI', 'cs.LG'])
            max_results: Maximum number of papers to fetch
            query: Optional custom query string

        Returns:
            List of paper metadata dictionaries
        """
        if categories is None:
            categories = ["cs.AI", "cs.LG", "cs.CL"]

        # Build query
        if query:
            search_query = query
        else:
            cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
            search_query = cat_query

        self.logger.info(
            f"Fetching up to {max_results} papers with query: {search_query}"
        )

        # Create search
        search = arxiv.Search(
            query=search_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

        papers = []
        for i, result in enumerate(search.results(), 1):
            try:
                paper_data = {
                    "arxiv_id": result.entry_id.split("/")[-1],
                    "title": result.title,
                    "authors": [author.name for author in result.authors],
                    "abstract": result.summary,
                    "categories": result.categories,
                    "published": result.published.isoformat(),
                    "updated": result.updated.isoformat(),
                    "pdf_url": result.pdf_url,
                    "fetched_at": datetime.now().isoformat(),
                }
                papers.append(paper_data)

                if i % 10 == 0:
                    self.logger.info(f"Fetched {i}/{max_results} papers...")

            except Exception as e:
                self.logger.error(f"Error processing paper: {e}")
                continue

        self.logger.info(f"Successfully fetched {len(papers)} papers")
        return papers

    def download_pdf(self, paper_data: Dict) -> Optional[str]:
        """
        Download PDF for a paper

        Args:
            paper_data: Paper metadata dictionary

        Returns:
            Path to downloaded PDF, or None if failed
        """
        arxiv_id = paper_data["arxiv_id"]
        local_path = self.temp_dir / f"{arxiv_id}.pdf"

        try:
            # Create search with just this paper ID
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(search.results())

            # Download PDF
            paper.download_pdf(dirpath=str(self.temp_dir), filename=f"{arxiv_id}.pdf")

            self.logger.info(f"Downloaded PDF: {arxiv_id}")
            return str(local_path)

        except Exception as e:
            self.logger.error(f"Failed to download {arxiv_id}: {e}")
            return None

    def upload_to_s3(self, paper_data: Dict, local_pdf_path: str) -> bool:
        """
        Upload paper PDF and metadata to S3

        Args:
            paper_data: Paper metadata
            local_pdf_path: Path to local PDF file

        Returns:
            True if successful
        """
        arxiv_id = paper_data["arxiv_id"]

        # Upload PDF
        pdf_s3_key = f"raw/papers/{arxiv_id}.pdf"
        pdf_success = self.s3.upload_file(local_pdf_path, pdf_s3_key)

        # Upload metadata
        metadata_path = self.temp_dir / f"{arxiv_id}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(paper_data, f, indent=2)

        metadata_s3_key = f"raw/papers/{arxiv_id}_metadata.json"
        metadata_success = self.s3.upload_file(str(metadata_path), metadata_s3_key)

        # Clean up local files
        Path(local_pdf_path).unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)

        return pdf_success and metadata_success

    def run_pipeline(
        self, categories: List[str] = None, max_results: int = 100
    ) -> Dict:
        """
        Run the complete ingestion pipeline

        Args:
            categories: arXiv categories to fetch
            max_results: Maximum number of papers

        Returns:
            Summary statistics
        """
        self.logger.info("Starting arXiv ingestion pipeline...")

        # Fetch paper metadata
        papers = self.fetch_papers(categories=categories, max_results=max_results)

        # Download and upload each paper
        success_count = 0
        failed_count = 0

        for i, paper in enumerate(papers, 1):
            arxiv_id = paper["arxiv_id"]

            # Download PDF
            pdf_path = self.download_pdf(paper)

            if pdf_path:
                # Upload to S3
                if self.upload_to_s3(paper, pdf_path):
                    success_count += 1
                else:
                    failed_count += 1
            else:
                failed_count += 1

            if i % 10 == 0:
                self.logger.info(f"Progress: {i}/{len(papers)} papers processed")

        summary = {
            "total_fetched": len(papers),
            "successfully_uploaded": success_count,
            "failed": failed_count,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.info(f"Pipeline complete: {summary}")
        return summary


# Usage
if __name__ == "__main__":
    ingestion = ArxivIngestion()

    # Test with just 5 papers
    summary = ingestion.run_pipeline(categories=["cs.AI", "cs.LG"], max_results=5)

    print(f"\n✅ Ingestion complete!")
    print(f"   Uploaded: {summary['successfully_uploaded']} papers")
    print(f"   Failed: {summary['failed']} papers")
