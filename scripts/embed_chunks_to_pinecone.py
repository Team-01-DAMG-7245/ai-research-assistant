"""
Embed processed text chunks and upsert them into the Pinecone index.

This script:
  1. Lists processed chunk JSON files in S3 under 'processed/text_chunks/'.
  2. Downloads each JSON file.
  3. Uses OpenAI text-embedding-3-small to create embeddings for each chunk's text.
  4. Upserts vectors into the configured Pinecone index with useful metadata.

Environment variables required:
  - OPENAI_API_KEY
  - PINECONE_API_KEY
  - PINECONE_INDEX_NAME
  - S3_BUCKET_NAME
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from tqdm import tqdm
from pinecone import Pinecone

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.s3_client import S3Client  # noqa: E402
from src.utils.openai_client import OpenAIClient  # noqa: E402


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _extract_texts_from_chunks(chunks: List[Any]) -> List[str]:
    """
    Extract text content from chunks.

    Handles both string chunks and dictionary chunks.
    """
    texts: List[str] = []
    for chunk in chunks:
        if isinstance(chunk, str):
            # Chunk is already a string
            text = chunk.strip()
        elif isinstance(chunk, dict):
            # Chunk is a dictionary - try common keys
            text = (
                chunk.get("text")
                or chunk.get("content")
                or ""
            )
            text = str(text).strip()
        else:
            # Fallback: convert to string
            text = str(chunk).strip()
        
        if text:
            texts.append(text)
    return texts


def main() -> None:
    logger.info("=" * 70)
    logger.info("EMBEDDING CHUNKS INTO PINECONE")
    logger.info("=" * 70)

    # Validate env vars early
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME")

    if not pinecone_api_key:
        raise ValueError("PINECONE_API_KEY environment variable is not set")
    if not index_name:
        raise ValueError("PINECONE_INDEX_NAME environment variable is not set")

    # Initialize clients
    s3_client = S3Client()
    openai_client = OpenAIClient()
    pc = Pinecone(api_key=pinecone_api_key)
    index = pc.Index(index_name)

    # 1) List all processed chunk files in S3
    logger.info("Listing processed chunk files from S3 prefix 'processed/text_chunks/'")
    keys = s3_client.list_objects(prefix="processed/text_chunks/")
    json_keys = [k for k in keys if k.endswith(".json")]
    logger.info("Found %d processed chunk JSON files", len(json_keys))

    total_vectors = 0

    for key in tqdm(json_keys, desc="Embedding chunk files"):
        try:
            local_path = Path("temp") / Path(key).name
            local_path.parent.mkdir(parents=True, exist_ok=True)

            # Download JSON from S3
            ok = s3_client.download_file(key, str(local_path))
            if not ok:
                logger.error("Failed to download %s from S3", key)
                continue

            with local_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            arxiv_id = data.get("arxiv_id") or Path(key).stem
            chunks = data.get("chunks", [])
            if not isinstance(chunks, list) or not chunks:
                logger.warning("No chunks found in %s", key)
                local_path.unlink(missing_ok=True)
                continue

            texts = _extract_texts_from_chunks(chunks)
            if not texts:
                logger.warning("No non-empty texts found in %s", key)
                local_path.unlink(missing_ok=True)
                continue

            # 2) Create embeddings
            emb_resp = openai_client.create_embedding(
                texts,
                model="text-embedding-3-small",
            )
            embeddings = emb_resp["embeddings"]

            if len(embeddings) != len(texts):
                logger.warning(
                    "Embedding count (%d) does not match text count (%d) for %s",
                    len(embeddings),
                    len(texts),
                    key,
                )

            # 3) Build vectors with metadata (flat structure, no nested objects)
            vectors = []
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                # Handle both string and dict chunks
                if isinstance(chunk, str):
                    text_content = chunk
                    chunk_id = f"{arxiv_id}-{i}"
                    title = arxiv_id
                elif isinstance(chunk, dict):
                    chunk_id = (
                        chunk.get("chunk_id")
                        or chunk.get("id")
                        or f"{arxiv_id}-{i}"
                    )
                    text_content = chunk.get("text") or chunk.get("content", "")
                    title = chunk.get("title") or arxiv_id
                else:
                    text_content = str(chunk)
                    chunk_id = f"{arxiv_id}-{i}"
                    title = arxiv_id
                
                # Construct arXiv URL from arxiv_id
                # Format: https://arxiv.org/pdf/{arxiv_id}.pdf or https://arxiv.org/abs/{arxiv_id}
                arxiv_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                
                # Flat metadata only (AGENTS.md: no nested objects)
                metadata = {
                    "doc_id": str(arxiv_id),
                    "chunk_id": str(chunk_id),
                    "text": str(text_content)[:40000],  # Respect 40KB metadata limit
                    "title": str(title),
                    "url": str(arxiv_url),  # Add URL for citations
                }
                vectors.append((str(chunk_id), emb, metadata))

            if not vectors:
                logger.warning("No vectors built for %s", key)
                local_path.unlink(missing_ok=True)
                continue

            # 4) Upsert into Pinecone with namespace and batch processing
            # AGENTS.md: Use namespace, batch size 1000 for vectors
            namespace = "research_papers"  # Consistent namespace for all papers
            batch_size = 1000  # AGENTS.md: max 1000 vectors per batch
            
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                try:
                    index.upsert(vectors=batch, namespace=namespace)
                    total_vectors += len(batch)
                    logger.debug("Upserted batch of %d vectors (total: %d)", len(batch), total_vectors)
                except Exception as batch_exc:
                    logger.error("Failed to upsert batch from %s: %s", key, batch_exc)
                    raise
            
            logger.info("Upserted %d vectors from %s into namespace '%s'", len(vectors), key, namespace)

            # Cleanup
            local_path.unlink(missing_ok=True)

        except Exception as exc:
            logger.exception("Failed to embed/upload chunks from %s: %s", key, exc)
            # Try to clean up local file if it exists
            try:
                local_path.unlink(missing_ok=True)
            except Exception:
                pass

    logger.info("=" * 70)
    logger.info("EMBEDDING COMPLETE")
    logger.info("Total vectors upserted into '%s': %d", index_name, total_vectors)
    logger.info("=" * 70)


if __name__ == "__main__":
    main()


