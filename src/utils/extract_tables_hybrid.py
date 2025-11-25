"""
Hybrid Table Extraction using Camelot
"""

import camelot
import pdfplumber
from pathlib import Path
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)


class PDFTableExtractor:
    """Extract tables from PDFs using hybrid lattice/stream approach"""
    
    def __init__(self, threshold: int = 22):
        """
        Initialize table extractor
        
        Args:
            threshold: Number of lines/curves to determine lattice vs stream
        """
        self.threshold = threshold
        self.logger = logging.getLogger(__name__)
    
    def count_rules(self, pdf_path: str, page_num: int) -> int:
        """
        Count lines and curves on a page to determine table type
        
        Args:
            pdf_path: Path to PDF
            page_num: Page number (1-indexed)
        
        Returns:
            Count of lines + curves
        """
        with pdfplumber.open(pdf_path) as doc:
            page = doc.pages[page_num - 1]
            return len(page.lines) + len(page.curves)
    
    def extract_tables_from_page(
        self,
        pdf_path: str,
        page_num: int
    ) -> Dict:
        """
        Extract tables from a specific page using hybrid approach
        
        Args:
            pdf_path: Path to PDF
            page_num: Page number (1-indexed)
        
        Returns:
            Dictionary with extracted tables and metadata
        """
        # Determine flavor based on rule count
        rule_count = self.count_rules(pdf_path, page_num)
        flavor = "lattice" if rule_count >= self.threshold else "stream"
        
        self.logger.info(f"Page {page_num}: {rule_count} rules, using {flavor}")
        
        # Try extraction with determined flavor
        tables = camelot.read_pdf(
            pdf_path,
            flavor=flavor,
            pages=str(page_num)
        )
        
        # Fallback to stream if lattice found nothing
        if tables.n == 0 and flavor == "lattice":
            self.logger.info(f"Page {page_num}: Lattice found nothing, trying stream")
            tables = camelot.read_pdf(
                pdf_path,
                flavor="stream",
                pages=str(page_num)
            )
            flavor = "stream"
        
        # Convert to list of DataFrames
        extracted_tables = []
        for i, table in enumerate(tables):
            extracted_tables.append({
                'table_id': i,
                'dataframe': table.df,
                'shape': table.df.shape,
                'accuracy': table.accuracy if hasattr(table, 'accuracy') else None
            })
        
        return {
            'page_number': page_num,
            'flavor': flavor,
            'rule_count': rule_count,
            'tables_found': len(extracted_tables),
            'tables': extracted_tables
        }
    
    def extract_tables_from_pdf(
        self,
        pdf_path: str,
        pages: List[int] = None,
        output_dir: str = None
    ) -> Dict:
        """
        Extract tables from entire PDF or specific pages
        
        Args:
            pdf_path: Path to PDF
            pages: List of page numbers (None = all pages)
            output_dir: Optional directory to save CSV files
        
        Returns:
            Dictionary with all extracted tables
        """
        pdf_path = Path(pdf_path)
        
        # Determine pages to process
        if pages is None:
            with pdfplumber.open(pdf_path) as doc:
                pages = list(range(1, len(doc.pages) + 1))
        
        if output_dir:
            output_dir = Path(output_dir) / pdf_path.stem
            output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            'pdf_name': pdf_path.name,
            'pages_processed': [],
            'total_tables': 0
        }
        
        for page_num in pages:
            try:
                page_result = self.extract_tables_from_page(str(pdf_path), page_num)
                results['pages_processed'].append(page_result)
                results['total_tables'] += page_result['tables_found']
                
                # Save tables to CSV if output_dir specified
                if output_dir and page_result['tables']:
                    for table_data in page_result['tables']:
                        filename = (
                            f"{pdf_path.stem}_p{page_num:03d}_"
                            f"{page_result['flavor']}_{table_data['table_id']:02d}.csv"
                        )
                        csv_path = output_dir / filename
                        table_data['dataframe'].to_csv(csv_path, index=False)
                        self.logger.info(f"Saved table: {filename}")
                
            except Exception as e:
                self.logger.error(f"Error on page {page_num}: {e}")
                continue
        
        self.logger.info(f"Extracted {results['total_tables']} tables from {len(pages)} pages")
        
        return results


def expand_pages(page_str: str) -> List[int]:
    """
    Parse page string like '1-5,7,9-12' into list of page numbers
    
    Args:
        page_str: Page specification string
    
    Returns:
        List of page numbers
    """
    pages = []
    for chunk in page_str.split(","):
        if "-" in chunk:
            start, end = chunk.split("-")
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(chunk))
    return pages


# Quick test
if __name__ == "__main__":
    extractor = PDFTableExtractor(threshold=22)
    
    # Test with specific pages
    result = extractor.extract_tables_from_pdf(
        "./data/raw/test.pdf",
        pages=[1, 2, 3],
        output_dir="./data/processed/tables"
    )
    
    print(f"Extracted {result['total_tables']} tables")