# Use official lightweight Python 3.12 image
FROM python:3.12-slim

# Set environment variables:
# - PYTHONUNBUFFERED: ensures stdout/stderr are sent directly to terminal without buffering
# - PYTHONDONTWRITEBYTECODE: prevents Python from writing .pyc files
# - PIP_NO_CACHE_DIR: disables pip cache for cleaner, smaller container
# - PIP_DISABLE_PIP_VERSION_CHECK: avoids noisy pip version check logs
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies (curl for container health check)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose FastAPI default port
EXPOSE 8000

# Container health check using the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: launch Uvicorn with hot-reload enabled for local development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
