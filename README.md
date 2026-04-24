# CV Parser and Builder

Parse a CV PDF with [Tesseract OCR](https://tesseract-ocr.github.io/) into structured JSON and generate a styled PDF CV from that data.

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=coverage)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![mise](https://img.shields.io/badge/managed%20with-mise-6f42c1)](https://mise.jdx.dev/)
[![Python](https://img.shields.io/badge/Python-3.14-2496ED?logo=python&logoColor=white)](https://www.python.org/)

## Requirements

- [mise](https://mise.jdx.dev/)
- Homebrew (macOS) for native libraries used by PDF tooling
- Python 3.14 (managed by `mise`)

## Setup

Install tools and Python dependencies:

```bash
mise install
mise run bootstrap
```

## Usage

The CLI entry point is `main.py` with two subcommands:

### Parse PDF → JSON

```bash
python main.py parse [pdf_path] -o [output_json]
```

or run with defaults:

```bash
mise run parse
```

Defaults:

- input PDF: `resources/cv_original.pdf`
- output JSON: `results/cv_data.json`

### Build JSON → PDF

```bash
python main.py build --json [input_json] --output [output_pdf] [--photo path/to/photo.jpg]
```

or run with defaults:

```bash
mise run build
```

Defaults:

- input JSON: `results/cv_data.json`
- output PDF: `results/cv_updated.pdf`

## API

The application also provides a REST API using FastAPI.

### Running the API

Start the API server:

```bash
uvicorn api:app --host 0.0.0.0 --port 8080
```

Or with Docker:

```bash
docker-compose up
```

The API will be available at `http://localhost:8080`.

### Endpoints

- `GET /healthz`: Health check endpoint.
- `POST /parse`: Upload a PDF file to parse into structured JSON.
- `POST /build`: Provide JSON data to generate a PDF CV.

For detailed API documentation, visit `http://localhost:8080/docs` when the server is running.

## Docker

To run the application in a container:

```bash
docker-compose up --build
```

This will build the image and start the API server on port 8080.

## Mise Tasks

Common workflows are exposed through `mise` tasks:

- `mise run bootstrap` — install dependencies
- `mise run info` — print project + venv info
- `mise run parse` — parse CV PDF → results/cv_data.json
- `mise run build` — build PDF from JSON data → default: results/cv.pdf
- `mise run full` — parse + build (full regeneration)
- `mise run lint` — lint and check formatting with Ruff
- `mise run format` — format and fix code with Ruff
- `mise run test` — run tests with pytest
- `mise run coverage` — run tests with coverage report
- `mise run docker-build` — build the Docker image
- `mise run docker-parse-pdf` — parse PDF inside Docker
- `mise run docker-build-pdf` — build PDF inside Docker
- `mise run docker-full-pdf` — full parse + build inside Docker
- `mise run docker-compose-up` — run docker-compose (API server)
- `mise run docker-compose-down` — stop docker-compose

## Testing

Run tests:

```bash
mise run test
```

Run tests with coverage:

```bash
mise run coverage
```

## CI

GitHub Actions workflow: `.github/workflows/ci.yml`

On pushes and pull requests to `main`, CI runs setup, linting, tests, and coverage tasks via `mise`.
