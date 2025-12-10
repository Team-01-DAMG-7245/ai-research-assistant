"""
PDF Layout Detection using LayoutParser
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np
import pdfplumber
from PIL import Image

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
            self.logger.warning(
                "layoutparser or torch not available. Layout detection disabled."
            )
            return

        # Load model with fallback strategies
        self.model = self._load_robust_model()

        if self.model is None:
            self.logger.warning(
                "Failed to load layout model. Layout detection disabled."
            )

    def _load_robust_model(self):
        """Load model with version compatibility handling"""
        # Strategy: Try multiple approaches in order of preference

        # Option 1: Try custom PubLayNet model with detectron2 (if model_dir provided and detectron2 available)
        if self.model_dir.exists():
            config_files = list(self.model_dir.glob("*.yaml")) + list(
                self.model_dir.glob("*.yml")
            )
            weight_files = list(self.model_dir.glob("*.pth"))

            if config_files and weight_files:
                config_path = config_files[0]
                weight_path = weight_files[0]

                self.logger.info(
                    f"Loading custom PubLayNet model from {self.model_dir}"
                )
                try:
                    model = lp.Detectron2LayoutModel(
                        config_path=str(config_path),
                        model_path=str(weight_path),
                        extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.3],
                        label_map={
                            0: "Text",
                            1: "Title",
                            2: "List",
                            3: "Table",
                            4: "Figure",
                        },
                    )
                    self.logger.info(
                        "✅ Loaded custom PubLayNet model (detectron2 backend)"
                    )
                    return model
                except Exception as e:
                    self.logger.warning(f"Custom model loading failed: {e}")
                    self.logger.info(
                        "Falling back to layoutparser's pre-trained model..."
                    )

        # Option 2: Try layoutparser's pre-trained PubLayNet model (requires detectron2 but downloads automatically)
        try:
            self.logger.info("Loading layoutparser's pre-trained PubLayNet model...")
            # This uses detectron2 under the hood but handles installation automatically
            model = lp.Detectron2LayoutModel(
                config_path="lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config",
                model_path="lp://PubLayNet/faster_rcnn_R_50_FPN_3x/model",
                label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
                extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.3],
            )
            self.logger.info("✅ Loaded layoutparser's pre-trained PubLayNet model")
            return model
        except Exception as e:
            self.logger.error(f"Failed to load pre-trained model: {e}")
            self.logger.warning("Layout detection requires detectron2. Install with:")
            self.logger.warning(
                "  pip install 'git+https://github.com/facebookresearch/detectron2.git'"
            )
            return None

    def detect_page_layout(self, page, page_num: int, resolution: int = 200) -> Dict:
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
            return {"page_number": page_num, "blocks": [], "error": "Model not loaded"}

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

                blocks.append(
                    {
                        "block_id": idx,
                        "type": str(block.type),
                        "confidence": float(block.score),
                        "bbox": {
                            "x1": float(x1),
                            "y1": float(y1),
                            "x2": float(x2),
                            "y2": float(y2),
                        },
                        "width": float(x2 - x1),
                        "height": float(y2 - y1),
                    }
                )

            # Count by type
            block_counts = {}
            for b in blocks:
                block_type = b["type"]
                block_counts[block_type] = block_counts.get(block_type, 0) + 1

            return {
                "page_number": page_num,
                "total_blocks": len(blocks),
                "blocks": blocks,
                "block_types": block_counts,
            }

        except Exception as e:
            self.logger.error(f"Layout detection failed on page {page_num}: {e}")
            return {"page_number": page_num, "blocks": [], "error": str(e)}

    def detect_pdf_layout(
        self,
        pdf_path: str,
        output_dir: Optional[str] = None,
        save_visualizations: bool = False,
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
            return {"success": False, "error": "Layout model not available"}

        pdf_path = Path(pdf_path)

        if output_dir:
            output_dir = Path(output_dir) / pdf_path.stem
            output_dir.mkdir(parents=True, exist_ok=True)

        results = {"pdf_name": pdf_path.name, "pages": []}

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            self.logger.info(f"Detecting layout for {total_pages} pages")

            for page_num, page in enumerate(pdf.pages, 1):
                page_layout = self.detect_page_layout(page, page_num)
                results["pages"].append(page_layout)

                self.logger.info(
                    f"Page {page_num}/{total_pages}: "
                    f"{page_layout.get('total_blocks', 0)} blocks"
                )

                # Save individual page layout if output_dir specified
                if output_dir:
                    layout_file = output_dir / f"page_{page_num:03d}_layout.json"
                    with open(layout_file, "w") as f:
                        json.dump(page_layout, f, indent=2)

        # Calculate summary
        results["total_pages"] = len(results["pages"])
        results["total_blocks"] = sum(
            p.get("total_blocks", 0) for p in results["pages"]
        )

        # Aggregate block types
        all_types = {}
        for page in results["pages"]:
            for block_type, count in page.get("block_types", {}).items():
                all_types[block_type] = all_types.get(block_type, 0) + count

        results["overall_block_counts"] = all_types

        self.logger.info(
            f"Layout detection complete: {results['total_blocks']} total blocks"
        )

        return results

    def is_available(self) -> bool:
        """Check if layout detection is available"""
        return self.model is not None


# Quick test
if __name__ == "__main__":
    detector = PDFLayoutDetector(model_dir="publaynet-model")

    if detector.is_available():
        result = detector.detect_pdf_layout(
            "./data/raw/test.pdf", output_dir="./data/processed/layout"
        )
        print(f"Detected {result['total_blocks']} blocks")
    else:
        print("Layout detection not available")
