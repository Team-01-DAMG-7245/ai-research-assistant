"""
Pytest configuration and shared fixtures for API tests.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment variables
os.environ["APP_ENV"] = "test"
os.environ["API_MODE"] = "true"
os.environ["DEBUG"] = "true"

# Disable external service connections in tests
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("PINECONE_INDEX_NAME", "test-index")
os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")

