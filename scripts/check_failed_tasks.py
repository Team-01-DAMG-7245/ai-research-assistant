#!/usr/bin/env python
"""
Check Failed Tasks
Shows detailed error messages for failed tasks in the database
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.task_manager import get_task_manager

def main():
    task_manager = get_task_manager()
    
    # Get all failed tasks
    failed_tasks = task_manager.get_tasks_by_status("failed")
    
    print("\n" + "=" * 70)
    print("FAILED TASKS ANALYSIS")
    print("=" * 70)
    
    if not failed_tasks:
        print("\n✅ No failed tasks found in database.")
        return
    
    print(f"\nFound {len(failed_tasks)} failed task(s):\n")
    
    for i, task in enumerate(failed_tasks, 1):
        task_id = task.get("task_id")
        query = task.get("query", "Unknown")
        error_message = task.get("error_message", "No error message")
        created_at = task.get("created_at")
        updated_at = task.get("updated_at")
        current_agent = task.get("current_agent", "Unknown")
        
        print(f"{'=' * 70}")
        print(f"Task {i}: {task_id}")
        print(f"{'=' * 70}")
        print(f"Query: {query}")
        print(f"Status: failed")
        print(f"Current Agent: {current_agent}")
        print(f"Created: {created_at}")
        print(f"Updated: {updated_at}")
        print(f"\nError Message:")
        print(f"{'-' * 70}")
        print(error_message)
        print(f"{'-' * 70}")
        print()
    
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    print("\nCommon causes of failures:")
    print("1. OpenAI API errors (rate limits, invalid requests)")
    print("2. Pinecone connection issues")
    print("3. Invalid JSON response from LLM")
    print("4. Missing data in Pinecone index")
    print("5. Network connectivity issues")
    print("\nTo debug further:")
    print("1. Check FastAPI server logs for detailed stack traces")
    print("2. Check agent-specific logs in src/logs/")
    print("3. Verify Pinecone index has data")
    print("4. Test individual components with check_config.py")
    print("=" * 70)

if __name__ == "__main__":
    main()

