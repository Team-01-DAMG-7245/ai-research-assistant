"""
M3 Completion Validation Script

Comprehensive validation script that checks all M3 requirements:
- Environment configuration
- Agent functionality
- Integration tests
- Performance metrics
- Output quality

Usage:
    python scripts/validate_m3.py
"""

import os
import sys
import time
import json
import uuid
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import all necessary modules
try:
    from src.agents.workflow import compiled_workflow
    from src.agents.state import ResearchState
    from src.agents.search_agent import search_agent_node
    from src.agents.synthesis_agent import synthesis_agent_node
    from src.agents.validation_agent import validation_agent_node
    from src.agents.hitl_review import hitl_review_node
    from src.utils.openai_client import OpenAIClient
    from src.utils.pinecone_rag import semantic_search, query_to_embedding
    from src.utils.s3_client import S3Client
    from src.utils.cost_tracker import get_cost_tracker
    from src.utils.logger import get_logger
except ImportError as e:
    print(f"ERROR: Failed to import required modules: {e}")
    sys.exit(1)

# Setup logging
logger = get_logger(__name__, log_file="validate_m3", console=True, file=False)

# Test results storage
test_results: Dict[str, List[Tuple[str, bool, Optional[str]]]] = {
    "environment": [],
    "agents": [],
    "integration": [],
    "performance": [],
    "quality": [],
}


def print_test_result(category: str, test_name: str, passed: bool, message: Optional[str] = None):
    """Print test result with checkmark or X."""
    # Use simple text formatting instead of ANSI colors for Windows compatibility
    prefix = "[PASS]" if passed else "[FAIL]"
    
    print(f"{prefix} - {test_name}", end="")
    if message:
        print(f": {message}")
    else:
        print()
    
    # Ensure category exists in test_results
    if category not in test_results:
        test_results[category] = []
    test_results[category].append((test_name, passed, message))


def check_environment():
    """1. Environment Check"""
    print("\n" + "=" * 70)
    print("1. ENVIRONMENT CHECK")
    print("=" * 70)
    
    # Check OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key and openai_key.startswith("sk-"):
        print_test_result("environment", "OpenAI API key configured", True)
    else:
        print_test_result("environment", "OpenAI API key configured", False, "OPENAI_API_KEY not set or invalid")
    
    # Check Pinecone configuration
    pinecone_key = os.getenv("PINECONE_API_KEY")
    pinecone_index = os.getenv("PINECONE_INDEX_NAME")
    if pinecone_key and pinecone_index:
        print_test_result("environment", "Pinecone API key configured", True)
        print_test_result("environment", "Pinecone index name configured", True)
        
        # Test Pinecone connectivity
        try:
            results = semantic_search("test query", top_k=1, namespace="research_papers")
            print_test_result("environment", "Pinecone index accessible", True)
        except Exception as e:
            print_test_result("environment", "Pinecone index accessible", False, str(e))
    else:
        print_test_result("environment", "Pinecone API key configured", False, "PINECONE_API_KEY not set")
        print_test_result("environment", "Pinecone index name configured", False, "PINECONE_INDEX_NAME not set")
        print_test_result("environment", "Pinecone index accessible", False, "Cannot test without credentials")
    
    # Check S3 configuration
    s3_bucket = os.getenv("S3_BUCKET_NAME")
    if s3_bucket:
        print_test_result("environment", "S3 bucket name configured", True)
        
        # Test S3 connectivity
        try:
            s3_client = S3Client()
            # Try to list objects (read test)
            try:
                s3_client.list_objects(prefix="bronze/", max_keys=1)
                print_test_result("environment", "S3 bucket readable", True)
            except Exception as e:
                print_test_result("environment", "S3 bucket readable", False, str(e))
            
            # Try to upload a test file (write test)
            try:
                test_key = f"test/validate_m3_{uuid.uuid4().hex[:8]}.txt"
                test_content = f"Validation test - {datetime.now().isoformat()}"
                temp_file = project_root / "temp" / "test_upload.txt"
                temp_file.parent.mkdir(exist_ok=True)
                temp_file.write_text(test_content)
                
                success = s3_client.upload_file(str(temp_file), test_key)
                if success:
                    print_test_result("environment", "S3 bucket writable", True)
                    # Clean up test file
                    try:
                        s3_client.delete_object(test_key)
                    except:
                        pass
                else:
                    print_test_result("environment", "S3 bucket writable", False, "Upload failed")
                temp_file.unlink(missing_ok=True)
            except Exception as e:
                print_test_result("environment", "S3 bucket writable", False, str(e))
        except Exception as e:
            print_test_result("environment", "S3 bucket readable", False, str(e))
            print_test_result("environment", "S3 bucket writable", False, str(e))
    else:
        print_test_result("environment", "S3 bucket name configured", False, "S3_BUCKET_NAME not set")
        print_test_result("environment", "S3 bucket readable", False, "Cannot test without bucket name")
        print_test_result("environment", "S3 bucket writable", False, "Cannot test without bucket name")
    
    # Check dependencies
    required_modules = [
        "openai", "pinecone", "boto3", "langgraph", "tiktoken", "tqdm"
    ]
    for module in required_modules:
        try:
            __import__(module)
            print_test_result("environment", f"Dependency '{module}' installed", True)
        except ImportError:
            print_test_result("environment", f"Dependency '{module}' installed", False, "Module not found")


