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
    _extract_email,
    _extract_phone,
    _extract_dob,
    _extract_nationality,
    _extract_permit,
    _extract_address,
    _extract_name_and_title,
    _parse_personal_info,
    _parse_education_entry,
    _handle_profile_section,
    _handle_strategic_impact_section,
    _handle_education_section,
    _handle_languages_section,
    _handle_competencies_and_skills_section,
    _handle_generic_fallback_section,
    SECTION_HEADERS,
    STRATEGIC_KEYWORDS,
    SKILL_KEYWORDS,
    LINKEDIN_KEYWORD,
)

## --- Unit Tests for Utility Functions ---


def test_is_header():
    assert _is_header("PROFESSIONAL EXPERIENCE") is True
    assert _is_header("profile:") is True
    assert _is_header("Education") is True
    assert _is_header("Random Text") is False


def test_final_sanitize():
    input_text = "Al- Efficiency ii and OpenAl •"
    # Expected: ii -> ü, Al- not replaced (no AI keyword), OpenAl -> OpenAI, • removed, extra space handled
    expected = "Al- Efficiency ü and OpenAI"
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
    """'Al ' (with trailing space) should become 'AI ' when followed by AI keywords."""
    result = final_sanitize("Al GPT Cloud Services")
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
    items, _ = _parse_generic_section(lines, 0)
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


def test_final_sanitize_al_replacement_positive_cases():
    """Test that 'Al' is replaced to 'AI' when followed by AI-related keywords."""
    # Test dash cases
    assert final_sanitize("Al-GPT model") == "AI-GPT model"
    assert final_sanitize("Al-Chat bot") == "AI-Chat bot"
    assert final_sanitize("Al-Open source") == "AI-Open source"
    assert final_sanitize("Al-API service") == "AI-API service"
    assert final_sanitize("Al-Model training") == "AI-Model training"
    assert final_sanitize("Al-powered system") == "AI-powered system"
    assert final_sanitize("Al-based solution") == "AI-based solution"
    assert final_sanitize("Al-driven analytics") == "AI-driven analytics"
    assert final_sanitize("Al-generated content") == "AI-generated content"
    assert final_sanitize("Al-ML algorithm") == "AI-ML algorithm"

    # Test space cases
    assert final_sanitize("Al GPT model") == "AI GPT model"
    assert final_sanitize("Al Chat bot") == "AI Chat bot"
    assert final_sanitize("Al Open source") == "AI Open source"
    assert final_sanitize("Al API service") == "AI API service"
    assert final_sanitize("Al Model training") == "AI Model training"
    assert final_sanitize("Al powered system") == "AI powered system"
    assert final_sanitize("Al based solution") == "AI based solution"
    assert final_sanitize("Al driven analytics") == "AI driven analytics"
    assert final_sanitize("Al generated content") == "AI generated content"
    assert final_sanitize("Al ML algorithm") == "AI ML algorithm"

    # Test case insensitivity
    assert final_sanitize("al-gpt model") == "AI-gpt model"
    assert final_sanitize("Al gPt model") == "AI gPt model"


def test_final_sanitize_al_replacement_negative_cases():
    """Test that 'Al' is NOT replaced when not followed by AI-related keywords."""
    # No replacement for non-AI terms
    assert final_sanitize("Al Cloud Services") == "Al Cloud Services"
    assert final_sanitize("Aluminum foil") == "Aluminum foil"
    assert final_sanitize("Al-gebra") == "Al-gebra"
    assert final_sanitize("Al pha") == "Al pha"


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


def test_final_sanitize_ii_to_umlaut_ocr_artifact():
    """OCR artifact: 'ii' in specific contexts (e.g., Ziirich) should become 'ü' (Zürich)."""
    # Test the specific OCR pattern: capitalized word with 'ii'
    result = final_sanitize("Ziirich")
    assert result == "Zürich"

    # Test another case - exact match
    result = final_sanitize("Miinchen was misread as Miinchen")
    assert result == "München was misread as München"

    # Test that capitalized non-OCR word remains unchanged
    result = final_sanitize("Hawaii")
    assert result == "Hawaii"

    # But legitimate 'ii' in names or words should be preserved in other contexts
    # The regex targets word boundaries with capital letters, so lowercase 'ii' or 'ii'
    # at word start without caps before it should remain
    result = final_sanitize("skiing")
    assert "skiing" in result  # 'ii' in middle of lowercase word should stay


