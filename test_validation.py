import pytest
from typing import Dict, List, Any
import re

class ReportValidator:
    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
        self.citation_pattern = re.compile(r'\[(\d+)\]')
    
    def validate_report(self, report: str, sources: List[Dict], metadata: Dict = None) -> Dict[str, Any]:
        validation_result = {
            'valid': True,
            'confidence': 0.0,
            'issues': [],
            'passed_checks': [],
            'failed_checks': []
        }
        
        checks = [
            self._check_length(report),
            self._check_citations(report, sources),
            self._check_structure(report),
            self._check_sources(sources),
            self._check_factual_claims(report),
            self._check_coherence(report),
        ]
        
        for check in checks:
            if check['passed']:
                validation_result['passed_checks'].append(check['name'])
            else:
                validation_result['failed_checks'].append(check['name'])
                validation_result['issues'].extend(check['issues'])
        
        validation_result['confidence'] = self._calculate_confidence(checks)
        validation_result['valid'] = validation_result['confidence'] >= self.confidence_threshold
        validation_result['needs_hitl'] = validation_result['confidence'] < self.confidence_threshold
        
        return validation_result
    
    def _check_length(self, report: str) -> Dict:
        min_length = 500
        max_length = 5000
        report_length = len(report)
        
        issues = []
        if report_length < min_length:
            issues.append(f"Report too short: {report_length} characters (minimum: {min_length})")
        elif report_length > max_length:
            issues.append(f"Report too long: {report_length} characters (maximum: {max_length})")
        
        return {
            'name': 'length_check',
            'passed': len(issues) == 0,
            'issues': issues,
            'score': 1.0 if len(issues) == 0 else 0.5
        }
    
    def _check_citations(self, report: str, sources: List[Dict]) -> Dict:
        citations = self.citation_pattern.findall(report)
        citation_numbers = [int(c) for c in citations]
        
        issues = []
        if not citations:
            issues.append("No citations found in report")
        
        invalid_citations = [c for c in citation_numbers if c > len(sources)]
        if invalid_citations:
            issues.append(f"Invalid citation numbers: {invalid_citations}")
        
        sentences = report.split('.')
        uncited_sentences = []
        for i, sentence in enumerate(sentences):
            if len(sentence) > 50 and not self.citation_pattern.search(sentence):
                uncited_sentences.append(i)
        
        if len(uncited_sentences) > len(sentences) * 0.3:
            issues.append(f"Too many sentences without citations: {len(uncited_sentences)}")
        
        return {
            'name': 'citation_check',
            'passed': len(issues) == 0,
            'issues': issues,
            'score': max(0.3, 1.0 - len(issues) * 0.2)
        }
    
    def _check_structure(self, report: str) -> Dict:
        issues = []
        
        if not report.strip():
            issues.append("Report is empty")
        
        paragraphs = report.split('\n\n')
        if len(paragraphs) < 2:
            issues.append("Report lacks proper paragraph structure")
        
        if not any(paragraph.strip().endswith('.') for paragraph in paragraphs):
            issues.append("Paragraphs don't end with proper punctuation")
        
        return {
            'name': 'structure_check',
            'passed': len(issues) == 0,
            'issues': issues,
            'score': 1.0 if len(issues) == 0 else 0.7
        }
    
    def _check_sources(self, sources: List[Dict]) -> Dict:
        issues = []
        
        if len(sources) < 3:
            issues.append(f"Insufficient sources: {len(sources)} (minimum: 3)")
        
        for i, source in enumerate(sources):
            if 'url' not in source or not source['url']:
                issues.append(f"Source {i+1} missing URL")
            if 'title' not in source or not source['title']:
                issues.append(f"Source {i+1} missing title")
        
        return {
            'name': 'source_check',
            'passed': len(issues) == 0,
            'issues': issues,
            'score': max(0.4, 1.0 - len(issues) * 0.1)
        }
    
    def _check_factual_claims(self, report: str) -> Dict:
        issues = []
        
        problematic_phrases = [
            "it is certain that",
            "without a doubt",
            "100%",
            "always",
            "never",
            "guaranteed"
        ]
        
        report_lower = report.lower()
        for phrase in problematic_phrases:
            if phrase in report_lower:
                issues.append(f"Overly absolute claim: '{phrase}'")
        
        return {
            'name': 'factual_claims_check',
            'passed': len(issues) == 0,
            'issues': issues,
            'score': 1.0 if len(issues) == 0 else 0.8
        }
    
    def _check_coherence(self, report: str) -> Dict:
        issues = []
        
        sentences = report.split('.')
        if len(sentences) > 0:
            avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
            if avg_sentence_length > 150:
                issues.append("Sentences are too long on average")
            elif avg_sentence_length < 20:
                issues.append("Sentences are too short on average")
        
        transition_words = ['however', 'moreover', 'furthermore', 'therefore', 'thus', 'additionally']
        has_transitions = any(word in report.lower() for word in transition_words)
        if not has_transitions:
            issues.append("Report lacks transition words for coherence")
        
        return {
            'name': 'coherence_check',
            'passed': len(issues) == 0,
            'issues': issues,
            'score': 1.0 if len(issues) == 0 else 0.7
        }
    
    def _calculate_confidence(self, checks: List[Dict]) -> float:
        if not checks:
            return 0.0
        
        total_score = sum(check['score'] for check in checks)
        return total_score / len(checks)

