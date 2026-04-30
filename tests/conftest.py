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
    """Provide a path to a test PDF (create a dummy one if needed)."""
    test_pdf_path = tmp_path / "test_cv.pdf"

    # Create a minimal dummy PDF for testing if one doesn't exist
    if not test_pdf_path.exists():
        # Simple way: create an empty PDF using reportlab or just copy a real one if available
        # For now, we'll assume you have a test PDF or we'll create a placeholder
        test_pdf_path.touch()  # placeholder

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
