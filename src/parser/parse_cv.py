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
    clean = line.upper().strip().rstrip(":")
    return clean in SECTION_HEADERS


def final_sanitize(text: str) -> str:
    """
    Sanitize OCR-derived text by applying common corrections, collapsing duplicated keywords, and normalizing punctuation and whitespace.

    Performs a set of fixed string replacements for common OCR errors, collapses adjacent duplicated occurrences of keywords from ACHIEVEMENT_KEYWORDS, SKILL_KEYWORDS, and STRATEGIC_KEYWORDS (case-insensitive), normalizes repeated whitespace to single spaces, normalizes colon spacing to ": ", trims surrounding whitespace, replaces "Nativ" with "Native", and returns an empty string when the input is falsy.

    Parameters:
        text (str): Raw OCR-extracted text to sanitize.

    Returns:
        str: The sanitized text.
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
    """Extract email address from a line."""
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", line)
    return email_match.group(0) if email_match else None


def _extract_phone(line: str) -> Optional[str]:
    """Extract phone number from a line."""
    # Match international E.164-style phone numbers with flexible separators
    # Lookahead ensures at least 7-15 digits are present before normalization
    phone_match = re.search(
        r"(?=(?:.*\d){7,15})(?:\+[\d]{1,3})?[\d\s\-().]{7,18}", line
    )
    if phone_match:
        # Normalize by removing spaces, dashes, and parentheses while preserving the leading +
        phone = phone_match.group(0)
        normalized = re.sub(r"[\s\-().]", "", phone)
        # Validate that the normalized number has 7-15 digits, optionally with leading +
        if re.match(r"(?:\+)?\d{7,15}$", normalized):
            return normalized
    return None


def _extract_dob(line: str) -> Optional[str]:
    """Extract date of birth from a line."""
    dob_match = re.search(r"Date of Birth:\s*([\d.]+)", line)
    return dob_match.group(1) if dob_match else None


def _extract_nationality(line: str) -> Optional[str]:
    """Extract nationality from a line."""
    nat_match = re.search(r"Nationality:\s*(\w+)", line)
    return nat_match.group(1) if nat_match else None


def _extract_permit(line: str) -> Optional[str]:
    """Extract permit information from a line."""
    permit_match = re.search(r"Permit:\s*(.+)$", line)
    return permit_match.group(1).strip() if permit_match else None


def _extract_address(line: str) -> Optional[str]:
    """Extract address from a line if it looks like an address."""
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
    Extract name and title from the first few lines of the CV.

    Parameters:
        lines (list[str]): OCR'd lines from the document.
        common_headers (set): Set of common section headers to skip.

    Returns:
        tuple[str, str]: A tuple of (name, title).
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

    Scans up to the first 20 non-empty OCR lines and extracts common personal info fields using regex heuristics. Detected keys may include: `name`, `title`, `email`, `phone`, `date_of_birth`, `nationality`, `permit`, and `address`. The `address` is the first line that looks address-like (contains a digit) and is not a "Date of Birth" line.

    Parameters:
        lines (list[str]): OCR'd lines from the document.

    Returns:
        info (dict[str, str]): A dictionary of extracted fields; only keys for which a match was found are present.
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
    Parse consecutive professional experience entries from OCR lines starting after start_idx.

    @param lines: List of OCR-extracted, non-empty lines.
    @param start_idx: Index of the header line that begins the experience section; parsing starts from the next line.
    @returns: A tuple (jobs, next_index) where `jobs` is a list of job dictionaries and `next_index` is the line index where parsing stopped (the first header or end). Each job dictionary contains:
        - `title` (str): Job title.
        - `company` (str): Employer or organisation name.
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
    Parse a single education entry and extract institution and degree.

    Parameters:
        item (str): The raw education line to parse.
        degree_keywords (list[str]): List of keywords to detect degrees.

    Returns:
        dict[str, str]: Dictionary with 'institution' and 'degree' keys.
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


def parse_cv_to_json(pdf_path: str):
    """
    Parse a CV PDF and extract structured resume data as a JSON-serializable dictionary.

    Parameters:
        pdf_path (str): Path to the PDF file containing the CV.

    Returns:
        dict: A mapping with the following keys:
            - personal_info (dict): Extracted contact and identity fields (e.g., email, phone, date_of_birth, nationality, permit, address) where available.
            - profile (str): Profile/summary text.
            - strategic_impact (list[str]): Extracted strategic-impact bullet items.
            - professional_experience (list[dict]): List of job entries; each entry may include `title`, `company`, `location`, `dates`, `description`, and `achievements`.
            - certificates_and_training (list[str]): Items from certificates and training section.
            - education (list[dict]): Education entries, typically containing `institution` and optionally `degree`.
            - languages (list[str]): Language lines grouped into items (filtered and sanitized).
            - competencies_and_skills (dict): Mapping of skill categories to lists of sanitized skill values.
            - volunteering (list[str]): Volunteering entries.
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

    i = 0
    while i < len(lines):
        line_upper = lines[i].upper().strip().rstrip(":")

        # Use SECTION_HEADERS for config-driven routing
        if line_upper in SECTION_HEADERS:
            canonical_section = SECTION_HEADERS[line_upper]

            # Handle special sections with custom parsing logic
            if canonical_section == "profile":
                profile_lines, i = _parse_generic_section(lines, i)
                cv_data["profile"] = final_sanitize("\n".join(profile_lines))
            elif canonical_section == "professional_experience":
                cv_data["professional_experience"], i = _parse_experience(lines, i)
            elif canonical_section == "strategic_impact":
                content, i = _parse_generic_section(lines, i)
                _, bullets = semantic_bullet_split(
                    " ".join(content), STRATEGIC_KEYWORDS
                )
                cv_data["strategic_impact"] = bullets
            elif canonical_section == "education":
                content, i = _parse_generic_section(lines, i)
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
                cv_data["education"] = [
                    _parse_education_entry(item, degree_keywords) for item in content
                ]
            elif canonical_section == "languages":
                content, i = _parse_generic_section(lines, i)
                languages = []

                # Detect if section uses bullets
                has_bullets = any("•" in line for line in content)

                if has_bullets:
                    # Use bullet aggregation logic
                    current = None
                    for original_line in content:
                        if original_line.startswith("•"):
                            line_without_bullet = re.sub(
                                r"^\s*•\s*", "", original_line
                            ).strip()
                            sanitized_text = final_sanitize(line_without_bullet)
                            if (
                                sanitized_text
                                and LINKEDIN_KEYWORD not in sanitized_text.lower()
                            ):
                                if current:
                                    languages.append(current)
                                current = sanitized_text
                        else:
                            sanitized_text = final_sanitize(original_line)
                            if (
                                sanitized_text
                                and LINKEDIN_KEYWORD not in sanitized_text.lower()
                            ):
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
                        if (
                            sanitized_line
                            and LINKEDIN_KEYWORD not in sanitized_line.lower()
                        ):
                            languages.append(sanitized_line)

                cv_data["languages"] = languages
            elif canonical_section == "competencies_and_skills":
                content, i = _parse_generic_section(lines, i)
                _, skill_blocks = semantic_bullet_split(
                    " ".join(content), SKILL_KEYWORDS
                )
                skills_dict = {}
                for block in skill_blocks:
                    if ":" in block:
                        cat, vals = block.split(":", 1)
                        skills_dict[final_sanitize(cat.strip())] = [
                            final_sanitize(v.strip())
                            for v in re.split(r"[;,]", vals)
                            if v.strip()
                        ]
                cv_data["competencies_and_skills"] = skills_dict
            else:
                # Generic fallback for other configured sections
                content, i = _parse_generic_section(lines, i)
                cv_data[canonical_section] = [final_sanitize(item) for item in content]
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
