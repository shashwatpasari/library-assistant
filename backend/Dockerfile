
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# libpq-dev is required for psycopg2 to compile
# gcc, g++ are needed for compiling python extensions
# curl for healthcheck
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Use increased timeout for large packages like torch
RUN pip install --no-cache-dir --timeout 300 -r requirements.txt

# Create a non-root user for security
RUN adduser --disabled-password --gecos "" appuser

# Copy the rest of the application code
COPY . .

# Switch to non-root user
USER appuser

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -sf http://localhost:8000/docs || exit 1

# Run app.main:app when the container launches
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
