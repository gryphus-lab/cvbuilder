# 1. Build Stage
FROM python:3.14-slim AS builder

# Install uv from official binaries
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory and configuration
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Copy lockfiles first to leverage Docker layer caching
COPY uv.lock pyproject.toml ./

# Install dependencies without installing the project itself yet
# --frozen ensures uv uses the lockfile without attempting to update it
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --no-build

# 2. Runtime Stage
FROM python:3.14-slim AS runtime

# Set security and performance environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Create a dedicated non-root user
RUN adduser --disabled-password --gecos "" --home /home/appuser appuser && \
    chown -R appuser:appuser /home/appuser && \
    chmod -R 750 /home/appuser && \
    # Install system dependencies (runtime-only)
    apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code with restrictive permissions
COPY --chown=appuser:appuser ./src ./src
COPY --chown=appuser:appuser ./main.py ./api.py ./config.json ./

# Create runtime directories with restrictive permissions (750)
RUN mkdir -p /app/results /app/uploads && \
    chown -R appuser:appuser /app && \
    chmod -R 750 /app

USER appuser

# Healthcheck using Python's internal library to avoid external curl/wget dependencies
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import http.client; c=http.client.HTTPConnection('localhost', 8080); c.request('GET', '/healthz'); exit(0 if c.getresponse().status==200 else 1)"

EXPOSE 8080

# Execute using the absolute path of the pinned uvicorn binary
CMD ["/app/.venv/bin/uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
