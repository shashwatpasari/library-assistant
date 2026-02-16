"""
LangChain LLM factory for Groq and Ollama providers.

Provides a unified interface for creating chat models with:
- Streaming support
- JSON mode for structured outputs
- Configurable timeouts and retries
"""

from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import (
    LLM_PROVIDER,
    GROQ_API_KEY,
    GROQ_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    LLM_TIMEOUT_SECONDS,
)


def get_llm(
    streaming: bool = True,
    json_mode: bool = False,
    temperature: float = 0.7,
    max_tokens: int = 1500,
) -> BaseChatModel:
    """
    Get a LangChain chat model based on the configured provider.
    
    Args:
        streaming: Enable streaming responses
        json_mode: Enable JSON output mode (for structured outputs)
        temperature: Sampling temperature (0.0-1.0)
        max_tokens: Maximum tokens in response
        
    Returns:
        A LangChain BaseChatModel instance (ChatGroq or ChatOllama)
    """
    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        return _get_groq_llm(
            streaming=streaming,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        return _get_ollama_llm(
            streaming=streaming,
            json_mode=json_mode,
            temperature=temperature,
            max_tokens=max_tokens,
        )


def _get_groq_llm(
    streaming: bool,
    json_mode: bool,
    temperature: float,
    max_tokens: int,
    model_name: Optional[str] = None,
) -> BaseChatModel:
    """Create a ChatGroq instance."""
    from langchain_groq import ChatGroq
    
    model_kwargs = {}
    if json_mode:
        model_kwargs["response_format"] = {"type": "json_object"}
    
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=model_name or GROQ_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        timeout=LLM_TIMEOUT_SECONDS,
        model_kwargs=model_kwargs,
    )


def _get_ollama_llm(
    streaming: bool,
    json_mode: bool,
    temperature: float,
    max_tokens: int,
    model_name: Optional[str] = None,
) -> BaseChatModel:
    """Create a ChatOllama instance."""
    from langchain_ollama import ChatOllama
    
    format_param = "json" if json_mode else None
    
    return ChatOllama(
        base_url=OLLAMA_BASE_URL,
        model=model_name or OLLAMA_MODEL,
        temperature=temperature,
        num_predict=max_tokens,
        format=format_param,
    )


def get_router_llm() -> BaseChatModel:
    """Get an LLM configured for routing (fast, low temperature, JSON mode)."""
    # Use specific router model if configured
    from app.config import ROUTER_MODEL
    
    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        return _get_groq_llm(
            streaming=False,
            json_mode=True,
            temperature=0.0,
            max_tokens=500,  # Increased strictly for JSON stability
            model_name=ROUTER_MODEL,
        )
    else:
        return _get_ollama_llm(
            streaming=False,
            json_mode=True,
            temperature=0.0,
            max_tokens=300,
            model_name=ROUTER_MODEL, # Assuming OLLAMA fallback also uses this var or defaults
        )


def get_filter_llm() -> BaseChatModel:
    """Get an LLM configured for filter extraction (fast, JSON mode)."""
    return get_llm(
        streaming=False,
        json_mode=True,
        temperature=0.0,
        max_tokens=300,
    )


def get_generation_llm() -> BaseChatModel:
    """Get an LLM configured for generation (streaming, plain text output)."""
    return get_llm(
        streaming=True,
        json_mode=False,  # Plain text output, NOT JSON
        temperature=0.7,
        max_tokens=1500,
    )

