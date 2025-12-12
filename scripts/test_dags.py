"""
Test script to run Airflow DAG tasks locally without full Airflow installation.

This allows testing DAG tasks on Windows without needing WSL2 or Docker.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add dags directory to path
project_root = Path(__file__).parent.parent
dags_dir = project_root / "dags"
sys.path.insert(0, str(dags_dir))

# Mock Airflow context
class MockTaskInstance:
    def __init__(self):
        self.xcom_data = {}
    
    def xcom_pull(self, task_ids=None, key=None):
        if task_ids and task_ids in self.xcom_data:
            return self.xcom_data[task_ids]
        return None
    
    def xcom_push(self, key, value):
        if not hasattr(self, 'current_task_id'):
            self.current_task_id = 'test_task'
        if self.current_task_id not in self.xcom_data:
            self.xcom_data[self.current_task_id] = {}
        self.xcom_data[self.current_task_id][key] = value

class MockContext:
    def __init__(self):
        self.ti = MockTaskInstance()

def test_ingestion_dag():
    """Test ingestion DAG tasks."""
    print("=" * 70)
    print("Testing Ingestion DAG Tasks")
    print("=" * 70)
    
    try:
        from common import arxiv_utils, s3_utils
        
        # Test 1: Check new papers
        print("\n1. Testing check_new_papers_task...")
        context = MockContext()
        
        # Import task function
        sys.path.insert(0, str(dags_dir))
        from ingestion_dag import check_new_papers_task
        
        result = check_new_papers_task(**{'ti': context.ti})
        print(f"✓ Found {result.get('count', 0)} papers")
        
        # Store result for next task
        context.ti.xcom_data['check_new_papers_task'] = result
        
        # Test 2: Download PDFs (limited test)
        print("\n2. Testing download_pdfs_task...")
        from ingestion_dag import download_pdfs_task
        
        # Limit to first 2 papers for testing
        if result.get('papers'):
            limited_result = {
                'papers': result['papers'][:2],  # Only test with 2 papers
                'paper_ids': result['paper_ids'][:2],
                'count': min(2, result['count'])
            }
            context.ti.xcom_data['check_new_papers_task'] = limited_result
            
            download_result = download_pdfs_task(**{'ti': context.ti})
            print(f"✓ Downloaded {download_result.get('count', 0)} PDFs")
            
            # Test 3: Upload to S3
            print("\n3. Testing upload_to_s3_bronze_task...")
            context.ti.xcom_data['download_pdfs_task'] = download_result
            from ingestion_dag import upload_to_s3_bronze_task
            
            upload_result = upload_to_s3_bronze_task(**{'ti': context.ti})
            print(f"✓ Uploaded {upload_result.get('uploaded_count', 0)} PDFs to S3")
        else:
            print("⚠ No papers found to test download/upload")
        
        print("\nSUCCESS: Ingestion DAG tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"\nERROR: Error testing ingestion DAG: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_processing_dag():
    """Test processing DAG tasks."""
    print("\n" + "=" * 70)
    print("Testing Processing DAG Tasks")
    print("=" * 70)
    
    try:
        from common import s3_utils, processing_utils
        
        # Test 1: List unprocessed papers
        print("\n1. Testing list_unprocessed_papers_task...")
        context = MockContext()
        
        from processing_dag import list_unprocessed_papers_task
        
        result = list_unprocessed_papers_task(**{'ti': context.ti})
        print(f"✓ Found {result.get('count', 0)} unprocessed papers")
        
        context.ti.xcom_data['list_unprocessed_papers_task'] = result
        
        if result.get('s3_keys'):
            # Test 2: Extract text (limited)
            print("\n2. Testing extract_text_parallel_task...")
            from processing_dag import extract_text_parallel_task
            
            extract_result = extract_text_parallel_task(**{'ti': context.ti})
            print(f"✓ Extracted text from {extract_result.get('count', 0)} PDFs")
            
            context.ti.xcom_data['extract_text_parallel_task'] = extract_result
            
            # Test 3: Chunk text
            print("\n3. Testing chunk_text_task...")
            from processing_dag import chunk_text_task
            
            chunk_result = chunk_text_task(**{'ti': context.ti})
            print(f"✓ Created {chunk_result.get('count', 0)} chunks")
            
            context.ti.xcom_data['chunk_text_task'] = chunk_result
            
            # Test 4: Upload chunks
            print("\n4. Testing upload_chunks_to_s3_silver_task...")
            from processing_dag import upload_chunks_to_s3_silver_task
            
            upload_result = upload_chunks_to_s3_silver_task(**{'ti': context.ti})
            print(f"✓ Uploaded {upload_result.get('uploaded_count', 0)} chunks")
        else:
            print("⚠ No unprocessed papers found")
        
        print("\nSUCCESS: Processing DAG tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"\nERROR: Error testing processing DAG: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_embedding_dag():
    """Test embedding DAG tasks."""
    print("\n" + "=" * 70)
    print("Testing Embedding DAG Tasks")
    print("=" * 70)
    
    try:
        from common import embedding_utils
        
        # Test 1: List new chunks
        print("\n1. Testing list_new_chunks_task...")
        context = MockContext()
        
        from embedding_dag import list_new_chunks_task
        
        result = list_new_chunks_task(**{'ti': context.ti})
        print(f"✓ Found {result.get('count', 0)} new chunks needing embeddings")
        
        context.ti.xcom_data['list_new_chunks_task'] = result
        
        if result.get('s3_keys'):
            # Test 2: Generate embeddings (limited to avoid API costs)
            print("\n2. Testing generate_embeddings_batch_task (limited)...")
            from embedding_dag import generate_embeddings_batch_task
            
            # Limit to first 5 chunks for testing
            limited_result = {
                's3_keys': result['s3_keys'][:5],
                'chunk_ids': result['chunk_ids'][:5],
                'count': min(5, result['count'])
            }
            context.ti.xcom_data['list_new_chunks_task'] = limited_result
            
            embed_result = generate_embeddings_batch_task(**{'ti': context.ti})
            print(f"✓ Generated {embed_result.get('count', 0)} embeddings")
            
            context.ti.xcom_data['generate_embeddings_batch_task'] = embed_result
            
            # Test 3: Upsert to Pinecone
            print("\n3. Testing upsert_to_pinecone_task...")
            from embedding_dag import upsert_to_pinecone_task
            
            upsert_result = upsert_to_pinecone_task(**{'ti': context.ti})
            print(f"✓ Upserted {upsert_result.get('upserted_count', 0)} vectors to Pinecone")
        else:
            print("WARNING: No new chunks found")
        
        print("\n✓ Embedding DAG tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n✗ Error testing embedding DAG: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all DAG tests."""
    print("Airflow DAG Local Testing Script")
    print("=" * 70)
    print("\nNote: This tests DAG tasks locally without full Airflow.")
    print("For production, use Docker or WSL2.\n")
    
    # Check environment variables
    required_vars = ['AWS_ACCESS_KEY_ID', 'OPENAI_API_KEY', 'PINECONE_API_KEY', 'S3_BUCKET_NAME']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"⚠ Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("Some tests may fail.\n")
    
    results = []
    
    # Test each DAG
    try:
        results.append(("Ingestion DAG", test_ingestion_dag()))
    except Exception as e:
        print(f"Failed to test Ingestion DAG: {e}")
        results.append(("Ingestion DAG", False))
    
    try:
        results.append(("Processing DAG", test_processing_dag()))
    except Exception as e:
        print(f"Failed to test Processing DAG: {e}")
        results.append(("Processing DAG", False))
    
    try:
        results.append(("Embedding DAG", test_embedding_dag()))
    except Exception as e:
        print(f"Failed to test Embedding DAG: {e}")
        results.append(("Embedding DAG", False))
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    for name, success in results:
        status = "PASSED" if success else "FAILED"
        print(f"{name}: {status}")
    
    all_passed = all(result[1] for result in results)
    if all_passed:
        print("\nSUCCESS: All DAG tests passed!")
    else:
        print("\nWARNING: Some tests failed. Check errors above.")

if __name__ == "__main__":
    main()
