# 📚 Library Assistant

> **An intelligent book discovery platform that transforms how you find your next read.**

Traditional library catalogs rely on keyword searches and rigid filters—but readers often don't know exactly what they want. They know a *feeling*: "something like The Alchemist but more philosophical" or "a cozy mystery for a rainy weekend."

**Library Assistant** solves this by combining **semantic vector search** with a **conversational AI chatbot** powered by RAG (Retrieval-Augmented Generation). Instead of browsing endless catalogs, users simply *describe* what they're looking for, and the AI understands context, mood, and themes to deliver personalized recommendations.

### Key Highlights

- 🧠 **RAG-Powered Chatbot** — Understands natural language queries and retrieves contextually relevant books before generating responses
- 🔍 **Semantic Search** — Uses 384-dimensional embeddings to find books by meaning, not just keywords
- ⚡ **Streaming Responses** — Real-time token streaming for instant feedback
- 🎯 **Personalization** — Learns preferences through onboarding and liked books
- 🐳 **Production-Ready** — Fully containerized with automated CI/CD deployment

[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-Visit_Site-blue?style=for-the-badge)](http://YOUR_IP_HERE:3000)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/shashwatpasari/library-assistant/actions)

---

## 🎬 Demo

### Live Application
🔗 **[http://YOUR_IP_HERE:3000](http://YOUR_IP_HERE:3000)**

### Video Walkthrough
<!-- Add your video link here -->
[![Watch Demo](https://img.shields.io/badge/▶_Watch_Demo-YouTube-red?style=for-the-badge&logo=youtube)](https://youtube.com/watch?v=YOUR_VIDEO_ID)

<!-- Or embed a GIF -->
<!-- ![Demo GIF](docs/demo.gif) -->

---

## 🧠 How It Works

The chatbot uses **RAG (Retrieval-Augmented Generation)** to understand queries like:
- *"Suggest something like Harry Potter but darker"*
- *"Fast-paced thriller for a beach read"*
- *"Books about AI and consciousness"*

### RAG Pipeline

```
User Query → Embedding → Vector Search (pgvector) → Context Injection → LLM Response
```

1. **Embed**: Query converted to 384-dim vector using `sentence-transformers/all-MiniLM-L6-v2`
2. **Retrieve**: pgvector finds semantically similar books from 8,000 embeddings
3. **Generate**: Qwen 2.5 LLM generates personalized recommendations with retrieved context

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI Chatbot** | Natural language book recommendations with streaming responses |
| 🔍 **Semantic Search** | Find books by vibe, mood, or theme—not just keywords |
| 📚 **8,000 Books** | Comprehensive catalog with covers, ratings, and synopses |
| ❤️ **Personal Library** | Like, borrow, and organize your reading list |
| 🎯 **Preference Learning** | Onboarding flow tailors recommendations to your taste |
| 🔐 **Secure Auth** | JWT authentication with email verification |
| ⚡ **Real-time Streaming** | See AI responses as they're generated |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         NGINX (Port 3000)                        │
│                    Reverse Proxy + Static Files                  │
├─────────────────────────────────────────────────────────────────┤
│                              │                                   │
│    ┌──────────────────┐     │     ┌──────────────────────┐      │
│    │     Frontend     │     │     │      Backend API     │      │
│    │   (Vite + JS)    │ ◄───┼───► │      (FastAPI)       │      │
│    └──────────────────┘     │     └──────────────────────┘      │
│                              │              │                    │
│                              │              ▼                    │
│                    ┌─────────┴─────────────────────────┐        │
│                    │                                    │        │
│         ┌──────────▼──────────┐    ┌──────────────────▼─┐       │
│         │     PostgreSQL      │    │       Ollama       │       │
│         │   + pgvector        │    │    (Qwen 2.5)      │       │
│         │   (Embeddings)      │    │                    │       │
│         └─────────────────────┘    └────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Vite, JavaScript, Tailwind CSS |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy |
| **Database** | PostgreSQL 16 + pgvector |
| **AI/ML** | Qwen 2.5 LLM, Sentence Transformers |
| **Embeddings** | all-MiniLM-L6-v2 (384 dimensions) |
| **Infrastructure** | Docker Compose, Nginx, GCP Compute Engine |
| **CI/CD** | GitHub Actions |

---

## 📸 Screenshots

<!-- Add your screenshots here -->

| Home Page | Catalog | AI Chat |
|:---------:|:-------:|:-------:|
| ![Home](docs/screenshots/home.png) | ![Catalog](docs/screenshots/catalog.png) | ![Chat](docs/screenshots/chat.png) |

| Book Details | My Books | Onboarding |
|:------------:|:--------:|:----------:|
| ![Details](docs/screenshots/details.png) | ![MyBooks](docs/screenshots/mybooks.png) | ![Onboarding](docs/screenshots/onboarding.png) |

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- 8GB+ RAM (for LLM)

### Run Locally

```bash
# Clone the repository
git clone https://github.com/shashwatpasari/library-assistant.git
cd library-assistant

# Copy environment file
cp .env.example .env
# Edit .env and add your secrets (JWT_SECRET_KEY, POSTGRES_PASSWORD)

# Start all services
docker compose up --build

# Wait for services to start, then pull the LLM model
docker compose exec ollama ollama pull qwen2.5:3b-instruct
```

**Access the app at:** http://localhost:3000

---

## 📁 Project Structure

```
library-assistant/
├── frontend/               # Vite frontend (MPA)
│   ├── src/
│   │   ├── components/     # Shared components (header, chat-widget)
│   │   └── services/       # API, auth, user-books services
│   ├── index.html          # Home page
│   ├── catalog.html        # Book browsing
│   ├── book-details.html   # Individual book view
│   ├── my-books.html       # User's library
│   └── nginx.conf          # Nginx config with API proxy
│
├── backend/                # FastAPI backend
│   ├── app/
│   │   ├── api/routes/     # API endpoints
│   │   ├── models/         # SQLAlchemy models
│   │   └── services/       # Business logic (chat, embedding, email)
│   └── scripts/            # Data import utilities
│
├── docker-compose.yml      # Service orchestration
└── .github/workflows/      # CI/CD pipeline
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `POSTGRES_PASSWORD` | Database password | ✅ |
| `JWT_SECRET_KEY` | JWT signing key | ✅ |
| `OLLAMA_MODEL` | LLM model name | Default: `qwen2.5:3b-instruct` |
| `SMTP_HOST` | Email server | Optional |
| `SMTP_USER` | Email username | Optional |
| `SMTP_PASSWORD` | Email password | Optional |

---

## 🚢 Deployment

The app is deployed on **GCP Compute Engine** with automated CI/CD:

## 📊 Data

The book dataset includes 8000+ titles sourced from:
- Goodreads (scraped with custom scripts)

Each book includes: title, authors, genres, synopsis, cover image, ratings, and 384-dimensional embedding vector.

---

## 👤 Author

**Shashwat Pasari**

[![GitHub](https://img.shields.io/badge/GitHub-shashwatpasari-181717?style=flat&logo=github)](https://github.com/shashwatpasari)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?style=flat&logo=linkedin)](https://linkedin.com/in/shashwatpasari)


