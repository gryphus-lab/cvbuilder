from fastapi.testclient import TestClient
from io import BytesIO
from unittest.mock import patch
from api import app

client = TestClient(app)

# --- MOCK DATA ---
MOCK_CV_DATA = {
    "personal_info": {"name": "Test User", "email": "test@example.com"},
    "profile": "Software Engineer",
    "strategic_impact": [],
    "professional_experience": [],
    "certificates_and_training": [],
    "education": [],
    "languages": [],
    "competencies_and_skills": {},
    "volunteering": [],
}


def test_api_parse_success():
    """Tests that a PDF upload is correctly passed to main.run_parse."""
    # Mock the return value of the parser logic
    mock_data = {"status": "parsed", "name": "Test User"}

    with patch("main.run_parse", return_value=mock_data) as mock_parse:
        # Create a dummy PDF file in memory
        pdf_content = b"%PDF-1.4 dummy content"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}

        response = client.post("/parse", files=files)

        assert response.status_code == 200
        assert response.json() == mock_data
        mock_parse.assert_called_once()

        # Assert the arguments passed to main.run_parse
        call_args = mock_parse.call_args[0]
        temp_pdf_path = str(call_args[0])
        assert temp_pdf_path.startswith("uploads/")
        assert temp_pdf_path.endswith(".pdf")


def test_api_build_success():
    """Tests that JSON data results in a PDF FileResponse."""

    # Mock run_build_from_data to simulate creating a file on disk
    def side_effect_create_file(data, output_path, photo):
        """
        Create an empty file at output_path to simulate a generated output file for tests.
        
        Parameters:
            data: Builder input data (not used).
            output_path (pathlike): Path where an empty file will be created; the file will exist after this call.
            photo: Optional photo data passed to the builder (not used).
        """
        output_path.touch()  # Create the empty file so exists() returns True

    with patch(
        "main.run_build_from_data", side_effect=side_effect_create_file
    ) as mock_build:
        response = client.post("/build", json=MOCK_CV_DATA)

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert (
            response.headers["content-disposition"]
            == 'attachment; filename="my_cv.pdf"'
        )
        # Verify exact arguments
        mock_build.assert_called_once()
        call_args = mock_build.call_args[0]
        assert call_args[0] == MOCK_CV_DATA
        assert call_args[2] is None


def test_api_parse_error_handling():
    """Tests that exceptions in main.py are converted to 500 errors."""
    with patch("main.run_parse", side_effect=Exception("OCR Failed")):
        files = {"file": ("test.pdf", b"content", "application/pdf")}
        response = client.post("/parse", files=files)

        assert response.status_code == 500
        assert "Parse Error: OCR Failed" in response.json()["detail"]


def test_api_build_file_not_created():
    """Tests 500 error if builder fails to actually write the file."""
    from fastapi import HTTPException

    def raise_http_exception(*args, **kwargs):
        """
        Raise an HTTP 500 HTTPException with detail "PDF generation failed."
        
        Raises:
            fastapi.HTTPException: status_code 500 with detail "PDF generation failed."
        """
        raise HTTPException(status_code=500, detail="PDF generation failed.")

    with patch("main.run_build_from_data", side_effect=raise_http_exception):
        response = client.post("/build", json=MOCK_CV_DATA)
        assert response.status_code == 500
        assert response.json()["detail"] == "PDF generation failed."


def test_api_parse_http_exception_reraise():
    """Tests that an HTTPException raised by run_parse is re-raised unchanged (not wrapped in 500)."""
    from fastapi import HTTPException

    def raise_http_404(*args, **kwargs):
        """
        Raise an HTTP 404 Not Found exception with detail "Resource not found".

        Raises:
            HTTPException: An exception with status_code=404 and detail="Resource not found".
        """
        raise HTTPException(status_code=404, detail="Resource not found")

    with patch("main.run_parse", side_effect=raise_http_404):
        files = {"file": ("test.pdf", b"%PDF content", "application/pdf")}
        response = client.post("/parse", files=files)

        assert response.status_code == 404
        assert response.json()["detail"] == "Resource not found"


def test_api_parse_temp_file_cleaned_up_on_success():
    """Tests that the temporary PDF file is deleted after a successful /parse call."""
    mock_data = {"name": "Test"}
    captured_temp_path = []

    def capturing_run_parse(pdf_path):
        """
        Append the given PDF path to the test's captured_temp_path list and return the prepared mock_data.
        
        Parameters:
            pdf_path (str | pathlib.Path): Path passed by the code under test; appended to the global `captured_temp_path` list.
        
        Returns:
            dict: The preconfigured `mock_data` object.
        """
        captured_temp_path.append(pdf_path)
        return mock_data

    with patch("main.run_parse", side_effect=capturing_run_parse):
        files = {"file": ("test.pdf", b"%PDF content", "application/pdf")}
        response = client.post("/parse", files=files)

    assert response.status_code == 200
    # Verify temp file was cleaned up (does not exist after request)
    assert len(captured_temp_path) == 1
    assert not captured_temp_path[0].exists(), (
        "Temp file was not cleaned up after success"
    )


