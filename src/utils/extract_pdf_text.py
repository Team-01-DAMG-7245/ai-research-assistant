"""
PDF Text Extraction with OCR Fallback
"""

import pdfplumber
import pytesseract
from pathlib import Path
import json
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)


class PDFTextExtractor:
    """Extract text from PDFs with OCR fallback and word bounding boxes"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def extract_page_text(
        self, page, page_num: int, use_ocr_fallback: bool = True
    ) -> Dict:
        """
        Extract text from a single PDF page

        Args:
            page: pdfplumber page object
            page_num: Page number (1-indexed)
            use_ocr_fallback: Whether to use OCR if no text found

        Returns:
            Dictionary with text, bounding boxes, and metadata
        """
        # Extract text using pdfplumber with layout parameters
        text = page.extract_text(x_density=2.0, y_density=2.0)

        used_ocr = False

        # OCR fallback if no text found
        if (not text or not text.strip()) and use_ocr_fallback:
            self.logger.info(f"Page {page_num}: No text found, applying OCR...")
            try:
                img = page.to_image(resolution=300)
                pil_image = img.original
                text = pytesseract.image_to_string(pil_image, config="--psm 6")
                used_ocr = True
            except Exception as e:
                self.logger.error(f"OCR failed on page {page_num}: {e}")
                text = ""

        # Extract word bounding boxes
        word_bboxes = []
        try:
            words = page.extract_words()
            word_bboxes = [
                {
                    "text": word["text"],
                    "x0": word["x0"],
                    "y0": word["y0"],
                    "x1": word["x1"],
                    "y1": word["y1"],
                    "fontname": word.get("fontname", ""),
                    "size": word.get("size", 0),
                }
                for word in words
            ]
        except Exception as e:
            self.logger.warning(f"Could not extract word bboxes: {e}")

        return {
            "page_number": page_num,
            "text": text,
            "word_bboxes": word_bboxes,
            "word_count": len(word_bboxes),
            "used_ocr": used_ocr,
        }

    def extract_pdf(self, pdf_path: str, output_dir: Optional[str] = None) -> Dict:
        """
        Extract text from entire PDF

        Args:
            pdf_path: Path to PDF file
            output_dir: Optional directory to save per-page outputs

        Returns:
            Dictionary with all pages' data
        """
        pdf_path = Path(pdf_path)

        if output_dir:
            output_dir = Path(output_dir) / pdf_path.stem
            output_dir.mkdir(parents=True, exist_ok=True)

        results = {"pdf_name": pdf_path.name, "pages": [], "ocr_pages": []}

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            self.logger.info(f"Processing {pdf_path.name}: {total_pages} pages")

            for page_num, page in enumerate(pdf.pages, 1):
                page_data = self.extract_page_text(page, page_num)
                results["pages"].append(page_data)

                if page_data["used_ocr"]:
                    results["ocr_pages"].append(page_num)

                # Save individual page if output_dir specified
                if output_dir:
                    # Save text
                    page_file = output_dir / f"page_{page_num:03d}.txt"
                    page_file.write_text(page_data["text"], encoding="utf-8")

                    # Save bounding boxes
                    if page_data["word_bboxes"]:
                        bbox_file = output_dir / f"page_{page_num:03d}_bboxes.json"
                        bbox_file.write_text(
                            json.dumps(
                                {
                                    "page_number": page_num,
                                    "word_count": page_data["word_count"],
                                    "words": page_data["word_bboxes"],
                                },
                                indent=2,
                            )
                        )

        results["total_pages"] = len(results["pages"])
        results["total_ocr_pages"] = len(results["ocr_pages"])

        self.logger.info(
            f"Extraction complete: {results['total_ocr_pages']} pages used OCR"
        )

        return results


# Quick test
if __name__ == "__main__":
    extractor = PDFTextExtractor()

    # Test with a sample PDF
    result = extractor.extract_pdf(
        "./data/raw/test.pdf", output_dir="./data/processed/text"
    )

    print(f"Extracted {result['total_pages']} pages")
    print(f"OCR used on {result['total_ocr_pages']} pages")
