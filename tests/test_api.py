import io
from fastapi.testclient import TestClient
from unittest.mock import patch
from pathlib import Path
from fastapi import HTTPException
from pdf2image.exceptions import PDFSyntaxError, PopplerNotInstalledError
import api

client = TestClient(api.app)


# -------------------------
# Health check
# -------------------------
def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# -------------------------
# /parse success
# -------------------------
@patch("api.main.run_parse")
def test_parse_success(mock_run_parse):
    mock_run_parse.return_value = {"name": "John"}

    file_content = b"%PDF-1.4 fake pdf"
    response = client.post(
        "/parse",
        files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {"name": "John"}
    mock_run_parse.assert_called_once()


# -------------------------
# /parse invalid PDF
# -------------------------


@patch("api.main.run_parse")
def test_parse_invalid_pdf(mock_run_parse):
    mock_run_parse.side_effect = PDFSyntaxError("bad pdf")

    response = client.post(
        "/parse",
        files={"file": ("bad.pdf", io.BytesIO(b"bad"), "application/pdf")},
    )

    assert response.status_code == 400
    assert "Invalid PDF file" in response.json()["detail"]


# -------------------------
# /parse server config error
# -------------------------


@patch("api.main.run_parse")
def test_parse_poppler_error(mock_run_parse):
    mock_run_parse.side_effect = PopplerNotInstalledError("missing")

    response = client.post(
        "/parse",
        files={"file": ("file.pdf", io.BytesIO(b"data"), "application/pdf")},
    )

    assert response.status_code == 500
    assert "Server configuration error" in response.json()["detail"]


# -------------------------
# /parse generic error
# -------------------------
@patch("api.main.run_parse")
def test_parse_generic_error(mock_run_parse):
    mock_run_parse.side_effect = Exception("boom")

    response = client.post(
        "/parse",
        files={"file": ("file.pdf", io.BytesIO(b"data"), "application/pdf")},
    )

    assert response.status_code == 500
    assert "Parse Error" in response.json()["detail"]


# -------------------------
# /parse re-raises HTTPException
# -------------------------
@patch("api.main.run_parse")
def test_parse_http_exception_passthrough(mock_run_parse):
    mock_run_parse.side_effect = HTTPException(status_code=418, detail="teapot")

    response = client.post(
        "/parse",
        files={"file": ("file.pdf", io.BytesIO(b"data"), "application/pdf")},
    )

    assert response.status_code == 418
    assert response.json()["detail"] == "teapot"


# -------------------------
# /build success
# -------------------------
@patch("api.main.run_build_from_data")
def test_build_success(mock_build, tmp_path):
    def fake_build(data, output_path, _):
        Path(output_path).write_bytes(b"%PDF-1.4")

    mock_build.side_effect = fake_build

    response = client.post("/build", json={"name": "John"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment")


# -------------------------
# /build file not created
# -------------------------
@patch("api.main.run_build_from_data")
def test_build_no_file_created(mock_build):
    mock_build.return_value = None  # does not create file

    response = client.post("/build", json={"name": "John"})

    assert response.status_code == 500
    assert "PDF generation failed" in response.json()["detail"]


# -------------------------
# /build HTTPException passthrough
# -------------------------
@patch("api.main.run_build_from_data")
def test_build_http_exception(mock_build):
    mock_build.side_effect = HTTPException(status_code=400, detail="bad input")

    response = client.post("/build", json={"name": "John"})

    assert response.status_code == 400
    assert response.json()["detail"] == "bad input"


# -------------------------
# /build generic error
# -------------------------
@patch("api.main.run_build_from_data")
def test_build_generic_error(mock_build):
    mock_build.side_effect = Exception("boom")

    response = client.post("/build", json={"name": "John"})

    assert response.status_code == 500
    assert "Builder Error" in response.json()["detail"]
