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


## --- Additional Unit Tests ---


def test_render_html_without_photo_omits_img_tag(builder, sample_cv_data):
    """When no photo is provided the photo block must be absent from the HTML."""
    html = builder._render_html(sample_cv_data)
    assert 'class="photo-img"' not in html
    assert "<img" not in html


def test_render_html_contains_certificate(builder, sample_cv_data):
    """Certificate entries must appear in the rendered HTML."""
    html = builder._render_html(sample_cv_data)
    assert "AWS Certified Architect" in html


def test_render_html_contains_competencies(builder, sample_cv_data):
    """Competency category names and skills must appear in the rendered HTML."""
    html = builder._render_html(sample_cv_data)
    assert "Development" in html
    assert "Python" in html
    assert "Rust" in html


def test_render_html_contains_volunteering(builder, sample_cv_data):
    """Volunteering entries must appear in the rendered HTML."""
    html = builder._render_html(sample_cv_data)
    assert "Open Source Contributor" in html


def test_render_html_contains_contact_info(builder, sample_cv_data):
    """Personal contact details must appear in the rendered HTML."""
    html = builder._render_html(sample_cv_data)
    assert "jane@example.com" in html
    assert "+49 123 456789" in html
    assert "Berlin, Germany" in html


def test_render_html_multiple_jobs(builder, sample_cv_data):
    """All professional experience entries must appear when the list has multiple items."""
    sample_cv_data["professional_experience"].append(
        {
            "title": "Junior Dev",
            "company": "StartupAG",
            "location": "Hamburg",
            "dates": "2018 - 2020",
            "description": "",
            "achievements": ["Built MVP in 3 months"],
        }
    )
    html = builder._render_html(sample_cv_data)
    assert "Lead Engineer" in html
    assert "Junior Dev" in html
    assert "StartupAG" in html
    assert "Built MVP in 3 months" in html


def test_render_html_returns_string(builder, sample_cv_data):
    """_render_html must return a str object."""
    result = builder._render_html(sample_cv_data)
    assert isinstance(result, str)


def test_render_html_is_valid_html_document(builder, sample_cv_data):
    """Output must be a complete HTML document with doctype and html tags."""
    html = builder._render_html(sample_cv_data)
    assert "<!DOCTYPE html>" in html
    assert "<html>" in html
    assert "</html>" in html


def test_render_html_photo_empty_string_omits_img(builder, sample_cv_data):
    """Explicitly passing photo='' must still suppress the photo block."""
    html = builder._render_html(sample_cv_data, photo="")
    assert "<img" not in html


## --- Additional Integration Tests ---


@patch("src.builder.cv_builder.HTML")
def test_build_without_photo_passes_empty_photo_url(
    mock_html_class, builder, sample_cv_data, tmp_path
):
    """When photo_path is None the rendered HTML must not contain a photo img tag."""
    output_file = tmp_path / "cv.pdf"
    mock_html_instance = MagicMock()
    mock_html_class.return_value = mock_html_instance

    builder.build(sample_cv_data, output_file)

    _, kwargs = mock_html_class.call_args
    assert "<img" not in kwargs["string"]


@patch("src.builder.cv_builder.HTML")
def test_build_with_existing_output_directory_does_not_raise(
    mock_html_class, builder, sample_cv_data, tmp_path
):
    """build() must not raise an error when the output directory already exists."""
    output_file = tmp_path / "cv.pdf"
    mock_html_instance = MagicMock()
    mock_html_class.return_value = mock_html_instance

    # Call twice: second call must succeed even though directory already exists
    builder.build(sample_cv_data, output_file)
    builder.build(sample_cv_data, output_file)

    assert mock_html_instance.write_pdf.call_count == 2


@patch("src.builder.cv_builder.HTML")
def test_build_passes_base_url_to_weasyprint(
    mock_html_class, builder, sample_cv_data, tmp_path
):
    """build() must supply a base_url keyword argument to the HTML constructor."""
    output_file = tmp_path / "cv.pdf"
    mock_html_instance = MagicMock()
    mock_html_class.return_value = mock_html_instance

    builder.build(sample_cv_data, output_file)

    _, kwargs = mock_html_class.call_args
    assert "base_url" in kwargs


@patch("src.builder.cv_builder.HTML")
def test_build_output_path_accepts_string(
    mock_html_class, builder, sample_cv_data, tmp_path
):
    """build() must accept a plain string as the output_pdf argument."""
    output_file = str(tmp_path / "cv_string_path.pdf")
    mock_html_instance = MagicMock()
    mock_html_class.return_value = mock_html_instance

    builder.build(sample_cv_data, output_file)

    mock_html_instance.write_pdf.assert_called_once_with(output_file)