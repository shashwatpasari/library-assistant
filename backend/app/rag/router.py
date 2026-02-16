"""
Intent router — LLM-based query classification.

The LLM is used ONLY for intent understanding, never for routing decisions.
Routing is deterministic and happens in the graph's conditional edges.
"""

import json
import logging
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage

from app.rag.schemas import RouterOutput, QueryIntent, IntentParserOutput
from app.rag.prompts import ROUTER_SYSTEM_PROMPT, ROUTER_USER_TEMPLATE
from app.rag.llm import get_router_llm
from app.rag.cache import get_cached_router_output as get_cached_route, cache_router_output as cache_route

logger = logging.getLogger(__name__)


async def parse_intent(query: str) -> IntentParserOutput:
    """
    Use LLM to classify intent. Returns structured IntentParserOutput.

    This is the ONLY place the LLM is used for understanding —
    all routing decisions are made deterministically in the graph.
    """
    # Check cache first
    hit, cached = get_cached_route(query)
    if hit and cached:
        return IntentParserOutput(
            intent=QueryIntent(cached.intent),
            confidence=cached.confidence,
            referenced_titles=cached.targets,
            filters=cached.filters if hasattr(cached, 'filters') else {},
        )

    llm = get_router_llm()

    messages = [
        SystemMessage(content=ROUTER_SYSTEM_PROMPT),
        HumanMessage(content=ROUTER_USER_TEMPLATE.format(query=query)),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = response.content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        result = json.loads(content)

        # Map the intent string to our enum
        intent_str = result.get("intent", "general_info")
        try:
            intent = QueryIntent(intent_str)
        except ValueError:
            # Backward compat mapping for any lingering old intent names
            LEGACY_MAP = {
                "greeting": QueryIntent.GENERAL_INFO,
                "general_library": QueryIntent.GENERAL_INFO,
                "title_lookup": QueryIntent.SIMILAR_BOOKS,
                "similarity": QueryIntent.SIMILAR_BOOKS,
                "filtered_search": QueryIntent.RECOMMENDATION,
                "generic_reco": QueryIntent.RECOMMENDATION,
                "compare": QueryIntent.COMPARISON,
                "account_action": QueryIntent.ACCOUNT_ACTION,
                "details": QueryIntent.BOOK_DETAILS,
                "book_info": QueryIntent.BOOK_DETAILS,
            }
            intent = LEGACY_MAP.get(intent_str, QueryIntent.GENERAL_INFO)

        output = IntentParserOutput(
            intent=intent,
            confidence=result.get("confidence", 0.8),
            referenced_titles=result.get("targets", []),
            filters=result.get("filters", {}),
        )

        # Cache the result
        cache_route(query, RouterOutput(
            intent=output.intent,
            confidence=output.confidence,
            targets=output.referenced_titles,
            filters=output.filters,
        ))

        return output

    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Intent parsing failed: {e}. Defaulting to GENERAL_INFO")
        return IntentParserOutput(
            intent=QueryIntent.GENERAL_INFO,
            confidence=0.5,
            referenced_titles=[],
            filters={},
        )

