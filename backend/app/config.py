import os

# PostgreSQL connection string
# Format: postgresql://username:password@host:port/database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/library_assistant")

# Ollama API endpoint (where your local LLM is running)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Which Ollama model to use for chat responses
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")

# Sentence-transformers model for generating text embeddings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Vector dimensions size (must match the embedding model's output)
# all-MiniLM-L6-v2 produces 384-dimensional vectors
EMBEDDING_DIMENSION = 384
