import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level up from backend/)
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")

# PostgreSQL connection string
# Format: postgresql://username:password@host:port/database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/library_assistant")

# LLM Provider: "ollama" or "groq"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

# Ollama API endpoint (where your local LLM is running)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Which Ollama model to use for chat responses
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")

# Groq API settings
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "llama-3.1-8b-instant")

# Sentence-transformers model for generating text embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Vector dimensions size (must match the embedding model's output)
# all-MiniLM-L6-v2 produces 384-dimensional vectors
EMBEDDING_DIMENSION = 384

# =============================================================================
# LLM CONFIGURATION
# =============================================================================

# Timeouts
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

# =============================================================================
# CACHING CONFIGURATION
# =============================================================================

# Embedding cache TTL in seconds (default 1 hour)
EMBEDDING_CACHE_TTL = int(os.getenv("EMBEDDING_CACHE_TTL", "3600"))

# Router/filter cache TTL in seconds (default 5 minutes)
ROUTER_CACHE_TTL = int(os.getenv("ROUTER_CACHE_TTL", "300"))

# =============================================================================
# RETRIEVAL CONFIGURATION
# =============================================================================

# Maximum candidates to retrieve before filtering
RETRIEVAL_CANDIDATE_LIMIT = int(os.getenv("RETRIEVAL_CANDIDATE_LIMIT", "50"))

# RRF (Reciprocal Rank Fusion) constant
RRF_K = int(os.getenv("RRF_K", "60"))

# =============================================================================
# LIBRARY INFORMATION (for prompts)
# =============================================================================

LIBRARY_NAME = os.getenv("LIBRARY_NAME", "Library Hub")
LIBRARY_OWNER = os.getenv("LIBRARY_OWNER", "Shashwat Pasari")
LIBRARY_HOURS = os.getenv("LIBRARY_HOURS", "9:00 AM to 9:00 PM")

