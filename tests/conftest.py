"""
Pytest configuration and shared fixtures for API tests.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file first
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

# Set test environment variables
os.environ["APP_ENV"] = "test"
os.environ["API_MODE"] = "true"
os.environ["DEBUG"] = "true"

# Use real API keys from .env if available, otherwise use test defaults
# This allows tests to use real services when credentials are available
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "test-key"
if not os.getenv("PINECONE_API_KEY"):
    os.environ["PINECONE_API_KEY"] = "test-key"
if not os.getenv("PINECONE_INDEX_NAME"):
    os.environ["PINECONE_INDEX_NAME"] = "test-index"
if not os.getenv("S3_BUCKET_NAME"):
    os.environ["S3_BUCKET_NAME"] = "test-bucket"
