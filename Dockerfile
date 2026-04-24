FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libcairo2 \
    libffi-dev \
    libgdk-pixbuf-2.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && adduser --disabled-password --gecos "" appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src src
COPY ./main.py main.py
COPY ./api.py api.py
COPY ./pyproject.toml pyproject.toml
COPY ./config.json /app/config.json

RUN mkdir -p /app/results && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8080/healthz || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]