class TestReportValidation:
    @pytest.fixture
    def validator(self) -> ReportValidator:
        return ReportValidator(confidence_threshold=0.7)
    
    @pytest.fixture
    def sample_report(self) -> str:
        return """
        Artificial Intelligence has made significant progress in recent years [1]. 
        The field encompasses various subdomains including machine learning, 
        natural language processing, and computer vision [2].
        
        Machine learning algorithms have become increasingly sophisticated [3]. 
        Deep learning, in particular, has achieved remarkable results in image 
        recognition and natural language understanding [4]. These advances have 
        enabled practical applications across industries [5].
        
        However, challenges remain in areas such as explainability and bias [6]. 
        Researchers continue to work on making AI systems more transparent and 
        fair [7]. The future of AI looks promising with ongoing research and 
        development [8].
        """
    
    @pytest.fixture
    def sample_sources(self) -> List[Dict]:
        return [
            {"url": "https://example.com/1", "title": "AI Progress Report"},
            {"url": "https://example.com/2", "title": "AI Subdomains Overview"},
            {"url": "https://example.com/3", "title": "ML Algorithm Advances"},
            {"url": "https://example.com/4", "title": "Deep Learning Achievements"},
            {"url": "https://example.com/5", "title": "AI Applications"},
            {"url": "https://example.com/6", "title": "AI Challenges"},
            {"url": "https://example.com/7", "title": "AI Transparency Research"},
            {"url": "https://example.com/8", "title": "Future of AI"},
        ]
    
    def test_valid_report(self, validator: ReportValidator, sample_report: str, sample_sources: List[Dict]):
        result = validator.validate_report(sample_report, sample_sources)
        
        assert result['valid'] == True
        assert result['confidence'] >= 0.7
        assert len(result['passed_checks']) > len(result['failed_checks'])
    
    def test_report_too_short(self, validator: ReportValidator, sample_sources: List[Dict]):
        short_report = "This is too short [1]."
        result = validator.validate_report(short_report, sample_sources)
        
        assert 'length_check' in result['failed_checks']
        assert any("too short" in issue.lower() for issue in result['issues'])
    
    def test_missing_citations(self, validator: ReportValidator, sample_sources: List[Dict]):
        report_no_citations = """
        This is a report without any citations. It talks about various topics 
        but never references any sources. This is problematic for credibility.
        """ * 5
        
        result = validator.validate_report(report_no_citations, sample_sources)
        
        assert 'citation_check' in result['failed_checks']
        assert any("no citations" in issue.lower() for issue in result['issues'])
    
    def test_invalid_citations(self, validator: ReportValidator, sample_sources: List[Dict]):
        report_invalid = "This has invalid citation [99] and [100]."
        result = validator.validate_report(report_invalid, sample_sources)
        
        assert 'citation_check' in result['failed_checks']
        assert any("invalid" in issue.lower() for issue in result['issues'])
    
    def test_insufficient_sources(self, validator: ReportValidator, sample_report: str):
        few_sources = [
            {"url": "https://example.com/1", "title": "Source 1"},
        ]
        
        result = validator.validate_report(sample_report, few_sources)
        
        assert 'source_check' in result['failed_checks']
        assert any("insufficient sources" in issue.lower() for issue in result['issues'])
    
    def test_confidence_threshold(self, validator: ReportValidator):
        poor_report = "Short report [1]."
        sources = [{"url": "https://example.com", "title": "Source"}]
        
        result = validator.validate_report(poor_report, sources)
        
        assert result['confidence'] < 0.7
        assert result['valid'] == False
        assert result['needs_hitl'] == True
    
    def test_absolute_claims(self, validator: ReportValidator, sample_sources: List[Dict]):
        report_absolute = """
        It is certain that AI will replace all jobs [1]. This is guaranteed 
        to happen within 5 years [2]. There is never any doubt about this [3].
        """ * 3
        
        result = validator.validate_report(report_absolute, sample_sources)
        
        assert 'factual_claims_check' in result['failed_checks']
        assert any("absolute claim" in issue.lower() for issue in result['issues'])
    
    def test_structure_check(self, validator: ReportValidator, sample_sources: List[Dict]):
        no_structure = "This is all one big paragraph with no structure " * 50
        result = validator.validate_report(no_structure, sample_sources)
        
        assert 'structure_check' in result['failed_checks']
    
    def test_coherence_check(self, validator: ReportValidator, sample_sources: List[Dict]):
        incoherent = "Short [1]. Choppy [2]. No flow [3]. Bad [4]." * 20
        result = validator.validate_report(incoherent, sample_sources)
        
        assert 'coherence_check' in result['failed_checks']