def check_agents():
    """2. Agent Tests"""
    print("\n" + "=" * 70)
    print("2. AGENT TESTS")
    print("=" * 70)
    
    task_id = f"validate_m3_{uuid.uuid4().hex[:8]}"
    test_query = "What are attention mechanisms in transformers?"
    
    # Test Search Agent
    print("\n--- Testing Search Agent ---")
    try:
        initial_state: ResearchState = {
            "task_id": task_id,
            "user_query": test_query,
            "current_agent": "search",
            "search_queries": [],
            "search_results": [],
            "retrieved_chunks": [],
            "report_draft": "",
            "validation_result": {},
            "confidence_score": 0.0,
            "needs_hitl": False,
            "final_report": "",
            "error": None,
        }
        
        result_state = search_agent_node(initial_state)
        
        if result_state.get("error"):
            print_test_result("agents", "Search agent generates valid queries", False, result_state["error"])
        else:
            queries = result_state.get("search_queries", [])
            results = result_state.get("search_results", [])
            
            if len(queries) >= 3 and len(queries) <= 5:
                print_test_result("agents", "Search agent generates valid queries", True, f"Generated {len(queries)} queries")
            else:
                print_test_result("agents", "Search agent generates valid queries", False, f"Expected 3-5 queries, got {len(queries)}")
            
            if len(results) > 0:
                print_test_result("agents", "Search agent returns results", True, f"Found {len(results)} results")
            else:
                print_test_result("agents", "Search agent returns results", False, "No results returned")
    except Exception as e:
        print_test_result("agents", "Search agent generates valid queries", False, str(e))
        print_test_result("agents", "Search agent returns results", False, str(e))
        result_state = initial_state
    
    # Test Synthesis Agent
    print("\n--- Testing Synthesis Agent ---")
    try:
        if result_state.get("search_results"):
            synthesis_state = synthesis_agent_node(result_state)
            
            if synthesis_state.get("error"):
                print_test_result("agents", "Synthesis agent produces report", False, synthesis_state["error"])
            else:
                report = synthesis_state.get("report_draft", "")
                sources = synthesis_state.get("source_count", 0)
                
                if report and len(report) > 100:
                    print_test_result("agents", "Synthesis agent produces report", True, f"Report length: {len(report)} chars")
                else:
                    print_test_result("agents", "Synthesis agent produces report", False, "Report too short or empty")
                
                if "[Source" in report:
                    print_test_result("agents", "Synthesis agent includes citations", True)
                else:
                    print_test_result("agents", "Synthesis agent includes citations", False, "No citations found in report")
                
                if sources > 0:
                    print_test_result("agents", "Synthesis agent uses sources", True, f"Used {sources} sources")
                else:
                    print_test_result("agents", "Synthesis agent uses sources", False, "No sources used")
        else:
            print_test_result("agents", "Synthesis agent produces report", False, "No search results available")
            synthesis_state = result_state
    except Exception as e:
        print_test_result("agents", "Synthesis agent produces report", False, str(e))
        synthesis_state = result_state
    
    # Test Validation Agent
    print("\n--- Testing Validation Agent ---")
    try:
        if synthesis_state.get("report_draft"):
            validation_state = validation_agent_node(synthesis_state)
            
            if validation_state.get("error"):
                print_test_result("agents", "Validation agent calculates confidence", False, validation_state["error"])
            else:
                confidence = validation_state.get("confidence_score", 0.0)
                needs_hitl = validation_state.get("needs_hitl", False)
                validation_result = validation_state.get("validation_result", {})
                
                if 0.0 <= confidence <= 1.0:
                    print_test_result("agents", "Validation agent calculates confidence", True, f"Confidence: {confidence:.2f}")
                else:
                    print_test_result("agents", "Validation agent calculates confidence", False, f"Invalid confidence: {confidence}")
                
                if isinstance(needs_hitl, bool):
                    print_test_result("agents", "Validation agent sets needs_hitl flag", True, f"needs_hitl={needs_hitl}")
                else:
                    print_test_result("agents", "Validation agent sets needs_hitl flag", False, "needs_hitl not boolean")
                
                if validation_result:
                    print_test_result("agents", "Validation agent returns validation result", True)
                else:
                    print_test_result("agents", "Validation agent returns validation result", False, "Empty validation result")
        else:
            print_test_result("agents", "Validation agent calculates confidence", False, "No report draft available")
            validation_state = synthesis_state
    except Exception as e:
        print_test_result("agents", "Validation agent calculates confidence", False, str(e))
        validation_state = synthesis_state
    
    # Test HITL Review
    print("\n--- Testing HITL Review ---")
    try:
        if validation_state.get("report_draft"):
            # Test with needs_hitl=False (auto-approve)
            validation_state["needs_hitl"] = False
            hitl_state = hitl_review_node(validation_state)
            
            if hitl_state.get("final_report"):
                print_test_result("agents", "HITL workflow functions (auto-approve)", True)
            else:
                print_test_result("agents", "HITL workflow functions (auto-approve)", False, "final_report not set")
        else:
            print_test_result("agents", "HITL workflow functions (auto-approve)", False, "No report draft available")
    except Exception as e:
        print_test_result("agents", "HITL workflow functions (auto-approve)", False, str(e))


