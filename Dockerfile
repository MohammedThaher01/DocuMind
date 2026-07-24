# syntax=docker/dockerfile:1.6

# DocuMind backend — FastAPI + LangGraph + Groq
# Deployable on Render (Native Dockerfile deploy) or any container host.

FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps needed by python-docx / common libs
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install deps first (cache-friendly layer)
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application code
COPY . ./

# Where generated .docx files live. Render supports a persistent disk at /data —
# see render.yaml. If no disk is attached, /app/generated_docs is an in-container
# tmp directory (docs survive only until the next deploy / restart).
ENV OUTPUT_DIR=/app/generated_docs
RUN mkdir -p /app/generated_docs && chmod 777 /app/generated_docs

# Render injects $PORT dynamically. uvicorn must bind to it explicitly.
ENV HOST=0.0.0.0
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --workers 1"]
