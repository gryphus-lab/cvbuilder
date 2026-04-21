# 1. Using a stable Python version (3.13 is current stable, 3.14 is in development)
FROM python:3.13-slim

# 2. Combined RUN commands to reduce layers and minimize image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libcairo2 \
    libffi-dev \
    libgdk-pixbuf-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. Requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy project files
COPY . .

# 5. Create results directory and set permissions if needed
RUN mkdir -p /app/results

# 6. config.json is likely already in '.' from the previous COPY, 
# but explicit COPY is fine for clarity.
COPY config.json /app/config.json

CMD ["python", "main.py", "--help"]
