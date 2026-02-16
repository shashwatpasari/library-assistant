# 📚 Library Assistant

A full-stack book discovery platform with an AI chatbot that recommends books based on your taste, mood, and reading history.

> *Try asking: "I loved The Hunger Games — what should I read next?"*

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI Chatbot** | Conversational book recommendations powered by RAG |
| 🔍 **Semantic Search** | Finds books by meaning using 384-dim vector embeddings |
| 🧠 **LangGraph Pipeline** | Multi-agent graph with intent routing, guardrails, and hybrid retrieval |
| 📊 **Collaborative Filtering** | Recommendations improve as more users interact |
| 📚 **8,000+ Books** | Full catalog with covers, ratings, synopses, and metadata |
| ❤️ **Personal Library** | Save, borrow, and organize books into reading lists |
| 🎯 **Preference Learning** | Onboarding flow and liked-book history tailor recommendations |
| 🔐 **Auth** | JWT authentication with email verification and password reset |
| ⚡ **Streaming** | SSE-based token streaming for real-time responses |

---

## 🧠 How It Works

The chatbot is built on a **LangGraph** state machine that routes each query through specialized agent nodes:

```
User Query
    │
    ▼
┌──────────────────────┐
│  Intent Router (LLM) │  Classifies into one of 7 intents
└──────────┬───────────┘
           │
     deterministic routing
           │
    ┌──────┴──────────────────────────────────────┐
    │              Agent Nodes                     │
    ├─ recommendation_agent   (hybrid retrieval)   │
    ├─ similar_books_agent    (cosine similarity)  │
    ├─ comparison_agent       (side-by-side)       │
    ├─ user_history_agent     (saved/borrowed)     │
    ├─ book_details_agent     (single book info)   │
    ├─ account_action_agent   (save/borrow)        │
    └─ general_info_agent     (library info)       │
           │
           ▼
┌──────────────────────┐
│  LLM Generation      │  Generates response using retrieved context
└──────────┬───────────┘
           │
           ▼
    Streamed Response + Book Cards
```

**Key design decisions:**
- The LLM is used **only** for intent classification and response generation — all routing is deterministic
- Similarity scoring is computed **in code** (cosine similarity), never delegated to the LLM
- Hybrid retrieval combines **vector search** (pgvector), **full-text search** (PostgreSQL FTS), and **collaborative filtering**

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────┐
│                  NGINX (Port 3000)                      │
│             Reverse Proxy + Static Files                │
├───────────────────────┬─────────────────────────────────┤
│                       │                                  │
│  ┌────────────────┐   │   ┌───────────────────────┐     │
│  │   Frontend     │   │   │    Backend API        │     │
│  │  (Vite + JS)   │◄──┼──►│    (FastAPI)          │     │
│  └────────────────┘   │   └───────────┬───────────┘     │
│                       │               │                  │
│             ┌─────────┴───────┐       │                  │
│             │                 │       │                  │
│  ┌──────────▼──────┐  ┌──────▼───────▼──┐              │
│  │  PostgreSQL 16  │  │   Groq Cloud    │              │
│  │  + pgvector     │  │   (LLM API)     │              │
│  └─────────────────┘  └─────────────────┘              │
└───────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Vite, Vanilla JavaScript, HTML/CSS |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy |
| **Database** | PostgreSQL 16 + pgvector |
| **RAG Pipeline** | LangGraph, LangChain |
| **LLMs** | Groq — Llama 3.3 70B (generation), Llama 3.1 8B (intent routing) |
| **Embeddings** | Sentence Transformers — all-MiniLM-L6-v2 (384-dim) |
| **Infrastructure** | Docker Compose, Nginx |

---

## 🚀 Getting Started

### Prerequisites

- Docker & Docker Compose
- A [Groq API key](https://console.groq.com) (free tier available)

### Configuration

Copy the example environment file and fill in the required values:

```bash
cp .env.example .env
```

| Variable | Description | Required |
|----------|-------------|----------|
| `POSTGRES_PASSWORD` | Database password | ✅ |
| `JWT_SECRET_KEY` | JWT signing key — generate with `openssl rand -hex 32` | ✅ |
| `GROQ_API_KEY` | Groq API key for LLM inference | ✅ |
| `LLM_PROVIDER` | Set to `groq` | ✅ |
| `GROQ_MODEL` | Generation model | Default: `llama-3.3-70b-versatile` |
| `CORS_ORIGINS` | Allowed CORS origins | Default: `http://localhost:3000` |
| `SMTP_HOST` | Email server (for password reset) | Optional |
| `SMTP_USER` / `SMTP_PASSWORD` | Email credentials | Optional |
| `FROM_EMAIL` | Sender email address | Optional |
| `FRONTEND_URL` | Frontend URL for email links | Default: `http://localhost:3000` |

### Start

```bash
docker compose up --build
```

The app will be available at <!-- add your URL here -->.

---

## 📁 Project Structure

```
library-assistant/
├── backend/
│   ├── app/
│   │   ├── api/routes/         # REST endpoints (auth, books, chat, saved_books, …)
│   │   ├── rag/                # LangGraph pipeline
│   │   │   ├── graph.py        # State machine — agent nodes & conditional edges
│   │   │   ├── router.py       # LLM-based intent classification
│   │   │   ├── retrievers.py   # Hybrid retrieval (vector + FTS + collaborative)
│   │   │   ├── prompts.py      # All LLM prompt templates
│   │   │   ├── streaming.py    # SSE streaming adapter
│   │   │   ├── collaborative.py # Collaborative filtering embeddings
│   │   │   └── …
│   │   ├── services/           # Business logic (auth, books, borrow, email, …)
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   └── config.py           # Environment-based configuration
│   ├── migrations/             # SQL migrations (FTS indexes, collaborative filtering)
│   ├── scripts/                # Data import & enrichment utilities
│   ├── tests/                  # Pytest test suite
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/         # Chat widget, header, star rating
│   │   ├── services/           # API, auth, user-books clients
│   │   └── lib/                # Shared utilities
│   ├── *.html                  # MPA pages (index, catalog, book-details, …)
│   ├── vite.config.js
│   ├── nginx.conf              # Reverse proxy configuration
│   └── Dockerfile
│
├── docker-compose.yml          # Full-stack orchestration
├── .github/workflows/          # CI/CD pipeline
└── .env.example                # Configuration template
```

---

## 📊 Data

The catalog contains **8,000+ books** sourced from Goodreads and enriched with:

- Titles, authors, genres, themes, moods
- Synopses, cover images, page counts, ratings
- 384-dimensional embedding vectors for semantic search

Utility scripts in `backend/scripts/` handle scraping, enrichment, embedding, and import.

---

## 🚢 Deployment

Deployed on **GCP Compute Engine** with automated CI/CD:

1. Push to `main` triggers a GitHub Actions workflow
2. The workflow SSHs into the GCP VM
3. Pulls latest code, rebuilds containers, restarts services

---

## 👤 Author

**Shashwat Pasari**

[![GitHub](https://img.shields.io/badge/GitHub-shashwatpasari-181717?style=flat&logo=github)](https://github.com/shashwatpasari)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?style=flat&logo=linkedin)](https://linkedin.com/in/shashwatpasari)
