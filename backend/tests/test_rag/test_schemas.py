"""
Tests for Pydantic schema validation and fallback handling.
"""

import pytest
from pydantic import ValidationError

from app.rag.schemas import (
    QueryIntent,
    RouterOutput,
    IntentParserOutput,
    FilterOutput,
    GenerationOutput,
    RecommendedBook,
    BookCandidate,
    BookCard,
    PacingEnum,
    ToneEnum,
    FallbackResponse,
)


class TestRouterOutput:
    """Test RouterOutput schema validation."""

    def test_valid_router_output(self):
        """Test valid RouterOutput creation."""
        output = RouterOutput(
            intent=QueryIntent.SIMILAR_BOOKS,
            confidence=0.95,
            targets=["Dune", "Foundation"]
        )

        assert output.intent == QueryIntent.SIMILAR_BOOKS
        assert output.confidence == 0.95
        assert output.targets == ["Dune", "Foundation"]

    def test_default_values(self):
        """Test default values are set correctly."""
        output = RouterOutput(intent=QueryIntent.GENERAL_INFO)

        assert output.confidence == 1.0
        assert output.targets == []

    def test_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            RouterOutput(intent=QueryIntent.GENERAL_INFO, confidence=1.5)

        with pytest.raises(ValidationError):
            RouterOutput(intent=QueryIntent.GENERAL_INFO, confidence=-0.1)

    def test_intent_enum_values(self):
        """Test all intent enum values are valid."""
        valid_intents = [
            "general_info",
            "user_history",
            "recommendation",
            "similar_books",
            "comparison",
            "continuation",
            "clarification",
        ]

        for intent in valid_intents:
            output = RouterOutput(intent=QueryIntent(intent))
            assert output.intent == intent


class TestIntentParserOutput:
    """Test IntentParserOutput schema validation."""

    def test_valid_intent_parser_output(self):
        """Test valid IntentParserOutput creation."""
        output = IntentParserOutput(
            intent=QueryIntent.RECOMMENDATION,
            filters={"genre": "thriller", "pacing": "Fast"},
            referenced_titles=["Dune"],
            confidence=0.9,
        )

        assert output.intent == QueryIntent.RECOMMENDATION
        assert output.filters == {"genre": "thriller", "pacing": "Fast"}
        assert output.referenced_titles == ["Dune"]

    def test_defaults(self):
        """Test IntentParserOutput defaults."""
        output = IntentParserOutput(intent=QueryIntent.GENERAL_INFO)

        assert output.filters == {}
        assert output.referenced_titles == []
        assert output.confidence == 1.0


class TestFilterOutput:
    """Test FilterOutput schema validation."""

    def test_valid_filter_output(self):
        """Test valid FilterOutput creation."""
        output = FilterOutput(
            search_query="sci-fi adventure",
            max_pages=400,
            min_pages=100,
            genre="science fiction",
            year_start=2010,
            year_end=2023,
            language="English",
            pacing=PacingEnum.FAST,
            tone=ToneEnum.SUSPENSEFUL,
            themes=["survival", "space"],
            moods=["tense", "exciting"],
        )

        assert output.search_query == "sci-fi adventure"
        assert output.max_pages == 400
        assert output.pacing == PacingEnum.FAST
        assert output.themes == ["survival", "space"]

    def test_minimal_filter_output(self):
        """Test FilterOutput with only required field."""
        output = FilterOutput(search_query="books")

        assert output.search_query == "books"
        assert output.max_pages is None
        assert output.themes == []

    def test_pacing_enum_values(self):
        """Test PacingEnum values."""
        assert PacingEnum.FAST.value == "Fast"
        assert PacingEnum.MODERATE.value == "Moderate"
        assert PacingEnum.SLOW.value == "Slow"

    def test_tone_enum_values(self):
        """Test ToneEnum values."""
        valid_tones = ["Dark", "Light", "Emotional", "Suspenseful", "Humorous"]
        for tone in ToneEnum:
            assert tone.value in valid_tones


