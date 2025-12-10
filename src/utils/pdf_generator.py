"""
PDF Generation Utility

Converts markdown reports to PDF format with proper styling.
"""

import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

import markdown
from weasyprint import CSS, HTML
from weasyprint.text.fonts import FontConfiguration

logger = logging.getLogger(__name__)


def markdown_to_pdf(
    markdown_content: str,
    output_path: Optional[str] = None,
    title: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> bytes:
    """
    Convert markdown content to PDF bytes.

    Args:
        markdown_content: Markdown text to convert
        output_path: Optional path to save PDF file (if None, returns bytes only)
        title: Optional title for the PDF document
        metadata: Optional metadata dict (e.g., task_id, confidence_score)

    Returns:
        PDF file as bytes
    """
    try:
        # Convert markdown to HTML
        # Use safe extensions that don't require additional dependencies
        extensions = ["extra", "tables"]
        try:
            # Try to use codehilite if available (requires Pygments)
            html_content = markdown.markdown(
                markdown_content, extensions=extensions + ["codehilite"]
            )
        except Exception:
            # Fallback to basic extensions if codehilite fails
            html_content = markdown.markdown(markdown_content, extensions=extensions)

        # Create styled HTML document
        html_doc = _create_html_document(html_content, title, metadata)

        # Generate PDF
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_doc).write_pdf(font_config=font_config)

        # Save to file if output_path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(pdf_bytes)
            logger.info(f"PDF saved to {output_path}")

        return pdf_bytes

    except Exception as e:
        logger.error(f"Error generating PDF: {e}", exc_info=True)
        raise


def _create_html_document(
    content: str, title: Optional[str] = None, metadata: Optional[dict] = None
) -> str:
    """
    Create a styled HTML document from content.

    Args:
        content: HTML content (from markdown conversion)
        title: Document title
        metadata: Optional metadata to display

    Returns:
        Complete HTML document string
    """
    title_text = title or "Research Report"

    # Build metadata section if provided
    metadata_html = ""
    if metadata:
        metadata_items = []
        if metadata.get("task_id"):
            metadata_items.append(f"<strong>Task ID:</strong> {metadata['task_id']}")
        if metadata.get("confidence_score") is not None:
            metadata_items.append(
                f"<strong>Confidence Score:</strong> {metadata['confidence_score']:.2f}"
            )
        if metadata.get("source_count"):
            metadata_items.append(
                f"<strong>Sources Used:</strong> {metadata['source_count']}"
            )
        if metadata.get("created_at"):
            metadata_items.append(
                f"<strong>Generated:</strong> {metadata['created_at']}"
            )

        if metadata_items:
            metadata_html = f"""
            <div class="metadata">
                <h3>Report Information</h3>
                <ul>
                    {''.join(f'<li>{item}</li>' for item in metadata_items)}
                </ul>
            </div>
            """

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title_text}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
            @top-center {{
                content: "{title_text}";
                font-size: 10pt;
                color: #666;
            }}
            @bottom-center {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 10pt;
                color: #666;
            }}
        }}
        
        body {{
            font-family: 'Georgia', 'Times New Roman', serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
            max-width: 100%;
        }}
        
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 0;
            page-break-after: avoid;
        }}
        
        h2 {{
            color: #34495e;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 8px;
            margin-top: 30px;
            page-break-after: avoid;
        }}
        
        /* Special styling for References heading */
        h2:last-of-type {{
            border-top: 2px solid #3498db;
            border-bottom: 2px solid #95a5a6;
            padding-top: 20px;
            margin-top: 40px;
        }}
        
        h3 {{
            color: #555;
            margin-top: 25px;
            page-break-after: avoid;
        }}
        
        h4, h5, h6 {{
            color: #666;
            margin-top: 20px;
            page-break-after: avoid;
        }}
        
        p {{
            margin: 12px 0;
            text-align: justify;
        }}
        
        .metadata {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 30px;
        }}
        
        .metadata h3 {{
            margin-top: 0;
            color: #495057;
        }}
        
        .metadata ul {{
            list-style: none;
            padding-left: 0;
        }}
        
        .metadata li {{
            margin: 8px 0;
            padding-left: 20px;
        }}
        
        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        
        pre {{
            background-color: #f4f4f4;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            overflow-x: auto;
            page-break-inside: avoid;
        }}
        
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        
        blockquote {{
            border-left: 4px solid #3498db;
            margin: 20px 0;
            padding-left: 20px;
            color: #555;
            font-style: italic;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            page-break-inside: avoid;
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }}
        
        th {{
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }}
        
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        
        ul, ol {{
            margin: 15px 0;
            padding-left: 30px;
        }}
        
        li {{
            margin: 8px 0;
        }}
        
        a {{
            color: #3498db;
            text-decoration: underline;
        }}
        
        a:hover {{
            color: #2980b9;
            text-decoration: underline;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #ddd;
            margin: 30px 0;
        }}
        
        strong {{
            color: #2c3e50;
        }}
        
        em {{
            color: #555;
        }}
        
        /* Reference links styling - ensure they're clearly clickable */
        a[href] {{
            color: #3498db;
            text-decoration: underline;
            word-break: break-all;
        }}
        
        /* Make reference links stand out more */
        h2 ~ ul a[href],
        h2 ~ ol a[href] {{
            color: #2980b9;
            font-weight: 500;
        }}
        
        /* Better spacing for reference lists */
        h2 + ul, h2 + ol {{
            margin-top: 15px;
            page-break-inside: avoid;
        }}
        
        h2 + ul li, h2 + ol li {{
            margin: 10px 0;
            padding-left: 5px;
        }}
    </style>
</head>
<body>
    <h1>{title_text}</h1>
    {metadata_html}
    {content}
</body>
</html>"""

    return html_doc
