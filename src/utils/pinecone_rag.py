"""
Pinecone RAG Utilities
High-level helpers for performing semantic search and context preparation
using Pinecone, OpenAI embeddings, and S3-stored chunk content.
"""

import logging
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from pinecone import Pinecone

from .openai_client import OpenAIClient
from .s3_client import S3Client

load_dotenv()

logger = logging.getLogger(__name__)


def _get_pinecone_index() -> Any:
    """
    Initialize and return a Pinecone index client.

    Environment variables:
        PINECONE_API_KEY: API key for Pinecone
        PINECONE_INDEX_NAME: Name of the index to query

    Returns:
        Pinecone Index instance (typed as Any to be compatible with different SDK versions)

    Raises:
        ValueError: If required environment variables are missing
    """
    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME")

    if not api_key:
        raise ValueError("PINECONE_API_KEY environment variable is not set")
    if not index_name:
        raise ValueError("PINECONE_INDEX_NAME environment variable is not set")

    try:
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)
        logger.info("Initialized Pinecone index '%s'", index_name)
        return index
    except Exception as exc:
        logger.exception("Failed to initialize Pinecone index '%s': %s", index_name, exc)
        raise


def query_to_embedding(query: str) -> List[float]:
    """
    Convert a query string to an OpenAI embedding vector.

    Uses the `text-embedding-3-small` model and returns a 1536-dimensional vector.

    Args:
        query: Natural language query text.

    Returns:
        List of floats representing the embedding (length 1536).

    Raises:
        ValueError: If the query is empty or embedding creation fails.
    """
    if not query or not query.strip():
        raise ValueError("Query text must be a non-empty string")

    client = OpenAIClient()
    try:
        result = client.create_embedding(
            query,
            model="text-embedding-3-small",
        )
        embedding = result["embeddings"]

        if not isinstance(embedding, list) or not embedding:
            raise ValueError("Received invalid embedding from OpenAI")

        # Optional sanity check on dimension (1536 for text-embedding-3-small)
        if len(embedding) != 1536:
            logger.warning(
                "Expected 1536-dimensional embedding, got %d dimensions", len(embedding)
            )

        return embedding  # type: ignore[return-value]
    except Exception as exc:
        logger.exception("Failed to convert query to embedding: %s", exc)
        raise


def semantic_search(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """
    Perform a semantic search in Pinecone for the given query.

    This function:
      1. Converts the query to an embedding.
      2. Queries the configured Pinecone index.
      3. Returns the top_k results with useful metadata.

    Args:
        query: Natural language query text.
        top_k: Number of top matches to return (default: 10).

    Returns:
        List of dictionaries, each containing:
            - doc_id: ID of the document or chunk
            - score: Similarity score
            - text: Chunk text (if stored in metadata)
            - title: Document title (if present)
            - url: Source URL (if present)
            - metadata: Full metadata dictionary

    Raises:
        ValueError: If top_k is invalid or query/embedding fails.
    """
    if top_k <= 0:
        raise ValueError("top_k must be a positive integer")

    # Step 1: embed the query
    embedding = query_to_embedding(query)

    # Step 2: get Pinecone index
    index = _get_pinecone_index()

    try:
        response = index.query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
        )
    except Exception as exc:
        logger.exception("Error during Pinecone query: %s", exc)
        raise

    results: List[Dict[str, Any]] = []
    matches = getattr(response, "matches", []) or []

    for match in matches:
        metadata = getattr(match, "metadata", {}) or {}
        doc_id = metadata.get("doc_id") or getattr(match, "id", None)

        result = {
            "doc_id": doc_id,
            "score": getattr(match, "score", None),
            "text": metadata.get("text"),
            "title": metadata.get("title"),
            "url": metadata.get("url"),
            "metadata": metadata,
        }
        results.append(result)

    logger.info("Semantic search returned %d results for query", len(results))
    return results


