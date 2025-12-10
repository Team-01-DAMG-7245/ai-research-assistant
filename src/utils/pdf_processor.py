"""
PDF Processor - Orchestrates text and table extraction
"""

from pathlib import Path
from typing import Dict, Optional, List
import json
import logging
from .extract_pdf_text import PDFTextExtractor
from .extract_tables_hybrid import PDFTableExtractor

logging.basicConfig(level=logging.INFO)


class PDFProcessor:
    """
    Complete PDF processing pipeline
    Combines text extraction, table extraction, and chunking
    """

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 50,
        table_threshold: int = 22,
    ):
        """
        Initialize PDF processor

        Args:
            chunk_size: Words per chunk
            overlap: Overlapping words between chunks
            table_threshold: Threshold for camelot lattice/stream decision
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

        self.text_extractor = PDFTextExtractor()
        self.table_extractor = PDFTableExtractor(threshold=table_threshold)

        # Layout detection - DISABLED (removed from project)
        self.layout_detector = None

        self.logger = logging.getLogger(__name__)

    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks"""
        words = text.split()
        chunks = []

        if len(words) <= self.chunk_size:
            return [text] if text else []

        start = 0
        while start < len(words):
            end = start + self.chunk_size
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start = end - self.overlap

            if end >= len(words):
                break

        return chunks

    def process_pdf(
        self,
        pdf_path: str,
        extract_tables: bool = True,
        extract_layout: bool = False,  # Layout detection disabled
        create_chunks: bool = True,
        save_intermediates: bool = False,
        output_dir: Optional[str] = None,
    ) -> Dict:
        """
        Process PDF through complete pipeline

        Args:
            pdf_path: Path to PDF file
            extract_tables: Whether to extract tables
            extract_layout: Whether to detect layout (disabled - feature removed)
            create_chunks: Whether to chunk text
            save_intermediates: Whether to save intermediate files
            output_dir: Base output directory for intermediate files

        Returns:
            Complete processing results
        """
        pdf_path = Path(pdf_path)
        self.logger.info(f"Processing PDF: {pdf_path.name}")

        # Set up output directories
        text_dir = None
        table_dir = None

        if save_intermediates and output_dir:
            text_dir = Path(output_dir) / "text"
            table_dir = Path(output_dir) / "tables"

        # 1. Extract text
        self.logger.info("Step 1/3: Extracting text...")
        text_result = self.text_extractor.extract_pdf(
            str(pdf_path), output_dir=text_dir
        )

        # Combine all text
        full_text = "\n\n".join(
            [page["text"] for page in text_result["pages"] if page["text"]]
        )

        # 2. Create chunks
        chunks = []
        if create_chunks and full_text:
            self.logger.info("Step 2/3: Creating text chunks...")
            chunks = self.chunk_text(full_text)
            self.logger.info(f"Created {len(chunks)} chunks")
        else:
            self.logger.info("Step 2/3: Skipping chunking")

        # 3. Extract tables
        table_result = None
        if extract_tables:
            self.logger.info("Step 3/3: Extracting tables...")
            table_result = self.table_extractor.extract_tables_from_pdf(
                str(pdf_path), output_dir=table_dir
            )
        else:
            self.logger.info("Step 3/3: Skipping table extraction")

        # Compile results
        result = {
            "success": True,
            "pdf_name": pdf_path.name,
            "text_extraction": {
                "total_pages": text_result["total_pages"],
                "ocr_pages": text_result["ocr_pages"],
                "total_ocr_pages": text_result["total_ocr_pages"],
                "full_text_length": len(full_text),
            },
            "chunks": {
                "num_chunks": len(chunks),
                "chunk_size": self.chunk_size,
                "overlap": self.overlap,
                "chunks": chunks,  # Include actual chunks list
            },
        }

        if table_result:
            result["table_extraction"] = {
                "total_tables": table_result["total_tables"],
                "pages_with_tables": len(
                    [
                        p
                        for p in table_result["pages_processed"]
                        if p["tables_found"] > 0
                    ]
                ),
            }

        # Layout detection results removed (feature disabled)

        self.logger.info(f"✅ Processing complete: {pdf_path.name}")
        return result


# Test with all features
if __name__ == "__main__":
    processor = PDFProcessor(chunk_size=512, overlap=50)

    result = processor.process_pdf(
        "./data/raw/test.pdf",
        extract_tables=True,
        extract_layout=False,  # Layout detection disabled
        create_chunks=True,
        save_intermediates=True,
        output_dir="./data/processed",
    )

    print(json.dumps(result, indent=2))
