# 📚 Library Assistant with AI

A modern library discovery platform featuring an intelligent AI assistant for personalized book recommendations.

**Key Tech**: Python FastAPI, React (Vite MPA), PostgreSQL (pgvector), Docker.

[![Deployed on Render](https://img.shields.io/badge/Render-Deployed-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://library-assistant.onrender.com)
*(Replace the link above with your actual Render URL)*

## 🚀 Live Demo

**[View the Live Application on Render](https://library-assistant.onrender.com)**

## 🎥 Video Demo

[![Watch the Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/0.jpg)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)
*(Link your demo video here)*

## 🚀 Overview

Library Assistant transforms the traditional library catalog into a conversational experience. It uses **Retrieval-Augmented Generation (RAG)** to understand the semantic context of user queries, allowing for nuanced book discovery beyond simple keyword matching.

For example, asking *"I want a book that explores the concept of memory like 'The Giver' but darker"* triggers a vector search to find conceptually similar books, which the AI then evaluates and recommends.

## 📊 Data Collection

The comprehensive book dataset for this application was curated from **Goodreads.com**.

1.  **Extraction**: We used custom Python scripts (included in `backend/scripts/extract_goodreads_list.py`) to scrape book data, including titles, authors, genres, and detailed summaries.
2.  **Processing**: The raw data was compiled into a structured CSV format. A sample of this structure is available at [`backend/scripts/goodreads_list_books_sample.csv`](backend/scripts/goodreads_list_books_sample.csv).
3.  **Ingestion**: This CSV data was then enriched and imported into our **PostgreSQL** database, where embedding vectors were generated for each book's description to enable semantic search.

## 🏗️ Architecture

The application follows a containerized, service-oriented architecture:

### **1. AI & Data Layer**
-   **Vector Database**: **PostgreSQL** with the `pgvector` extension stores 384-dimensional embeddings of book content.
-   **LLM Inference**: Uses **Ollama** running the `qwen2.5:7b-instruct` model (configurable) for generating natural language responses.
-   **RAG Pipeline**:
    1.  **Embed**: User query is converted to a vector using `sentence-transformers/all-MiniLM-L6-v2`.
    2.  **Retrieve**: `pgvector` finds the most semantically similar books.
    3.  **Generate**: Retrieved context is fed to Qwen 2.5 to generate a helpful, accurate response.

### **2. Backend (FastAPI)**
-   Provides RESTful endpoints for book management and search.
-   Manages streaming chat using Server-Sent Events (SSE) logic.
-   Handles user authentication and session management.

### **3. Frontend (React Multi-Page App)**
-   Built with **Vite** as a Multi-Page Application (MPA) for distinct entry points:
    -   `index.html`: Home / Landing
    -   `catalog.html`: Browsing interface
    -   `book-details.html`: Deep dive into specific titles
    -   `my-books.html`: User collections
-   Styled with **Tailwind CSS**.

## ✨ Key Features

-   **🤖 Intelligent Chat**: Discuss books with an assistant that remembers context and understands intent.
-   **🔍 Semantic Search**: Find books by plot, mood, or "vibe" — not just title/author.
-   **⚡ Real-Time Availability**: See live copy availability for every book.
-   **📱 Modern UI**: Clean, responsive interface optimized for all devices.
-   **🐳 Fully Containerized**: The entire stack (Frontend, Backend, Database) runs in Docker.

## 🛠️ Tech Stack

| Component | Technology |
| :--- | :--- |
| **Frontend** | React 18, Vite (MPA), Tailwind CSS |
| **Backend** | Python 3.11, FastAPI, SQLModel |
| **Database** | PostgreSQL 16 + `pgvector` |
| **AI / LLM** | Ollama (Qwen 2.5), Sentence Transformers |
| **Hosting**  | **Render** (Dockerized Web Service) |

## 📸 Screenshots

| AI Chat Interface | Book Details |
|:---:|:---:|
| ![Chat Interface](docs/chat_placeholder.png) | ![Book Details](docs/details_placeholder.png) |
| *Get personalized recommendations* | *View deep metadata and reviews* |

## 🚀 Local Quick Start

The entire application can be spun up locally using Docker.

### Prerequisites
-   Docker & Docker Compose
-   Ollama running locally (configured for `qwen2.5`)

### Run the App
```bash
# 1. Clone the repository
git clone https://github.com/shashwatpasari/library-assistant.git

# 2. Start all services
docker-compose up --build
```