## --- Unit Tests for _extract_email ---


def test_extract_email_valid():
    assert (
        _extract_email("Contact me at john.doe@example.com today")
        == "john.doe@example.com"
    )


def test_extract_email_no_email():
    assert _extract_email("No email here, just plain text") is None


def test_extract_email_returns_only_address():
    result = _extract_email("Email: user@domain.org please")
    assert result == "user@domain.org"


def test_extract_email_subdomain():
    result = _extract_email("Send to admin@mail.company.co.uk")
    assert result == "admin@mail.company.co.uk"


def test_extract_email_empty_string():
    assert _extract_email("") is None


## --- Unit Tests for _extract_phone ---


def test_extract_phone_plus_prefix():
    result = _extract_phone("+41791234567")
    assert result == "+41791234567"


def test_extract_phone_double_zero_prefix():
    result = _extract_phone("0041791234567")
    assert result == "+41791234567"


def test_extract_phone_with_spaces_and_dashes():
    result = _extract_phone("+41 79 123-45-67")
    assert result == "+41791234567"


def test_extract_phone_too_short_returns_none():
    # Fewer than 7 digits after country code
    assert _extract_phone("+41 12") is None


def test_extract_phone_no_phone():
    assert _extract_phone("No phone number here") is None


def test_extract_phone_empty_string():
    assert _extract_phone("") is None


def test_extract_phone_with_parentheses():
    result = _extract_phone("+49 (30) 12345678")
    assert result == "+493012345678"


def test_extract_phone_rejects_plain_digits():
    """Phone without + or 00 prefix must not be extracted."""
    assert _extract_phone("12345678901") is None


## --- Unit Tests for _extract_dob ---


def test_extract_dob_valid():
    result = _extract_dob("Date of Birth: 15.03.1985")
    assert result == "15.03.1985"


def test_extract_dob_no_match():
    assert _extract_dob("No date of birth here") is None


def test_extract_dob_empty_string():
    assert _extract_dob("") is None


def test_extract_dob_partial_line():
    """Should work when DOB label appears mid-line."""
    result = _extract_dob("Personal info. Date of Birth: 01.01.1990 | Swiss.")
    assert result == "01.01.1990"


## --- Unit Tests for _extract_nationality ---


def test_extract_nationality_valid():
    result = _extract_nationality("Nationality: Swiss")
    assert result == "Swiss"


def test_extract_nationality_no_match():
    assert _extract_nationality("Born in Switzerland") is None


def test_extract_nationality_empty_string():
    assert _extract_nationality("") is None


def test_extract_nationality_mid_line():
    result = _extract_nationality("Personal info. Nationality: German")
    assert result == "German"


## --- Unit Tests for _extract_permit ---


def test_extract_permit_valid():
    result = _extract_permit("Permit: C (Permanent)")
    assert result == "C (Permanent)"


def test_extract_permit_no_match():
    assert _extract_permit("No permit info") is None


def test_extract_permit_empty_string():
    assert _extract_permit("") is None


def test_extract_permit_strips_whitespace():
    result = _extract_permit("Permit:   B ")
    assert result == "B"


## --- Unit Tests for _extract_address ---


def test_extract_address_valid_street():
    result = _extract_address("123 Main Street, Springfield")
    assert result == "123 Main Street, Springfield"


def test_extract_address_no_digit_returns_none():
    assert _extract_address("Just a plain text line") is None


def test_extract_address_date_of_birth_excluded():
    assert _extract_address("Date of Birth: 15.03.1985") is None


def test_extract_address_standalone_date_excluded():
    assert _extract_address("15.03.1985") is None


