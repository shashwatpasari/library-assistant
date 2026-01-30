#!/bin/bash
# Quick start script for the backend server

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Start the FastAPI server
echo "Starting FastAPI server on http://localhost:8000"
echo "API docs available at http://localhost:8000/docs"
uvicorn app.main:app --reload

