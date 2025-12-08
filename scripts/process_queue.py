#!/usr/bin/env python
"""Queue processor using actual TaskManager methods"""

import sys
import time
import sqlite3
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.api.task_manager import TaskManager
from src.agents.workflow import compiled_workflow

def main():
    print("Starting queue processor...")
    task_manager = TaskManager()
    db_path = "data/tasks.db"
    
    while True:
        try:
            # Query database directly for queued tasks
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT task_id, query, status 
                FROM research_tasks 
                WHERE status IN ('queued', 'pending')
                LIMIT 1
            """)
            
            task_row = cursor.fetchone()
            conn.close()
            
            if task_row:
                task_id, query, status = task_row
                print(f"\nFound task: {task_id}")
                print(f"Query: {query}")
                print(f"Status: {status}")
                
                # Update progress
                task_manager.update_task_progress(task_id, 0.1, "Starting processing")
                
                # Create state for workflow
                state = {
                    "task_id": task_id,
                    "user_query": query,
                    "current_agent": "search",
                    "search_queries": [],
                    "search_results": [],
                    "retrieved_chunks": [],
                    "report_draft": "",
                    "validation_result": {},
                    "confidence_score": 0.0,
                    "needs_hitl": False,
                    "final_report": "",
                    "error": None
                }
                
                # Run workflow
                try:
                    print("Running workflow...")
                    task_manager.update_task_progress(task_id, 0.5, "Processing through agents")
                    
                    result = compiled_workflow.invoke(state)
                    
                    if result.get('final_report'):
                        print("Report generated!")
                        # Store the result
                        task_manager.store_task_result(task_id, {
                            'report': result['final_report'],
                            'confidence_score': result.get('confidence_score', 0)
                        })
                        task_manager.update_task_report(task_id, result['final_report'])
                        print(f"✓ Task completed: {task_id}")
                    else:
                        task_manager.mark_task_failed(task_id, "No report generated")
                        print(f"✗ Task failed: {task_id}")
                        
                except Exception as e:
                    print(f"Workflow error: {e}")
                    task_manager.mark_task_failed(task_id, str(e))
            else:
                print(".", end="", flush=True)
                
            time.sleep(3)
            
        except KeyboardInterrupt:
            print("\nStopping queue processor")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()