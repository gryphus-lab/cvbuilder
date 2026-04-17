import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.builder.cv_builder import CVBuilder


@pytest.fixture
def sample_cv_data():
    """Returns a minimal valid CV data structure."""
    return {
        "personal_info": {
            "name": "Jane Doe",
            "title": "Software Architect",
            "address": "Berlin, Germany",
            "phone": "+49 123 456789",
            "email": "jane@example.com",
        },
        "profile": "Passionate developer with 10 years experience.",
        "strategic_impact": ["Modernized legacy stack"],
        "professional_experience": [
            {
                "title": "Lead Engineer",
                "company": "Tech Corp",
                "location": "Berlin",
                "dates": "2020 - Present",
                "description": "Led the platform team.",
                "achievements": ["Reduced latency by 40%"],
            }
        ],
        "certificates_and_training": ["AWS Certified Architect"],
        "education": [{"institution": "TU Berlin", "degree": "M.Sc. CS"}],
        "languages": ["English (Native)", "German (C1)"],
        "competencies_and_skills": {"Development": ["Python", "Rust"]},
        "volunteering": ["Open Source Contributor"],
    }


@pytest.fixture
def builder():
    return CVBuilder()


## --- Unit Tests ---


def test_render_html_contains_data(builder, sample_cv_data):
    """Verify that the Jinja2 template correctly renders the provided dictionary."""
    html = builder._render_html(sample_cv_data)

    # Check for presence of key data points in the HTML string
    assert "Jane Doe" in html
    assert "Software Architect" in html
    assert "Modernized legacy stack" in html
    assert "Reduced latency by 40%" in html
    assert "TU Berlin" in html
    assert "English (Native)" in html


def test_render_html_with_photo(builder, sample_cv_data):
    """Verify photo URL is correctly injected into the template."""
    photo_url = "file:///abs/path/to/photo.jpg"
    html = builder._render_html(sample_cv_data, photo=photo_url)

    assert f'src="{photo_url}"' in html
    assert 'class="photo-img"' in html


## --- Integration Tests (Mocking WeasyPrint) ---


@patch("src.builder.cv_builder.HTML")
def test_build_creates_directory_and_calls_weasyprint(
    mock_html_class, builder, sample_cv_data, tmp_path
):
    """Verify the build process: directory creation and PDF writing."""
    output_file = tmp_path / "subdir" / "my_cv.pdf"

    # Setup mock instance
    mock_html_instance = MagicMock()
    mock_html_class.return_value = mock_html_instance

    builder.build(sample_cv_data, output_file)

    # 1. Check if parent directory was created
    assert output_file.parent.exists()

    # 2. Check if HTML was initialized with some string content
    mock_html_class.assert_called_once()
    _, kwargs = mock_html_class.call_args
    assert "Jane Doe" in kwargs["string"]

    # 3. Check if write_pdf was called with the correct path
    mock_html_instance.write_pdf.assert_called_once_with(str(output_file))


def test_photo_path_resolution(builder, sample_cv_data, tmp_path):
    """Check if a relative photo path is converted to a file:// absolute URL."""
    fake_photo = tmp_path / "me.jpg"
    fake_photo.touch()  # Create empty file

    with patch.object(
        CVBuilder, "_render_html", return_value="<html></html>"
    ) as mock_render:
        with patch("src.builder.cv_builder.HTML"):  # Avoid actual PDF generation
            builder.build(sample_cv_data, tmp_path / "out.pdf", photo_path=fake_photo)

            # Get the second argument (photo) passed to _render_html
            called_photo_url = mock_render.call_args[0][1]
            assert called_photo_url.startswith("file://")
            assert str(fake_photo.resolve()) in called_photo_url
