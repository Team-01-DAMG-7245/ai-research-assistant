"""Test script to run validation agent and save results to JSON"""
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.search_agent import search_agent_node
from src.agents.synthesis_agent import synthesis_agent_node
from src.agents.validation_agent import validation_agent_node
from src.agents.state import ResearchState

def main():
    # Initialize state with user query
    state: ResearchState = {
        'task_id': f'validation_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
        'user_query': 'What are the latest advances in transformer architectures?'
    }
    
    print("=" * 70)
    print("STEP 1: Running Search Agent")
    print("=" * 70)
    
    # Run search agent
    state = search_agent_node(state)
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
    report_draft = state.get('report_draft', '')
    word_count = len(report_draft.split()) if report_draft else 0
    print(f"  - Generated report: {word_count} words")
    print(f"  - Retrieved {state.get('source_count', 0)} sources")
    
    if state.get('error'):
        print(f"  - ERROR: {state.get('error')}")
        return
    
    print("\n" + "=" * 70)
    print("STEP 3: Running Validation Agent")
    print("=" * 70)
    
    # Run validation agent
    state = validation_agent_node(state)
    
    validation_result = state.get('validation_result', {})
    confidence_score = state.get('confidence_score', 0.0)
    needs_hitl = state.get('needs_hitl', False)
    
    print(f"\nValidation completed:")
    print(f"  - Valid: {validation_result.get('valid', False)}")
    print(f"  - Confidence Score: {confidence_score:.2f}")
    print(f"  - Needs HITL: {needs_hitl}")
    print(f"  - Invalid Citations: {len(validation_result.get('invalid_citations', []))}")
    print(f"  - Unsupported Claims: {len(validation_result.get('unsupported_claims', []))}")
    print(f"  - Issues: {len(validation_result.get('issues', []))}")
    
    if validation_result.get('issues'):
        print(f"\n  Issues found:")
        for issue in validation_result.get('issues', [])[:5]:  # Show first 5
            print(f"    - {issue}")
    
    if state.get('error'):
        print(f"  - ERROR: {state.get('error')}")
    
    # Save results to JSON
    output_file = Path(__file__).parent / "validation_results.json"
    
    json_state = {
        'task_id': state.get('task_id'),
        'user_query': state.get('user_query'),
        'report_word_count': word_count,
        'source_count': state.get('source_count', 0),
        'validation_result': validation_result,
        'confidence_score': confidence_score,
        'needs_hitl': needs_hitl,
        'error': state.get('error'),
        'timestamp': datetime.now().isoformat(),
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(json_state, f, indent=2, ensure_ascii=False)
    
    print(f"\n" + "=" * 70)
    print(f"Results saved to: {output_file}")
    print("=" * 70)

if __name__ == "__main__":
    main()