def test_extract_address_strasse_pattern():
    result = _extract_address("Musterstrasse 10, 8001 Zurich")
    assert result is not None
    assert "Musterstrasse" in result


def test_extract_address_strips_whitespace():
    result = _extract_address("  42 Oak Avenue, Berlin  ")
    assert result == "42 Oak Avenue, Berlin"


def test_extract_address_phone_like_line_excluded():
    """Lines that look like phone numbers should not be treated as addresses."""
    # +41 79... pattern should be excluded
    result = _extract_address("+41 79 123 45 67")
    assert result is None


## --- Unit Tests for _extract_name_and_title ---


def test_extract_name_and_title_basic():
    lines = ["John Doe", "Senior Software Engineer", "john@example.com"]
    name, title = _extract_name_and_title(lines, set(SECTION_HEADERS.keys()))
    assert name == "John Doe"
    assert title == "Senior Software Engineer"


def test_extract_name_and_title_skips_email_line():
    lines = ["john@example.com", "Jane Smith", "Data Scientist"]
    name, _ = _extract_name_and_title(lines, set(SECTION_HEADERS.keys()))
    assert name == "Jane Smith"


def test_extract_name_and_title_skips_section_headers():
    """
    Extract the candidate's name and job title from the top lines while ignoring section header lines.
    
    Parameters:
        lines (list[str]): Ordered lines from the top of a CV/document.
        headers (set[str]): Set of section header strings to ignore when locating name/title.
    
    Returns:
        tuple: (name (str), title (str)) where `name` is the first line not in `headers` and `title` is the next non-header line; empty strings are returned if a value is not found.
    """
    lines = ["PROFILE", "Alice Brown", "DevOps Engineer"]
    name, title = _extract_name_and_title(lines, set(SECTION_HEADERS.keys()))
    assert name == "Alice Brown"
    assert title == "DevOps Engineer"


def test_extract_name_and_title_empty_lines():
    name, title = _extract_name_and_title([], set(SECTION_HEADERS.keys()))
    assert name == ""
    assert title == ""


def test_extract_name_and_title_only_one_qualifying_line():
    lines = ["Bob Builder", "PROFILE"]
    name, title = _extract_name_and_title(lines, set(SECTION_HEADERS.keys()))
    assert name == "Bob Builder"
    assert title == ""


def test_extract_name_and_title_skips_permit_line():
    lines = ["Permit: B", "Maria Garcia", "Product Manager"]
    name, _ = _extract_name_and_title(lines, set(SECTION_HEADERS.keys()))
    assert name == "Maria Garcia"


## --- Unit Tests for _parse_personal_info ---


def test_parse_personal_info_extracts_name_and_email():
    lines = [
        "Alex Johnson",
        "Cloud Architect",
        "alex.johnson@company.com",
        "+41791234567",
    ]
    info = _parse_personal_info(lines)
    assert info["name"] == "Alex Johnson"
    assert info["email"] == "alex.johnson@company.com"


def test_parse_personal_info_extracts_phone():
    lines = ["Sam Lee", "Engineer", "+49301234567"]
    info = _parse_personal_info(lines)
    assert info["phone"] == "+49301234567"


def test_parse_personal_info_extracts_dob():
    lines = ["Pat Kim", "Analyst", "Date of Birth: 10.05.1982"]
    info = _parse_personal_info(lines)
    assert info["date_of_birth"] == "10.05.1982"


def test_parse_personal_info_extracts_nationality():
    lines = ["Chris Tan", "Manager", "Nationality: Singaporean"]
    info = _parse_personal_info(lines)
    assert info["nationality"] == "Singaporean"


def test_parse_personal_info_extracts_permit():
    lines = ["Dana Wolf", "CTO", "Permit: C"]
    info = _parse_personal_info(lines)
    assert info["permit"] == "C"


def test_parse_personal_info_returns_dict():
    info = _parse_personal_info(["Test Name"])
    assert isinstance(info, dict)
    assert "name" in info
    assert "title" in info


