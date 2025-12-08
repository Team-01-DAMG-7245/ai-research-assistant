#!/usr/bin/env python
"""
Configuration Checker for AI Research Assistant
Checks all required environment variables and service connectivity
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment variables
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env file from: {env_path}")
else:
    print(f"⚠️  No .env file found at: {env_path}")
    print("   Loading from system environment variables...")

print("\n" + "=" * 70)
print("CONFIGURATION CHECK")
print("=" * 70)

# Check OpenAI
print("\n1. OpenAI Configuration:")
openai_key = os.getenv("OPENAI_API_KEY")
if openai_key:
    if openai_key.startswith("sk-"):
        print(f"   ✅ OPENAI_API_KEY: Set (starts with 'sk-', length: {len(openai_key)})")
        
        # Test OpenAI connection
        try:
            from src.utils.openai_client import OpenAIClient
            client = OpenAIClient()
            # Simple test call
            test_response = client.chat_completion(
                messages=[{"role": "user", "content": "Say 'test'"}],
                model="gpt-4o-mini",
                max_tokens=10
            )
            if test_response.get("content"):
                print("   ✅ OpenAI API: Connection successful")
            else:
                print("   ❌ OpenAI API: Connection failed - no response")
        except Exception as e:
            print(f"   ❌ OpenAI API: Connection failed - {str(e)}")
    else:
        print(f"   ⚠️  OPENAI_API_KEY: Set but doesn't start with 'sk-' (may be invalid)")
else:
    print("   ❌ OPENAI_API_KEY: Not set")

# Check Pinecone
print("\n2. Pinecone Configuration:")
pinecone_key = os.getenv("PINECONE_API_KEY")
pinecone_index = os.getenv("PINECONE_INDEX_NAME")
pinecone_env = os.getenv("PINECONE_ENVIRONMENT")

if pinecone_key:
    print(f"   ✅ PINECONE_API_KEY: Set (length: {len(pinecone_key)})")
else:
    print("   ❌ PINECONE_API_KEY: Not set")

if pinecone_index:
    print(f"   ✅ PINECONE_INDEX_NAME: {pinecone_index}")
else:
    print("   ❌ PINECONE_INDEX_NAME: Not set")

if pinecone_env:
    print(f"   ℹ️  PINECONE_ENVIRONMENT: {pinecone_env}")
else:
    print("   ℹ️  PINECONE_ENVIRONMENT: Not set (optional)")

# Test Pinecone connection
if pinecone_key and pinecone_index:
    try:
        from src.utils.pinecone_rag import _get_pinecone_index, semantic_search
        index = _get_pinecone_index()
        print("   ✅ Pinecone Index: Initialized successfully")
        
        # Test search
        try:
            results = semantic_search("test query", top_k=1, namespace="research_papers")
            print(f"   ✅ Pinecone Search: Working (returned {len(results)} results)")
        except Exception as e:
            print(f"   ❌ Pinecone Search: Failed - {str(e)}")
    except ValueError as e:
        print(f"   ❌ Pinecone: Configuration error - {str(e)}")
    except Exception as e:
        print(f"   ❌ Pinecone: Connection failed - {str(e)}")
else:
    print("   ⚠️  Pinecone: Cannot test without API key and index name")

# Check S3
print("\n3. AWS S3 Configuration:")
s3_bucket = os.getenv("S3_BUCKET_NAME")
aws_region = os.getenv("AWS_REGION", "us-east-1")
aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

if s3_bucket:
    print(f"   ✅ S3_BUCKET_NAME: {s3_bucket}")
else:
    print("   ❌ S3_BUCKET_NAME: Not set")

print(f"   ℹ️  AWS_REGION: {aws_region}")

if aws_access_key:
    print(f"   ✅ AWS_ACCESS_KEY_ID: Set (length: {len(aws_access_key)})")
else:
    print("   ⚠️  AWS_ACCESS_KEY_ID: Not set (may use IAM role)")

if aws_secret_key:
    print(f"   ✅ AWS_SECRET_ACCESS_KEY: Set (length: {len(aws_secret_key)})")
else:
    print("   ⚠️  AWS_SECRET_ACCESS_KEY: Not set (may use IAM role)")

# Test S3 connection
if s3_bucket:
    try:
        from src.utils.s3_client import S3Client
        s3_client = S3Client()
        print("   ✅ S3 Client: Initialized successfully")
    except Exception as e:
        print(f"   ❌ S3 Client: Initialization failed - {str(e)}")

# Check Database
print("\n4. Database Configuration:")
db_path = project_root / "data" / "tasks.db"
if db_path.exists():
    print(f"   ✅ Database file exists: {db_path}")
    print(f"   ℹ️  Database size: {db_path.stat().st_size / 1024:.2f} KB")
else:
    print(f"   ⚠️  Database file not found: {db_path}")
    print("      (Will be created automatically on first use)")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

required_vars = {
    "OPENAI_API_KEY": openai_key,
    "PINECONE_API_KEY": pinecone_key,
    "PINECONE_INDEX_NAME": pinecone_index,
    "S3_BUCKET_NAME": s3_bucket,
}

missing = [name for name, value in required_vars.items() if not value]

if not missing:
    print("✅ All required environment variables are set!")
    print("\n💡 If tasks are still failing, check:")
    print("   1. API logs for detailed error messages")
    print("   2. Service connectivity (internet, firewall)")
    print("   3. API quotas and rate limits")
    print("   4. Pinecone index has data (run ingestion scripts)")
else:
    print(f"❌ Missing required environment variables: {', '.join(missing)}")
    print("\n💡 To fix:")
    print("   1. Create a .env file in the project root")
    print("   2. Add the missing variables:")
    for var in missing:
        print(f"      {var}=your_value_here")
    print("   3. Restart the FastAPI server")

print("\n" + "=" * 70)

