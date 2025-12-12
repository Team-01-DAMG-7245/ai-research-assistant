"""
Utilities for arXiv API interactions
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import arxiv

logger = logging.getLogger(__name__)


def query_arxiv_papers(
    categories: List[str] = None,
    hours_back: int = 24,
    max_results: int = 100
) -> List[Dict[str, Any]]:
    """
    Query arXiv API for papers published in the last N hours.
    
    Args:
        categories: List of arXiv categories (e.g., ['cs.AI', 'cs.LG'])
        hours_back: Number of hours to look back
        max_results: Maximum number of results to return
    
    Returns:
        List of paper dictionaries with metadata
    """
    if categories is None:
        categories = ['cs.AI', 'cs.LG', 'cs.CL', 'cs.CV']
    
    try:
        # Calculate date threshold
        cutoff_date = datetime.now() - timedelta(hours=hours_back)
        
        # Build query string
        category_query = ' OR '.join([f'cat:{cat}' for cat in categories])
        query = f'({category_query}) AND submittedDate:[{cutoff_date.strftime("%Y%m%d")}000000 TO {datetime.now().strftime("%Y%m%d")}235959]'
        
        logger.info(f"Querying arXiv with: {query}")
        
        # Search arXiv
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        papers = []
        for result in search.results():
            # Filter by submitted date
            if result.published and result.published.replace(tzinfo=None) >= cutoff_date:
                paper_data = {
                    'arxiv_id': result.entry_id.split('/')[-1],
                    'title': result.title,
                    'authors': [author.name for author in result.authors],
                    'published': result.published.isoformat() if result.published else None,
                    'summary': result.summary,
                    'pdf_url': result.pdf_url,
                    'entry_id': result.entry_id
                }
                papers.append(paper_data)
                logger.info(f"Found paper: {paper_data['arxiv_id']} - {paper_data['title'][:50]}")
        
        logger.info(f"Total papers found: {len(papers)}")
        return papers
        
    except Exception as e:
        logger.error(f"Error querying arXiv: {e}", exc_info=True)
        raise


def download_arxiv_pdf(arxiv_id: str, output_path: str, delay: float = 3.0) -> str:
    """
    Download a PDF from arXiv.
    
    Args:
        arxiv_id: arXiv paper ID (e.g., '2301.12345')
        output_path: Local path to save PDF
        delay: Delay between downloads (rate limiting)
    
    Returns:
        Path to downloaded file
    """
    import requests
    import os
    
    try:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        logger.info(f"Downloading PDF: {pdf_url}")
        
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Downloaded PDF to: {output_path}")
        time.sleep(delay)  # Rate limiting
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error downloading PDF {arxiv_id}: {e}", exc_info=True)
        raise