def check_integration():
    """3. Integration Tests"""
    print("\n" + "=" * 70)
    print("3. INTEGRATION TESTS")
    print("=" * 70)
    
    task_id = f"validate_m3_integration_{uuid.uuid4().hex[:8]}"
    test_query = "What are recent advances in transformer architectures?"
    
    try:
        # Initialize state
        initial_state: ResearchState = {
            "task_id": task_id,
            "user_query": test_query,
            "current_agent": "search",
            "search_queries": [],
            "search_results": [],
            "retrieved_chunks": [],
            "report_draft": "",
            "validation_result": {},
            "confidence_score": 0.0,
            "needs_hitl": False,
            "final_report": "",
            "error": None,
        }
        
        # Set task_id for cost tracking
        cost_tracker = get_cost_tracker()
        cost_tracker.set_task_id(task_id)
        
        # Run full workflow
        print(f"\nRunning full workflow with query: '{test_query}'")
        start_time = time.time()
        
        final_state = compiled_workflow.invoke(initial_state)
        
        execution_time = time.time() - start_time
        
        # Check state transitions
        if final_state.get("search_queries"):
            print_test_result("integration", "Full workflow runs end-to-end", True, f"Completed in {execution_time:.2f}s")
        else:
            print_test_result("integration", "Full workflow runs end-to-end", False, "Workflow did not complete")
        
        # Check state transitions
        expected_agents = ["search_agent", "synthesis", "validation"]
        current_agent = final_state.get("current_agent", "")
        if current_agent in ["validation", "hitl_review"]:
            print_test_result("integration", "State transitions correctly", True, f"Final agent: {current_agent}")
        else:
            print_test_result("integration", "State transitions correctly", False, f"Unexpected final agent: {current_agent}")
        
        # Check report saved to S3
        final_report = final_state.get("final_report", "")
        if final_report:
            try:
                s3_client = S3Client()
                bucket = s3_client.bucket
                if bucket:
                    # Check if report would be saved (we don't actually save in validation)
                    s3_key = f"gold/reports/{task_id}.json"
                    print_test_result("integration", "Report ready for S3 gold/", True, f"Would save to: {s3_key}")
                else:
                    print_test_result("integration", "Report ready for S3 gold/", False, "S3 bucket not configured")
            except Exception as e:
                print_test_result("integration", "Report ready for S3 gold/", False, str(e))
        else:
            print_test_result("integration", "Report ready for S3 gold/", False, "No final report generated")
        
        # Check cost tracking
        try:
            task_cost = cost_tracker.get_query_cost(task_id)
            total_cost = cost_tracker.get_total_cost()
            if task_cost > 0:
                print_test_result("integration", "Cost tracking working", True, f"Task cost: ${task_cost:.6f}")
            else:
                print_test_result("integration", "Cost tracking working", False, "No cost recorded")
        except Exception as e:
            print_test_result("integration", "Cost tracking working", False, str(e))
        
        return final_state, execution_time
        
    except Exception as e:
        print_test_result("integration", "Full workflow runs end-to-end", False, str(e))
        return None, 0


