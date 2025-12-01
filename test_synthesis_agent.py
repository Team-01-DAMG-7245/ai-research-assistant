"""Test script to run synthesis agent and save results to JSON"""
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.search_agent import search_agent_node
from src.agents.synthesis_agent import synthesis_agent_node
from src.agents.state import ResearchState

def main():
    # Initialize state with user query
    state: ResearchState = {
        'task_id': f'synthesis_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
        'user_query': 'What are the latest advances in transformer architectures?'
    }
    
    print("=" * 70)
    print("STEP 1: Running Search Agent")
    print("=" * 70)
    
    # Run search agent first
    state = search_agent_node(state)
    
    print(f"\nSearch completed:")
    print(f"  - Generated {len(state.get('search_queries', []))} search queries")
    print(f"  - Found {len(state.get('search_results', []))} search results")
    
    if state.get('error'):
        print(f"  - ERROR: {state.get('error')}")
        return
    
    print("\n" + "=" * 70)
    print("STEP 2: Running Synthesis Agent")
    print("=" * 70)
    
    # Run synthesis agent
    state = synthesis_agent_node(state)
    
    print(f"\nSynthesis completed:")
    print(f"  - Retrieved {state.get('source_count', 0)} sources")
    report_draft = state.get('report_draft', '')
    word_count = len(report_draft.split()) if report_draft else 0
    print(f"  - Generated report: {word_count} words")
    
    if state.get('error'):
        print(f"  - ERROR: {state.get('error')}")
    
    # Save results to JSON
    output_file = Path(__file__).parent / "synthesis_results.json"
    
    # Prepare JSON-serializable state
    json_state = {
        'task_id': state.get('task_id'),
        'user_query': state.get('user_query'),
        'search_queries': state.get('search_queries', []),
        'search_results_count': len(state.get('search_results', [])),
        'source_count': state.get('source_count', 0),
        'report_draft': state.get('report_draft', ''),
        'word_count': word_count,
        'error': state.get('error'),
        'current_agent': state.get('current_agent'),
        'timestamp': datetime.now().isoformat(),
        # Include sample search results (first 3) for reference
        'sample_search_results': [
            {
                'doc_id': r.get('doc_id'),
                'score': r.get('score'),
                'title': r.get('title', '')[:100] if r.get('title') else 'N/A'
            }
            for r in state.get('search_results', [])[:3]
        ],
        # Include sample retrieved chunks metadata (first 3)
        'sample_retrieved_chunks': [
            {
                'chunk_id': c.get('chunk_id'),
                'doc_id': c.get('doc_id'),
                'title': c.get('title', '')[:100] if c.get('title') else 'N/A'
            }
            for c in state.get('retrieved_chunks', [])[:3]
        ]
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_state, f, indent=2, ensure_ascii=False)
    
    print(f"\n" + "=" * 70)
    print(f"Results saved to: {output_file}")
    print("=" * 70)
    
    # Display report preview
    if report_draft:
        print("\n" + "=" * 70)
        print("REPORT PREVIEW (first 500 characters):")
        print("=" * 70)
        print(report_draft[:500] + "..." if len(report_draft) > 500 else report_draft)
        print("\n" + "=" * 70)
        print(f"Full report length: {len(report_draft)} characters, {word_count} words")
        print("=" * 70)

if __name__ == "__main__":
    main()

