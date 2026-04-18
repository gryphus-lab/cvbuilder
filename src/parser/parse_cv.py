import re
import json
from pathlib import Path
from typing import Any, Optional
import pytesseract as pt
from pdf2image import convert_from_path

# Load configuration from project root
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.json"
with open(CONFIG_PATH, encoding="utf-8") as f:
    CONFIG = json.load(f)

SECTION_HEADERS = CONFIG["section_headers"]
ACHIEVEMENT_KEYWORDS = CONFIG["achievement_keywords"]
SKILL_KEYWORDS = CONFIG["skill_keywords"]
STRATEGIC_KEYWORDS = CONFIG["strategic_keywords"]

LINKEDIN_KEYWORD = "linkedin.com"


def _is_header(line: str) -> bool:
    """
    Determine whether a text line corresponds to a configured section header.
    
    Returns:
        True if the uppercased, trimmed line with any trailing colon removed matches an entry in SECTION_HEADERS, False otherwise.
    """
    clean = line.upper().strip().rstrip(":")
    return clean in SECTION_HEADERS


def final_sanitize(text: str) -> str:
    """
    Sanitize OCR-extracted text by applying targeted OCR corrections and normalization.
    
    Performs observable normalizations such as contextual fixes for AI-related "Al"/"OpenAl" variants, removal of stray symbols (e.g., bullets, copyright/cent symbols), context-constrained replacement of `ii` with `ü`, collapsing adjacent duplicated configured keywords, collapsing repeated whitespace, normalizing colon spacing to ": ", and fixing "Nativ" to "Native". Returns an empty string when the input is falsy.
    
    Parameters:
        text (str): Raw OCR-extracted text.
    
    Returns:
        str: The sanitized text; returns an empty string if `text` is falsy.
    """
    if not text:
        return ""

    # Apply OCR normalizations - targeted "Al" → "AI" fixes for AI-related terms only
    text = re.sub(
        r"(?i)\bAl-(?=GPT|Chat|Open|API|Model|powered|based|driven|generated|ML)",
        "AI-",
        text,
    )
    text = re.sub(
        r"(?i)\bAl (?=GPT|Chat|Open|API|Model|powered|based|driven|generated|ML)",
        "AI ",
        text,
    )
    text = re.sub(r"OpenAl\b", "OpenAI", text)
    text = re.sub(r"[•©¢]", "", text)

    # Replace 'ii' with 'ü' only in specific OCR contexts (e.g., Zürich misread as Ziirich)
    # Match standalone 'ii' or 'ii' NOT preceded by a vowel (to avoid Hawaii)
    text = re.sub(r"\bii\b", "ü", text)  # standalone 'ii'
    # Match capitalized words with 'ii' not preceded by a vowel (Ziirich, Miinchen)
    text = re.sub(r"\b([A-Z](?:[^aeiouAEIOU])*?)ii(\w*)\b", r"\1ü\2", text)

    for kw in ACHIEVEMENT_KEYWORDS + SKILL_KEYWORDS + STRATEGIC_KEYWORDS:
        double_pattern = rf"\b({re.escape(kw)})\s+({re.escape(kw)})\b"
        text = re.sub(double_pattern, r"\1", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*:\s*", ": ", text)
    text = re.sub(r"\bNativ\b", "Native", text)

    return text.strip()


def semantic_bullet_split(text: str, keywords: list) -> tuple[str, list[str]]:
    """
    Split a block of text into a lead-in and sanitized keyword-led bullet segments.

    Parameters:
        text (str): The input text to split.
        keywords (list): Iterable of keyword strings to detect when followed by a colon.

    Returns:
        tuple[str, list[str]]:
            lead_in — sanitized text that appears before the first detected `keyword:` occurrence (empty string if none).
            bullets — list of sanitized "Keyword: content" strings for each detected keyword occurrence.
    """
    if not text:
        return "", []

    pattern = rf"(?:\.|\s|^)({'|'.join([re.escape(k) for k in keywords])})\s*:"

    parts = re.split(pattern, text)

    lead_in = final_sanitize(parts[0])
    bullets = []

    for i in range(1, len(parts), 2):
        kw = parts[i]
        content = parts[i + 1] if i + 1 < len(parts) else ""
        bullet_full = final_sanitize(f"{kw}: {content}")
        if len(bullet_full) > len(kw) + 5:
            bullets.append(bullet_full)

    return lead_in, bullets


def _extract_email(line: str) -> Optional[str]:
    """
    Extracts the first email address found in the input line.
    
    Returns:
        The matched email address as a string, or `None` if no email is present.
    """
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", line)
    return email_match.group(0) if email_match else None


def _extract_phone(line: str) -> Optional[str]:
    """
    Extracts an international phone number from a text line and returns it in E.164 format.
    
    Parameters:
        line (str): Text to scan for a phone number.
    
    Returns:
        str | None: The phone number normalized to E.164 (e.g. "+491771234567") if a valid international number is found, `None` otherwise.
    """
    # Match international E.164-style phone numbers with explicit prefix (+ or 00)
    # Only match strings that start with + or 00, followed by digits with optional separators
    phone_match = re.search(
        r"(?:\+|00)[\d\s\-().]{7,18}", line
    )
    if phone_match:
        # Normalize by removing spaces, dashes, parentheses, and dots
        phone = phone_match.group(0)
        normalized = re.sub(r"[\s\-().]", "", phone)
        # Prepend + if the number starts with 00
        if normalized.startswith("00"):
            normalized = "+" + normalized[2:]
        # Validate E.164 style: must start with + followed by 7-15 digits
        if re.match(r"\+\d{7,15}$", normalized):
            return normalized
    return None


def _extract_dob(line: str) -> Optional[str]:
    """
    Extract a date-of-birth string in digit-and-dot format from a single line of text.

    Returns:
        The matched date string (digits and dots, e.g. "01.01.1990" or "01.01"), or `None` if no date-of-birth pattern is found.
    """
    dob_match = re.search(r"Date of Birth:\s*(\d{1,2}\.\d{1,2}\.\d{2,4})", line)
    return dob_match.group(1) if dob_match else None


def _extract_nationality(line: str) -> Optional[str]:
    """
    Extract nationality from a single text line.
    
    Parameters:
        line (str): A line of text expected to contain the pattern "Nationality: <value>".
    
    Returns:
        nationality (Optional[str]): The token following "Nationality:" (an alphanumeric/underscore word) if present, otherwise `None`.
    """
    nat_match = re.search(r"Nationality:\s*(\w+)", line)
    return nat_match.group(1) if nat_match else None


def _extract_permit(line: str) -> Optional[str]:
    """
    Extracts the value following a "Permit:" label from a single line of text.
    
    Returns:
        permit (str): The captured permit text with surrounding whitespace removed, or None if the line does not contain a "Permit:" label.
    """
    permit_match = re.search(r"Permit:\s*(.+)$", line)
    return permit_match.group(1).strip() if permit_match else None


def _extract_address(line: str) -> Optional[str]:
    """
    Detects and returns an address-like string from a single line of text.
    
    Evaluates the line for address characteristics and returns the trimmed line when:
    - it contains at least one digit,
    - it is not a "Date of Birth" line,
    - it does not match common phone-like patterns (e.g., "+CC NN"),
    - it is not a standalone date in dd.mm.yyyy format,
    - and it contains an address-like pattern (number + word or common street keywords such as St, Street, Ave, Road, Blvd, Lane, Strasse).
    
    Parameters:
        line (str): A single line of OCR/text to inspect for an address.
    
    Returns:
        Optional[str]: The trimmed input line if it appears to be an address, `None` otherwise.
    """
    if (
        any(c.isdigit() for c in line)
        and "Date of Birth" not in line
        and not re.search(r"\+\d{2}\s?\d{2}", line)  # Skip phone numbers
        and not re.search(
            r"^\d{2}\.\d{2}\.\d{4}$", line.strip()
        )  # Skip standalone dates
        and re.search(
            r"\d+\s+\w+|St\b|Street\b|Ave\b|Avenue\b|Rd\b|Road\b|Blvd\b|Lane\b|Strasse\b|strasse\b",
            line,
        )  # Require address pattern
    ):
        return line.strip()
    return None


def _extract_name_and_title(lines: list[str], common_headers: set) -> tuple[str, str]:
    """
    Identify the candidate's name and job title from the first up-to-five OCR lines.
    
    Scans up to the first five lines and selects the first non-header, non-contact line as the name and the next such line (if any) as the title.
    
    Parameters:
        lines (list[str]): OCR-extracted lines from the top of the document.
        common_headers (set): Uppercased section header tokens used to recognize and skip heading lines.
    
    Returns:
        tuple[str, str]: (name, title) where each is a sanitized line string or an empty string if not found.
    """
    name = ""
    title = ""

    for idx, line in enumerate(lines[:5]):
        stripped = line.strip()
        # Skip section headers using config-driven SECTION_HEADERS
        line_upper = stripped.upper().rstrip(":")
        is_heading = (
            line_upper in common_headers
            or stripped.endswith(":")
            or any(word in common_headers for word in line_upper.split())
            or any(line_upper.startswith(header) for header in common_headers)
        )

        if (
            stripped
            and not is_heading
            and not re.search(r"@|Date of Birth|Nationality|Permit|\+\d{2}", stripped)
        ):
            # First line that doesn't look like contact info or header is likely the name
            if not name:
                name = stripped
            elif not title and idx > 0:
                # Second such line is likely the title/role
                title = stripped
                break

    return name, title


def _parse_personal_info(lines: list[str]) -> dict[str, str]:
    """
    Extract personal contact and identity fields from the top of OCR'd lines.
    
    Scans up to the first 20 OCR lines and fills `name` and `title` (always present, possibly empty). Attempts to extract additional fields using heuristics: `email`, `phone`, `date_of_birth`, `nationality`, `permit`, and `address`; these keys are added only when a match is found.
    
    Parameters:
        lines (list[str]): OCR'd lines from the document (top of page first).
    
    Returns:
        info (dict[str, str]): Dictionary of extracted fields; `name` and `title` are always present, other keys appear only if detected.
    """
    info = {"name": "", "title": ""}

    # Extract name and title
    name, title = _extract_name_and_title(lines, SECTION_HEADERS)
    info["name"] = name
    info["title"] = title

    # Define field extractors mapping
    field_extractors = [
        ("email", _extract_email),
        ("phone", _extract_phone),
        ("date_of_birth", _extract_dob),
        ("nationality", _extract_nationality),
        ("permit", _extract_permit),
        ("address", _extract_address),
    ]

    # Extract fields using the mapping
    for line in lines[:20]:  # only top of document
        for field_name, extractor_func in field_extractors:
            if not info.get(field_name):
                value = extractor_func(line)
                if value:
                    info[field_name] = value

    return info


def _parse_experience(lines: list[str], start_idx: int) -> tuple[list[dict], int]:
    """
    Parse professional experience entries from OCR lines starting immediately after the given section header index.
    
    Parameters:
        lines (list[str]): Non-empty OCR-extracted lines.
        start_idx (int): Index of the section header line; parsing begins at the next line.
    
    Returns:
        tuple[list[dict], int]: A pair (jobs, next_index) where `jobs` is a list of job objects and `next_index` is the line index where parsing stopped (first detected header or end of input). Each job object contains:
            - `title` (str): Job title.
            - `company` (str): Employer or organization name.
            - `location` (str): Sanitized location string or empty string if not present.
            - `dates` (str): Date or date-range string as found in parentheses.
            - `description` (str): Leading descriptive text for the role (may be empty).
            - `achievements` (list[str]): Extracted achievement/keyword-led bullet segments (may be empty).
    """
    # Job header pattern: matches lines like "Title, Company, Location (Dates)"
    job_header_pattern = r"(.+?),\s*(.+?)(?:,\s*(.+?))?\s*\((.+?)\)"

    jobs = []
    i = start_idx + 1

    while i < len(lines):
        line = lines[i].strip()
        if _is_header(line):
            break

        job_match = re.search(job_header_pattern, line)

        if job_match:
            job = {
                "title": job_match.group(1).strip(),
                "company": job_match.group(2).strip(),
                "location": (
                    final_sanitize(job_match.group(3).strip())
                    if job_match.group(3)
                    else ""
                ),
                "dates": job_match.group(4).strip(),
                "description": "",
                "achievements": [],
            }
            i += 1
            content_parts = []
            while (
                i < len(lines)
                and not _is_header(lines[i])
                and not re.search(job_header_pattern, lines[i])
            ):
                content_parts.append(lines[i].strip())
                i += 1

            desc, achs = semantic_bullet_split(
                " ".join(content_parts), ACHIEVEMENT_KEYWORDS
            )
            job["description"] = desc
            job["achievements"] = achs
            jobs.append(job)
        else:
            i += 1
    return jobs, i


def _parse_generic_section(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """
    Collects consecutive non-header, non-empty lines immediately after a given index as a section's items.
    
    Parameters:
        lines (list[str]): All OCR-derived lines from the CV.
        start_idx (int): Index of the section header line; collection begins at the next line.
    
    Returns:
        tuple[list[str], int]: A tuple where the first element is a list of stripped, non-empty lines belonging to the section, and the second element is the index of the next line to process (the first header line encountered or len(lines)).
    """
    items = []
    i = start_idx + 1
    while i < len(lines) and not _is_header(lines[i]):
        line = lines[i].strip()
        if line:
            items.append(line)
        i += 1
    return items, i


def _parse_education_entry(item: str, degree_keywords: list[str]) -> dict[str, str]:
    """
    Parse a single education-line and extract the institution name and degree text.
    
    Sanitizes the input and heuristically splits the line by common separators (comma or " - ")
    and keyword presence to determine which part represents the degree versus the institution.
    If no degree keyword or separator is detected, prefers detecting institution names that
    contain "Institute", "University", or "College"; otherwise treats the full sanitized line
    as the institution.
    
    Parameters:
        item (str): Raw education line (OCR output) to parse.
        degree_keywords (list[str]): Degree-identifying keywords (e.g., "Bachelor", "MSc",
            "PhD") used to detect which segment denotes the degree.
    
    Returns:
        dict[str, str]: Dictionary with keys:
            - 'institution': Institution name or an empty string if not identified.
            - 'degree': Degree text or an empty string if not identified.
    """
    sanitized = final_sanitize(item)
    entry = {"institution": "", "degree": ""}

    # Try to detect degree keywords
    degree_found = ""
    for deg_kw in degree_keywords:
        if deg_kw in item:
            degree_found = sanitized
            break

    # Try to split by common separators
    if "," in item:
        parts = item.split(",", 1)
        sanitized_parts = [final_sanitize(p) for p in parts]
        # Check which part contains the degree keyword
        part0_has_degree = any(
            deg_kw in sanitized_parts[0] for deg_kw in degree_keywords
        )
        part1_has_degree = len(sanitized_parts) > 1 and any(
            deg_kw in sanitized_parts[1] for deg_kw in degree_keywords
        )

        # Consolidate assignment logic
        if part0_has_degree and not part1_has_degree:
            # Case 1: Degree is in sanitized_parts[0]
            entry["degree"] = sanitized_parts[0]
            entry["institution"] = (
                sanitized_parts[1] if len(sanitized_parts) > 1 else ""
            )
        elif part1_has_degree and not part0_has_degree:
            # Case 2: Degree is in sanitized_parts[1]
            entry["institution"] = sanitized_parts[0]
            entry["degree"] = sanitized_parts[1] if len(sanitized_parts) > 1 else ""
        elif degree_found:
            # Case 3: Degree found but neither part has degree detected
            entry["degree"] = sanitized_parts[0]
            entry["institution"] = (
                sanitized_parts[1] if len(sanitized_parts) > 1 else ""
            )
        else:
            # Case 4: No degree detected, assume institution comes first
            entry["institution"] = sanitized_parts[0]
            entry["degree"] = sanitized_parts[1] if len(sanitized_parts) > 1 else ""
    elif " - " in item:
        parts = item.split(" - ", 1)
        entry["institution"] = final_sanitize(parts[0])
        entry["degree"] = final_sanitize(parts[1]) if len(parts) > 1 else ""
    elif degree_found:
        # No separator found and degree detected
        entry["degree"] = sanitized
    elif "Institute" in item or "University" in item or "College" in item:
        entry["institution"] = sanitized
    else:
        # Fallback: use the whole line as institution
        entry["institution"] = sanitized

    return entry


def _handle_profile_section(lines: list[str], start_idx: int) -> tuple[str, int]:
    """
    Extract and sanitize the text content of the Profile section starting at the given header index.
    
    Parameters:
        lines (list[str]): OCR-extracted lines from the document.
        start_idx (int): Index of the Profile section header in `lines`; parsing begins after this index.
    
    Returns:
        tuple[str, int]: The sanitized profile text and the index of the next line after the section.
    """
    profile_lines, next_idx = _parse_generic_section(lines, start_idx)
    return final_sanitize("\n".join(profile_lines)), next_idx


def _handle_strategic_impact_section(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """
    Extract strategic impact bullet items from the section starting at start_idx.
    
    Returns:
        bullets (list[str]): Sanitized strategic impact bullets extracted from the section.
        next_idx (int): Index of the line immediately after the parsed section.
    """
    content, next_idx = _parse_generic_section(lines, start_idx)
    _, bullets = semantic_bullet_split(" ".join(content), STRATEGIC_KEYWORDS)
    return bullets, next_idx


def _handle_education_section(lines: list[str], start_idx: int) -> tuple[list[dict], int]:
    """
    Parse the Education section and return structured education entries.
    
    Processes the section starting at start_idx and converts each line in the section into a dictionary with at least the keys "institution" and "degree".
    
    Parameters:
        lines (list[str]): OCR'd lines from the document.
        start_idx (int): Index of the section header line.
    
    Returns:
        tuple[list[dict], int]: A tuple where the first element is a list of education entry dictionaries (each contains at minimum "institution" and "degree") and the second element is the index of the line immediately after the parsed section.
    """
    content, next_idx = _parse_generic_section(lines, start_idx)
    degree_keywords = [
        "Bachelor",
        "Master",
        "B.Tech",
        "B.Sc",
        "M.Tech",
        "M.Sc",
        "PhD",
        "Doctorate",
    ]
    education_entries = [_parse_education_entry(item, degree_keywords) for item in content]
    return education_entries, next_idx


def _handle_languages_section(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """
    Parse the Languages section into a list of sanitized language entries.
    
    This routine reads the section content starting after the header, supports both bullet-formatted and plain-line formats, aggregates multi-line bullet items into single entries, filters out lines containing the LinkedIn URL keyword, and applies OCR sanitization to each entry.
    
    Parameters:
        lines (list[str]): OCR text lines for the whole document.
        start_idx (int): Index of the section header line; parsing begins at the line after this index.
    
    Returns:
        tuple[list[str], int]: A tuple where the first element is the list of sanitized language entries (in original order) and the second element is the index of the next line to process after this section.
    """
    content, next_idx = _parse_generic_section(lines, start_idx)
    languages = []

    # Detect if section uses bullets
    has_bullets = any("•" in line for line in content)

    if has_bullets:
        # Use bullet aggregation logic
        current = None
        for original_line in content:
            if original_line.startswith("•"):
                line_without_bullet = re.sub(r"^\s*•\s*", "", original_line).strip()
                sanitized_text = final_sanitize(line_without_bullet)
                if sanitized_text and LINKEDIN_KEYWORD not in sanitized_text.lower():
                    if current:
                        languages.append(current)
                    current = sanitized_text
            else:
                sanitized_text = final_sanitize(original_line)
                if sanitized_text and LINKEDIN_KEYWORD not in sanitized_text.lower():
                    if current:
                        current += " " + sanitized_text
                    else:
                        current = sanitized_text
        if current:
            languages.append(current)
    else:
        # Treat each non-empty line as a separate language entry
        for content_line in content:
            sanitized_line = final_sanitize(content_line)
            if sanitized_line and LINKEDIN_KEYWORD not in sanitized_line.lower():
                languages.append(sanitized_line)

    return languages, next_idx


def _handle_competencies_and_skills_section(lines: list[str], start_idx: int) -> tuple[dict, int]:
    """
    Parse the Competencies & Skills section and return a mapping from category to a list of skills.
    
    Collects the section content following start_idx and extracts blocks of the form "Category: value1, value2"; categories and values are sanitized. Blocks without a colon are ignored.
    
    Returns:
        tuple[dict, int]: A tuple where the first element is a dict mapping category (str) to a list of skill strings, and the second element is the index of the line after the section.
    """
    content, next_idx = _parse_generic_section(lines, start_idx)
    _, skill_blocks = semantic_bullet_split(" ".join(content), SKILL_KEYWORDS)
    skills_dict = {}
    for block in skill_blocks:
        if ":" in block:
            cat, vals = block.split(":", 1)
            skills_dict[final_sanitize(cat.strip())] = [
                final_sanitize(v.strip())
                for v in re.split(r"[;,]", vals)
                if v.strip()
            ]
    return skills_dict, next_idx


def _handle_generic_fallback_section(lines: list[str], start_idx: int, _canonical_section: str) -> tuple[list[str], int]:
    """
    Handle a non-canonical section by collecting its lines and returning them sanitized.
    
    Parameters:
        lines (list[str]): OCR'd lines from the document.
        start_idx (int): Index of the section header.
    
    Returns:
        tuple[list[str], int]: A list of sanitized section lines and the index of the first line after the section.
    """
    content, next_idx = _parse_generic_section(lines, start_idx)
    return [final_sanitize(item) for item in content], next_idx


def parse_cv_to_json(pdf_path: str):
    """
    Parse a curriculum vitae PDF and extract structured resume data.
    
    Parameters:
        pdf_path (str): Filesystem path to the CV PDF.
    
    Returns:
        dict: JSON-serializable mapping with keys:
            - personal_info (dict): Contact and identity fields found near the top of the CV (e.g., `name`, `title`, `email`, `phone`, `date_of_birth`, `nationality`, `permit`, `address`) when available.
            - profile (str): Sanitized profile or summary text.
            - strategic_impact (list[str]): Strategic-impact bullet items extracted from the matching section.
            - professional_experience (list[dict]): Parsed job entries; each entry may include `title`, `company`, `location`, `dates`, `description`, and `achievements`.
            - certificates_and_training (list[str]): Lines from certificates and training section.
            - education (list[dict]): Education entries typically containing `institution` and optionally `degree`.
            - languages (list[str]): Language entries grouped and sanitized (LinkedIn links filtered).
            - competencies_and_skills (dict): Mapping of skill category to list of sanitized skill values.
            - volunteering (list[str]): Volunteering entries from the CV.
    """
    images = convert_from_path(pdf_path, dpi=300)
    raw_text = "\n".join([pt.image_to_string(img, lang="deu+eng") for img in images])

    # Debug raw output
    output_file = Path("results/raw_ocr_debug.txt")
    output_file.parent.mkdir(exist_ok=True, parents=True)
    output_file.write_text(raw_text, encoding="utf-8")

    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    cv_data = {
        "personal_info": {},
        "profile": "",
        "strategic_impact": [],
        "professional_experience": [],
        "certificates_and_training": [],
        "education": [],
        "languages": [],
        "competencies_and_skills": {},
        "volunteering": [],
    }

    # === PERSONAL INFO - parsed once from the very top ===
    cv_data["personal_info"] = _parse_personal_info(lines)

    # Define section handler mapping
    section_handlers = {
        "profile": _handle_profile_section,
        "professional_experience": _parse_experience,
        "strategic_impact": _handle_strategic_impact_section,
        "education": _handle_education_section,
        "languages": _handle_languages_section,
        "competencies_and_skills": _handle_competencies_and_skills_section,
    }

    i = 0
    while i < len(lines):
        line_upper = lines[i].upper().strip().rstrip(":")

        # Use SECTION_HEADERS for config-driven routing
        if line_upper in SECTION_HEADERS:
            canonical_section = SECTION_HEADERS[line_upper]

            # Route to appropriate handler
            if canonical_section in section_handlers:
                cv_data[canonical_section], i = section_handlers[canonical_section](lines, i)
            else:
                # Generic fallback for other configured sections
                cv_data[canonical_section], i = _handle_generic_fallback_section(lines, i, canonical_section)
        else:
            i += 1

    return cv_data


def save_to_json(data: dict[str, Any], output_path: Path) -> None:
    """
    Write `data` as UTF-8 encoded, pretty-printed JSON to `output_path`, creating parent directories if necessary.

    Parameters:
        data (dict[str, Any]): The JSON-serializable object to write.
        output_path (Path): Destination file path where the JSON will be written; parent directories will be created if missing.
    """
    output_path.parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


__all__ = ["parse_cv_to_json", "save_to_json"]