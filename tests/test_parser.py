from unittest.mock import patch, MagicMock
from pathlib import Path
import json

from src.parser.parse_cv import (
    _is_header,
    final_sanitize,
    semantic_bullet_split,
    _parse_experience,
    parse_cv_to_json,
)

## --- Unit Tests for Utility Functions ---


def test_is_header():
    assert _is_header("PROFESSIONAL EXPERIENCE") is True
    assert _is_header("profile:") is True
    assert _is_header("Education") is True
    assert _is_header("Random Text") is False


def test_final_sanitize():
    input_text = "Al- Efficiency ii and OpenAl •"
    # Expected: ii -> ü, Al- -> AI-, OpenAl -> OpenAI, • removed, extra space handled
    expected = "AI- Efficiency ü and OpenAI"
    assert final_sanitize(input_text) == expected


def test_final_sanitize_deduplication():
    # Test keyword deduplication logic
    input_text = "Modernization Modernization results"
    assert final_sanitize(input_text) == "Modernization results"


def test_semantic_bullet_split():
    keywords = ["Cloud & Platforms", "Tools"]
    text = "Some intro text. Cloud & Platforms: AWS, Azure. Tools: Pytest, Docker."

    lead_in, bullets = semantic_bullet_split(text, keywords)

    assert lead_in == "Some intro text"
    assert "Cloud & Platforms: AWS, Azure" in bullets
    assert "Tools: Pytest, Docker" in bullets


## --- Unit Tests for Logic Blocks ---


def test_parse_experience():
    lines = [
        "PROFESSIONAL EXPERIENCE",
        "Senior Dev, TechCorp, Berlin (01/2020 - Present)",
        "Migration Impact: Moved to cloud.",
        "Worked on legacy systems.",
        "EDUCATION",  # Next header
    ]
    jobs, next_idx = _parse_experience(lines, 0)

    assert len(jobs) == 1
    assert jobs[0]["title"] == "Senior Dev"
    assert jobs[0]["company"] == "TechCorp"
    assert jobs[0]["location"] == "Berlin"
    assert jobs[0]["dates"] == "01/2020 - Present"
    assert "Migration Impact: Moved to cloud" in jobs[0]["achievements"]
    assert next_idx == 4  # Index of EDUCATION


## --- Integration/Mock Tests ---


@patch("src.parser.parse_cv.convert_from_path")
@patch("src.parser.parse_cv .image_to_string")
def test_parse_cv_to_json_full_flow(mock_ocr, mock_pdf_conv, tmp_path):
    # Setup Mock OCR output
    mock_ocr.return_value = (
        "PROFILE\n"
        "Experienced engineer.\n"
        "PROFESSIONAL EXPERIENCE\n"
        "Lead, Acme, London (2022-2023)\n"
        "AI Efficiency: Optimized models.\n"
        "LANGUAGES\n"
        "English (Native)\n"
    )
    mock_pdf_conv.return_value = [MagicMock()]  # Mock one page

    # We need to mock Path.write_text to avoid writing real debug files
    with patch("src.parser.parse_cv.Path.write_text"):
        result = parse_cv_to_json("dummy.pdf")

    assert result["profile"] == "Experienced engineer"
    assert len(result["professional_experience"]) == 1
    assert result["professional_experience"][0]["company"] == "Acme"
    assert "Native" in result["languages"][0]


def test_save_to_json(tmp_path):
    from src.parser.parse_cv import save_to_json

    data = {"test": "data"}
    file_path = tmp_path / "output.json"

    save_to_json(data, file_path)

    assert file_path.exists()
    with open(file_path, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data == data
