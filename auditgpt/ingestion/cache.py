"""
Caching layer for AuditGPT.

Provides TTL-based caching for:
- Statement data
- Note extraction results
- Peer benchmark summaries
"""

import os
import json
import time
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class CacheEntry:
    """A single cache entry with TTL."""
    key: str
    value: Any
    created_at: float
    ttl: int  # seconds
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() - self.created_at > self.ttl


class CacheManager:
    """
    TTL-based cache manager for AuditGPT.
    
    Supports:
    - In-memory caching with TTL
    - Optional file-based persistence
    - Separate caches for different data types
    """
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        statement_ttl: int = 3600,  # 1 hour
        note_ttl: int = 86400,  # 24 hours
        peer_ttl: int = 1800,  # 30 minutes
    ):
        """
        Initialize the cache manager.
        
        Args:
            cache_dir: Directory for file-based cache (optional)
            statement_ttl: TTL for statement data
            note_ttl: TTL for note extraction data
            peer_ttl: TTL for peer benchmark data
        """
        self._statement_cache: Dict[str, CacheEntry] = {}
        self._note_cache: Dict[str, CacheEntry] = {}
        self._peer_cache: Dict[str, CacheEntry] = {}
        
        self._statement_ttl = statement_ttl
        self._note_ttl = note_ttl
        self._peer_ttl = peer_ttl
        
        self._cache_dir = cache_dir
        self._lock = Lock()
        
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
    
    # Statement cache methods
    def get_statement(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get cached statement data for a ticker."""
        return self._get('statement', ticker)
    
    def set_statement(self, ticker: str, data: Dict[str, Any]):
        """Cache statement data for a ticker."""
        self._set('statement', ticker, data, self._statement_ttl)
    
    # Alias methods for company data (used by engine)
    def get_company_data(self, company: str) -> Optional[Dict[str, Any]]:
        """Get cached company data (alias for get_statement)."""
        return self.get_statement(company)
    
    def set_company_data(self, company: str, data: Dict[str, Any]):
        """Cache company data (alias for set_statement)."""
        self.set_statement(company, data)
    
    # Note cache methods
    def get_notes(self, ticker: str) -> Optional[List[Any]]:
        """Get cached note chunks for a ticker."""
        return self._get('note', ticker)
    
    def set_notes(self, ticker: str, notes: List[Any]):
        """Cache note chunks for a ticker."""
        self._set('note', ticker, notes, self._note_ttl)
    
    # Peer cache methods
    def get_peer_data(self, sector: str) -> Optional[Dict[str, Any]]:
        """Get cached peer benchmark data for a sector."""
        return self._get('peer', sector)
    
    def set_peer_data(self, sector: str, data: Dict[str, Any]):
        """Cache peer benchmark data for a sector."""
        self._set('peer', sector, data, self._peer_ttl)
    
    # Generic cache methods
    def _get(self, cache_type: str, key: str) -> Optional[Any]:
        """Get value from specified cache."""
        with self._lock:
            cache = self._get_cache(cache_type)
            entry = cache.get(key)
            
            if entry is None:
                return None
            
            if entry.is_expired:
                del cache[key]
                return None
            
            return entry.value
    
    def _set(self, cache_type: str, key: str, value: Any, ttl: int):
        """Set value in specified cache."""
        with self._lock:
            cache = self._get_cache(cache_type)
            cache[key] = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl,
            )
    
    def _get_cache(self, cache_type: str) -> Dict[str, CacheEntry]:
        """Get the appropriate cache dict."""
        if cache_type == 'statement':
            return self._statement_cache
        elif cache_type == 'note':
            return self._note_cache
        elif cache_type == 'peer':
            return self._peer_cache
        raise ValueError(f"Unknown cache type: {cache_type}")
    
    def clear(self, cache_type: Optional[str] = None):
        """
        Clear cache(s).
        
        Args:
            cache_type: Specific cache to clear, or None for all
        """
        with self._lock:
            if cache_type is None or cache_type == 'statement':
                self._statement_cache.clear()
            if cache_type is None or cache_type == 'note':
                self._note_cache.clear()
            if cache_type is None or cache_type == 'peer':
                self._peer_cache.clear()
    
    def cleanup_expired(self):
        """Remove all expired entries from caches."""
        with self._lock:
            for cache in [self._statement_cache, self._note_cache, self._peer_cache]:
                expired_keys = [k for k, v in cache.items() if v.is_expired]
                for key in expired_keys:
                    del cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'statement_entries': len(self._statement_cache),
                'note_entries': len(self._note_cache),
                'peer_entries': len(self._peer_cache),
                'statement_ttl': self._statement_ttl,
                'note_ttl': self._note_ttl,
                'peer_ttl': self._peer_ttl,
            }
    
    # File-based persistence
    def save_to_disk(self, ticker: str):
        """Save ticker's cached data to disk."""
        if not self._cache_dir:
            return
        
        entry = self._statement_cache.get(ticker)
        if entry and not entry.is_expired:
            filepath = os.path.join(self._cache_dir, f"{ticker}_cache.json")
            try:
                # Convert non-serializable data
                data = self._make_serializable(entry.value)
                with open(filepath, 'w') as f:
                    json.dump({
                        'data': data,
                        'created_at': entry.created_at,
                        'ttl': entry.ttl,
                    }, f)
            except Exception as e:
                print(f"Cache save error for {ticker}: {e}")
    
    def load_from_disk(self, ticker: str) -> bool:
        """
        Load ticker's cached data from disk.
        
        Returns True if cache was loaded and valid.
        """
        if not self._cache_dir:
            return False
        
        filepath = os.path.join(self._cache_dir, f"{ticker}_cache.json")
        if not os.path.exists(filepath):
            return False
        
        try:
            with open(filepath, 'r') as f:
                cached = json.load(f)
            
            # Check if still valid
            age = time.time() - cached['created_at']
            if age > cached['ttl']:
                os.remove(filepath)
                return False
            
            # Restore to cache
            self._statement_cache[ticker] = CacheEntry(
                key=ticker,
                value=cached['data'],
                created_at=cached['created_at'],
                ttl=cached['ttl'],
            )
            return True
            
        except Exception as e:
            print(f"Cache load error for {ticker}: {e}")
            return False
    
    def _make_serializable(self, data: Any) -> Any:
        """Convert data to JSON-serializable format."""
        if isinstance(data, dict):
            return {k: self._make_serializable(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._make_serializable(v) for v in data]
        elif hasattr(data, 'to_dict'):
            return data.to_dict()
        elif hasattr(data, 'tolist'):  # numpy arrays
            return data.tolist()
        return data
