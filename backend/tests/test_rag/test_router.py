"""
Tests for intent router (LLM-based classification).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.rag.router import parse_intent
from app.rag.schemas import QueryIntent, RouterOutput, IntentParserOutput


class TestParseIntent:
    """Test the intent parser function."""

    @pytest.mark.asyncio
    async def test_general_info_greeting(self):
        """Test that greetings are classified as GENERAL_INFO."""
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (False, None)
            with patch("app.rag.router.get_router_llm") as mock_llm:
                mock_response = MagicMock()
                mock_response.content = '{"intent": "general_info", "confidence": 1.0, "targets": [], "filters": {}}'
                mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

                result = await parse_intent("hello")
                assert result.intent == QueryIntent.GENERAL_INFO
                assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_recommendation_intent(self):
        """Test that recommendation queries are classified correctly."""
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (False, None)
            with patch("app.rag.router.get_router_llm") as mock_llm:
                mock_response = MagicMock()
                mock_response.content = '{"intent": "recommendation", "confidence": 0.9, "targets": [], "filters": {"genre": "thriller", "pacing": "Fast"}}'
                mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

                result = await parse_intent("fast-paced thrillers")
                assert result.intent == QueryIntent.RECOMMENDATION
                assert result.filters.get("genre") == "thriller"

    @pytest.mark.asyncio
    async def test_similar_books_with_targets(self):
        """Test that similarity queries extract targets."""
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (False, None)
            with patch("app.rag.router.get_router_llm") as mock_llm:
                mock_response = MagicMock()
                mock_response.content = '{"intent": "similar_books", "confidence": 0.95, "targets": ["Dune"], "filters": {}}'
                mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

                result = await parse_intent("books like Dune")
                assert result.intent == QueryIntent.SIMILAR_BOOKS
                assert "Dune" in result.referenced_titles

    @pytest.mark.asyncio
    async def test_comparison_intent(self):
        """Test that comparison queries are classified correctly."""
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (False, None)
            with patch("app.rag.router.get_router_llm") as mock_llm:
                mock_response = MagicMock()
                mock_response.content = '{"intent": "comparison", "confidence": 0.9, "targets": ["1984", "Brave New World"], "filters": {}}'
                mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

                result = await parse_intent("compare 1984 and Brave New World")
                assert result.intent == QueryIntent.COMPARISON
                assert len(result.referenced_titles) == 2

    @pytest.mark.asyncio
    async def test_user_history_intent(self):
        """Test that user history queries are classified correctly."""
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (False, None)
            with patch("app.rag.router.get_router_llm") as mock_llm:
                mock_response = MagicMock()
                mock_response.content = '{"intent": "user_history", "confidence": 1.0, "targets": [], "filters": {}}'
                mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

                result = await parse_intent("show my saved books")
                assert result.intent == QueryIntent.USER_HISTORY

    @pytest.mark.asyncio
    async def test_continuation_intent(self):
        """Test that continuation queries are classified correctly."""
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (False, None)
            with patch("app.rag.router.get_router_llm") as mock_llm:
                mock_response = MagicMock()
                mock_response.content = '{"intent": "continuation", "confidence": 1.0, "targets": [], "filters": {}}'
                mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

                result = await parse_intent("yes")
                assert result.intent == QueryIntent.CONTINUATION

    @pytest.mark.asyncio
    async def test_book_details_intent(self):
        """Test that book details queries are classified correctly."""
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (False, None)
            with patch("app.rag.router.get_router_llm") as mock_llm:
                mock_response = MagicMock()
                mock_response.content = '{"intent": "book_details", "confidence": 0.95, "targets": ["The Summer I Turned Pretty"], "filters": {}}'
                mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

                result = await parse_intent("tell me about The Summer I Turned Pretty")
                assert result.intent == QueryIntent.BOOK_DETAILS
                assert "The Summer I Turned Pretty" in result.referenced_titles

    @pytest.mark.asyncio
    async def test_account_action_intent(self):
        """Test that save/borrow queries are classified as ACCOUNT_ACTION."""
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (False, None)
            with patch("app.rag.router.get_router_llm") as mock_llm:
                mock_response = MagicMock()
                mock_response.content = '{"intent": "account_action", "confidence": 0.95, "targets": ["The Great Gatsby"], "filters": {}}'
                mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

                result = await parse_intent("save The Great Gatsby to my books")
                assert result.intent == QueryIntent.ACCOUNT_ACTION
                assert "The Great Gatsby" in result.referenced_titles

    @pytest.mark.asyncio
    async def test_legacy_intent_mapping(self):
        """Test that old intent names are mapped to new ones correctly."""
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (False, None)
            with patch("app.rag.router.get_router_llm") as mock_llm:
                mock_response = MagicMock()
                mock_response.content = '{"intent": "similarity", "confidence": 0.9, "targets": ["Dune"]}'
                mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

                result = await parse_intent("books like Dune")
                assert result.intent == QueryIntent.SIMILAR_BOOKS

    @pytest.mark.asyncio
    async def test_json_parse_failure_defaults_to_general_info(self):
        """Test that invalid JSON defaults to GENERAL_INFO."""
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (False, None)
            with patch("app.rag.router.get_router_llm") as mock_llm:
                mock_response = MagicMock()
                mock_response.content = "This is not valid JSON"
                mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)

                result = await parse_intent("random text")
                assert result.intent == QueryIntent.GENERAL_INFO
                assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_cached_result(self):
        """Test that cached results are returned."""
        cached_output = RouterOutput(
            intent=QueryIntent.RECOMMENDATION,
            confidence=0.9,
            targets=[],
            filters={"genre": "thriller"},
        )
        with patch("app.rag.router.get_cached_route") as mock_cache:
            mock_cache.return_value = (True, cached_output)

            result = await parse_intent("fast thrillers")
            assert result.intent == QueryIntent.RECOMMENDATION
            assert result.confidence == 0.9


class TestIntentEnumCompleteness:
    """Test that all 7 intents are present and valid."""

    def test_all_intents_exist(self):
        """Test all 7 expected intents are in the enum."""
        expected = [
            "general_info", "user_history", "recommendation",
            "similar_books", "comparison", "book_details",
            "continuation", "clarification", "account_action",
        ]
        for intent_val in expected:
            intent = QueryIntent(intent_val)
            assert intent.value == intent_val

    def test_intent_count(self):
        """Test we have exactly 7 intents."""
        assert len(QueryIntent) == 9
