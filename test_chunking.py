import pytest
from typing import List
import hashlib

class ChunkingStrategy:
    FIXED = "fixed"
    SEMANTIC = "semantic"
    PARAGRAPH = "paragraph"

class TextChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, strategy: str = ChunkingStrategy.SEMANTIC):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy
    
    def chunk_text(self, text: str) -> List[str]:
        if not text:
            return []
        
        if len(text) <= self.chunk_size:
            return [text]
        
        if self.strategy == ChunkingStrategy.SEMANTIC:
            return self._semantic_chunk(text)
        elif self.strategy == ChunkingStrategy.PARAGRAPH:
            return self._paragraph_chunk(text)
        else:
            return self._fixed_chunk(text)
    
    def _fixed_chunk(self, text: str) -> List[str]:
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap if end < len(text) else end
        
        return chunks
    
    def _semantic_chunk(self, text: str) -> List[str]:
        sentences = text.replace('!', '.').replace('?', '.').split('.')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            if current_size + sentence_size > self.chunk_size and current_chunk:
                chunks.append('. '.join(current_chunk) + '.')
                overlap_sentences = []
                overlap_size = 0
                
                for s in reversed(current_chunk):
                    if overlap_size + len(s) <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_size += len(s)
                    else:
                        break
                
                current_chunk = overlap_sentences
                current_size = overlap_size
            
            current_chunk.append(sentence)
            current_size += sentence_size
        
        if current_chunk:
            chunks.append('. '.join(current_chunk) + '.')
        
        return chunks
    
    def _paragraph_chunk(self, text: str) -> List[str]:
        paragraphs = text.split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for paragraph in paragraphs:
            paragraph_size = len(paragraph)
            
            if current_size + paragraph_size > self.chunk_size and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(paragraph)
            current_size += paragraph_size
        
        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks
    
    def chunk_text_with_metadata(self, text: str, metadata: dict) -> List[dict]:
        chunks = self.chunk_text(text)
        result = []
        
        for i, chunk in enumerate(chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata['chunk_index'] = i
            chunk_metadata['chunk_id'] = hashlib.md5(chunk.encode()).hexdigest()
            chunk_metadata['total_chunks'] = len(chunks)
            
            result.append({
                'text': chunk,
                'metadata': chunk_metadata
            })
        
        return result

class TestTextChunking:
    @pytest.fixture
    def sample_text(self) -> str:
        return """
        Artificial Intelligence has revolutionized many fields. 
        Machine learning, a subset of AI, enables computers to learn from data.
        Deep learning has shown remarkable results in image recognition.
        Natural language processing helps computers understand human language.
        Computer vision enables machines to interpret visual information.
        Robotics combines AI with mechanical systems for automation.
        """ * 10
    
    @pytest.fixture
    def chunker(self) -> TextChunker:
        return TextChunker(
            chunk_size=100,
            chunk_overlap=20,
            strategy=ChunkingStrategy.SEMANTIC
        )
    
    def test_basic_chunking(self, chunker: TextChunker, sample_text: str):
        chunks = chunker.chunk_text(sample_text)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert all(len(chunk) <= chunker.chunk_size * 1.2 for chunk in chunks)
    
    def test_chunk_overlap(self, chunker: TextChunker, sample_text: str):
        chunks = chunker.chunk_text(sample_text)
        
        for i in range(len(chunks) - 1):
            chunk1_end = chunks[i][-chunker.chunk_overlap:]
            chunk2_start = chunks[i + 1][:chunker.chunk_overlap]
            
            assert any(word in chunk2_start for word in chunk1_end.split()[-3:])
    
    def test_semantic_chunking(self, sample_text: str):
        chunker = TextChunker(
            chunk_size=100,
            chunk_overlap=20,
            strategy=ChunkingStrategy.SEMANTIC
        )
        chunks = chunker.chunk_text(sample_text)
        
        for chunk in chunks:
            assert chunk.rstrip().endswith(('.', '!', '?')) or chunk == chunks[-1]
    
    def test_empty_text(self, chunker: TextChunker):
        chunks = chunker.chunk_text("")
        assert chunks == []
    
    def test_short_text(self, chunker: TextChunker):
        short_text = "This is a short text."
        chunks = chunker.chunk_text(short_text)
        
        assert len(chunks) == 1
        assert chunks[0] == short_text
    
    def test_preserve_metadata(self, chunker: TextChunker, sample_text: str):
        metadata = {"source": "test", "page": 1}
        chunks = chunker.chunk_text_with_metadata(sample_text, metadata)
        
        assert all(chunk["metadata"]["source"] == "test" for chunk in chunks)
        assert all("chunk_index" in chunk["metadata"] for chunk in chunks)
    
    @pytest.mark.parametrize("chunk_size,expected_min_chunks", [
        (50, 10),
        (100, 5),
        (200, 3),
    ])
    def test_different_chunk_sizes(self, sample_text: str, chunk_size: int, expected_min_chunks: int):
        chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=10)
        chunks = chunker.chunk_text(sample_text)
        
        assert len(chunks) >= expected_min_chunks
    
    def test_paragraph_chunking(self, sample_text: str):
        chunker = TextChunker(
            chunk_size=200,
            chunk_overlap=50,
            strategy=ChunkingStrategy.PARAGRAPH
        )
        chunks = chunker.chunk_text(sample_text)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)