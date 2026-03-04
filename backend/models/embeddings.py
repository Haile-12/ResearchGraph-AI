from __future__ import annotations
import time
import logging
import os
from typing import List
from sentence_transformers import SentenceTransformer
import torch
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Silence noisy libraries
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Using the model defined in settings (currently all-mpnet-base-v2)
_MODEL_NAME = settings.gemini_embedding_model
_model_instance = None

def _get_model() -> SentenceTransformer:
    global _model_instance
    if _model_instance is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading local embedding model: %s on %s", _MODEL_NAME, device)
        _model_instance = SentenceTransformer(_MODEL_NAME, device=device)
    return _model_instance


def generate_embedding(text: str) -> List[float]:
    if not text or not text.strip():
        raise ValueError("Cannot generate embedding for empty text")
    text = text.strip()[:8000]
    start = time.perf_counter()
    model = _get_model()
    # Generate embedding
    with torch.no_grad():
        embedding_array = model.encode(text, convert_to_tensor=False)
    elapsed = time.perf_counter() - start
    embedding = embedding_array.tolist()
    logger.debug(
        "Generated local embedding dim=%d in %.3fs for text: '%s.........'",
        len(embedding),
        elapsed,
        text[:15].replace("\n", " "),
    )
    return embedding

def generate_query_embedding(query: str) -> List[float]:
    """Optimised for retrieval queries (asymmetric search)."""
    return generate_embedding(query)

def generate_document_embedding(text: str) -> List[float]:
    """Optimised for document indexing."""
    return generate_embedding(text)

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(f"Vector dimension mismatch: {len(vec_a)} vs {len(vec_b)}")
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = sum(a ** 2 for a in vec_a) ** 0.5
    mag_b = sum(b ** 2 for b in vec_b) ** 0.5

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot_product / (mag_a * mag_b)
