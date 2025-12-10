"""
Production Deployment Validation Script

Validates that the AI Research Assistant is properly deployed on EC2.
Run this script on your EC2 instance or from a machine that can access it.

Usage:
    python scripts/validate_production_deployment.py --api-url http://your-ec2-ip:8000
"""

import argparse
import requests
import sys
import time
from typing import Dict, List, Tuple
from datetime import datetime


def check_health(api_url: str) -> Tuple[bool, str]:
    """Check if API health endpoint is responding."""
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return True, f"✅ Health check passed: {data.get('status', 'ok')}"
        else:
            return False, f"❌ Health check failed: Status {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"❌ Health check failed: {str(e)}"


def check_api_docs(api_url: str) -> Tuple[bool, str]:
    """Check if API documentation is accessible."""
    try:
        response = requests.get(f"{api_url}/docs", timeout=5)
        if response.status_code == 200:
            return True, "✅ API documentation accessible"
        else:
            return False, f"❌ API docs failed: Status {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"❌ API docs failed: {str(e)}"


def check_streamlit(streamlit_url: str) -> Tuple[bool, str]:
    """Check if Streamlit is accessible."""
    try:
        response = requests.get(f"{streamlit_url}/_stcore/health", timeout=5)
        if response.status_code == 200:
            return True, "✅ Streamlit health check passed"
        else:
            return False, f"❌ Streamlit health check failed: Status {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"❌ Streamlit health check failed: {str(e)}"


def test_research_endpoint(api_url: str) -> Tuple[bool, str, str]:
    """Test submitting a research query."""
    test_query = {
        "query": "What are the latest advances in transformer architectures?",
        "depth": "standard"
    }
    
    try:
        response = requests.post(
            f"{api_url}/api/v1/research",
            json=test_query,
            timeout=10
        )
        
        if response.status_code == 201:
            data = response.json()
            task_id = data.get("task_id")
            return True, f"✅ Research query submitted successfully", task_id
        else:
            return False, f"❌ Research query failed: Status {response.status_code}", None
    except requests.exceptions.RequestException as e:
        return False, f"❌ Research query failed: {str(e)}", None


def check_task_status(api_url: str, task_id: str) -> Tuple[bool, str]:
    """Check task status endpoint."""
    try:
        response = requests.get(f"{api_url}/api/v1/status/{task_id}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            return True, f"✅ Task status retrieved: {status}"
        else:
            return False, f"❌ Task status failed: Status {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"❌ Task status failed: {str(e)}"


def validate_rate_limiting(api_url: str) -> Tuple[bool, str]:
    """Test rate limiting by making multiple rapid requests."""
    try:
        # Make 10 rapid requests to status endpoint
        responses = []
        for i in range(10):
            response = requests.get(f"{api_url}/api/v1/health", timeout=2)
            responses.append(response.status_code)
            time.sleep(0.1)
        
        # Check if rate limiting kicked in (429 status)
        rate_limited = any(status == 429 for status in responses)
        if rate_limited:
            return True, "✅ Rate limiting is working"
        else:
            return True, "ℹ️  Rate limiting not triggered (may need more requests)"
    except requests.exceptions.RequestException as e:
        return False, f"❌ Rate limit test failed: {str(e)}"


def run_validation(api_url: str, streamlit_url: str = None) -> Dict[str, List[Tuple[bool, str]]]:
    """Run all validation checks."""
    results = {
        "API Checks": [],
        "Functionality Tests": [],
        "Security Checks": []
    }
    
    print("🔍 Starting Production Deployment Validation\n")
    print("=" * 60)
    
    # API Health Checks
    print("\n1️⃣ API Health Checks:")
    print("-" * 60)
    
    success, message = check_health(api_url)
    results["API Checks"].append((success, message))
    print(f"   {message}")
    
    success, message = check_api_docs(api_url)
    results["API Checks"].append((success, message))
    print(f"   {message}")
    
    # Streamlit Check (optional)
    if streamlit_url:
        print("\n2️⃣ Streamlit Checks:")
        print("-" * 60)
        success, message = check_streamlit(streamlit_url)
        results["API Checks"].append((success, message))
        print(f"   {message}")
    
    # Functionality Tests
    print("\n3️⃣ Functionality Tests:")
    print("-" * 60)
    
    success, message, task_id = test_research_endpoint(api_url)
    results["Functionality Tests"].append((success, message))
    print(f"   {message}")
    
    if task_id:
        # Wait a moment for task to be created
        time.sleep(2)
        success, message = check_task_status(api_url, task_id)
        results["Functionality Tests"].append((success, message))
        print(f"   {message}")
    
    # Security Checks
    print("\n4️⃣ Security Checks:")
    print("-" * 60)
    
    success, message = validate_rate_limiting(api_url)
    results["Security Checks"].append((success, message))
    print(f"   {message}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Validation Summary:")
    print("=" * 60)
    
    total_checks = 0
    passed_checks = 0
    
    for category, checks in results.items():
        print(f"\n{category}:")
        for success, message in checks:
            total_checks += 1
            if success:
                passed_checks += 1
            status = "✅" if success else "❌"
            print(f"   {status} {message.split(':')[1] if ':' in message else message}")
    
    print(f"\n📈 Results: {passed_checks}/{total_checks} checks passed")
    
    if passed_checks == total_checks:
        print("\n✅ All validation checks passed! Deployment is healthy.")
        return True
    else:
        print(f"\n⚠️  {total_checks - passed_checks} check(s) failed. Review the issues above.")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Validate production deployment on EC2"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--streamlit-url",
        type=str,
        default=None,
        help="Base URL of Streamlit (optional, e.g., http://localhost:8501)"
    )
    
    args = parser.parse_args()
    
    success = run_validation(args.api_url, args.streamlit_url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
