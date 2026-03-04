import sys
import os
import math
import pytest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.embeddings import cosine_similarity
from utils.text_utils import truncate, clean_text, format_list_as_prose, paginate_list

# Cosine Similarity Math Tests
class TestCosineSimilarity:
    """Verify the cosine similarity utility is mathematically correct."""

    def test_identical_vectors_score_one(self):
        """Two identical vectors should have cosine similarity = 1.0."""
        vec = [1.0, 2.0, 3.0, 4.0]
        score = cosine_similarity(vec, vec)
        assert abs(score - 1.0) < 1e-6, f"Expected 1.0, got {score}"

    def test_orthogonal_vectors_score_zero(self):
        """Perpendicular vectors should have cosine similarity ≈ 0."""
        vec_a = [1.0, 0.0]
        vec_b = [0.0, 1.0]
        score = cosine_similarity(vec_a, vec_b)
        assert abs(score) < 1e-6, f"Expected 0.0, got {score}"

    def test_opposite_vectors_score_negative_one(self):
        """Opposite vectors should have cosine similarity = -1."""
        vec_a = [1.0, 0.0]
        vec_b = [-1.0, 0.0]
        score = cosine_similarity(vec_a, vec_b)
        assert abs(score - (-1.0)) < 1e-6, f"Expected -1.0, got {score}"

    def test_similar_vectors_high_score(self):
        """Similar vectors should produce a high score (> 0.9)."""
        vec_a = [0.9, 0.1, 0.8, 0.2]
        vec_b = [0.85, 0.15, 0.75, 0.25]
        score = cosine_similarity(vec_a, vec_b)
        assert score > 0.9, f"Similar vectors should score > 0.9, got {score}"

    def test_zero_vector_returns_zero(self):
        """Zero vector should return 0.0 without crashing."""
        zero = [0.0, 0.0, 0.0]
        vec  = [1.0, 2.0, 3.0]
        score = cosine_similarity(zero, vec)
        assert score == 0.0

    def test_dimension_mismatch_raises(self):
        """Mismatched dimensions should raise ValueError."""
        with pytest.raises(ValueError, match="dimension mismatch"):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_768_dim_vector(self):
        """768-dimensional vectors (Gemini embedding size) should work."""
        import random
        random.seed(42)
        vec_a = [random.gauss(0, 1) for _ in range(768)]
        vec_b = [a + random.gauss(0, 0.1) for a in vec_a] 
        score = cosine_similarity(vec_a, vec_b)
        assert score > 0.95, f"Near-identical 768-dim vectors should score >0.95, got {score}"

    def test_threshold_filtering_logic(self):
        """Simulate the threshold filter used in Neo4j vector search."""
        THRESHOLD = 0.7
        vec_base = [1.0, 0.0, 0.0]
        test_cases = [
            ([1.0, 0.0, 0.0], True),    
            ([0.9, 0.44, 0.0], True),   
            ([0.5, 0.87, 0.0], False),  
            ([0.0, 1.0, 0.0], False),   
        ]
        for vec, expected_pass in test_cases:
            score = cosine_similarity(vec_base, vec)
            passes = score >= THRESHOLD
            assert passes == expected_pass, (
                f"Vector {vec}: score={score:.3f}, expected_pass={expected_pass}"
            )


# Query Expansion Tests 
class TestQueryExpansion:
    """Verify query expansion enriches the search text."""

    @patch("services.vector_service.generate_text")
    def test_expansion_adds_vocabulary(self, mock_generate):
        """Expanded query should be longer and richer than the original."""
        from services.vector_service import expand_query

        original = "AI fairness"
        expanded = (
            "Research examining algorithmic bias and fairness in machine learning systems, "
            "disparate impact of AI decisions on marginalised groups, fairness metrics, "
            "debiasing techniques, and ethical AI development frameworks."
        )
        mock_generate.return_value = expanded

        result = expand_query(original)
        assert len(result) > len(original), "Expansion should produce longer text"
        assert result == expanded

    @patch("services.vector_service.generate_text")
    def test_expansion_fallback_on_error(self, mock_generate):
        """If expansion fails, should return original query."""
        from services.vector_service import expand_query

        mock_generate.side_effect = Exception("API error")
        result = expand_query("reinforcement learning")
        assert result == "reinforcement learning"


# Vector Search Pipeline Tests
class TestVectorSearchPipeline:
    """Integration tests for the full vector search pipeline (mocked)."""

    @patch("services.vector_service.generate_query_embedding")
    @patch("services.vector_service.run_query")
    @patch("services.vector_service.generate_text")
    def test_search_returns_results(self, mock_gen_text, mock_run_query, mock_embedding):
        """Vector search should return results above the threshold."""
        from services.vector_service import search_papers_by_similarity

        mock_gen_text.return_value = "Generative adversarial training for image synthesis"
        mock_embedding.return_value = [0.5] * 768
        mock_run_query.return_value = [
            {
                "title": "Generative Adversarial Networks",
                "year": 2014,
                "citations": 75231,
                "abstract": "We propose a new framework...",
                "authors": ["Ian Goodfellow"],
                "topics": ["Generative AI"],
                "journal": "NeurIPS",
                "score": 0.92,
            }
        ]

        result = search_papers_by_similarity("Papers similar to GANs", top_k=5)
        assert result is not None
        assert len(result.results) > 0
        assert result.results[0]["score"] >= 0.7

    @patch("services.vector_service.generate_query_embedding")
    @patch("services.vector_service.run_query")
    @patch("services.vector_service.generate_text")
    def test_empty_results_graceful(self, mock_gen_text, mock_run_query, mock_embedding):
        """When no papers pass the threshold, return helpful message."""
        from services.vector_service import search_papers_by_similarity

        mock_gen_text.return_value = "quantum underwater basket weaving fusion"
        mock_embedding.return_value = [0.0] * 768
        mock_run_query.return_value = []

        result = search_papers_by_similarity("quantum underwater basket weaving")
        assert result is not None
        assert "No papers" in result.answer or "threshold" in result.answer

    @patch("services.vector_service.generate_query_embedding")
    def test_embedding_error_handled(self, mock_embedding):
        """Embedding failure should return error result, not crash."""
        from services.vector_service import search_papers_by_similarity

        mock_embedding.side_effect = Exception("Quota exceeded")
        result = search_papers_by_similarity("any query")
        assert result is not None
        assert "Failed" in result.answer or "error" in result.answer.lower()