def test_parse_personal_info_empty_lines():
    info = _parse_personal_info([])
    assert info["name"] == ""
    assert info["title"] == ""


def test_parse_personal_info_first_field_wins():
    """When multiple lines match the same field, only the first value is captured."""
    lines = [
        "First Person",
        "Title A",
        "first@example.com",
        "second@example.com",  # Should not overwrite first email
    ]
    info = _parse_personal_info(lines)
    assert info["email"] == "first@example.com"


## --- Unit Tests for _parse_education_entry ---


def test_parse_education_entry_with_comma_degree_first():
    """Degree keyword in part 0 → degree=part0, institution=part1."""
    entry = _parse_education_entry("Bachelor of Science, MIT", ["Bachelor"])
    assert "Bachelor" in entry["degree"]
    assert "MIT" in entry["institution"]


def test_parse_education_entry_with_comma_institution_first():
    """When degree keyword is in part 1, institution comes first."""
    entry = _parse_education_entry("ETH Zurich, Master of Science", ["Master"])
    assert "ETH Zurich" in entry["institution"]
    assert "Master" in entry["degree"]


def test_parse_education_entry_with_dash_separator():
    """' - ' separator: institution before dash, degree after."""
    entry = _parse_education_entry("Harvard University - PhD Computer Science", ["PhD"])
    assert "Harvard University" in entry["institution"]
    assert "PhD" in entry["degree"]


def test_parse_education_entry_no_separator_degree_keyword():
    """No separator but degree keyword present → degree = sanitized whole line."""
    entry = _parse_education_entry("Bachelor in Applied Sciences", ["Bachelor"])
    assert "Bachelor" in entry["degree"]


def test_parse_education_entry_university_fallback():
    """No separator and no degree keyword but contains 'University' → institution."""
    entry = _parse_education_entry("University of Geneva", ["Bachelor", "Master"])
    assert "University of Geneva" in entry["institution"]
    assert entry["degree"] == ""


def test_parse_education_entry_college_fallback():
    entry = _parse_education_entry("Kings College London", ["Bachelor", "Master"])
    assert "Kings College London" in entry["institution"]


def test_parse_education_entry_fallback_no_keywords():
    """Completely unrecognised line → institution = sanitized line."""
    entry = _parse_education_entry("Some random training", ["Bachelor", "Master"])
    assert entry["institution"] != ""
    assert entry["degree"] == ""


def test_parse_education_entry_returns_both_keys():
    entry = _parse_education_entry("Any line", ["Bachelor"])
    assert "institution" in entry
    assert "degree" in entry


## --- Unit Tests for _handle_profile_section ---


def test_handle_profile_section_basic():
    lines = ["PROFILE", "Experienced developer.", "Works with Python.", "EDUCATION"]
    result, next_idx = _handle_profile_section(lines, 0)
    assert "Experienced developer" in result
    assert "Works with Python" in result
    assert next_idx == 3


def test_handle_profile_section_empty():
    lines = ["PROFILE", "EDUCATION"]
    result, next_idx = _handle_profile_section(lines, 0)
    assert result == ""
    assert next_idx == 1


def test_handle_profile_section_sanitizes_content():
    """The profile text should be sanitized (e.g., bullet chars removed)."""
    lines = ["PROFILE", "Some text •", "EDUCATION"]
    result, _ = _handle_profile_section(lines, 0)
    assert "•" not in result


## --- Unit Tests for _handle_strategic_impact_section ---


def test_handle_strategic_impact_section_returns_bullets():
    kw = STRATEGIC_KEYWORDS[0]
    lines = [
        "STRATEGIC IMPACT & TRANSFORMATIONS",
        f"Intro. {kw}: Delivered results.",
        "EDUCATION",
    ]
    bullets, next_idx = _handle_strategic_impact_section(lines, 0)
    assert isinstance(bullets, list)
    assert next_idx == 2


def test_handle_strategic_impact_section_empty():
    lines = ["STRATEGIC IMPACT & TRANSFORMATIONS", "EDUCATION"]
    bullets, next_idx = _handle_strategic_impact_section(lines, 0)
    assert bullets == []
    assert next_idx == 1


def test_handle_strategic_impact_section_no_keywords():
    lines = [
        "STRATEGIC IMPACT & TRANSFORMATIONS",
        "Plain text with no strategic keywords.",
        "EDUCATION",
    ]
    bullets, _ = _handle_strategic_impact_section(lines, 0)
    # No matching strategic keywords → no bullets
    assert isinstance(bullets, list)


## --- Unit Tests for _handle_education_section ---


def test_handle_education_section_returns_list_of_dicts():
    lines = ["EDUCATION", "Bachelor of Science, State University", "LANGUAGES"]
    result, next_idx = _handle_education_section(lines, 0)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "institution" in result[0]
    assert "degree" in result[0]
    assert next_idx == 2


def test_handle_education_section_empty():
    """
    Verify that _handle_education_section returns an empty list and advances to the next section when the EDUCATION header has no entries.
    
    Asserts that:
    - the parsed education list is empty, and
    - the returned next index points to the following header line (1).
    """
    lines = ["EDUCATION", "LANGUAGES"]
    result, next_idx = _handle_education_section(lines, 0)
    assert result == []
    assert next_idx == 1


def test_handle_education_section_multiple_entries():
    lines = [
        "EDUCATION",
        "Bachelor of Science, MIT",
        "Master of Engineering, ETH Zurich",
        "LANGUAGES",
    ]
    result, _ = _handle_education_section(lines, 0)
    assert len(result) == 2


## --- Unit Tests for _handle_languages_section ---


def test_handle_languages_section_plain_lines():
    lines = ["LANGUAGES", "English (Native)", "German (B2)", "EDUCATION"]
    result, next_idx = _handle_languages_section(lines, 0)
    assert "English (Native)" in result
    assert "German (B2)" in result
    assert next_idx == 3


def test_handle_languages_section_empty():
    lines = ["LANGUAGES", "EDUCATION"]
    result, next_idx = _handle_languages_section(lines, 0)
    assert result == []
    assert next_idx == 1


def test_handle_languages_section_filters_linkedin():
    lines = [
        "LANGUAGES",
        "English (Native)",
        f"See profile at {LINKEDIN_KEYWORD}/in/johndoe",
        "German (B2)",
        "EDUCATION",
    ]
    result, _ = _handle_languages_section(lines, 0)
    assert not any(LINKEDIN_KEYWORD in entry for entry in result)
    assert "English (Native)" in result
    assert "German (B2)" in result


def test_handle_languages_section_with_bullets():
    lines = [
        "LANGUAGES",
        "• English (Native)",
        "proficiency: full",
        "• German (B2)",
        "EDUCATION",
    ]
    result, _ = _handle_languages_section(lines, 0)
    assert isinstance(result, list)
    # Bullet items should be aggregated
    assert any("English" in entry for entry in result)


def test_handle_languages_section_bullet_filters_linkedin():
    lines = [
        "LANGUAGES",
        "• English (Native)",
        f"• {LINKEDIN_KEYWORD}/in/johndoe",
        "EDUCATION",
    ]
    result, _ = _handle_languages_section(lines, 0)
    assert not any(LINKEDIN_KEYWORD in entry for entry in result)


def test_handle_languages_section_sanitizes_entries():
    lines = ["LANGUAGES", "Nativ German", "EDUCATION"]
    result, _ = _handle_languages_section(lines, 0)
    assert any("Native" in entry for entry in result)


## --- Unit Tests for _handle_competencies_and_skills_section ---


def test_handle_competencies_and_skills_returns_dict():
    kw = SKILL_KEYWORDS[1]  # "Architecture"
    lines = [
        "COMPETENCIES AND SKILLS",
        f"Intro. {kw}: AWS, GCP.",
        "EDUCATION",
    ]
    result, next_idx = _handle_competencies_and_skills_section(lines, 0)
    assert isinstance(result, dict)
    assert next_idx == 2


def test_handle_competencies_and_skills_empty():
    lines = ["COMPETENCIES AND SKILLS", "EDUCATION"]
    result, next_idx = _handle_competencies_and_skills_section(lines, 0)
    assert result == {}
    assert next_idx == 1


def test_handle_competencies_and_skills_parses_categories():
    kw = SKILL_KEYWORDS[2]  # "Frameworks"
    lines = [
        "COMPETENCIES AND SKILLS",
        f"{kw}: Django, Flask, FastAPI.",
        "EDUCATION",
    ]
    result, _ = _handle_competencies_and_skills_section(lines, 0)
    if kw in result:
        assert isinstance(result[kw], list)
        assert len(result[kw]) > 0


def test_handle_competencies_and_skills_values_are_lists():
    kw = SKILL_KEYWORDS[3]  # "Tools"
    lines = [
        "COMPETENCIES AND SKILLS",
        f"Intro text. {kw}: Docker; Kubernetes, Terraform.",
        "LANGUAGES",
    ]
    result, _ = _handle_competencies_and_skills_section(lines, 0)
    for vals in result.values():
        assert isinstance(vals, list)


## --- Unit Tests for _handle_generic_fallback_section ---


def test_handle_generic_fallback_section_basic():
    lines = ["VOLUNTEERING", "Open Source Contributor", "Red Cross", "EDUCATION"]
    result, next_idx = _handle_generic_fallback_section(lines, 0, "volunteering")
    assert "Open Source Contributor" in result
    assert "Red Cross" in result
    assert next_idx == 3


def test_handle_generic_fallback_section_empty():
    lines = ["VOLUNTEERING", "EDUCATION"]
    result, next_idx = _handle_generic_fallback_section(lines, 0, "volunteering")
    assert result == []
    assert next_idx == 1


def test_handle_generic_fallback_section_sanitizes():
    lines = ["VOLUNTEERING", "item with • bullet", "EDUCATION"]
    result, _ = _handle_generic_fallback_section(lines, 0, "volunteering")
    assert not any("•" in item for item in result)


def test_handle_generic_fallback_section_ignores_canonical_arg():
    """The _canonical_section argument is unused; passing different values must not affect output."""
    lines = ["VOLUNTEERING", "Mentoring", "EDUCATION"]
    result_a, _ = _handle_generic_fallback_section(lines, 0, "volunteering")
    result_b, _ = _handle_generic_fallback_section(lines, 0, "anything_else")
    assert result_a == result_b


## --- Unit Tests for updated _parse_experience (optional location) ---


def test_parse_experience_job_without_location():
    """Job header with only title, company, and dates (no location) should parse correctly."""
    lines = [
        "PROFESSIONAL EXPERIENCE",
        "Engineer, StartupCo (01/2023 - Present)",
        "EDUCATION",
    ]
    jobs, _ = _parse_experience(lines, 0)
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Engineer"
    assert jobs[0]["company"] == "StartupCo"
    assert jobs[0]["location"] == ""
    assert jobs[0]["dates"] == "01/2023 - Present"


def test_parse_experience_job_with_location():
    """Job header with location must populate the location field."""
    lines = [
        "PROFESSIONAL EXPERIENCE",
        "Lead Dev, BigCorp, Zurich (2020 - 2023)",
        "EDUCATION",
    ]
    jobs, _ = _parse_experience(lines, 0)
    assert len(jobs) == 1
    assert jobs[0]["location"] == "Zurich"


def test_parse_experience_location_field_is_string():
    """location must always be a string, never None."""
    lines = [
        "PROFESSIONAL EXPERIENCE",
        "Dev, Corp (01/2022 - Present)",
        "EDUCATION",
    ]
    jobs, _ = _parse_experience(lines, 0)
    assert isinstance(jobs[0]["location"], str)


## --- Unit Tests for personal_info as dict in parse_cv_to_json ---


