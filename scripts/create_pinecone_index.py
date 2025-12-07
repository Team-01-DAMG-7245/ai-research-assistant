"""
Create a Pinecone index for the AI Research Assistant project.

This script creates an index compatible with OpenAI text-embedding-3-small
(1536 dimensions) using cosine similarity.

Usage:
    python scripts/create_pinecone_index.py [index_name]
    
If index_name is not provided, it will prompt you for one.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv()

def main():
    """Create a Pinecone index for research papers."""
    api_key = os.getenv("PINECONE_API_KEY")
    
    if not api_key:
        print("❌ ERROR: PINECONE_API_KEY environment variable is not set")
        print("\nPlease set it in your .env file or export it:")
        print("  export PINECONE_API_KEY=your_api_key_here")
        return
    
    # Get index name from command line or prompt
    if len(sys.argv) > 1:
        index_name = sys.argv[1]
    else:
        index_name = input("Enter index name (e.g., 'ai-research-index'): ").strip()
        if not index_name:
            print("❌ Index name cannot be empty")
            return
    
    try:
        pc = Pinecone(api_key=api_key)
        
        # Check if index already exists
        existing_indexes = pc.list_indexes()
        existing_names = [idx.name if hasattr(idx, 'name') else str(idx) for idx in existing_indexes]
        
        if index_name in existing_names:
            print(f"⚠️  Index '{index_name}' already exists!")
            print(f"\nYou can use it by setting in your .env file:")
            print(f"  PINECONE_INDEX_NAME={index_name}")
            return
        
        print(f"\n📦 Creating index '{index_name}'...")
        print("   - Dimensions: 1536 (for OpenAI text-embedding-3-small)")
        print("   - Metric: cosine")
        print("   - Cloud: AWS")
        print("   - Region: us-east-1")
        print()
        
        # Create index with specifications for OpenAI embeddings
        pc.create_index(
            name=index_name,
            dimension=1536,  # OpenAI text-embedding-3-small dimension
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        
        print(f"✅ Successfully created index '{index_name}'!")
        print()
        print("=" * 70)
        print("NEXT STEPS:")
        print("=" * 70)
        print(f"1. Add to your .env file:")
        print(f"   PINECONE_INDEX_NAME={index_name}")
        print()
        print("2. Embed your research papers:")
        print("   python scripts/embed_chunks_to_pinecone.py")
        print()
        
    except Exception as e:
        print(f"❌ ERROR: Failed to create index: {e}")
        print("\nPossible issues:")
        print("  - Index name may already exist (use list_pinecone_indexes.py to check)")
        print("  - Invalid API key")
        print("  - Network connectivity issues")
        print("  - Insufficient Pinecone account permissions")

if __name__ == "__main__":
    main()

