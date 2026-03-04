from __future__ import annotations
import hashlib
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from cachetools import TTLCache
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class CacheEntry:
    """A cached query result with metadata."""
    answer: str
    query_type: str
    confidence_score: float
    explanation: str
    cached_at: float       
    hit_count: int = 0     

# Cache singleton
_cache_lock = threading.Lock()
_cache: TTLCache = TTLCache(
    maxsize=settings.cache_max_size,
    ttl=settings.cache_ttl_seconds,
)
# Statistics
_stats = {"hits": 0, "misses": 0, "stores": 0, "evictions": 0}

# Key generation
def _normalize_question(question: str) -> str:
    normalized = question.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)        
    normalized = re.sub(r"[?.!,]+$", "", normalized)    
    return normalized

def make_cache_key(question: str, query_type: str = "") -> str:
    key_content = f"{_normalize_question(question)}::{query_type}"
    return hashlib.sha256(key_content.encode()).hexdigest()[:32]

# Cache operations
def get_cached(question: str, query_type: str = "") -> CacheEntry | None:
    key = make_cache_key(question, query_type)
    with _cache_lock:
        entry = _cache.get(key)
    if entry is not None:
        entry.hit_count += 1
        _stats["hits"] += 1
        age_sec = time.time() - entry.cached_at
        logger.debug(
            "Cache HIT for '%s...' (age=%.0fs, hits=%d)",
            question[:50],
            age_sec,
            entry.hit_count,
        )
        return entry
    _stats["misses"] += 1
    logger.debug("Cache MISS for '%s...'", question[:10])
    return None

def store_in_cache(
    question: str,
    answer: str,
    query_type: str = "",
    confidence_score: float = 1.0,
    explanation: str = "",
) -> None:
    if confidence_score < settings.confidence_threshold:
        logger.debug(
            "Not caching low-confidence result (score=%.2f) for: '%s'",
            confidence_score,
            question[:50],
        )
        return

    key = make_cache_key(question, query_type)
    entry = CacheEntry(
        answer=answer,
        query_type=query_type,
        confidence_score=confidence_score,
        explanation=explanation,
        cached_at=time.time(),
    )

    with _cache_lock:
        _cache[key] = entry

    _stats["stores"] += 1
    logger.debug(
        "Cached result for (key=%s, type=%s)",
        key[:8],
        query_type,
    )
def invalidate(question: str, query_type: str = "") -> bool:
    key = make_cache_key(question, query_type)
    with _cache_lock:
        existed = key in _cache
        _cache.pop(key, None)
    return existed


def clear_all() -> int:
    with _cache_lock:
        count = len(_cache)
        _cache.clear()
    logger.info("Cache cleared: %d entries removed", count)
    return count

def get_stats() -> dict[str, Any]:
    with _cache_lock:
        current_size = len(_cache)

    total_requests = _stats["hits"] + _stats["misses"]
    hit_rate = (_stats["hits"] / total_requests * 100) if total_requests > 0 else 0.0

    return {
        "current_size":  current_size,
        "max_size":      settings.cache_max_size,
        "ttl_seconds":   settings.cache_ttl_seconds,
        "hits":          _stats["hits"],
        "misses":        _stats["misses"],
        "stores":        _stats["stores"],
        "hit_rate_pct":  round(hit_rate, 1),
    }
