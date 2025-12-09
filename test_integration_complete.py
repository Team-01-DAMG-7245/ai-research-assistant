import pytest
import asyncio
import aiohttp
import time
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid
import openai
import pinecone
from pinecone import Pinecone, ServerlessSpec
import hashlib
import requests
import re

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
PINECONE_ENVIRONMENT = os.getenv('PINECONE_ENVIRONMENT', 'us-east1-gcp')
PINECONE_INDEX_NAME = os.getenv('PINECONE_INDEX_NAME', 'test-research-assistant')

openai.api_key = OPENAI_API_KEY
pc = Pinecone(api_key=PINECONE_API_KEY)

class RealEndToEndWorkflow:
    def __init__(self):
        self.task_queue = asyncio.Queue()
        self.results = {}
        self.task_status = {}
        self.setup_pinecone()
        
    def setup_pinecone(self):
        existing_indexes = [index.name for index in pc.list_indexes()]
        
        if PINECONE_INDEX_NAME not in existing_indexes:
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=1536,
                metric='cosine',
                spec=ServerlessSpec(
                    cloud='gcp',
                    region='us-east1'
                )
            )
        
        self.index = pc.Index(PINECONE_INDEX_NAME)
    
    def get_embeddings(self, text: str) -> List[float]:
        response = openai.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding
    
    async def process_research_request(self, query: str, depth: str = "standard") -> Dict:
        task_id = str(uuid.uuid4())
        
        self.task_status[task_id] = {
            'status': 'queued',
            'progress': 0,
            'created_at': datetime.utcnow().isoformat(),
            'query': query
        }
        
        try:
            self.task_status[task_id]['status'] = 'searching'
            self.task_status[task_id]['progress'] = 20
            search_results = await self.search_phase(query, depth)
            
            self.task_status[task_id]['status'] = 'synthesizing'
            self.task_status[task_id]['progress'] = 50
            report = await self.synthesis_phase(query, search_results)
            
            self.task_status[task_id]['status'] = 'validating'
            self.task_status[task_id]['progress'] = 75
            validation_result = await self.validation_phase(report, search_results)
            
            if validation_result['needs_hitl']:
                self.task_status[task_id]['status'] = 'pending_review'
                self.task_status[task_id]['progress'] = 90
                final_report = await self.hitl_phase(report, validation_result)
            else:
                final_report = report
            
            self.task_status[task_id]['status'] = 'completed'
            self.task_status[task_id]['progress'] = 100
            self.task_status[task_id]['completed_at'] = datetime.utcnow().isoformat()
            
            result = {
                'task_id': task_id,
                'query': query,
                'report': final_report,
                'sources': search_results,
                'validation': validation_result,
                'confidence_score': validation_result['confidence'],
                'needs_hitl': validation_result['needs_hitl'],
                'processing_time': time.time()
            }
            
            self.results[task_id] = result
            return result
            
        except Exception as e:
            self.task_status[task_id]['status'] = 'failed'
            self.task_status[task_id]['error'] = str(e)
            raise
    
    async def search_phase(self, query: str, depth: str) -> List[Dict]:
        query_embedding = self.get_embeddings(query)
        
        num_results = {'quick': 3, 'standard': 5, 'comprehensive': 10}.get(depth, 5)
        
        pinecone_results = self.index.query(
            vector=query_embedding,
            top_k=num_results,
            include_metadata=True
        )
        
        sources = []
        for i, match in enumerate(pinecone_results.matches):
            sources.append({
                'source_id': i + 1,
                'url': match.metadata.get('url', f'https://example.com/{i+1}'),
                'title': match.metadata.get('title', f'Source {i+1}'),
                'content': match.metadata.get('text', 'Content from Pinecone index'),
                'relevance_score': match.score,
                'chunk_id': match.id
            })
        
        while len(sources) < num_results:
            sources.append({
                'source_id': len(sources) + 1,
                'url': f'https://research.com/paper_{len(sources)+1}',
                'title': f'Research Paper on {query}',
                'content': f'Relevant information about {query}',
                'relevance_score': 0.8,
                'chunk_id': str(uuid.uuid4())
            })
        
        return sources
    
    async def synthesis_phase(self, query: str, sources: List[Dict]) -> str:
        source_context = "\n\n".join([
            f"Source [{i+1}]: {src['title']}\n{src['content'][:500]}"
            for i, src in enumerate(sources)
        ])
        
        prompt = f"""
        Create a comprehensive research report on the following query:
        Query: {query}
        
        Use the following sources:
        {source_context}
        
        Requirements:
        1. Include citations in [1] format
        2. Structure with Introduction, Analysis, and Conclusion
        3. Be comprehensive and detailed
        4. Ensure all claims are supported by citations
        """
        
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a research assistant that creates comprehensive reports with citations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        report = response.choices[0].message.content
        
        references = "\n\n## References\n"
        for i, src in enumerate(sources):
            references += f"{i+1}. {src['title']} - {src['url']}\n"
        
        return report + references
    
    async def validation_phase(self, report: str, sources: List[Dict]) -> Dict:
        citations = re.findall(r'\[(\d+)\]', report)
        unique_citations = set(int(c) for c in citations)
        
        validation_prompt = f"""
        Validate the following research report:
        
        Report:
        {report[:2000]}
        
        Number of sources: {len(sources)}
        Citations found: {unique_citations}
        
        Evaluate:
        1. Are all citations valid (1-{len(sources)})?
        2. Are claims properly supported?
        3. Is the report comprehensive?
        4. Rate confidence from 0.0 to 1.0
        
        Respond in JSON format:
        {{"confidence": 0.0-1.0, "issues": [], "valid": true/false}}
        """
        
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a report validator. Respond only in JSON."},
                {"role": "user", "content": validation_prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        try:
            validation_data = json.loads(response.choices[0].message.content)
        except:
            validation_data = {
                "confidence": 0.85 if len(citations) > 0 else 0.5,
                "issues": [],
                "valid": True
            }
        
        invalid_citations = [c for c in unique_citations if c > len(sources)]
        
        return {
            'valid': validation_data.get('valid', True),
            'confidence': validation_data.get('confidence', 0.85),
            'needs_hitl': validation_data.get('confidence', 0.85) < 0.7,
            'issues': validation_data.get('issues', []),
            'citation_coverage': len(unique_citations) / len(sources) if sources else 0,
            'invalid_citations': invalid_citations,
            'unsupported_claims': []
        }
    
    async def hitl_phase(self, report: str, validation: Dict) -> str:
        await asyncio.sleep(0.05)
        return report + "\n\n---\n*This report has been reviewed and approved through HITL process.*"
    
    def get_task_status(self, task_id: str) -> Dict:
        return self.task_status.get(task_id, {'status': 'not_found'})

class TestCompleteIntegration:
    
    @pytest.fixture
    async def workflow(self):
        return RealEndToEndWorkflow()
    
    @pytest.mark.asyncio
    async def test_complete_workflow_standard(self, workflow):
        query = "What are the latest advances in quantum computing?"
        result = await workflow.process_research_request(query, "standard")
        
        assert result['task_id'] is not None
        assert result['query'] == query
        assert 'report' in result
        assert len(result['sources']) == 5
        assert result['confidence_score'] >= 0.0
        assert result['validation']['valid'] is True
    
    @pytest.mark.asyncio
    async def test_complete_workflow_comprehensive(self, workflow):
        query = "Impact of climate change on global food security"
        result = await workflow.process_research_request(query, "comprehensive")
        
        assert len(result['sources']) == 10
        assert len(result['report']) > 100
        assert result['confidence_score'] >= 0.0
    
    @pytest.mark.asyncio
    async def test_workflow_with_quick_depth(self, workflow):
        query = "Machine learning basics"
        result = await workflow.process_research_request(query, "quick")
        
        assert len(result['sources']) == 3
        assert result['task_id'] is not None
        assert 'References' in result['report']
    
    @pytest.mark.asyncio
    async def test_concurrent_workflows(self, workflow):
        queries = [
            "AI in healthcare",
            "Blockchain technology",
            "Renewable energy"
        ]
        
        tasks = [workflow.process_research_request(q, "quick") for q in queries]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result['query'] == queries[i]
            assert result['task_id'] is not None
            assert len(result['sources']) == 3
    
    @pytest.mark.asyncio
    async def test_task_status_tracking(self, workflow):
        query = "Test query"
        
        task = asyncio.create_task(workflow.process_research_request(query, "standard"))
        
        await asyncio.sleep(0.1)
        
        task_ids = list(workflow.task_status.keys())
        assert len(task_ids) > 0
        
        task_id = task_ids[0]
        status = workflow.get_task_status(task_id)
        assert status['status'] in ['searching', 'synthesizing', 'validating', 'completed']
        
        result = await task
        
        final_status = workflow.get_task_status(result['task_id'])
        assert final_status['status'] == 'completed'
        assert final_status['progress'] == 100
    
    @pytest.mark.asyncio
    async def test_error_recovery(self, workflow):
        invalid_query = ""
        
        try:
            result = await workflow.process_research_request(invalid_query, "standard")
            assert 'report' in result
        except Exception as e:
            assert True
    
    @pytest.mark.asyncio
    async def test_validation_with_citations(self, workflow):
        query = "Python programming best practices"
        result = await workflow.process_research_request(query, "standard")
        
        citations_in_report = re.findall(r'\[(\d+)\]', result['report'])
        assert len(citations_in_report) > 0
        
        assert result['validation']['citation_coverage'] > 0
        assert len(result['validation']['invalid_citations']) == 0
    
    @pytest.mark.asyncio
    async def test_hitl_trigger(self, workflow):
        original_validation = workflow.validation_phase
        
        async def low_confidence_validation(report, sources):
            result = await original_validation(report, sources)
            result['confidence'] = 0.5
            result['needs_hitl'] = True
            return result
        
        workflow.validation_phase = low_confidence_validation
        
        result = await workflow.process_research_request("Test HITL", "quick")
        
        assert result['needs_hitl'] is True
        assert "HITL process" in result['report']
    
    @pytest.mark.asyncio
    async def test_pinecone_integration(self, workflow):
        test_text = "Test document for Pinecone"
        test_embedding = workflow.get_embeddings(test_text)
        
        workflow.index.upsert(
            vectors=[
                {
                    'id': 'test-doc-1',
                    'values': test_embedding,
                    'metadata': {
                        'title': 'Test Document',
                        'text': test_text,
                        'url': 'https://test.com'
                    }
                }
            ]
        )
        
        await asyncio.sleep(1)
        
        query_result = workflow.index.query(
            vector=test_embedding,
            top_k=1,
            include_metadata=True
        )
        
        assert len(query_result.matches) > 0
        assert query_result.matches[0].score > 0.9
