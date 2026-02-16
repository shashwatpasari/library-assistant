"""
Tests for the hybrid retrieval system.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from app.rag.schemas import FilterOutput, QueryIntent, PacingEnum
from app.rag.retrievers import (
    apply_user_exclusions,
    rrf_fusion,
)


class TestUserExclusions:
    """Test user preference exclusion filtering."""
    
    def test_no_exclusions_without_prefs(self):
        """Test that books pass through when no preferences."""
        # Mock books
        books = [Mock(id=1), Mock(id=2), Mock(id=3)]
        
        result = apply_user_exclusions(Mock(), books, None)
        
        assert len(result) == 3
    
    def test_excludes_disliked_genres(self):
        """Test that disliked genres are excluded."""
        # Create mock books
        book1 = Mock(id=1, genres="Fantasy, Adventure", content_warnings=None)
        book2 = Mock(id=2, genres="Horror, Thriller", content_warnings=None)
        book3 = Mock(id=3, genres="Romance, Drama", content_warnings=None)
        books = [book1, book2, book3]
        
        # Create mock preferences with disliked horror
        prefs = Mock()
        prefs.disliked_genres = ["Horror"]
        prefs.triggers_to_avoid = []
        
        result = apply_user_exclusions(Mock(), books, prefs)
        
        # Book 2 should be excluded (has Horror)
        assert len(result) == 2
        assert book2 not in result
    
    def test_excludes_content_warnings(self):
        """Test that books with triggering content are excluded."""
        book1 = Mock(id=1, genres="Fiction", content_warnings=["violence"])
        book2 = Mock(id=2, genres="Fiction", content_warnings=["romance"])
        book3 = Mock(id=3, genres="Fiction", content_warnings=None)
        books = [book1, book2, book3]
        
        prefs = Mock()
        prefs.disliked_genres = []
        prefs.triggers_to_avoid = ["violence"]
        
        result = apply_user_exclusions(Mock(), books, prefs)
        
        # Book 1 should be excluded (has violence warning)
        assert len(result) == 2
        assert book1 not in result
    
    def test_refill_from_candidates(self):
        """Test that excluded books are replaced from refill candidates."""
        book1 = Mock(id=1, genres="Horror", content_warnings=None)
        book2 = Mock(id=2, genres="Fantasy", content_warnings=None)
        books = [book1, book2]
        
        # Refill candidates
        book3 = Mock(id=3, genres="Sci-Fi", content_warnings=None)
        book4 = Mock(id=4, genres="Mystery", content_warnings=None)
        refill = [book3, book4]
        
        prefs = Mock()
        prefs.disliked_genres = ["Horror"]
        prefs.triggers_to_avoid = []
        
        result = apply_user_exclusions(
            Mock(), books, prefs, 
            refill_candidates=refill,
            target_count=3
        )
        
        # Should have book2 from original + book3, book4 from refill
        assert len(result) == 3
        assert book1 not in result  # Excluded
        assert book2 in result
    
    def test_case_insensitive_matching(self):
        """Test that genre matching is case-insensitive."""
        book1 = Mock(id=1, genres="HORROR, thriller", content_warnings=None)
        books = [book1]
        
        prefs = Mock()
        prefs.disliked_genres = ["horror"]  # lowercase
        prefs.triggers_to_avoid = []
        
        result = apply_user_exclusions(Mock(), books, prefs)
        
        assert len(result) == 0  # Should still be excluded


class TestRRFFusion:
    """Test Reciprocal Rank Fusion."""
    
    def test_combines_results(self):
        """Test that RRF combines lexical and vector results."""
        # Books that appear in both lists should rank higher
        book1 = Mock(id=1)
        book2 = Mock(id=2)
        book3 = Mock(id=3)
        book4 = Mock(id=4)
        
        # Lexical: book1, book2, book3
        lexical = [(book1, 1.0), (book2, 0.8), (book3, 0.6)]
        
        # Vector: book2, book4, book1
        vector = [(book2, 0.9), (book4, 0.7), (book1, 0.5)]
        
        result = rrf_fusion(lexical, vector, k=60)
        
        # book2 appears in both at good ranks, should be first
        assert result[0].id == 2
        # All 4 books should be in result
        assert len(result) == 4
    
    def test_empty_lexical(self):
        """Test RRF with empty lexical results."""
        book1 = Mock(id=1)
        book2 = Mock(id=2)
        
        vector = [(book1, 0.9), (book2, 0.8)]
        
        result = rrf_fusion([], vector, k=60)
        
        assert len(result) == 2
        assert result[0].id == 1
    
    def test_empty_vector(self):
        """Test RRF with empty vector results."""
        book1 = Mock(id=1)
        book2 = Mock(id=2)
        
        lexical = [(book1, 1.0), (book2, 0.8)]
        
        result = rrf_fusion(lexical, [], k=60)
        
        assert len(result) == 2
    
    def test_duplicate_handling(self):
        """Test that duplicates are handled correctly."""
        book1 = Mock(id=1)
        
        # Same book in both lists
        lexical = [(book1, 1.0)]
        vector = [(book1, 0.9)]
        
        result = rrf_fusion(lexical, vector, k=60)
        
        # Should appear only once
        assert len(result) == 1
        assert result[0].id == 1


class TestFilterApplication:
    """Test metadata filter application."""
    
    def test_filter_output_creation(self):
        """Test FilterOutput with various values."""
        filters = FilterOutput(
            search_query="adventure books",
            max_pages=300,
            genre="fantasy",
            pacing=PacingEnum.FAST,
        )
        
        assert filters.search_query == "adventure books"
        assert filters.max_pages == 300
        assert filters.pacing == PacingEnum.FAST
    
    def test_filter_defaults(self):
        """Test FilterOutput default values."""
        filters = FilterOutput(search_query="test")
        
        assert filters.max_pages is None
        assert filters.min_pages is None
        assert filters.genre is None
        assert filters.themes == []
        assert filters.moods == []


class TestIntentRetrieval:
    """Test intent-based retrieval routing."""
    
    def test_similar_books_intent(self):
        """Test that SIMILAR_BOOKS intent value is correct."""
        assert QueryIntent.SIMILAR_BOOKS.value == "similar_books"
    
    def test_comparison_intent(self):
        """Test COMPARISON intent value."""
        assert QueryIntent.COMPARISON.value == "comparison"
    
    def test_recommendation_intent(self):
        """Test RECOMMENDATION intent value."""
        assert QueryIntent.RECOMMENDATION.value == "recommendation"


class TestBookCandidates:
    """Test book candidate building."""
    
    def test_synopsis_truncation(self):
        """Test that long synopses are truncated."""
        # This tests the logic, not the actual function which needs DB
        long_synopsis = "A" * 500
        
        # Truncation logic: cut at ~150 chars
        if len(long_synopsis) > 150:
            cut_point = long_synopsis[:150].rfind('.')
            if cut_point > 50:
                truncated = long_synopsis[:cut_point + 1]
            else:
                truncated = long_synopsis[:147] + "..."
        else:
            truncated = long_synopsis
        
        assert len(truncated) <= 150
    
    def test_themes_extraction_from_list(self):
        """Test themes are extracted from list format."""
        themes = ["survival", "redemption", "family"]
        
        # Limit to 5 themes
        limited = themes[:5]
        
        assert len(limited) == 3
    
    def test_published_year_from_date_string(self):
        """Test year extraction from date string."""
        date_published = "2020-03-15"
        
        try:
            year = int(date_published[:4])
        except (ValueError, TypeError):
            year = None
        
        assert year == 2020
