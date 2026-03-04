from __future__ import annotations
import re
import unicodedata

def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max_length characters, appending suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", text) 
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_keywords(text: str, max_keywords: int = 10) -> list[str]:
    stopwords = {
        "the", "a", "an", "is", "in", "of", "and", "or", "to", "for",
        "with", "on", "at", "by", "from", "that", "this", "was", "are",
        "be", "as", "it", "its", "have", "has", "do", "we", "i", "you",
    }
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    seen: set[str] = set()
    keywords = []
    for w in words:
        if w not in stopwords and w not in seen:
            seen.add(w)
            keywords.append(w)
        if len(keywords) >= max_keywords:
            break
    return keywords

def format_duration_ms(ms: float) -> str:
    """Format a millisecond duration as a human-readable string."""
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms / 1000:.2f}s"

def safe_json_string(text: str) -> str:
    """Escape text for safe embedding in a JSON string."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def format_list_as_prose(items: list[str], conjunction: str = "and") -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return ", ".join(items[:-1]) + f", {conjunction} {items[-1]}"


def paginate_list(items: list, page: int, page_size: int) -> dict:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]

    return {
        "items":       page_items,
        "page":        page,
        "page_size":   page_size,
        "total":       total,
        "has_more":    end < total,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }
