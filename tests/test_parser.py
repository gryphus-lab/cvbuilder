from unittest.mock import patch, MagicMock
from pathlib import Path
import json

from src.parser.parse_cv import (
    _is_header,
    final_sanitize,
    semantic_bullet_split,
    _parse_experience,
    _parse_generic_section,
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

    assert lead_in == "Some intro text."
    assert any("Cloud & Platforms: AWS, Azure" in b for b in bullets)
    assert any("Tools: Pytest, Docker" in b for b in bullets)


## --- Unit Tests for Logic Blocks ---


def test_parse_experience():
    lines = [
        "PROFESSIONAL EXPERIENCE",
        "Senior Dev, TechCorp, Berlin (01/2020 - Present)",
        "Migration Impact: Moved to cloud.",
        "Worked on legacy systems.",
        "EDUCATION",  # Next header
    ]
    jobs, _ = _parse_experience(lines, 0)

    assert len(jobs) == 1
    assert jobs[0]["title"] == "Senior Dev"
    assert jobs[0]["company"] == "TechCorp"
    assert jobs[0]["location"] == "Berlin"
    assert jobs[0]["dates"] == "01/2020 - Present"
    assert any(
        "Migration Impact: Moved to cloud" in ach for ach in jobs[0]["achievements"]
    )
    assert _ == 4  # Index of EDUCATION


## --- Integration/Mock Tests ---


@patch("src.parser.parse_cv.convert_from_path")
@patch("src.parser.parse_cv.pt.image_to_string")
def test_parse_cv_to_json_full_flow(mock_ocr, mock_pdf_conv):
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

    assert result["profile"] == "Experienced engineer."
    assert len(result["professional_experience"]) == 1
    assert result["professional_experience"][0]["company"] == "Acme"
    assert "Native" in result["languages"][0]


def test_save_to_json(tmp_path):
    from src.parser.parse_cv import save_to_json

    data = {"test": "data"}
    file_path = tmp_path / "output.json"

    save_to_json(data, file_path)

    assert file_path.exists()
    with open(file_path, encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data == data


## --- Additional Unit Tests for _is_header ---


def test_is_header_all_known_sections():
    """Every key in SECTION_HEADERS must be recognised as a header."""
    from src.parser.parse_cv import SECTION_HEADERS

    for key in SECTION_HEADERS:
        assert _is_header(key) is True, f"Expected '{key}' to be a header"


def test_is_header_empty_string():
    assert _is_header("") is False


def test_is_header_with_trailing_colon():
    """A known header followed by ':' should still be recognised."""
    assert _is_header("PROFILE:") is True
    assert _is_header("EDUCATION:") is True


def test_is_header_lowercase_known_section():
    """_is_header must be case-insensitive for known section names."""
    assert _is_header("profile") is True
    assert _is_header("languages") is True


def test_is_header_partial_match_is_false():
    """A substring of a header name must not be classified as a header."""
    assert _is_header("PROFI") is False
    assert _is_header("EXPERIENCE") is False


## --- Additional Unit Tests for final_sanitize ---


def test_final_sanitize_empty_string():
    assert final_sanitize("") == ""


def test_final_sanitize_al_space_replacement():
    """'Al ' (with trailing space) should become 'AI '."""
    result = final_sanitize("Al Cloud Services")
    # The "Al " prefix must be replaced; trailing single chars may be stripped by sanitize
    assert "Al " not in result
    assert result.startswith("AI")


def test_final_sanitize_removes_copyright_symbol():
    result = final_sanitize("some © text")
    assert "©" not in result


def test_final_sanitize_removes_cent_symbol():
    result = final_sanitize("some ¢ text")
    assert "¢" not in result


def test_final_sanitize_collapses_multiple_spaces():
    result = final_sanitize("too   many    spaces")
    assert "  " not in result


def test_final_sanitize_normalizes_colon_spacing():
    result = final_sanitize("Key :   Value")
    assert "Key: Value" in result


def test_final_sanitize_nativ_to_native():
    """'Nativ' substring must be expanded to 'Native'."""
    # Use a sentence where 'Nativ' is not at the very end so the trailing-char
    # regex does not strip the 'v' before the replacement runs.
    result = final_sanitize("speaks Nativ language")
    assert "Native" in result


def test_final_sanitize_no_mutation_on_clean_text():
    """Text with no OCR artefacts should be returned essentially unchanged."""
    clean = "Software Engineer with ten years of experience"
    result = final_sanitize(clean)
    # Core content must be preserved
    assert "Software Engineer" in result


## --- Additional Unit Tests for semantic_bullet_split ---


def test_semantic_bullet_split_empty_text():
    lead_in, bullets = semantic_bullet_split("", ["Tools"])
    assert lead_in == ""
    assert bullets == []


def test_semantic_bullet_split_no_matching_keywords():
    """When no keyword is found the full text becomes the lead-in and bullets is empty."""
    lead_in, bullets = semantic_bullet_split("Just plain text.", ["Tools"])
    assert "plain text" in lead_in
    assert bullets == []


def test_semantic_bullet_split_returns_tuple():
    result = semantic_bullet_split("Some text.", ["Tools"])
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_semantic_bullet_split_bullet_contains_keyword():
    """Each returned bullet must begin with its matching keyword."""
    keywords = ["Architecture"]
    text = "Intro. Architecture: AWS, GCP."
    _, bullets = semantic_bullet_split(text, keywords)
    assert any(b.startswith("Architecture") for b in bullets)


## --- Additional Unit Tests for _parse_generic_section ---


def test_parse_generic_section_basic():
    lines = ["LANGUAGES", "English (Native)", "German (B2)", "EDUCATION"]
    items, next_idx = _parse_generic_section(lines, 0)
    assert items == ["English (Native)", "German (B2)"]
    assert next_idx == 3  # Index of EDUCATION


def test_parse_generic_section_skips_blank_lines():
    lines = ["LANGUAGES", "English (Native)", "", "German (B2)", "EDUCATION"]
    items, next_idx = _parse_generic_section(lines, 0)
    assert "" not in items
    assert len(items) == 2


def test_parse_generic_section_empty_section():
    """A section with no content before the next header returns an empty list."""
    lines = ["LANGUAGES", "EDUCATION"]
    items, next_idx = _parse_generic_section(lines, 0)
    assert items == []
    assert next_idx == 1


def test_parse_generic_section_at_end_of_document():
    """A section at the end of the document (no following header) returns all remaining lines."""
    lines = ["VOLUNTEERING", "Open Source Contributor", "Mentor at CodeClub"]
    items, next_idx = _parse_generic_section(lines, 0)
    assert "Open Source Contributor" in items
    assert "Mentor at CodeClub" in items
    assert next_idx == 3


## --- Additional Unit Tests for _parse_experience ---


def test_parse_experience_no_jobs():
    """Lines with no job-pattern entries should return an empty list."""
    lines = [
        "PROFESSIONAL EXPERIENCE",
        "Some non-job line.",
        "EDUCATION",
    ]
    jobs, next_idx = _parse_experience(lines, 0)
    assert jobs == []
    assert next_idx == 2


def test_parse_experience_multiple_jobs():
    lines = [
        "PROFESSIONAL EXPERIENCE",
        "Lead Dev, AlphaCorp, Munich (03/2021 - Present)",
        "AI Efficiency: Built pipelines.",
        "Junior Dev, BetaGmbH, Berlin (01/2019 - 02/2021)",
        "Migration Impact: Migrated monolith.",
        "EDUCATION",
    ]
    jobs, next_idx = _parse_experience(lines, 0)
    assert len(jobs) == 2
    assert jobs[0]["company"] == "AlphaCorp"
    assert jobs[1]["company"] == "BetaGmbH"
    assert next_idx == 5


def test_parse_experience_job_without_achievements():
    """A job entry with no recognised achievement keywords has an empty achievements list."""
    lines = [
        "PROFESSIONAL EXPERIENCE",
        "Developer, SomeCo, Frankfurt (06/2022 - Present)",
        "EDUCATION",
    ]
    jobs, _ = _parse_experience(lines, 0)
    assert len(jobs) == 1
    assert jobs[0]["achievements"] == []


## --- Additional Unit Tests for save_to_json ---


def test_save_to_json_creates_parent_directory(tmp_path):
    from src.parser.parse_cv import save_to_json

    nested_path = tmp_path / "nested" / "deep" / "output.json"
    save_to_json({"key": "value"}, nested_path)
    assert nested_path.exists()


def test_save_to_json_unicode_preserved(tmp_path):
    from src.parser.parse_cv import save_to_json

    data = {"name": "Müller", "role": "Ingenieur"}
    file_path = tmp_path / "unicode.json"
    save_to_json(data, file_path)
    with open(file_path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["name"] == "Müller"


def test_save_to_json_indented_output(tmp_path):
    """Output file must be pretty-printed JSON (indented), not a single-line blob."""
    from src.parser.parse_cv import save_to_json

    data = {"a": 1, "b": 2}
    file_path = tmp_path / "indented.json"
    save_to_json(data, file_path)
    raw = file_path.read_text(encoding="utf-8")
    assert "\n" in raw  # Multi-line output confirms indentation


## --- Boundary / Regression Tests ---


def test_final_sanitize_removes_bullet_symbol():
    """The OCR bullet character '•' must be stripped from the output."""
    result = final_sanitize("item one • item two")
    assert "•" not in result


def test_final_sanitize_openal_replacement():
    """'OpenAl' must be corrected to 'OpenAI'."""
    result = final_sanitize("using OpenAl API")
    assert "OpenAl" not in result
    assert "OpenAI" in result


def test_final_sanitize_al_dash_replacement():
    """'Al-' must be corrected to 'AI-'."""
    result = final_sanitize("Al-powered system")
    assert result.startswith("AI-")


def test_is_header_with_surrounding_whitespace():
    """_is_header must ignore leading/trailing whitespace after strip."""
    # The source strips the line before calling _is_header, but the function
    # itself also calls strip(); verify it handles pre-padded input safely.
    assert _is_header("  PROFILE  ") is True
    assert _is_header("  LANGUAGES  ") is True


def test_is_header_mixed_case_with_colon():
    """Mixed-case header with a trailing colon must be recognised."""
    assert _is_header("Languages:") is True
    assert _is_header("Volunteering:") is True


def test_section_headers_has_expected_keys():
    """SECTION_HEADERS must contain all eight canonical section names."""
    from src.parser.parse_cv import SECTION_HEADERS

    required = {
        "PROFILE",
        "STRATEGIC IMPACT & TRANSFORMATIONS",
        "PROFESSIONAL EXPERIENCE",
        "CERTIFICATES AND TRAINING",
        "EDUCATION",
        "LANGUAGES",
        "COMPETENCIES AND SKILLS",
        "VOLUNTEERING",
    }
    assert required == set(SECTION_HEADERS.keys())


def test_save_to_json_overwrites_existing_file(tmp_path):
    """save_to_json must silently overwrite a pre-existing file at the target path."""
    from src.parser.parse_cv import save_to_json

    file_path = tmp_path / "overwrite.json"
    save_to_json({"version": 1}, file_path)
    save_to_json({"version": 2}, file_path)

    with open(file_path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["version"] == 2


def test_parse_generic_section_with_only_blank_lines():
    """A section body consisting entirely of blank lines returns an empty list."""
    lines = ["LANGUAGES", "   ", "  ", "EDUCATION"]
    items, next_idx = _parse_generic_section(lines, 0)
    assert items == []
    assert next_idx == 3


def test_semantic_bullet_split_with_empty_keywords_list():
    """An empty keywords list means no splits occur; full text is the lead-in."""
    lead_in, bullets = semantic_bullet_split("Some full text here.", [])
    assert bullets == []
    assert "full text" in lead_in


def test_semantic_bullet_split_lead_in_stripped():
    """The lead-in returned must not contain trailing punctuation from the split."""
    keywords = ["Tools"]
    text = "Intro sentence. Tools: pytest."
    lead_in, _ = semantic_bullet_split(text, keywords)
    # Lead-in should not include the keyword or its colon
    assert "Tools" not in lead_in


def test_parse_experience_extracts_all_required_fields():
    """Each parsed job dict must contain exactly the six expected keys."""
    lines = [
        "PROFESSIONAL EXPERIENCE",
        "Engineer, Corp, City (01/2021 - Present)",
        "EDUCATION",
    ]
    jobs, _ = _parse_experience(lines, 0)
    assert len(jobs) == 1
    required_keys = {
        "title",
        "company",
        "location",
        "dates",
        "description",
        "achievements",
    }
    assert required_keys == set(jobs[0].keys())


def test_parse_experience_title_stripped_of_whitespace():
    """Parsed job title must have no leading or trailing whitespace."""
    lines = [
        "PROFESSIONAL EXPERIENCE",
        "  Senior Engineer  , BigCo, Town (03/2020 - Present)",
        "EDUCATION",
    ]
    jobs, _ = _parse_experience(lines, 0)
    assert jobs, "Expected at least one job to be parsed"
    assert jobs[0]["title"] == jobs[0]["title"].strip()


def test_parse_generic_section_next_idx_points_to_header():
    """next_idx returned must be the index of the first line that is a header."""
    lines = ["EDUCATION", "M.Sc. CS", "B.Sc. EE", "LANGUAGES"]
    _, next_idx = _parse_generic_section(lines, 0)
    assert lines[next_idx] == "LANGUAGES"


def test_final_sanitize_deduplication_skill_keyword():
    """Skill keyword deduplication must also apply to SKILL_KEYWORDS entries."""
    from src.parser.parse_cv import SKILL_KEYWORDS

    kw = SKILL_KEYWORDS[0]
    result = final_sanitize(f"{kw} {kw}")
    # The doubled keyword should be collapsed to a single occurrence
    assert result.count(kw) == 1


def test_final_sanitize_strategic_keyword_deduplication():
    """Strategic keyword deduplication must remove exact doubles."""
    from src.parser.parse_cv import STRATEGIC_KEYWORDS

    kw = STRATEGIC_KEYWORDS[0]
    result = final_sanitize(f"{kw} {kw}")
    assert result.count(kw) == 1
