# CV Parser and Builder

Parse a CV PDF with [Tesseract OCR](https://tesseract-ocr.github.io/) into structured JSON and generate a styled PDF CV from that data.

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=coverage)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=gryphus-lab_cvbuilder&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=gryphus-lab_cvbuilder)
[![mise](https://img.shields.io/badge/managed%20with-mise-6f42c1)](https://mise.jdx.dev/)
[![React](https://img.shields.io/badge/Python-3.14-2496ED?logo=python&logoColor=white)](https://www.python.org/)
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

## Mise Tasks

Common workflows are exposed through `mise` tasks:

- `mise run bootstrap` — install dependencies
- `mise run info` — print project + venv info
- `mise run parse` — parse CV PDF
- `mise run build` — build PDF from JSON
- `mise run full` — parse + build
- `mise run lint` — run `black --check`
- `mise run format` — run `black`
- `mise run test` — run test suite with `pytest`
- `mise run coverage` — run `pytest` with coverage reports

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
