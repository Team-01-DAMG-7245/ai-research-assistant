"""
List all Pinecone indexes in your account.

This script helps you determine what PINECONE_INDEX_NAME to use.
Run this to see all available indexes.

Usage:
    python scripts/list_pinecone_indexes.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pinecone import Pinecone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

def main():
    """List all Pinecone indexes."""
    api_key = os.getenv("PINECONE_API_KEY")
    
    if not api_key:
        print("❌ ERROR: PINECONE_API_KEY environment variable is not set")
        print("\nPlease set it in your .env file or export it:")
        print("  export PINECONE_API_KEY=your_api_key_here")
        return
    
    try:
        pc = Pinecone(api_key=api_key)
        
        # List all indexes
        indexes = pc.list_indexes()
        
        if not indexes:
            print("📭 No indexes found in your Pinecone account.")
            print("\nYou need to create an index first. See instructions below.")
            return
        
        print("=" * 70)
        print("AVAILABLE PINECONE INDEXES")
        print("=" * 70)
        print()
        
        for idx in indexes:
            index_name = idx.name if hasattr(idx, 'name') else str(idx)
            print(f"  ✓ {index_name}")
        
        print()
        print("=" * 70)
        print("TO USE AN INDEX:")
        print("=" * 70)
        print("Set PINECONE_INDEX_NAME in your .env file to one of the names above.")
        print("For example:")
        print("  PINECONE_INDEX_NAME=your-index-name")
        print()
        
    except Exception as e:
        print(f"❌ ERROR: Failed to list indexes: {e}")
        print("\nMake sure:")
        print("  1. PINECONE_API_KEY is correct")
        print("  2. You have internet connectivity")
        print("  3. Your Pinecone account is active")

if __name__ == "__main__":
    main()

