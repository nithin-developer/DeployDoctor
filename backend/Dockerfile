# Use lightweight Python base image
FROM python:3.13-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cloud Run requires PORT env var
ENV PORT=8080

# Set working directory
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install   -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose Cloud Run port
EXPOSE 8080

# Run Flask using Gunicorn (REQUIRED for production)
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
