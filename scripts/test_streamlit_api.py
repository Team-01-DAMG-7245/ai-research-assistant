#!/usr/bin/env python
"""
Test script to verify API calls work the same way Streamlit does
"""

import requests
import json

base_url = "http://localhost:8000"

print("Testing API calls as Streamlit would make them...")
print("=" * 70)

# Test 1: Get all tasks
print("\n1. Testing GET /api/v1/tasks")
try:
    response = requests.get(f"{base_url}/api/v1/tasks", params={}, timeout=5)
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        tasks = data.get("tasks", [])
        print(f"   ✅ Success: Got {len(tasks)} tasks")
        
        # Filter like Streamlit does
        tasks_with_reports = [
            t for t in tasks 
            if t.get("status", "").lower() in ["completed", "approved", "pending_review"]
        ]
        print(f"   ✅ Tasks with reports: {len(tasks_with_reports)}")
        
        if tasks_with_reports:
            print("\n   Tasks that should appear in Reports tab:")
            for i, task in enumerate(tasks_with_reports[:5], 1):
                print(f"   {i}. {task.get('task_id')[:8]}... - {task.get('query', '')[:40]} ({task.get('status')})")
        
        # Test getting a specific report
        if tasks_with_reports:
            test_task_id = tasks_with_reports[0].get("task_id")
            print(f"\n2. Testing GET /api/v1/report/{test_task_id[:8]}...")
            report_response = requests.get(f"{base_url}/api/v1/report/{test_task_id}", timeout=5)
            print(f"   Status: {report_response.status_code}")
            if report_response.status_code == 200:
                report_data = report_response.json()
                print(f"   ✅ Report retrieved: {len(report_data.get('report', ''))} characters")
            else:
                print(f"   ❌ Error: {report_response.text[:200]}")
    else:
        print(f"   ❌ Error: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
except requests.exceptions.ConnectionError:
    print("   ❌ Connection Error: Cannot connect to API")
    print("   Make sure FastAPI server is running: uvicorn src.api.main:app --reload")
except Exception as e:
    print(f"   ❌ Exception: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)

