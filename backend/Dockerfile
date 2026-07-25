# Multi-stage build: install deps once, produce a lean runtime image.
FROM python:3.12-slim AS base

# System deps: tesseract for OCR, plus build essentials for any native wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency manifests first so this layer caches unless deps change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Now the application code.
COPY . .

# The venv uv created is at /app/.venv; put it on PATH.
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Default command runs the API; the worker overrides this in compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