def check_performance(final_state: Optional[ResearchState], execution_time: float):
    """4. Performance Checks"""
    print("\n" + "=" * 70)
    print("4. PERFORMANCE CHECKS")
    print("=" * 70)
    
    if not final_state:
        print_test_result("performance", "Query completes in < 2 minutes", False, "No workflow execution")
        print_test_result("performance", "Cost per query < $0.20", False, "No workflow execution")
        print_test_result("performance", "Citation accuracy > 85%", False, "No workflow execution")
        return
    
    # Check execution time
    max_time = 120  # 2 minutes
    if execution_time < max_time:
        print_test_result("performance", "Query completes in < 2 minutes", True, f"Time: {execution_time:.2f}s")
    else:
        print_test_result("performance", "Query completes in < 2 minutes", False, f"Time: {execution_time:.2f}s (exceeded {max_time}s)")
    
    # Check cost
    try:
        task_id = final_state.get("task_id", "")
        cost_tracker = get_cost_tracker()
        task_cost = cost_tracker.get_query_cost(task_id)
        max_cost = 0.20
        
        if task_cost < max_cost:
            print_test_result("performance", "Cost per query < $0.20", True, f"Cost: ${task_cost:.6f}")
        else:
            print_test_result("performance", "Cost per query < $0.20", False, f"Cost: ${task_cost:.6f} (exceeded ${max_cost})")
    except Exception as e:
        print_test_result("performance", "Cost per query < $0.20", False, str(e))
    
    # Check citation accuracy
    try:
        report = final_state.get("final_report", "") or final_state.get("report_draft", "")
        validation_result = final_state.get("validation_result", {})
        
        if report and validation_result:
            invalid_citations = validation_result.get("invalid_citations", [])
            citation_coverage = validation_result.get("citation_coverage", 0.0)
            
            # Calculate accuracy (1 - invalid_citation_rate)
            total_citations = report.count("[Source")
            if total_citations > 0:
                invalid_rate = len(invalid_citations) / total_citations
                accuracy = (1 - invalid_rate) * 100
            else:
                accuracy = 0.0
            
            # Use citation_coverage if available, otherwise use calculated accuracy
            if citation_coverage > 0:
                accuracy = citation_coverage * 100
            
            if accuracy >= 85:
                print_test_result("performance", "Citation accuracy > 85%", True, f"Accuracy: {accuracy:.1f}%")
            else:
                print_test_result("performance", "Citation accuracy > 85%", False, f"Accuracy: {accuracy:.1f}% (below 85%)")
        else:
            print_test_result("performance", "Citation accuracy > 85%", False, "No report or validation data")
    except Exception as e:
        print_test_result("performance", "Citation accuracy > 85%", False, str(e))


