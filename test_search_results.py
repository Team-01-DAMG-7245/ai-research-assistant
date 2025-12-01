"""Test script to see which search queries generated which results"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.search_agent import search_agent_node
from src.utils.pinecone_rag import semantic_search
from src.agents.state import ResearchState

# Run search to get queries
state: ResearchState = {
    'task_id': 'query_test',
    'user_query': 'latest advances in transformer architectures'
}
out = search_agent_node(state)

queries = out.get('search_queries', [])

print("=" * 70)
print("SEARCH QUERIES GENERATED:")
print("=" * 70)
for i, q in enumerate(queries, 1):
    print(f"{i}. {q}")

print("\n" + "=" * 70)
print("RESULTS BY QUERY (showing which query found each result):")
print("=" * 70)

# Track all results with their source query
all_results_with_query = {}
for query_idx, query in enumerate(queries, 1):
    print(f"\n--- Query {query_idx}: '{query}' ---")
    try:
        results = semantic_search(query, top_k=10)
        print(f"Found {len(results)} results:")
        for i, r in enumerate(results[:5], 1):  # Show top 5 per query
            doc_id = r.get('doc_id')
            score = r.get('score', 0)
            title = r.get('title', 'N/A')
            text_preview = str(r.get('text', ''))[:150]
            
            print(f"  {i}. doc_id={doc_id}, score={score:.4f}")
            print(f"     title: {title}")
            print(f"     preview: {text_preview}...")
            
            # Track which query found this doc
            if doc_id not in all_results_with_query:
                all_results_with_query[doc_id] = {
                    'query': query,
                    'query_num': query_idx,
                    'score': score,
                    'title': title,
                    'text': r.get('text', '')
                }
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "=" * 70)
print("FINAL COMBINED RESULTS (after deduplication):")
print("=" * 70)
final_results = out.get('search_results', [])
for i, r in enumerate(final_results[:10], 1):
    doc_id = r.get('doc_id')
    source_info = all_results_with_query.get(doc_id, {})
    query_found_by = source_info.get('query', 'Unknown')
    query_num = source_info.get('query_num', '?')
    
    print(f"\nResult {i}:")
    print(f"  doc_id: {doc_id}")
    print(f"  score: {r.get('score'):.4f}")
    print(f"  Found by Query {query_num}: '{query_found_by}'")
    print(f"  title: {r.get('title', 'N/A')}")
    text_preview = str(r.get('text', ''))[:150]
    print(f"  preview: {text_preview}...")

print(f"\n\nTotal final results: {len(final_results)}")

