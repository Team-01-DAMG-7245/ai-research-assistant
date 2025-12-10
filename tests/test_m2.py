"""
M2: Data Pipeline Tests
Tests for arXiv ingestion and PDF processing
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

from src.pipelines.ingestion import ArxivIngestion
from src.utils.pdf_processor import PDFProcessor
from src.utils.s3_client import S3Client


def has_aws_credentials():
    """Check if AWS credentials are available"""
    return all(
        os.getenv(var)
        for var in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"]
    )


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_objects():
    """Fixture to clean up test objects after each test"""
    # Track test objects to delete
    test_objects = []

    # Yield control to test
    yield test_objects

    # Cleanup after test
    if test_objects and has_aws_credentials():
        try:
            s3 = S3Client()
            deleted = s3.delete_objects(test_objects)
            if deleted > 0:
                print(f"\n🧹 Cleaned up {deleted} test objects from S3")
        except Exception:
            pass  # Ignore cleanup errors if credentials aren't available


@pytest.fixture(scope="class", autouse=True)
def cleanup_test_prefix():
    """Fixture to clean up all test/ objects after all tests in class"""
    yield

    # Cleanup test/ prefix after all tests in class
    if has_aws_credentials():
        try:
            s3 = S3Client()
            deleted = s3.delete_prefix("test/")
            if deleted > 0:
                print(f"\n🧹 Cleaned up {deleted} objects from test/ prefix")
        except Exception:
            pass  # Ignore cleanup errors if credentials aren't available


class TestArxivIngestion:
    """Test arXiv paper ingestion"""

    def test_fetch_papers(self):
        """Test fetching papers from arXiv"""
        print("\n🧪 Testing arXiv paper fetching...")

        ingestion = ArxivIngestion()
        papers = ingestion.fetch_papers(categories=["cs.AI"], max_results=5)

        assert len(papers) > 0, "Should fetch at least 1 paper"
        assert len(papers) <= 5, "Should not exceed max_results"

        # Check paper structure
        paper = papers[0]
        assert "arxiv_id" in paper
        assert "title" in paper
        assert "authors" in paper
        assert "abstract" in paper

        print(f"   ✅ Fetched {len(papers)} papers")
        print(f"   📄 Sample: {paper['title'][:50]}...")

    def test_download_pdf(self):
        """Test downloading a single PDF"""
        print("\n🧪 Testing PDF download...")

        ingestion = ArxivIngestion()

        # Fetch one paper
        papers = ingestion.fetch_papers(categories=["cs.AI"], max_results=1)

        assert len(papers) == 1, "Should fetch exactly 1 paper"

        # Download it
        pdf_path = ingestion.download_pdf(papers[0])

        assert pdf_path is not None, "Download should succeed"
        assert Path(pdf_path).exists(), "PDF file should exist"

        print(f"   ✅ Downloaded: {papers[0]['arxiv_id']}")

        # Cleanup
        Path(pdf_path).unlink(missing_ok=True)

    def test_full_ingestion_pipeline(self):
        """Test complete ingestion pipeline with 5 papers"""
        print("\n🧪 Testing full ingestion pipeline...")

        ingestion = ArxivIngestion()
        summary = ingestion.run_pipeline(categories=["cs.AI"], max_results=5)

        assert summary["total_fetched"] > 0, "Should fetch papers"
        assert summary["successfully_uploaded"] > 0, "Should upload to S3"

        print(f"   ✅ Pipeline complete:")
        print(f"      Fetched: {summary['total_fetched']}")
        print(f"      Uploaded: {summary['successfully_uploaded']}")
        print(f"      Failed: {summary['failed']}")


class TestPDFProcessing:
    """Test PDF text extraction and processing"""

    def test_pdf_extraction(self):
        """Test extracting text from a PDF"""
        print("\n🧪 Testing PDF text extraction...")

        s3 = S3Client()
        processor = PDFProcessor()

        # Get first PDF from S3
        papers = s3.list_objects(prefix="raw/papers/", max_keys=10)
        pdf_keys = [k for k in papers if k.endswith(".pdf")]

        if not pdf_keys:
            pytest.skip("No PDFs in S3. Run ingestion first.")

        # Download and process first PDF
        pdf_key = pdf_keys[0]
        local_path = "./data/raw/test.pdf"

        success = s3.download_file(pdf_key, local_path)
        assert success, "Should download PDF from S3"

        # Extract text using the text extractor directly
        text_result = processor.text_extractor.extract_pdf(str(local_path))

        # Combine all text from pages
        text = "\n\n".join(
            [page["text"] for page in text_result["pages"] if page["text"]]
        )

        assert len(text) > 0, "Should extract text"
        assert len(text) > 100, "Should extract substantial text"

        print(
            f"   ✅ Extracted {len(text)} characters from {text_result['total_pages']} pages"
        )

        # Cleanup
        Path(local_path).unlink(missing_ok=True)

    def test_text_chunking(self):
        """Test text chunking"""
        print("\n🧪 Testing text chunking...")

        processor = PDFProcessor(chunk_size=100, overlap=10)

        # Create sample text (300 words)
        sample_text = " ".join([f"word{i}" for i in range(300)])

        chunks = processor.chunk_text(sample_text)

        assert len(chunks) > 1, "Should create multiple chunks"
        assert all(
            len(chunk.split()) <= 100 for chunk in chunks[:-1]
        ), "Chunks should respect size limit"

        print(f"   ✅ Created {len(chunks)} chunks from 300 words")

    def test_complete_pdf_processing(self):
        """Test complete PDF processing pipeline"""
        print("\n🧪 Testing complete PDF processing...")

        s3 = S3Client()
        processor = PDFProcessor(chunk_size=512, overlap=50)

        # Get a PDF
        papers = s3.list_objects(prefix="raw/papers/", max_keys=10)
        pdf_keys = [k for k in papers if k.endswith(".pdf")]

        if not pdf_keys:
            pytest.skip("No PDFs in S3. Run ingestion first.")

        # Process it
        pdf_key = pdf_keys[0]
        local_path = "./data/raw/test.pdf"
        s3.download_file(pdf_key, local_path)

        result = processor.process_pdf(
            local_path, extract_tables=False, extract_layout=False
        )

        assert result["success"], "Processing should succeed"
        assert result["chunks"]["num_chunks"] > 0, "Should create chunks"
        assert (
            len(result["chunks"]["chunks"]) == result["chunks"]["num_chunks"]
        ), "Chunk count should match"

        print(f"   ✅ Processed PDF:")
        print(f"      PDF name: {result['pdf_name']}")
        print(f"      Pages: {result['text_extraction']['total_pages']}")
        print(
            f"      Text length: {result['text_extraction']['full_text_length']:,} chars"
        )
        print(f"      Chunks: {result['chunks']['num_chunks']}")

        # Cleanup
        Path(local_path).unlink(missing_ok=True)


class TestS3Client:
    """Test S3 client utilities"""

    def test_list_objects(self):
        """Test listing objects in S3"""
        print("\n🧪 Testing S3 list objects...")

        s3 = S3Client()

        # List papers
        papers = s3.list_objects(prefix="raw/papers/")

        print(f"   ✅ Found {len(papers)} objects in raw/papers/")

    def test_upload_download_cycle(self, cleanup_test_objects):
        """Test uploading and downloading a file"""
        print("\n🧪 Testing S3 upload/download cycle...")

        s3 = S3Client()

        # Create a test file
        test_file = "./data/raw/test_upload.txt"
        Path(test_file).parent.mkdir(parents=True, exist_ok=True)

        with open(test_file, "w") as f:
            f.write("Test content for S3")

        # Upload
        s3_key = "test/test_upload.txt"
        upload_success = s3.upload_file(test_file, s3_key)
        assert upload_success, "Upload should succeed"

        # Add to cleanup list (will be auto-deleted after test)
        cleanup_test_objects.append(s3_key)

        # Download to different location
        download_path = "./data/raw/test_download.txt"
        download_success = s3.download_file(s3_key, download_path)
        assert download_success, "Download should succeed"

        # Verify content
        with open(download_path, "r") as f:
            content = f.read()
        assert content == "Test content for S3", "Content should match"

        print("   ✅ Upload/download cycle successful")

        # Cleanup local files (S3 cleanup happens automatically via fixture)
        Path(test_file).unlink(missing_ok=True)
        Path(download_path).unlink(missing_ok=True)


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