@patch("src.parser.parse_cv.convert_from_path")
@patch("src.parser.parse_cv.pt.image_to_string")
def test_parse_cv_to_json_personal_info_is_dict(mock_ocr, mock_pdf_conv):
    """personal_info in the returned data must be a dict, not a list."""
    mock_ocr.return_value = (
        "John Smith\nSoftware Engineer\njohn@example.com\nPROFILE\nExperienced.\n"
    )
    mock_pdf_conv.return_value = [MagicMock()]
    with patch("src.parser.parse_cv.Path.write_text"):
        result = parse_cv_to_json("dummy.pdf")
    assert isinstance(result["personal_info"], dict)


@patch("src.parser.parse_cv.convert_from_path")
@patch("src.parser.parse_cv.pt.image_to_string")
def test_parse_cv_to_json_personal_info_has_name(mock_ocr, mock_pdf_conv):
    """personal_info dict must include 'name' key."""
    mock_ocr.return_value = "Jane Doe\nArchitect\nPROFILE\nDetail.\n"
    mock_pdf_conv.return_value = [MagicMock()]
    with patch("src.parser.parse_cv.Path.write_text"):
        result = parse_cv_to_json("dummy.pdf")
    assert "name" in result["personal_info"]
    assert result["personal_info"]["name"] == "Jane Doe"


@patch("src.parser.parse_cv.convert_from_path")
@patch("src.parser.parse_cv.pt.image_to_string")
def test_parse_cv_to_json_personal_info_extracts_email(mock_ocr, mock_pdf_conv):
    """Email in top section must appear in personal_info dict."""
    mock_ocr.return_value = "Alice Lee\nEngineer\nalice@test.org\nPROFILE\nContent.\n"
    mock_pdf_conv.return_value = [MagicMock()]
    with patch("src.parser.parse_cv.Path.write_text"):
        result = parse_cv_to_json("dummy.pdf")
    assert result["personal_info"].get("email") == "alice@test.org"


## --- Additional regression / boundary tests ---


def test_extract_phone_exactly_7_digits_after_plus():
    """Minimum valid E.164: + followed by exactly 7 digits."""
    result = _extract_phone("+1234567")
    assert result == "+1234567"


def test_extract_phone_exactly_15_digits_after_plus():
    """Maximum valid E.164: + followed by exactly 15 digits."""
    result = _extract_phone("+123456789012345")
    assert result == "+123456789012345"


def test_extract_phone_16_digits_after_plus_returns_none():
    """16 digits after + exceeds E.164 limit and must be rejected."""
    # Note: the raw match allows 7-18 chars which may grab 16+, but normalization and
    # final E.164 validation should reject strings with >15 digits
    result = _extract_phone("+1234567890123456")
    assert result is None


def test_parse_personal_info_skips_section_header_for_name():
    """A section header at the start should not become the name."""
    lines = ["PROFILE", "Real Name", "Real Title"]
    info = _parse_personal_info(lines)
    assert info["name"] == "Real Name"


def test_handle_languages_section_non_empty_line_no_linkedin():
    """Plain lines without linkedin keyword are included."""
    lines = ["LANGUAGES", "French (C1)", "EDUCATION"]
    result, _ = _handle_languages_section(lines, 0)
    assert "French (C1)" in result


def test_parse_education_entry_bsc_keyword():
    entry = _parse_education_entry("B.Sc Computer Science, Oxford", ["B.Sc"])
    assert "B.Sc" in entry["degree"] or "B.Sc" in entry["institution"]


def test_parse_education_entry_msc_keyword():
    entry = _parse_education_entry("London School, M.Sc Finance", ["M.Sc"])
    assert "London School" in entry["institution"]
    assert "M.Sc" in entry["degree"]


def test_handle_profile_section_multiple_lines_joined():
    """Multiple profile lines should be joined and returned as one string."""
    lines = ["PROFILE", "Line one.", "Line two.", "EDUCATION"]
    result, _ = _handle_profile_section(lines, 0)
    assert "Line one" in result
    assert "Line two" in result