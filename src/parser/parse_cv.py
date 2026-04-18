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
    
    The line is cleaned by trimming whitespace, removing a single trailing colon if present, and uppercasing before checking against SECTION_HEADERS.
    
    Returns:
        `True` if the cleaned line matches an entry in SECTION_HEADERS, `False` otherwise.
    """
    clean = line.upper().strip().rstrip(":")
    return clean in SECTION_HEADERS


def final_sanitize(text: str) -> str:
    """
    Normalize and correct common OCR artifacts and whitespace/punctuation issues in extracted text.
    
    Performs observable normalizations including: targeted corrections of OCR variants like `Al`/`OpenAl` to `AI`/`OpenAI`, removal of stray symbols (e.g., bullets, ©, ¢), context-constrained replacement of `ii` with `ü` in OCR-specific cases, collapsing duplicated configured keywords, collapsing repeated whitespace, normalizing colon spacing to `": "`, and converting exact `Nativ` to `Native`. If `text` is falsy, returns an empty string.
    
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
    Extract an international phone number from a text line and return it in E.164 format.
    
    Scans the input for a number that begins with a leading `+` or `00`, normalizes common separators (spaces, dashes, parentheses, dots), and validates the result as an international E.164 number (leading `+` followed by 7–15 digits).
    
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
    Extract a date-of-birth token from a single text line.
    
    Searches for a "Date of Birth:" label followed by a date in day.month.year or day.month.year-short formats (e.g. "01.01.1990" or "1.1.90").
    
    Returns:
        The matched date string (e.g. "01.01.1990" or "1.1.90"), or `None` if no such pattern is present.
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
    Extracts the text following a 'Permit:' label on the given line.
    
    Returns:
        permit (str): The captured permit text with surrounding whitespace removed, or None if the line does not contain a 'Permit:' label.
    """
    permit_match = re.search(r"Permit:\s*(.+)$", line)
    return permit_match.group(1).strip() if permit_match else None


def _extract_address(line: str) -> Optional[str]:
    """
    Heuristically detects whether a single line contains an address-like string and returns it if so.
    
    Performs lightweight checks: requires at least one digit, excludes lines that look like a "Date of Birth", a standalone dd.mm.yyyy date, or a simple phone-like pattern, and requires an address-like pattern (e.g., number + word or common street keywords). If the line passes these heuristics the trimmed line is returned.
    
    Parameters:
        line (str): A single OCR/text line to inspect.
    
    Returns:
        Optional[str]: The trimmed input line when it appears to be an address, `None` otherwise.
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
    Selects the candidate's name and job title from the top OCR lines.
    
    Scans up to the first five lines. The first line that is not a section header and does not resemble contact/identity data becomes the name; the next such line (if any) becomes the title. Scanning stops early if a section header is encountered.
    
    Parameters:
        lines (list[str]): OCR-extracted lines from the top of the document.
        common_headers (set): Uppercased section header tokens used to recognize and skip heading lines.
    
    Returns:
        tuple[str, str]: (name, title) where each is the trimmed line string or an empty string if not found.
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

        # Stop scanning if we hit a section header
        if is_heading:
            break

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
    Parse a single education line into institution and degree components.
    
    This function heuristically determines which part of the raw education string represents the degree
    and which represents the institution by sanitizing the input and using common separators and
    degree-identifying keywords.
    
    Parameters:
        item (str): Raw education line (OCR output).
        degree_keywords (list[str]): Keywords that indicate a degree (e.g., "Bachelor", "Master", "PhD").
    
    Returns:
        dict[str, str]: Mapping with keys:
            - 'institution': The detected institution name (or empty string if not found).
            - 'degree': The detected degree text (or empty string if not found).
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
    Extracts and returns the sanitized text content of the Profile section.
    
    Parameters:
        lines (list[str]): OCR-extracted lines of the document.
        start_idx (int): Index of the Profile section header in `lines`; parsing begins at the line after this index.
    
    Returns:
        tuple[str, int]: A tuple where the first element is the sanitized profile text and the second is the index of the first line after the section.
    """
    profile_lines, next_idx = _parse_generic_section(lines, start_idx)
    return final_sanitize("\n".join(profile_lines)), next_idx


def _handle_strategic_impact_section(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """
    Extract strategic-impact bullet entries from a section and return them with the index after the section.
    
    Returns:
        tuple[list[str], int]: A list of sanitized strategic impact bullets, and the index of the line immediately following the parsed section.
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
    Map competencies and skills in the section to sanitized category→skill lists.
    
    Collects the section lines starting at start_idx, splits the text into keyword-led blocks, and for each block containing a colon interprets the left side as the category and the right side as comma- or semicolon-separated skill values. Category names and individual skill values are sanitized; blocks without a colon are ignored.
    
    Parameters:
        lines (list[str]): All OCR lines from the document.
        start_idx (int): Index of the section header line; parsing begins at the following line.
    
    Returns:
        tuple[dict, int]: A tuple where the first element maps sanitized category names to lists of sanitized skill strings, and the second element is the index of the first line after the section.
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
    Collects the raw lines of an unhandled section and returns them sanitized, plus the index of the first line after the section.
    
    Returns:
        tuple[list[str], int]: Sanitized section lines and the index of the first line after the section.
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