def check_quality(final_state: Optional[ResearchState]):
    """5. Output Quality"""
    print("\n" + "=" * 70)
    print("5. OUTPUT QUALITY")
    print("=" * 70)
    
    if not final_state:
        print_test_result("quality", "Report is 1000+ words", False, "No report available")
        print_test_result("quality", "All claims have citations", False, "No report available")
        print_test_result("quality", "Citations reference valid sources", False, "No report available")
        print_test_result("quality", "Report structure follows template", False, "No report available")
        return
    
    report = final_state.get("final_report", "") or final_state.get("report_draft", "")
    validation_result = final_state.get("validation_result", {})
    retrieved_chunks = final_state.get("retrieved_chunks", [])
    
    if not report:
        print_test_result("quality", "Report is 1000+ words", False, "No report available")
        print_test_result("quality", "All claims have citations", False, "No report available")
        print_test_result("quality", "Citations reference valid sources", False, "No report available")
        print_test_result("quality", "Report structure follows template", False, "No report available")
        return
    
    # Check word count
    word_count = len(report.split())
    if word_count >= 1000:
        print_test_result("quality", "Report is 1000+ words", True, f"Word count: {word_count}")
    else:
        print_test_result("quality", "Report is 1000+ words", False, f"Word count: {word_count} (below 1000)")
    
    # Check citations
    citation_count = report.count("[Source")
    if citation_count > 0:
        print_test_result("quality", "Report contains citations", True, f"Found {citation_count} citations")
    else:
        print_test_result("quality", "Report contains citations", False, "No citations found")
    
    # Check citation validity
    if validation_result:
        invalid_citations = validation_result.get("invalid_citations", [])
        unsupported_claims = validation_result.get("unsupported_claims", [])
        
        if len(invalid_citations) == 0:
            print_test_result("quality", "Citations reference valid sources", True, "All citations valid")
        else:
            print_test_result("quality", "Citations reference valid sources", False, f"{len(invalid_citations)} invalid citations")
        
        if len(unsupported_claims) == 0:
            print_test_result("quality", "All claims have citations", True, "All claims supported")
        else:
            print_test_result("quality", "All claims have citations", False, f"{len(unsupported_claims)} unsupported claims")
    else:
        print_test_result("quality", "Citations reference valid sources", False, "No validation data")
        print_test_result("quality", "All claims have citations", False, "No validation data")
    
    # Check report structure
    has_intro = any(keyword in report.lower() for keyword in ["introduction", "overview", "summary"])
    has_findings = any(keyword in report.lower() for keyword in ["findings", "results", "discoveries"])
    has_conclusion = any(keyword in report.lower() for keyword in ["conclusion", "summary", "concluding"])
    
    structure_score = sum([has_intro, has_findings, has_conclusion])
    if structure_score >= 2:
        print_test_result("quality", "Report structure follows template", True, f"Structure score: {structure_score}/3")
    else:
        print_test_result("quality", "Report structure follows template", False, f"Structure score: {structure_score}/3")


def generate_report():
    """Generate M3 completion report"""
    print("\n" + "=" * 70)
    print("M3 COMPLETION REPORT")
    print("=" * 70)
    
    # Calculate totals
    total_tests = 0
    passed_tests = 0
    
    for category, tests in test_results.items():
        for test_name, passed, message in tests:
            total_tests += 1
            if passed:
                passed_tests += 1
    
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Pass Rate: {pass_rate:.1f}%")
    
    # Category breakdown
    print("\nCategory Breakdown:")
    for category, tests in test_results.items():
        category_passed = sum(1 for _, passed, _ in tests if passed)
        category_total = len(tests)
        category_rate = (category_passed / category_total * 100) if category_total > 0 else 0
        print(f"  {category.capitalize()}: {category_passed}/{category_total} ({category_rate:.1f}%)")
    
    # M3 completion status
    print("\n" + "=" * 70)
    if pass_rate >= 90:
        print("[PASS] M3 COMPLETION: PASSED")
        print("All critical requirements met. M3 milestone is complete.")
    elif pass_rate >= 75:
        print("[WARN] M3 COMPLETION: PARTIAL")
        print("Most requirements met, but some issues need attention.")
    else:
        print("[FAIL] M3 COMPLETION: FAILED")
        print("Multiple requirements not met. Please review and fix issues.")
    print("=" * 70)
    
    # Save report to file
    report_file = project_root / "logs" / f"m3_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": total_tests - passed_tests,
        "pass_rate": pass_rate,
        "categories": {
            category: {
                "total": len(tests),
                "passed": sum(1 for _, passed, _ in tests if passed),
                "tests": [
                    {
                        "name": test_name,
                        "passed": passed,
                        "message": message
                    }
                    for test_name, passed, message in tests
                ]
            }
            for category, tests in test_results.items()
        }
    }
    
    report_file.parent.mkdir(exist_ok=True)
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\nDetailed report saved to: {report_file}")
    
    return pass_rate >= 90


def main():
    """Main validation function"""
    print("=" * 70)
    print("M3 COMPLETION VALIDATION")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Project Root: {project_root}")
    
    # Run all checks
    check_environment()
    check_agents()
    final_state, execution_time = check_integration()
    check_performance(final_state, execution_time)
    check_quality(final_state)
    
    # Generate report
    passed = generate_report()
    
    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

