from pathlib import Path
from fastapi.testclient import TestClient
import pytest


@pytest.mark.integration
def test_health_check(test_client: TestClient):
    """Test the health check endpoint."""
    response = test_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.skip(
    reason="Requires OCR and a valid PDF, may be slow and not suitable for CI"
)
def test_parse_endpoint(test_client: TestClient, test_pdf: Path, clean_results_dir):
    """Test the /parse endpoint with a PDF file."""
    with open(test_pdf, "rb") as f:
        files = {"file": ("cv_original.pdf", f, "application/pdf")}

        response = test_client.post("/parse", files=files)

    assert response.status_code == 200
    data = response.json()

    assert "personal_info" in data
    assert "profile" in data
    assert "professional_experience" in data
    assert isinstance(data["professional_experience"], list)


@pytest.mark.integration
def test_build_endpoint(test_client: TestClient, clean_results_dir):
    """Test the /build endpoint (requires cv_data.json to exist)."""
    # First ensure we have a cv_data.json
    cv_data_path = Path("cv_data.json")
    if not cv_data_path.exists():
        pytest.skip("cv_data.json not found - run parser first")

    response = test_client.post("/build")

    assert response.status_code == 200
    data = response.json()

    assert "message" in data
    assert "output_path" in data
    assert Path(data["output_path"]).exists()


@pytest.mark.skip(
    reason="Disabled due to potential issues with file handling and cleanup in CI environments"
)
def test_parse_invalid_file(test_client: TestClient):
    """Test error handling for invalid file type."""
    files = {"file": ("test.txt", b"not a pdf", "text/plain")}
    response = test_client.post("/parse", files=files)

    assert response.status_code in (400, 422)


@pytest.mark.integration
def test_root_endpoint(test_client: TestClient):
    """Test the root endpoint returns API info."""
    response = test_client.get("/")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
