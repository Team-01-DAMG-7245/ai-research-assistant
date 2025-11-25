"""
PDF Layout Detection using LayoutParser
"""

import cv2
import json
import numpy as np
from pathlib import Path
from PIL import Image
import pdfplumber
from typing import Dict, List, Optional
import logging

try:
    import layoutparser as lp
    import torch
    LAYOUT_AVAILABLE = True
except ImportError:
    LAYOUT_AVAILABLE = False

logging.basicConfig(level=logging.INFO)


class PDFLayoutDetector:
    """Detect document layout using PubLayNet model"""
    
    def __init__(self, model_dir: str = "publaynet-model"):
        """
        Initialize layout detector
        
        Args:
            model_dir: Directory containing PubLayNet model files
        """
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.model_dir = Path(model_dir)
        
        if not LAYOUT_AVAILABLE:
            self.logger.warning("layoutparser or torch not available. Layout detection disabled.")
            return
        
        # Load model with fallback strategies
        self.model = self._load_robust_model()
        
        if self.model is None:
            self.logger.warning("Failed to load layout model. Layout detection disabled.")
    
    def _load_robust_model(self):
        """Load model with version compatibility handling"""
        if not self.model_dir.exists():
            self.logger.error(f"Model directory not found: {self.model_dir}")
            return None
        
        config_files = list(self.model_dir.glob("*.yaml")) + list(self.model_dir.glob("*.yml"))
        weight_files = list(self.model_dir.glob("*.pth"))
        
        if not config_files or not weight_files:
            self.logger.error("Missing config or weight files")
            return None
        
        config_path = config_files[0]
        weight_path = weight_files[0]
        
        self.logger.info(f"Loading model from {self.model_dir}")
        
        # Try standard loading
        try:
            model = lp.Detectron2LayoutModel(
                config_path=str(config_path),
                model_path=str(weight_path),
                extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.3],
                label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
            )
            self.logger.info("Model loaded successfully")
            return model
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            return None
    
    def detect_page_layout(
        self,
        page,
        page_num: int,
        resolution: int = 200
    ) -> Dict:
        """
        Detect layout blocks on a single page
        
        Args:
            page: pdfplumber page object
            page_num: Page number (1-indexed)
            resolution: Image resolution for detection
        
        Returns:
            Dictionary with detected blocks
        """
        if self.model is None:
            return {
                'page_number': page_num,
                'blocks': [],
                'error': 'Model not loaded'
            }
        
        try:
            # Convert page to image
            img = page.to_image(resolution=resolution)
            pil_image = img.original
            opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            # Detect layout
            layout = self.model.detect(opencv_image)
            
            # Process blocks
            blocks = []
            for idx, block in enumerate(layout):
                x1, y1, x2, y2 = block.coordinates
                
                blocks.append({
                    "block_id": idx,
                    "type": str(block.type),
                    "confidence": float(block.score),
                    "bbox": {
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2)
                    },
                    "width": float(x2 - x1),
                    "height": float(y2 - y1)
                })
            
            # Count by type
            block_counts = {}
            for b in blocks:
                block_type = b["type"]
                block_counts[block_type] = block_counts.get(block_type, 0) + 1
            
            return {
                'page_number': page_num,
                'total_blocks': len(blocks),
                'blocks': blocks,
                'block_types': block_counts
            }
            
        except Exception as e:
            self.logger.error(f"Layout detection failed on page {page_num}: {e}")
            return {
                'page_number': page_num,
                'blocks': [],
                'error': str(e)
            }
    
    def detect_pdf_layout(
        self,
        pdf_path: str,
        output_dir: Optional[str] = None,
        save_visualizations: bool = False
    ) -> Dict:
        """
        Detect layout for entire PDF
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Optional directory to save results
            save_visualizations: Whether to save visualization images
        
        Returns:
            Dictionary with all pages' layout data
        """
        if self.model is None:
            return {
                'success': False,
                'error': 'Layout model not available'
            }
        
        pdf_path = Path(pdf_path)
        
        if output_dir:
            output_dir = Path(output_dir) / pdf_path.stem
            output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            'pdf_name': pdf_path.name,
            'pages': []
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            self.logger.info(f"Detecting layout for {total_pages} pages")
            
            for page_num, page in enumerate(pdf.pages, 1):
                page_layout = self.detect_page_layout(page, page_num)
                results['pages'].append(page_layout)
                
                self.logger.info(
                    f"Page {page_num}/{total_pages}: "
                    f"{page_layout.get('total_blocks', 0)} blocks"
                )
                
                # Save individual page layout if output_dir specified
                if output_dir:
                    layout_file = output_dir / f"page_{page_num:03d}_layout.json"
                    with open(layout_file, 'w') as f:
                        json.dump(page_layout, f, indent=2)
        
        # Calculate summary
        results['total_pages'] = len(results['pages'])
        results['total_blocks'] = sum(
            p.get('total_blocks', 0) for p in results['pages']
        )
        
        # Aggregate block types
        all_types = {}
        for page in results['pages']:
            for block_type, count in page.get('block_types', {}).items():
                all_types[block_type] = all_types.get(block_type, 0) + count
        
        results['overall_block_counts'] = all_types
        
        self.logger.info(f"Layout detection complete: {results['total_blocks']} total blocks")
        
        return results
    
    def is_available(self) -> bool:
        """Check if layout detection is available"""
        return self.model is not None


# Quick test
if __name__ == "__main__":
    detector = PDFLayoutDetector(model_dir="publaynet-model")
    
    if detector.is_available():
        result = detector.detect_pdf_layout(
            "./data/raw/test.pdf",
            output_dir="./data/processed/layout"
        )
        print(f"Detected {result['total_blocks']} blocks")
    else:
        print("Layout detection not available")