def test_api_parse_temp_file_cleaned_up_on_error():
    """Verify that when `run_parse` raises an exception, the uploaded temporary PDF file is removed after the request."""
    captured_temp_path = []

    def capturing_error_run_parse(pdf_path):
        """
        Append the given PDF path to the global `captured_temp_path` list and then raise a `RuntimeError` to simulate a parser crash.
        
        Parameters:
            pdf_path (pathlib.Path | str): The temporary PDF file path provided to the parser; appended to the global `captured_temp_path` list.
        
        Raises:
            RuntimeError: Always raised with message "Parser crashed".
        """
        captured_temp_path.append(pdf_path)
        raise RuntimeError("Parser crashed")

    with patch("main.run_parse", side_effect=capturing_error_run_parse):
        files = {"file": ("test.pdf", b"%PDF content", "application/pdf")}
        response = client.post("/parse", files=files)

    assert response.status_code == 500
    assert len(captured_temp_path) == 1
    assert not captured_temp_path[0].exists(), (
        "Temp file was not cleaned up after error"
    )


def test_api_parse_missing_file_field():
    """Tests that /parse returns 422 when no file is provided."""
    response = client.post("/parse")
    assert response.status_code == 422


def test_api_build_generic_exception_returns_500():
    """Tests that a generic exception from run_build_from_data results in a 500 Builder Error."""
    with patch("main.run_build_from_data", side_effect=RuntimeError("Builder crashed")):
        response = client.post("/build", json=MOCK_CV_DATA)

        assert response.status_code == 500
        assert "Builder Error: Builder crashed" in response.json()["detail"]


def test_api_build_no_file_created_returns_500():
    """Tests that /build returns 500 'PDF generation failed' when run_build_from_data succeeds but file is absent."""
    # run_build_from_data does nothing (no file created), so output_pdf_path.exists() is False
    with patch("main.run_build_from_data", return_value=None):
        response = client.post("/build", json=MOCK_CV_DATA)

        assert response.status_code == 500
        assert response.json()["detail"] == "PDF generation failed."


def test_api_build_output_path_in_results_dir():
    """
    Verify that POST /build creates a PDF file inside the results/ directory with a .pdf extension.

    Mocks `main.run_build_from_data` to capture and create the produced `output_path`, sends `MOCK_CV_DATA` to `/build`, and asserts a 200 response, exactly one captured path, the path string starts with "results/" and ends with ".pdf".
    """
    captured_paths = []

    def side_effect_capture(data, output_path, photo):
        """
        Capture the provided output path for later inspection and create an empty file at that location for tests.
        
        Parameters:
            data: Input data passed to the builder (unused by this side effect).
            output_path (pathlib.Path): Path where the test output file will be created and appended to the captured list.
            photo: Photo argument passed to the builder (unused by this side effect).
        """
        captured_paths.append(output_path)
        output_path.touch()

    with patch("main.run_build_from_data", side_effect=side_effect_capture):
        response = client.post("/build", json=MOCK_CV_DATA)

    assert response.status_code == 200
    assert len(captured_paths) == 1
    assert str(captured_paths[0]).startswith("results/")
    assert str(captured_paths[0]).endswith(".pdf")


def test_api_build_empty_dict_input():
    """Tests that /build accepts an empty dict without crashing at the API layer."""

    def side_effect_create_file(data, output_path, photo):
        """
        Create an empty file at the given output path.
        
        Parameters:
            data (dict): Input CV data; ignored by this side effect.
            output_path (Path): Filesystem path where an empty file will be created.
            photo: Optional photo input; ignored by this side effect.
        """
        output_path.touch()

    with patch("main.run_build_from_data", side_effect=side_effect_create_file):
        response = client.post("/build", json={})

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"


def test_api_build_http_exception_reraise():
    """Tests that an HTTPException from run_build_from_data is re-raised unchanged (not wrapped in Builder Error)."""
    from fastapi import HTTPException

    def raise_http_403(*args, **kwargs):
        """
        Raise an HTTP 403 Forbidden exception.

        This helper always raises fastapi.HTTPException with status_code=403 and detail "Forbidden".
        """
        raise HTTPException(status_code=403, detail="Forbidden")

    with patch("main.run_build_from_data", side_effect=raise_http_403):
        response = client.post("/build", json=MOCK_CV_DATA)

        assert response.status_code == 403
        assert response.json()["detail"] == "Forbidden"
