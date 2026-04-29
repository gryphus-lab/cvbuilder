FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Create non-root user BEFORE apt-get (better layer caching)
RUN adduser --disabled-password --gecos "" --no-create-home appuser

# Install dependencies with clean apt state
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    mkdir -p /app/results /app/uploads && \
    chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser ./src src
COPY --chown=appuser:appuser ./main.py main.py
COPY --chown=appuser:appuser ./api.py api.py
COPY --chown=appuser:appuser ./config.json /app/config.json

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -m http.client localhost 8080 /healthz 2>/dev/null || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
