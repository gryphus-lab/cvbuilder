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
        Create an empty file at output_path to simulate a generated output file during tests.
        
        Parameters:
            data: The input data for building the file (unused).
            output_path: Path-like object where an empty file will be created.
            photo: Optional photo data passed through to the builder (unused).
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
        Raise an HTTPException with status code 500 and detail "PDF generation failed."
        
        Parameters:
            *args: Ignored.
            **kwargs: Ignored.
        
        Raises:
            fastapi.HTTPException: Always raised with status_code=500 and detail "PDF generation failed."
        """
        raise HTTPException(status_code=500, detail="PDF generation failed.")

    with patch("main.run_build_from_data", side_effect=raise_http_exception):
        response = client.post("/build", json=MOCK_CV_DATA)
        assert response.status_code == 500
        assert response.json()["detail"] == "PDF generation failed."