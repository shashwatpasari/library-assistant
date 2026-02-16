"""
Tests for content-based feature vector encoding and hybrid scoring.
"""

import pytest
from unittest.mock import MagicMock

from app.rag.vectors import (
    encode_book_features,
    cosine_similarity,
    hybrid_score,
    _genre_multi_hot,
    _tone_multi_hot,
    _pacing_one_hot,
    _theme_hash_vector,
    _length_one_hot,
    _rating_scaled,
    _author_hash,
    VECTOR_DIM,
)


class TestFeatureEncoding:
    """Test content-based feature vector encoding."""

    def _make_book(self, **kwargs):
        """Create a mock book with given attributes."""
        book = MagicMock()
        book.genres = kwargs.get("genres", None)
        book.tone = kwargs.get("tone", None)
        book.pacing = kwargs.get("pacing", None)
        book.themes = kwargs.get("themes", None)
        book.pages = kwargs.get("pages", None)
        book.rating = kwargs.get("rating", None)
        book.popularity_score = kwargs.get("popularity_score", None)
        book.author = kwargs.get("author", None)
        return book

    def test_vector_dimension(self):
        """Test that output vector has exactly 128 dimensions."""
        book = self._make_book(
            genres="fantasy", tone="dark", pacing="fast",
            themes=["survival"], pages=300, rating=4.5,
            popularity_score=0.7, author="Brandon Sanderson",
        )
        vec = encode_book_features(book)
        assert len(vec) == VECTOR_DIM

    def test_empty_book(self):
        """Test encoding a book with no metadata."""
        book = self._make_book()
        vec = encode_book_features(book)
        assert len(vec) == VECTOR_DIM
        # Should not be all zeros (rating defaults to 0.5)
        assert any(v != 0.0 for v in vec)

    def test_genre_encoding(self):
        """Test genre multi-hot encoding."""
        vec = _genre_multi_hot("fantasy, thriller")
        assert vec[0] == 1.0  # fantasy is first
        assert vec[3] == 1.0  # thriller is 4th
        assert sum(vec) == 2.0  # exactly two genres

    def test_genre_none(self):
        """Test genre encoding with None."""
        vec = _genre_multi_hot(None)
        assert sum(vec) == 0.0

    def test_tone_encoding(self):
        """Test tone multi-hot encoding."""
        vec = _tone_multi_hot("Dark")
        assert vec[0] == 1.0  # "dark" is first
        assert sum(vec) == 1.0

    def test_pacing_one_hot(self):
        """Test pacing one-hot encoding."""
        vec = _pacing_one_hot("Fast")
        assert vec[0] == 1.0
        assert sum(vec) == 1.0

        vec = _pacing_one_hot("Slow")
        assert vec[2] == 1.0
        assert sum(vec) == 1.0

    def test_theme_hashing(self):
        """Test theme feature hashing."""
        vec = _theme_hash_vector(["survival", "revenge"])
        assert sum(vec) >= 1.0  # At least one bucket filled
        assert len(vec) == 20

    def test_length_buckets(self):
        """Test length bucket encoding."""
        assert _length_one_hot(100)[0] == 1.0   # short
        assert _length_one_hot(300)[1] == 1.0   # medium
        assert _length_one_hot(500)[2] == 1.0   # long
        assert _length_one_hot(800)[3] == 1.0   # epic
        assert sum(_length_one_hot(None)) == 0.0  # no pages

    def test_rating_scaled(self):
        """Test rating scaling."""
        assert _rating_scaled(5.0)[0] == 1.0
        assert _rating_scaled(0.0)[0] == 0.0
        assert _rating_scaled(None)[0] == 0.5  # default

    def test_author_hash(self):
        """Test author hash encoding."""
        vec1 = _author_hash("Brandon Sanderson")
        vec2 = _author_hash("Stephen King")
        assert len(vec1) == 32
        assert len(vec2) == 32
        # Different authors should produce different hashes
        assert list(vec1) != list(vec2)

    def test_same_author_same_hash(self):
        """Test same author produces same hash."""
        vec1 = _author_hash("Brandon Sanderson")
        vec2 = _author_hash("  Brandon Sanderson  ")
        assert list(vec1) == list(vec2)


class TestCosineSimilarity:
    """Test cosine similarity computation."""

    def test_identical_vectors(self):
        """Test similarity of identical vectors is 1.0."""
        vec = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(vec, vec) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        """Test similarity of orthogonal vectors is 0.0."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]
        assert abs(cosine_similarity(vec_a, vec_b)) < 1e-6

    def test_opposite_vectors(self):
        """Test similarity of opposite vectors is -1.0."""
        vec_a = [1.0, 0.0]
        vec_b = [-1.0, 0.0]
        assert abs(cosine_similarity(vec_a, vec_b) - (-1.0)) < 1e-6

    def test_zero_vector(self):
        """Test similarity with zero vector is 0.0."""
        vec_a = [1.0, 2.0, 3.0]
        vec_b = [0.0, 0.0, 0.0]
        assert cosine_similarity(vec_a, vec_b) == 0.0


class TestHybridScore:
    """Test hybrid scoring with dynamic alpha/beta."""

    def test_cold_start_pure_content(self):
        """Test that cold-start users get pure content-based score."""
        score = hybrid_score(
            content_sim=0.8, collaborative_sim=0.5,
            interaction_count=3, threshold_n=10,
        )
        assert abs(score - 0.8) < 1e-6

    def test_established_user_blended(self):
        """Test that established users get blended score."""
        score = hybrid_score(
            content_sim=0.8, collaborative_sim=0.9,
            interaction_count=100, threshold_n=10,
        )
        # At 100 interactions: alpha=0.3, beta=0.7
        expected = 0.3 * 0.8 + 0.7 * 0.9
        assert abs(score - expected) < 1e-6

    def test_mid_user_partial_blend(self):
        """Test partial blending at midpoint."""
        score = hybrid_score(
            content_sim=0.8, collaborative_sim=0.6,
            interaction_count=55, threshold_n=10,
        )
        # progress = (55-10)/(100-10) = 0.5
        # alpha = 1.0 - 0.7*0.5 = 0.65
        # beta = 0.7*0.5 = 0.35
        expected = 0.65 * 0.8 + 0.35 * 0.6
        assert abs(score - expected) < 1e-6

    def test_threshold_boundary(self):
        """Test exactly at threshold: pure content."""
        score = hybrid_score(
            content_sim=0.8, collaborative_sim=0.5,
            interaction_count=10, threshold_n=10,
        )
        # progress = 0, alpha=1.0, beta=0.0
        expected = 1.0 * 0.8 + 0.0 * 0.5
        assert abs(score - expected) < 1e-6

    def test_beyond_max_capped(self):
        """Test that interactions beyond 100 don't exceed max blend."""
        score = hybrid_score(
            content_sim=0.5, collaborative_sim=1.0,
            interaction_count=200, threshold_n=10,
        )
        expected = 0.3 * 0.5 + 0.7 * 1.0
        assert abs(score - expected) < 1e-6
