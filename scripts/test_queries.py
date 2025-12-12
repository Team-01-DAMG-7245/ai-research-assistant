"""
Extensive Query Testing Script

Tests the AI Research Assistant with 10-15 sample queries across different topics.
This validates the system works correctly with various research questions.

Usage:
    python scripts/test_queries.py --api-url http://localhost:8000
"""

import argparse
import requests
import sys
import time
import json
from typing import Dict, List, Tuple
from datetime import datetime


# Sample queries across different research topics
SAMPLE_QUERIES = [
    {
        "topic": "Machine Learning",
        "query": "What are the latest advances in transformer architectures for natural language processing?",
        "depth": "standard"
    },
    {
        "topic": "Computer Vision",
        "query": "How do vision transformers compare to convolutional neural networks for image classification?",
        "depth": "standard"
    },
    {
        "topic": "Reinforcement Learning",
        "query": "What are the state-of-the-art methods for multi-agent reinforcement learning?",
        "depth": "standard"
    },
    {
        "topic": "NLP",
        "query": "How do large language models handle few-shot learning and in-context learning?",
        "depth": "standard"
    },
    {
        "topic": "Deep Learning",
        "query": "What are the recent developments in neural architecture search and automated machine learning?",
        "depth": "standard"
    },
    {
        "topic": "Graph Neural Networks",
        "query": "What are the latest techniques for learning representations on graph-structured data?",
        "depth": "standard"
    },
    {
        "topic": "Generative Models",
        "query": "How do diffusion models compare to GANs for image generation tasks?",
        "depth": "standard"
    },
    {
        "topic": "Federated Learning",
        "query": "What are the main challenges and solutions for privacy-preserving federated learning?",
        "depth": "standard"
    },
    {
        "topic": "Meta-Learning",
        "query": "What are the current approaches to few-shot learning and meta-learning in deep learning?",
        "depth": "standard"
    },
    {
        "topic": "Robotics",
        "query": "How is deep learning being applied to robot control and manipulation tasks?",
        "depth": "standard"
    },
    {
        "topic": "Explainable AI",
        "query": "What methods exist for making deep learning models more interpretable and explainable?",
        "depth": "standard"
    },
    {
        "topic": "Efficient AI",
        "query": "What are the techniques for creating efficient and lightweight deep learning models?",
        "depth": "standard"
    },
    {
        "topic": "Causal Inference",
        "query": "How can causal inference be integrated with machine learning models?",
        "depth": "standard"
    },
    {
        "topic": "Continual Learning",
        "query": "What are the approaches to prevent catastrophic forgetting in neural networks?",
        "depth": "standard"
    },
    {
        "topic": "Multimodal Learning",
        "query": "How do multimodal models combine vision and language for joint understanding?",
        "depth": "standard"
    }
]


def submit_query(api_url: str, query: str, depth: str = "standard") -> Tuple[bool, str, Dict]:
    """Submit a research query and return task_id."""
    try:
        response = requests.post(
            f"{api_url}/api/v1/research",
            json={"query": query, "depth": depth},
            timeout=10
        )
        
        if response.status_code == 201:
            data = response.json()
            task_id = data.get("task_id")
            return True, task_id, data
        else:
            return False, None, {"error": f"Status {response.status_code}", "response": response.text}
    except requests.exceptions.RequestException as e:
        return False, None, {"error": str(e)}


