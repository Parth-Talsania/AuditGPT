"""
Hybrid retriever for AuditGPT RAG system.

Combines lexical (BM25-style) and semantic (embedding) retrieval
for finding relevant note chunks.
"""

from typing import List, Dict, Optional, Any
from collections import defaultdict
import re
import math

from auditgpt.evidence.models import NoteChunk
from auditgpt.evidence.store import EvidenceStore


class BM25Retriever:
    """
    BM25-based lexical retrieval.
    
    Fast keyword matching using TF-IDF-like scoring.
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._documents: List[NoteChunk] = []
        self._doc_freqs: Dict[str, int] = defaultdict(int)
        self._doc_lengths: List[int] = []
        self._avg_doc_length: float = 0
        self._indexed = False
    
    def index(self, chunks: List[NoteChunk]):
        """Index documents for retrieval."""
        self._documents = chunks
        self._doc_freqs = defaultdict(int)
        self._doc_lengths = []
        
        # Calculate document frequencies
        for chunk in chunks:
            tokens = self._tokenize(chunk.text)
            self._doc_lengths.append(len(tokens))
            
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self._doc_freqs[token] += 1
        
        # Average document length
        if self._doc_lengths:
            self._avg_doc_length = sum(self._doc_lengths) / len(self._doc_lengths)
        
        self._indexed = True
    
    def search(self, query: str, top_k: int = 5) -> List[tuple]:
        """
        Search for relevant documents.
        
        Returns list of (score, chunk) tuples.
        """
        if not self._indexed:
            return []
        
        query_tokens = self._tokenize(query)
        scores = []
        
        n_docs = len(self._documents)
        
        for i, chunk in enumerate(self._documents):
            doc_tokens = self._tokenize(chunk.text)
            doc_length = self._doc_lengths[i]
            
            score = 0
            for token in query_tokens:
                if token not in self._doc_freqs:
                    continue
                
                # Term frequency in document
                tf = doc_tokens.count(token)
                if tf == 0:
                    continue
                
                # Inverse document frequency
                df = self._doc_freqs[token]
                idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
                
                # BM25 score component
                tf_component = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * doc_length / self._avg_doc_length)
                )
                
                score += idf * tf_component
            
            if score > 0:
                scores.append((score, chunk))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        
        return scores[:top_k]
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Simple tokenization
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)
        return tokens


class EmbeddingRetriever:
    """
    Semantic retrieval using embeddings.
    
    Note: Requires sentence-transformers library for real embeddings.
    Falls back to TF-IDF-based similarity if not available.
    """
    
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model_name = model_name
        self._model = None
        self._chunks: List[NoteChunk] = []
        self._embeddings = None
        self._indexed = False
    
    def _load_model(self):
        """Load sentence transformer model."""
        if self._model is not None:
            return True
        
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            return True
        except ImportError:
            return False
    
    def index(self, chunks: List[NoteChunk]):
        """Index documents with embeddings."""
        self._chunks = chunks
        
        if not self._load_model():
            # Fallback: no embeddings available
            self._indexed = True
            return
        
        texts = [chunk.text for chunk in chunks]
        self._embeddings = self._model.encode(texts, convert_to_tensor=True)
        self._indexed = True
    
    def search(self, query: str, top_k: int = 5) -> List[tuple]:
        """
        Search for semantically similar documents.
        
        Returns list of (score, chunk) tuples.
        """
        if not self._indexed:
            return []
        
        if self._model is None or self._embeddings is None:
            # Fallback to simple keyword matching
            return self._simple_search(query, top_k)
        
        try:
            from sentence_transformers import util
            
            query_embedding = self._model.encode(query, convert_to_tensor=True)
            cos_scores = util.cos_sim(query_embedding, self._embeddings)[0]
            
            # Get top-k indices
            top_results = []
            scores_list = cos_scores.cpu().numpy()
            
            for i, score in enumerate(scores_list):
                top_results.append((float(score), self._chunks[i]))
            
            top_results.sort(key=lambda x: x[0], reverse=True)
            return top_results[:top_k]
            
        except Exception:
            return self._simple_search(query, top_k)
    
    def _simple_search(self, query: str, top_k: int) -> List[tuple]:
        """Simple keyword-based fallback search."""
        query_tokens = set(query.lower().split())
        
        scores = []
        for chunk in self._chunks:
            doc_tokens = set(chunk.text.lower().split())
            overlap = len(query_tokens & doc_tokens)
            if overlap > 0:
                score = overlap / (len(query_tokens) + len(doc_tokens))
                scores.append((score, chunk))
        
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[:top_k]


class HybridRetriever:
    """
    Hybrid retrieval combining lexical and semantic search.
    
    Uses reciprocal rank fusion to combine results.
    """
    
    def __init__(
        self,
        evidence_store: Optional[EvidenceStore] = None,
        lexical_weight: float = 0.4,
        semantic_weight: float = 0.6,
    ):
        self.evidence_store = evidence_store
        self.lexical_weight = lexical_weight
        self.semantic_weight = semantic_weight
        
        self._lexical = BM25Retriever()
        self._semantic = EmbeddingRetriever()
        self._indexed = False
    
    def index(self, chunks: List[NoteChunk]):
        """Index chunks for both lexical and semantic search."""
        self._lexical.index(chunks)
        self._semantic.index(chunks)
        self._indexed = True
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter_section: Optional[str] = None,
    ) -> List[NoteChunk]:
        """
        Retrieve relevant note chunks.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_section: Optional section type filter
            
        Returns:
            List of relevant NoteChunks
        """
        if not self._indexed:
            return []
        
        # Get results from both retrievers
        lexical_results = self._lexical.search(query, top_k * 2)
        semantic_results = self._semantic.search(query, top_k * 2)
        
        # Reciprocal rank fusion
        chunk_scores: Dict[int, float] = defaultdict(float)
        chunk_map: Dict[int, NoteChunk] = {}
        
        k = 60  # Fusion constant
        
        for rank, (score, chunk) in enumerate(lexical_results):
            chunk_id = id(chunk)
            chunk_scores[chunk_id] += self.lexical_weight / (k + rank + 1)
            chunk_map[chunk_id] = chunk
        
        for rank, (score, chunk) in enumerate(semantic_results):
            chunk_id = id(chunk)
            chunk_scores[chunk_id] += self.semantic_weight / (k + rank + 1)
            chunk_map[chunk_id] = chunk
        
        # Sort by fused score
        sorted_ids = sorted(chunk_scores.keys(), key=lambda x: chunk_scores[x], reverse=True)
        
        results = []
        for chunk_id in sorted_ids[:top_k]:
            chunk = chunk_map[chunk_id]
            
            # Apply section filter if specified
            if filter_section and chunk.section_type.value != filter_section:
                continue
            
            results.append(chunk)
        
        return results
    
    def retrieve_for_signal(
        self,
        signal_description: str,
        signal_family: str,
        year: Optional[int] = None,
        top_k: int = 3,
    ) -> List[NoteChunk]:
        """
        Retrieve evidence for a specific signal.
        
        Tailors the query based on signal family.
        """
        # Build query based on signal family
        family_queries = {
            'auditor_escalation': 'auditor opinion qualification emphasis matter uncertainty',
            'rpt_anomaly': 'related party transaction disclosure',
            'asset_quality': 'non-performing assets NPA provision bad loans',
            'revenue_divergence': 'revenue recognition accounting policy',
        }
        
        base_query = family_queries.get(signal_family, signal_description)
        
        # Add year context if available
        if year:
            base_query = f"FY{year} {base_query}"
        
        return self.retrieve(base_query, top_k)
