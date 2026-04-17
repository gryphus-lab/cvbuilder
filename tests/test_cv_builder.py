import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.builder.cv_builder import CVBuilder


@pytest.fixture
def sample_cv_data():
    """
    Return a minimal, valid CV data dictionary used by tests.
    
    The dictionary includes these top-level keys: personal_info, profile, strategic_impact,
    professional_experience, certificates_and_training, education, languages,
    competencies_and_skills, and volunteering.
    
    Returns:
        dict: Sample CV data matching the test-suite layout, containing placeholder
        values for personal information and minimal entries for each section.
    """
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
    """
    Provide a reusable CVBuilder instance for tests.

    Returns:
        CVBuilder: A new CVBuilder instance.
    """
    return CVBuilder()


@pytest.fixture
def minimal_cv_payload():
    """
    Provide a minimal CV data dictionary with empty sections.

    This fixture is useful for boundary/regression tests that need a bare-minimum
    CV structure without extensive content. Tests should copy() or deepcopy() the
    returned dict if they need to modify it.

    Returns:
        dict: A minimal CV data structure with all required keys but minimal content.
    """
    return {
        "personal_info": {
            "name": "A",
            "title": "B",
            "address": "C",
            "phone": "D",
            "email": "e@f.g",
        },
        "profile": "Profile text",
        "strategic_impact": [],
        "professional_experience": [],
        "certificates_and_training": [],
        "education": [],
        "languages": [],
        "competencies_and_skills": {},
        "volunteering": [],
    }


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


def test_photo_path_resolution(builder, sample_cv_data, tmp_path, monkeypatch):
    """Check if a relative photo path is converted to a file:// absolute URL."""
    fake_photo = tmp_path / "me.jpg"
    fake_photo.touch()  # Create empty file

    # Change to tmp_path so the relative path is resolved from there
    monkeypatch.chdir(tmp_path)

    with (
        patch.object(
            CVBuilder, "_render_html", return_value="<html></html>"
        ) as mock_render,
        patch("src.builder.cv_builder.HTML"),
    ):  # Avoid actual PDF generation
        builder.build(sample_cv_data, tmp_path / "out.pdf", photo_path="me.jpg")

        # Get the second argument (photo) passed to _render_html
        called_photo_url = mock_render.call_args[0][1]
        assert called_photo_url == fake_photo.resolve().as_uri()


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
    """
    Verify that the rendered HTML output is a complete HTML document including DOCTYPE and HTML tags.
    """
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
    assert kwargs["base_url"] == str(Path.cwd())


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


## --- Boundary / Regression Tests ---


def test_cv_builder_constructor_requires_no_arguments():
    """CVBuilder must be instantiable with no arguments."""
    instance = CVBuilder()
    assert isinstance(instance, CVBuilder)


def test_render_html_empty_strategic_impact(builder, minimal_cv_payload):
    """Rendering with an empty strategic_impact list must not raise."""
    data = minimal_cv_payload.copy()
    html = builder._render_html(data)
    assert isinstance(html, str)
    assert "STRATEGIC IMPACT" in html


def test_render_html_empty_professional_experience(builder, minimal_cv_payload):
    """An empty professional_experience list must render without error."""
    data = minimal_cv_payload.copy()
    data["profile"] = ""
    html = builder._render_html(data)
    assert "PROFESSIONAL EXPERIENCE" in html


def test_render_html_job_with_empty_description(builder, sample_cv_data):
    """A job entry with an empty description field must not raise and must still render."""
    sample_cv_data["professional_experience"][0]["description"] = ""
    html = builder._render_html(sample_cv_data)
    assert "Lead Engineer" in html


def test_render_html_job_with_empty_achievements(builder, sample_cv_data):
    """A job entry with no achievements must not inject stray list items."""
    sample_cv_data["professional_experience"][0]["achievements"] = []
    html = builder._render_html(sample_cv_data)
    assert "Lead Engineer" in html
    assert "Reduced latency" not in html


def test_render_html_multiple_competency_categories(builder, sample_cv_data):
    """All category names and their skills appear when there are multiple categories."""
    sample_cv_data["competencies_and_skills"] = {
        "Development": ["Python", "Rust"],
        "DevSecOps": ["Docker", "Terraform"],
    }
    html = builder._render_html(sample_cv_data)
    assert "Development" in html
    assert "DevSecOps" in html
    assert "Docker" in html
    assert "Terraform" in html


def test_render_html_multiple_languages(builder, sample_cv_data):
    """All language entries appear when multiple languages are present."""
    sample_cv_data["languages"] = ["English (Native)", "German (C1)", "French (B2)"]
    html = builder._render_html(sample_cv_data)
    assert "French (B2)" in html


def test_render_html_multiple_education_entries(builder, sample_cv_data):
    """Multiple education entries must all appear in the rendered HTML."""
    sample_cv_data["education"].append({"institution": "MIT", "degree": "B.Sc. EE"})
    html = builder._render_html(sample_cv_data)
    assert "TU Berlin" in html
    assert "MIT" in html
    assert "B.Sc. EE" in html


def test_render_html_photo_none_omits_img(builder, sample_cv_data):
    """Calling _render_html with photo=None (default '') must suppress the photo element."""
    html = builder._render_html(sample_cv_data, photo=None)
    assert "<img" not in html


@patch("src.builder.cv_builder.HTML")
def test_build_success_prints_output_path(
    mock_html_class, builder, sample_cv_data, tmp_path, capsys
):
    """build() must print a success message that includes the output path."""
    output_file = tmp_path / "cv.pdf"
    mock_html_class.return_value = MagicMock()

    builder.build(sample_cv_data, output_file)

    captured = capsys.readouterr()
    assert str(output_file.resolve()) in captured.out


@patch("src.builder.cv_builder.HTML")
def test_build_photo_path_as_string(mock_html_class, builder, sample_cv_data, tmp_path):
    """photo_path supplied as a plain string must be resolved to a file:// URL."""
    fake_photo = tmp_path / "headshot.png"
    fake_photo.touch()
    output_file = tmp_path / "cv.pdf"
    mock_html_instance = MagicMock()
    mock_html_class.return_value = mock_html_instance

    with patch.object(
        CVBuilder, "_render_html", return_value="<html></html>"
    ) as mock_render:
        builder.build(sample_cv_data, output_file, photo_path=str(fake_photo))
        called_photo_url = mock_render.call_args[0][1]
        assert called_photo_url == fake_photo.resolve().as_uri()


@patch("src.builder.cv_builder.HTML")
def test_build_write_pdf_called_with_string_version_of_path_object(
    mock_html_class, builder, sample_cv_data, tmp_path
):
    """write_pdf must always receive a str, not a Path object."""
    output_file = tmp_path / "cv.pdf"
    mock_html_instance = MagicMock()
    mock_html_class.return_value = mock_html_instance

    builder.build(sample_cv_data, output_file)

    args, _ = mock_html_instance.write_pdf.call_args
    assert isinstance(args[0], str)
