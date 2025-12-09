import pytest
import re
from typing import List, Tuple, Dict
from dataclasses import dataclass

@dataclass
class Citation:
    citation_number: int
    text: str
    position: Tuple[int, int]

class CitationExtractor:
    def __init__(self):
        self.citation_pattern = re.compile(r'\[(\d+(?:,\s*\d+)*)\]')
        self.multi_citation_pattern = re.compile(r'\[(\d+)\]\[(\d+)\](?:\[(\d+)\])?')
    
    def extract_citations(self, text: str) -> List[Citation]:
        citations = []
        
        for match in self.citation_pattern.finditer(text):
            citation_text = match.group(0)
            citation_numbers = match.group(1)
            
            for number_str in citation_numbers.split(','):
                number = int(number_str.strip())
                citations.append(Citation(
                    citation_number=number,
                    text=citation_text,
                    position=(match.start(), match.end())
                ))
        
        for match in self.multi_citation_pattern.finditer(text):
            for i, group in enumerate(match.groups()):
                if group:
                    citations.append(Citation(
                        citation_number=int(group),
                        text=f"[{group}]",
                        position=(match.start() + i * 3, match.start() + (i + 1) * 3)
                    ))
        
        return self._deduplicate_citations(citations)
    
    def _deduplicate_citations(self, citations: List[Citation]) -> List[Citation]:
        seen = set()
        unique_citations = []
        
        for citation in citations:
            key = (citation.citation_number, citation.position)
            if key not in seen:
                seen.add(key)
                unique_citations.append(citation)
        
        return sorted(unique_citations, key=lambda x: x.position[0])
    
    def validate_citations(self, text: str, num_sources: int) -> Dict[str, any]:
        citations = self.extract_citations(text)
        invalid_citations = []
        missing_citations = []
        
        cited_numbers = set(c.citation_number for c in citations)
        
        for citation in citations:
            if citation.citation_number > num_sources:
                invalid_citations.append(citation.citation_number)
        
        for i in range(1, num_sources + 1):
            if i not in cited_numbers:
                missing_citations.append(i)
        
        return {
            'valid': len(invalid_citations) == 0,
            'total_citations': len(citations),
            'unique_citations': len(cited_numbers),
            'invalid_citations': list(set(invalid_citations)),
            'missing_citations': missing_citations,
            'citations': citations
        }
    
    def extract_claims(self, text: str) -> List[Dict[str, any]]:
        sentences = text.split('.')
        claims = []
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            citations = self.extract_citations(sentence)
            
            claims.append({
                'sentence': sentence,
                'sentence_index': i,
                'has_citations': len(citations) > 0,
                'citation_numbers': [c.citation_number for c in citations],
                'num_citations': len(citations)
            })
        
        return claims

class TestCitationExtraction:
    @pytest.fixture
    def extractor(self) -> CitationExtractor:
        return CitationExtractor()
    
    @pytest.fixture
    def sample_report_with_citations(self) -> str:
        return """
        Recent advances in AI have been remarkable [1]. Machine learning 
        algorithms have improved significantly [2][3]. Deep learning, in 
        particular, has shown exceptional results [1][4]. Natural language 
        processing has evolved rapidly [5].
        """
    
    def test_extract_citations(self, extractor: CitationExtractor, sample_report_with_citations: str):
        citations = extractor.extract_citations(sample_report_with_citations)
        
        assert len(citations) > 0
        assert all(isinstance(c, Citation) for c in citations)
        
        citation_numbers = [c.citation_number for c in citations]
        assert 1 in citation_numbers
        assert 2 in citation_numbers
        assert 3 in citation_numbers
        assert 4 in citation_numbers
        assert 5 in citation_numbers
    
    def test_multiple_citations(self, extractor: CitationExtractor):
        text = "This is supported by multiple sources [1, 2, 3]."
        citations = extractor.extract_citations(text)
        
        assert len(citations) == 3
        assert citations[0].citation_number == 1
        assert citations[1].citation_number == 2
        assert citations[2].citation_number == 3
    
    def test_consecutive_citations(self, extractor: CitationExtractor):
        text = "This is supported [1][2][3] by sources."
        citations = extractor.extract_citations(text)
        
        assert len(citations) >= 3
        citation_numbers = [c.citation_number for c in citations]
        assert 1 in citation_numbers
        assert 2 in citation_numbers
        assert 3 in citation_numbers
    
    def test_validate_citations(self, extractor: CitationExtractor, sample_report_with_citations: str):
        result = extractor.validate_citations(sample_report_with_citations, 5)
        
        assert result['valid'] == True
        assert result['total_citations'] > 0
        assert result['unique_citations'] == 5
        assert result['invalid_citations'] == []
        assert result['missing_citations'] == []
    
    def test_invalid_citations(self, extractor: CitationExtractor):
        text = "This has an invalid citation [10] when we only have 5 sources."
        result = extractor.validate_citations(text, 5)
        
        assert result['valid'] == False
        assert 10 in result['invalid_citations']
    
    def test_missing_citations(self, extractor: CitationExtractor):
        text = "This only cites [1] and [3] from 3 sources."
        result = extractor.validate_citations(text, 3)
        
        assert result['valid'] == True
        assert 2 in result['missing_citations']
    
    def test_extract_claims(self, extractor: CitationExtractor, sample_report_with_citations: str):
        claims = extractor.extract_claims(sample_report_with_citations)
        
        assert len(claims) > 0
        assert all('sentence' in claim for claim in claims)
        assert all('has_citations' in claim for claim in claims)
        assert any(claim['has_citations'] for claim in claims)
    
    def test_no_citations(self, extractor: CitationExtractor):
        text = "This text has no citations at all."
        citations = extractor.extract_citations(text)
        
        assert citations == []
    
    def test_citation_position(self, extractor: CitationExtractor):
        text = "Start [1] middle [2] end [3]."
        citations = extractor.extract_citations(text)
        
        assert citations[0].position[0] < citations[1].position[0]
        assert citations[1].position[0] < citations[2].position[0]