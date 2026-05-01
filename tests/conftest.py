import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import shutil
from api import app  # Import the FastAPI app after mocking weasyprint

# Mock weasyprint's HTML class globally to prevent import errors on systems
# without required native libraries (libgobject, Pango, Cairo, etc.)
# Use a minimal stub that only exposes HTML to catch import typos or unexpected attribute access
sys.modules["weasyprint"] = SimpleNamespace(HTML=MagicMock())


@pytest.fixture(scope="session")
def test_client() -> TestClient:
    """Create a TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(scope="function")
def test_pdf(tmp_path: Path) -> Path:
    """Provide a path to a test PDF with minimal valid PDF content."""
    test_pdf_path = tmp_path / "test_cv.pdf"

    # Create minimal valid PDF with correct xref offsets
    minimal_pdf = b"""%PDF-1.4
1 0 obj
<</Type /Catalog /Pages 2 0 R>>
endobj
2 0 obj
<</Type /Pages /Kids [3 0 R] /Count 1>>
endobj
3 0 obj
<</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000056 00000 n
0000000111 00000 n
trailer
<</Size 4 /Root 1 0 R>>
startxref
180
%%EOF"""
    test_pdf_path.write_bytes(minimal_pdf)

    return test_pdf_path


@pytest.fixture(scope="function")
def clean_results_dir():
    """Clean results directory before/after tests."""
    results_dir = Path("results")
    if results_dir.exists():
        shutil.rmtree(results_dir)
    results_dir.mkdir(exist_ok=True)
    yield
    # Optional: clean up after test
    # shutil.rmtree(results_dir)


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests as integration (slow, uses OCR)"
    )