def _chunk_s3_key_from_id(chunk_id: str) -> str:
    """
    Build the S3 key for a chunk stored in the silver layer.

    This is a small helper that encapsulates the convention for where
    processed chunks are stored. Adjust this if your project uses
    a different layout or naming scheme.

    Args:
        chunk_id: Unique chunk identifier (e.g., from Pinecone metadata or ID).

    Returns:
        S3 key/path to the JSON or text file for this chunk.
    """
    # Example convention: silver/chunks/{chunk_id}.json
    # Modify this to match your actual S3 layout if needed.
    return f"silver/chunks/{chunk_id}.json"


def retrieve_full_chunks(chunk_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Retrieve full chunk data from the S3 silver layer.

    For each chunk_id, this function:
      - Builds the corresponding S3 key.
      - Downloads the object content.
      - Tries to parse JSON; falls back to plain text if needed.

    Args:
        chunk_ids: List of chunk IDs obtained from Pinecone search results.

    Returns:
        List of dictionaries representing complete chunk data. Each item
        will include at least:
            - chunk_id
            - text
        Plus any additional metadata stored in the S3 object.

    Notes:
        - Chunks that fail to download or parse are logged and skipped.
    """
    import json

    if not chunk_ids:
        return []

    s3_client = S3Client()
    bucket = os.getenv("S3_BUCKET_NAME")
    if not bucket:
        raise ValueError("S3_BUCKET_NAME environment variable is not set")

    # We will stream objects directly from S3 without persisting to disk
    s3 = s3_client.s3  # reuse underlying boto3 client
    results: List[Dict[str, Any]] = []

    for chunk_id in chunk_ids:
        s3_key = _chunk_s3_key_from_id(chunk_id)
        try:
            obj = s3.get_object(Bucket=bucket, Key=s3_key)
            body = obj["Body"].read()

            # Try JSON first
            try:
                data = json.loads(body)
            except Exception:
                # Fallback: treat as plain text
                text = body.decode("utf-8", errors="ignore")
                data = {"chunk_id": chunk_id, "text": text}

            # Ensure minimal fields are present
            data.setdefault("chunk_id", chunk_id)
            if "text" not in data and "content" in data:
                data["text"] = data["content"]

            results.append(data)
        except Exception as exc:
            logger.error(
                "Failed to retrieve or parse chunk '%s' from s3://%s/%s: %s",
                chunk_id,
                bucket,
                s3_key,
                exc,
            )
            continue

    logger.info("Retrieved %d/%d chunks from S3", len(results), len(chunk_ids))
    return results


def prepare_context(chunks: List[Dict[str, Any]]) -> str:
    """
    Format retrieved chunks into a context string with numbered sources.

    The output format is:
        "[Source 1] Title: <title> (Doc ID: <doc_id>, URL: <url>)\\n"
        "Content: <text>\\n\\n"

    This format includes enough metadata for downstream citation and
    attribution in RAG pipelines.

    Args:
        chunks: List of chunk dictionaries, typically from retrieve_full_chunks.

    Returns:
        Single string combining all sources, suitable for use as LLM context.
    """
    if not chunks:
        return ""

    lines: List[str] = []

    for idx, chunk in enumerate(chunks, start=1):
        title = chunk.get("title") or chunk.get("document_title") or "Untitled"
        doc_id = chunk.get("doc_id") or chunk.get("chunk_id") or "unknown"
        url = chunk.get("url") or chunk.get("source_url") or "N/A"
        text = chunk.get("text") or chunk.get("content") or ""

        header = f"[Source {idx}] Title: {title} (Doc ID: {doc_id}, URL: {url})"
        body = f"Content: {text}"

        lines.append(header)
        lines.append(body)
        lines.append("")  # blank line between sources

    context = "\n".join(lines).strip()
    logger.debug("Prepared context with %d sources, length=%d chars", len(chunks), len(context))
    return context


__all__ = [
    "query_to_embedding",
    "semantic_search",
    "retrieve_full_chunks",
    "prepare_context",
]


