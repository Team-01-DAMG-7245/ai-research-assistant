"""Test script to run the complete LangGraph workflow"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.workflow import compiled_workflow
from src.agents.state import ResearchState

def main():
    # Initialize state
    state: ResearchState = {
        'task_id': f'workflow_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
        'user_query': 'What are the latest advances in transformer architectures?'
    }
    
    print("=" * 70)
    print("Running Complete Research Agent Workflow")
    print("=" * 70)
    print(f"Task ID: {state['task_id']}")
    print(f"User Query: {state['user_query']}")
    print("=" * 70)
    print("\nStarting workflow execution...\n")
    
    try:
        # Run the compiled workflow
        final_state = compiled_workflow.invoke(state)
        
        print("\n" + "=" * 70)
        print("Workflow Execution Complete")
        print("=" * 70)
        
        # Display results
        print(f"\nTask ID: {final_state.get('task_id')}")
        print(f"Current Agent: {final_state.get('current_agent')}")
        print(f"Search Queries Generated: {len(final_state.get('search_queries', []))}")
        print(f"Search Results: {len(final_state.get('search_results', []))}")
        print(f"Sources Used: {final_state.get('source_count', 0)}")
        print(f"Report Word Count: {len(final_state.get('final_report', '').split())}")
        print(f"Confidence Score: {final_state.get('confidence_score', 0.0):.2f}")
        print(f"Needs HITL: {final_state.get('needs_hitl', False)}")
        print(f"Error: {final_state.get('error', 'None')}")
        
        final_report = final_state.get('final_report', '')
        if final_report:
            print(f"\nFinal Report Preview (first 300 chars):")
            print("-" * 70)
            print(final_report[:300] + "..." if len(final_report) > 300 else final_report)
            print("-" * 70)
        
        print("\n" + "=" * 70)
        
    except Exception as e:
        print(f"\nError during workflow execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