# Text Utility Tests (no mocking needed)
class TestTextUtils:
    """Tests for shared text processing utilities."""

    def test_truncate_short_text_unchanged(self):
        assert truncate("Hello", 100) == "Hello"

    def test_truncate_long_text(self):
        result = truncate("Hello World", 8)
        assert len(result) == 8
        assert result.endswith("...")

    def test_clean_text_removes_control_chars(self):
        text = "Hello\x00World\x1f"
        result = clean_text(text)
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_clean_text_collapses_whitespace(self):
        text = "Hello   World\n\nTest"
        result = clean_text(text)
        assert "   " not in result
        assert result == "Hello World Test"

    def test_format_list_single(self):
        assert format_list_as_prose(["Alice"]) == "Alice"

    def test_format_list_two(self):
        assert format_list_as_prose(["Alice", "Bob"]) == "Alice and Bob"

    def test_format_list_three(self):
        result = format_list_as_prose(["Alice", "Bob", "Carol"])
        assert result == "Alice, Bob, and Carol"

    def test_format_list_empty(self):
        assert format_list_as_prose([]) == ""

    def test_paginate_list_first_page(self):
        items = list(range(25))
        result = paginate_list(items, page=1, page_size=10)
        assert result["items"] == list(range(10))
        assert result["total"] == 25
        assert result["has_more"] is True
        assert result["total_pages"] == 3

    def test_paginate_list_last_page(self):
        items = list(range(25))
        result = paginate_list(items, page=3, page_size=10)
        assert result["items"] == [20, 21, 22, 23, 24]
        assert result["has_more"] is False

    def test_paginate_list_single_page(self):
        items = [1, 2, 3]
        result = paginate_list(items, page=1, page_size=10)
        assert result["items"] == [1, 2, 3]
        assert result["has_more"] is False
        assert result["total_pages"] == 1

# Cache Service Tests
class TestCacheService:
    """Tests for the query result cache."""

    def setup_method(self):
        """Clear cache before each test."""
        from services.cache_service import clear_all
        clear_all()

    def test_cache_miss_returns_none(self):
        from services.cache_service import get_cached
        result = get_cached("a question that was never asked")
        assert result is None

    def test_cache_store_and_retrieve(self):
        from services.cache_service import store_in_cache, get_cached
        store_in_cache(
            question="Who authored GPT-3?",
            answer="GPT-3 was authored by Alec Radford and Ilya Sutskever.",
            query_type="GRAPH_TRAVERSAL",
            confidence_score=0.95,
        )
        result = get_cached("Who authored GPT-3?", "GRAPH_TRAVERSAL")
        assert result is not None
        assert "Radford" in result.answer

    def test_low_confidence_not_cached(self):
        from services.cache_service import store_in_cache, get_cached
        store_in_cache(
            question="Low confidence query",
            answer="Some shaky answer",
            confidence_score=0.3,  # Below threshold
        )
        # Should NOT be cached
        result = get_cached("Low confidence query")
        assert result is None

    def test_cache_stats_track_hits(self):
        from services.cache_service import store_in_cache, get_cached, get_stats
        store_in_cache("cached?", "yes!", confidence_score=0.9)
        get_cached("cached?")
        get_cached("cached?")
        get_cached("not cached")
        stats = get_stats()
        assert stats["hits"] >= 2
        assert stats["misses"] >= 1

    def test_cache_normalizes_question(self):
        """Questions with different whitespace/punctuation should hit same cache entry."""
        from services.cache_service import store_in_cache, get_cached
        store_in_cache("Who wrote GPT-3?", "Alec Radford", confidence_score=0.9)
        # Same question with trailing punctuation
        result = get_cached("who wrote gpt-3")
        assert result is not None

# Memory Service Tests
class TestMemoryService:
    """Tests for conversation memory management."""

    def test_new_session_empty_history(self):
        from services.memory_service import get_conversation_history
        history = get_conversation_history("new_test_session_xyz")
        assert history == ""

    def test_save_and_retrieve_turn(self):
        from services.memory_service import save_turn, get_conversation_history
        sid = "test_memory_session_001"
        save_turn(sid, "Who is Yoshua Bengio?", "Yoshua Bengio is a deep learning pioneer.")
        history = get_conversation_history(sid)
        assert "Yoshua Bengio" in history
        assert "Human:" in history
        assert "AI:" in history

    def test_multi_turn_history(self):
        from services.memory_service import save_turn, get_conversation_history
        sid = "test_multi_turn_002"
        save_turn(sid, "Q1", "A1")
        save_turn(sid, "Q2", "A2")
        save_turn(sid, "Q3", "A3")
        history = get_conversation_history(sid)
        assert "Q1" in history
        assert "Q3" in history

    def test_clear_session(self):
        from services.memory_service import save_turn, clear_session, get_conversation_history
        sid = "test_clear_003"
        save_turn(sid, "Q", "A")
        clear_session(sid)
        history = get_conversation_history(sid)
        assert history == ""