def check_task_status(api_url: str, task_id: str) -> Tuple[str, Dict]:
    """Check the status of a task."""
    try:
        response = requests.get(f"{api_url}/api/v1/status/{task_id}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("status", "unknown"), data
        else:
            return "error", {"error": f"Status {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return "error", {"error": str(e)}


def wait_for_completion(api_url: str, task_id: str, max_wait: int = 120, poll_interval: int = 5) -> Tuple[str, Dict]:
    """Wait for a task to complete and return final status."""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status, data = check_task_status(api_url, task_id)
        
        if status in ["completed", "failed", "rejected"]:
            return status, data
        
        # Show progress
        elapsed = int(time.time() - start_time)
        print(f"      ⏳ Waiting... ({elapsed}s elapsed)", end="\r")
        time.sleep(poll_interval)
    
    # Timeout
    return "timeout", {"error": f"Task did not complete within {max_wait} seconds"}


def get_report(api_url: str, task_id: str, format: str = "json") -> Tuple[bool, Dict]:
    """Retrieve the final report for a completed task."""
    try:
        response = requests.get(
            f"{api_url}/api/v1/report/{task_id}?format={format}",
            timeout=10
        )
        
        if response.status_code == 200:
            if format == "json":
                return True, response.json()
            else:
                return True, {"content": response.text, "format": format}
        else:
            return False, {"error": f"Status {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return False, {"error": str(e)}


def run_query_tests(api_url: str, queries: List[Dict], wait_for_completion: bool = False) -> Dict:
    """Run tests for all queries."""
    results = {
        "total": len(queries),
        "submitted": 0,
        "completed": 0,
        "failed": 0,
        "timeout": 0,
        "queries": []
    }
    
    print("🧪 Starting Extensive Query Testing\n")
    print("=" * 70)
    print(f"Testing {len(queries)} queries across different research topics\n")
    
    for i, query_data in enumerate(queries, 1):
        topic = query_data["topic"]
        query = query_data["query"]
        depth = query_data.get("depth", "standard")
        
        print(f"\n[{i}/{len(queries)}] Testing: {topic}")
        print(f"   Query: {query[:60]}...")
        
        # Submit query
        success, task_id, submit_data = submit_query(api_url, query, depth)
        
        query_result = {
            "topic": topic,
            "query": query,
            "submitted": success,
            "task_id": task_id,
            "final_status": None,
            "has_report": False,
            "error": None
        }
        
        if not success:
            print(f"   ❌ Failed to submit: {submit_data.get('error', 'Unknown error')}")
            results["failed"] += 1
            query_result["error"] = submit_data.get("error")
            results["queries"].append(query_result)
            continue
        
        results["submitted"] += 1
        print(f"   ✅ Submitted successfully (Task ID: {task_id[:8]}...)")
        
        if wait_for_completion:
            # Wait for task to complete
            print(f"   ⏳ Waiting for completion...")
            status, status_data = wait_for_completion(api_url, task_id)
            query_result["final_status"] = status
            
            if status == "completed":
                results["completed"] += 1
                print(f"   ✅ Task completed successfully")
                
                # Try to get report
                success, report_data = get_report(api_url, task_id)
                if success:
                    query_result["has_report"] = True
                    if "report" in report_data:
                        report_length = len(report_data.get("report", ""))
                        print(f"   📄 Report generated ({report_length} characters)")
            elif status == "failed":
                results["failed"] += 1
                print(f"   ❌ Task failed")
                query_result["error"] = status_data.get("error", "Unknown error")
            elif status == "timeout":
                results["timeout"] += 1
                print(f"   ⏱️  Task timed out")
                query_result["error"] = "Timeout"
        else:
            # Just submit, don't wait
            status, _ = check_task_status(api_url, task_id)
            query_result["final_status"] = status
            print(f"   ℹ️  Task status: {status} (not waiting for completion)")
        
        results["queries"].append(query_result)
        
        # Small delay between queries to avoid overwhelming the API
        if i < len(queries):
            time.sleep(2)
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Results Summary:")
    print("=" * 70)
    print(f"Total Queries:      {results['total']}")
    print(f"Successfully Submitted: {results['submitted']} ✅")
    if wait_for_completion:
        print(f"Completed:          {results['completed']} ✅")
        print(f"Failed:             {results['failed']} ❌")
        print(f"Timed Out:          {results['timeout']} ⏱️")
    
    # Save results to file
    output_file = f"query_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {output_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Test AI Research Assistant with sample queries"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for each query to complete before moving to the next"
    )
    parser.add_argument(
        "--num-queries",
        type=int,
        default=None,
        help="Number of queries to test (default: all)"
    )
    
    args = parser.parse_args()
    
    queries = SAMPLE_QUERIES
    if args.num_queries:
        queries = queries[:args.num_queries]
    
    results = run_query_tests(args.api_url, queries, args.wait)
    
    # Exit code based on success rate
    if results["submitted"] == results["total"]:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