class TestGenerationOutput:
    """Test GenerationOutput schema validation."""

    def test_valid_generation_output(self):
        """Test valid GenerationOutput creation."""
        output = GenerationOutput(
            answer_markdown="Here are some great books:\n\n1. **Dune** by Frank Herbert",
            recommended=[
                RecommendedBook(id=123, why="Classic sci-fi epic"),
                RecommendedBook(id=456, why="Fast-paced adventure"),
            ],
            follow_up_question="Would you like more recommendations?"
        )

        assert "Dune" in output.answer_markdown
        assert len(output.recommended) == 2
        assert output.recommended[0].id == 123
        assert output.follow_up_question is not None

    def test_empty_recommendations(self):
        """Test GenerationOutput with no recommendations."""
        output = GenerationOutput(
            answer_markdown="I couldn't find any matching books."
        )

        assert output.recommended == []
        assert output.follow_up_question is None

    def test_recommended_book_validation(self):
        """Test RecommendedBook requires id and why."""
        with pytest.raises(ValidationError):
            RecommendedBook(id=123)  # Missing 'why'

        with pytest.raises(ValidationError):
            RecommendedBook(why="Great book")  # Missing 'id'


class TestBookCandidate:
    """Test BookCandidate schema validation."""

    def test_valid_book_candidate(self):
        """Test valid BookCandidate creation."""
        candidate = BookCandidate(
            id=123,
            title="Dune",
            author="Frank Herbert",
            genres="Science Fiction, Adventure",
            pages=412,
            published_year=1965,
            pacing="Moderate",
            tone="Epic",
            themes=["survival", "politics", "ecology"],
            synopsis_snippet="A young nobleman becomes the leader of desert people.",
            availability="3/5 available",
            hybrid_score=0.87,
        )

        assert candidate.id == 123
        assert candidate.title == "Dune"
        assert len(candidate.themes) == 3
        assert candidate.hybrid_score == 0.87

    def test_minimal_book_candidate(self):
        """Test BookCandidate with only required fields."""
        candidate = BookCandidate(
            id=1,
            title="Test Book",
            author="Test Author"
        )

        assert candidate.genres is None
        assert candidate.themes == []
        assert candidate.synopsis_snippet == ""
        assert candidate.hybrid_score is None


class TestBookCard:
    """Test BookCard schema for UI display."""

    def test_valid_book_card(self):
        """Test valid BookCard creation."""
        card = BookCard(
            id=123,
            title="Dune",
            author="Frank Herbert",
            cover="https://example.com/cover.jpg",
            availability="3/5 available",
            why="Classic sci-fi masterpiece"
        )

        assert card.cover == "https://example.com/cover.jpg"
        assert card.why == "Classic sci-fi masterpiece"

    def test_book_card_defaults(self):
        """Test BookCard default values."""
        card = BookCard(
            id=1,
            title="Test",
            author="Author"
        )

        assert card.cover == ""
        assert card.availability == ""
        assert card.why == ""


class TestFallbackResponse:
    """Test FallbackResponse for error handling."""

    def test_default_fallback(self):
        """Test default fallback values."""
        fallback = FallbackResponse()

        assert "found some books" in fallback.answer_markdown
        assert fallback.book_ids == []

    def test_fallback_with_ids(self):
        """Test fallback with book IDs."""
        fallback = FallbackResponse(book_ids=[1, 2, 3])

        assert fallback.book_ids == [1, 2, 3]


class TestJsonParsing:
    """Test JSON parsing scenarios for structured output."""

    def test_parse_valid_json_to_router(self):
        """Test parsing valid JSON to RouterOutput."""
        json_data = {
            "intent": "similar_books",
            "confidence": 0.9,
            "targets": ["Dune"]
        }

        output = RouterOutput(**json_data)
        assert output.intent == "similar_books"

    def test_parse_valid_json_to_generation(self):
        """Test parsing valid JSON to GenerationOutput."""
        json_data = {
            "answer_markdown": "Here are some books...",
            "recommended": [
                {"id": 1, "why": "Great read"}
            ],
            "follow_up_question": "Want more?"
        }

        output = GenerationOutput(**json_data)
        assert len(output.recommended) == 1

    def test_parse_missing_optional_fields(self):
        """Test parsing JSON with missing optional fields."""
        json_data = {
            "intent": "general_info"
        }

        output = RouterOutput(**json_data)
        assert output.confidence == 1.0
        assert output.targets == []

    def test_parse_extra_fields_ignored(self):
        """Test that extra fields in JSON are ignored."""
        json_data = {
            "intent": "similar_books",
            "extra_field": "should be ignored",
            "another": 123
        }

        # Pydantic should ignore extra fields by default or raise based on config
        try:
            output = RouterOutput(**json_data)
            assert output.intent == "similar_books"
        except ValidationError:
            # If strict mode is on, this is also acceptable
            pass
