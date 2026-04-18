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
DEGREE_KEYWORDS = CONFIG["degree_keywords"]

LINKEDIN_KEYWORD = "linkedin.com"

PHONE_PATTERN = re.compile(r"(?:\+|00)[\d\s\-().]{7,18}")
E164_PATTERN = re.compile(r"\+\d{7,15}$")


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
    text = text.replace(" : ", ": ")
    text = text.replace(" :", ": ")
    text = text.replace(":  ", ": ")
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
    for token in line.split():
        if token.count("@") == 1 and "." in token:
            candidate = token.strip(".,;")
            if "@" in candidate and "." in candidate:
                return candidate
    return None


def _extract_phone(line: str) -> Optional[str]:
    """
    Extract an international phone number from a text line and return it in E.164 format.

    Scans the input for a number that begins with a leading `+` or `00`, normalizes common separators (spaces, dashes, parentheses, dots), and validates the result as an international E.164 number (leading `+` followed by 7-15 digits).

    Parameters:
        line (str): Text to scan for a phone number.

    Returns:
        str | None: The phone number normalized to E.164 (e.g. "+491771234567") if a valid international number is found, `None` otherwise.
    """
    # Match international E.164-style phone numbers with explicit prefix (+ or 00)
    # Only match strings that start with + or 00, followed by digits with optional separators
    phone_match = PHONE_PATTERN.search(line)
    if phone_match:
        # Normalize by removing spaces, dashes, parentheses, and dots
        phone = phone_match.group(0)
        normalized = re.sub(r"[\s\-().]", "", phone)
        # Prepend + if the number starts with 00
        if normalized.startswith("00"):
            normalized = "+" + normalized[2:]
        # Validate E.164 style: must start with + followed by 7-15 digits
        if E164_PATTERN.match(normalized):
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
    if "Permit:" not in line:
        return None

    permit = line.split("Permit:", 1)[1].strip()
    return permit or None


def _extract_header_language_entries(line: str) -> list[str] | None:
    """
    Extracts language entries from a single header-like line.

    Detects explicit language header labels (`languages`, `sprache`, `sprachen`) followed by `:`/`-`/EN DASH or nothing, then parses the trailing content as comma- or semicolon-separated language entries. Rejects excessively long input lines, sanitizes each entry, and excludes entries that contain `linkedin.com`. Returns None when the line does not contain a language header or contains no parsable entries.

    Parameters:
        line (str): A single line of text (typically OCR output) to inspect for a language header.

    Returns:
        list[str] | None: A list of sanitized language entries when a language header is present; `None` if no header-language content is detected.
    """
    # Guard against excessively long OCR lines to reduce the risk of regex-based resource exhaustion.
    if len(line) > 1024:
        return None

    # The EN DASH (–) is deliberately included here to match OCR and typographic dash variants.
    # Do not remove it, as it is intentionally used for real-world input variations.
    match = re.search(r"(?i)\b(?:languages|sprache|sprachen)\b\s*[:\-–]?\s*(.+)$", line)
    if not match:
        return None

    raw_value = match.group(1).strip()
    if not raw_value:
        return None

    entries = [
        final_sanitize(part.strip())
        for part in re.split(r"[,;]", raw_value)
        if part.strip()
    ]
    return [
        entry for entry in entries if entry and LINKEDIN_KEYWORD not in entry.lower()
    ]


def _parse_header_languages(lines: list[str]) -> list[str]:
    """
    Extract language declarations found in header-style lines near the start of the document.

    Scans at most the first 20 lines and stops when a section header is encountered, collecting any language entries declared in header-like lines (comma- or semicolon-separated).

    Parameters:
        lines (list[str]): Lines of OCR/text from the document, in order from top to bottom.

    Returns:
        list[str]: Sanitized language entries found in header lines, in the order they were encountered.
    """
    languages = []
    for line in lines[:20]:
        stripped = line.strip()
        if not stripped:
            continue
        if _is_header(stripped):
            break
        extracted = _extract_header_language_entries(stripped)
        if extracted:
            languages.extend(extracted)
    return languages


def _is_standalone_date(text: str) -> bool:
    """
    Determine whether the input is an exact date in the dd.mm.yyyy format.

    Returns:
        `True` if the string consists of three dot-separated numeric parts with lengths 2, 2, and 4 (day, month, year), `False` otherwise.
    """
    stripped = text.strip()
    parts = stripped.split(".")
    return (
        len(parts) == 3
        and all(part.isdigit() for part in parts)
        and len(parts[0]) == 2
        and len(parts[1]) == 2
        and len(parts[2]) == 4
    )


def _has_numeric_street_pattern(tokens: list[str]) -> bool:
    """Check for numeric street-number patterns like '123 Main Street'."""
    for idx, token in enumerate(tokens[:-1]):
        next_token = tokens[idx + 1]
        if any(c.isdigit() for c in token) and any(c.isalpha() for c in next_token):
            # Reject year/experience patterns like '25 years' or '14+ years'
            if re.fullmatch(r"\d+\+?", token) and next_token in (
                "years",
                "year",
                "yrs",
                "yr",
                "months",
                "month",
                "days",
                "day",
                "of",
                "in",
            ):
                continue
            return True
    return False


def _has_address_keywords(normalized: str) -> bool:
    """Check for address-related keywords."""
    address_keywords = (
        " street",
        " ave",
        " avenue",
        " rd",
        " road",
        " blvd",
        " lane",
        "strasse",
        "address:",
    )
    return any(keyword in normalized for keyword in address_keywords)


def _has_comma_separated_location(line: str, normalized: str) -> bool:
    """Check for common header-style city/country patterns."""
    if "," not in line:
        return False
    if any(
        marker in normalized
        for marker in (
            "@",
            "linkedin.com",
            "http://",
            "https://",
            "www.",
            "date of birth",
            "nationality:",
            "permit:",
        )
    ):
        return False
    if len(line) > 60:
        return False
    segments = [seg.strip() for seg in normalized.split(",") if seg.strip()]
    if 2 <= len(segments) <= 3:
        bad_terms = (
            "engineer",
            "manager",
            "developer",
            "consultant",
            "architect",
            "director",
            "company",
            "corp",
            "inc",
            "llc",
            "solutions",
            "experience",
            "years",
            "year",
            "immersion",
            "seniority",
            "transformation",
            "leader",
        )
        if not any(term in normalized for term in bad_terms) and all(
            re.search(r"[a-z]", seg) for seg in segments
        ):
            return True
    return False


def _has_st_pattern(normalized: str) -> bool:
    """Check for 'st ' patterns."""
    return normalized.startswith("st ") or normalized.endswith(" st")


def _looks_like_address(line: str) -> bool:
    normalized = line.lower()
    tokens = normalized.split()

    if _has_numeric_street_pattern(tokens):
        return True

    if _has_address_keywords(normalized):
        return True

    if _has_comma_separated_location(line, normalized):
        return True

    if _has_st_pattern(normalized):
        return True

    return False


def _extract_address(line: str) -> Optional[str]:
    """
    Determine whether a line contains an address and return the address portion when found.

    Supports detection of short location/address lines and combined header rows in the form `address | phone | email` (returns the leftmost address part when phone and email are present).

    Returns:
        Optional[str]: The trimmed address string if the line appears to contain an address, `None` otherwise.
    """
    if _extract_header_language_entries(line):
        return None

    if re.search(r"(?i)\b(linkedin|https?://|www\.)\b", line):
        return None

    if "|" in line:
        parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(parts) >= 3:
            address_part = parts[0]
            phone_part = next((p for p in parts[1:] if _extract_phone(p)), None)
            email_part = next((p for p in parts[1:] if _extract_email(p)), None)
            if address_part and phone_part and email_part:
                return address_part

    if (
        "Date of Birth" not in line
        and not re.search(r"\+\d{2}\s?\d{2}", line)  # Skip obvious phone numbers
        and not _is_standalone_date(line)
        and _looks_like_address(line)
    ):
        return line.strip()
    return None


def _is_line_heading(stripped: str, common_headers: set) -> bool:
    """Determine if a stripped line is a section header."""
    line_upper = stripped.upper().rstrip(":")
    return (
        line_upper in common_headers
        or stripped.endswith(":")
        or any(line_upper.startswith(header + " ") for header in common_headers)
        or any((header + ":") in stripped for header in common_headers)
    )


def _looks_like_contact_info(stripped: str) -> bool:
    """Check if a stripped line looks like contact or identity data."""
    return bool(re.search(r"@|Date of Birth|Nationality|Permit|\+\d{2}", stripped))


def _extract_name_and_title(lines: list[str], common_headers: set) -> tuple[str, str]:
    """
    Select the candidate's name and title from the top OCR lines.

    Scans up to the first five lines and picks the first line that is not a section header, language header, or obvious contact/identity token as the name; uses the next such line (if present) as the title. Parsing halts early if a section header is encountered after both values are found.

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
        is_heading = _is_line_heading(stripped, common_headers)

        # If we've already captured name/title, stop at section headers
        if is_heading and name and title:
            break

        # Skip leading headers until we have a candidate name/title
        if is_heading:
            continue

        # Skip language header lines
        if _extract_header_language_entries(stripped):
            continue

        if stripped and not _looks_like_contact_info(stripped):
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


def _is_job_header(line: str) -> bool:
    """Check if a line looks like a job header with title, company, and dates."""
    if not ("(" in line and line.endswith(")") and "," in line):
        return False

    # Extract the content inside parentheses
    start = line.rfind("(")
    end = line.rfind(")")
    if start == -1 or end == -1 or start >= end:
        return False

    date_part = line[start + 1 : end].strip()

    # Check for date patterns: four-digit years or ranges
    import re

    date_pattern = re.compile(r"\d{4}")
    return bool(date_pattern.search(date_part))


def _parse_job_header(line: str) -> dict[str, str]:
    """Parse job header into title, company, location, dates."""
    header_part, dates_part = line.rsplit("(", 1)
    dates = dates_part[:-1].strip()
    header_parts = [part.strip() for part in header_part.split(",")]

    # Defensively handle header_parts length
    title = header_parts[0] if header_parts else header_part.strip()
    company = header_parts[1] if len(header_parts) >= 2 else ""
    location = final_sanitize(header_parts[2]) if len(header_parts) >= 3 else ""

    return {
        "title": title,
        "company": company,
        "location": location,
        "dates": dates,
    }


def _collect_job_content(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """
    Collects consecutive non-header lines belonging to a job entry starting at a given index.

    Parameters:
        lines (list[str]): The list of stripped OCR lines to scan.
        start_idx (int): Index in `lines` at which to begin collection.

    Returns:
        content_parts (list[str]): Stripped lines that belong to the job description (may be empty).
        next_index (int): Index of the first line that is a section header, a job header, or `len(lines)` if end was reached.
    """
    content_parts = []
    i = start_idx
    while i < len(lines):
        if _is_header(lines[i]) or _is_job_header(lines[i].strip()):
            break
        content_parts.append(lines[i].strip())
        i += 1
    return content_parts, i


def _parse_single_job(
    lines: list[str], job_header_idx: int
) -> tuple[dict[str, Any], int]:
    """
    Parse a single job entry and extract its structured fields from OCR lines.

    Parses the header at job_header_idx to populate title, company, location and dates, then collects the following content as a description and a list of achievement bullets.

    Parameters:
        lines (list[str]): OCR-extracted, stripped lines from the document.
        job_header_idx (int): Index of the line containing the job header.

    Returns:
        tuple[dict, int]: A tuple (job, next_index) where `job` contains the keys
        `title`, `company`, `location`, `dates`, `description`, and `achievements`,
        and `next_index` is the index in `lines` immediately after the parsed job block.
    """
    line = lines[job_header_idx].strip()
    job_data = _parse_job_header(line)
    job = {
        "title": job_data["title"],
        "company": job_data["company"],
        "location": job_data["location"],
        "dates": job_data["dates"],
        "description": "",
        "achievements": [],
    }
    i = job_header_idx + 1
    content_parts, i = _collect_job_content(lines, i)
    desc, achs = semantic_bullet_split(" ".join(content_parts), ACHIEVEMENT_KEYWORDS)
    job["description"] = desc
    job["achievements"] = achs
    return job, i


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
    jobs = []
    i = start_idx + 1

    while i < len(lines):
        line = lines[i].strip()
        if _is_header(line):
            break

        if _is_job_header(line):
            job, i = _parse_single_job(lines, i)
            jobs.append(job)
            continue

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


def _contains_degree_keyword(text: str, degree_keywords: list[str]) -> bool:
    """Check if text contains any degree keyword using case-insensitive whole-word matching."""
    text_lower = text.lower()
    for deg_kw in degree_keywords:
        # Use word-boundary regex for whole-word matching
        pattern = r"\b" + re.escape(deg_kw.lower()) + r"\b"
        if re.search(pattern, text_lower):
            return True
    return False


def _parse_comma_separated_education(
    item: str, degree_keywords: list[str]
) -> dict[str, str]:
    """Parse education entry with comma separator."""
    parts = item.split(",", 1)
    sanitized_parts = [final_sanitize(p) for p in parts]

    # Compute boolean flags once
    part0_has_degree = _contains_degree_keyword(sanitized_parts[0], degree_keywords)
    part1_has_degree = len(sanitized_parts) > 1 and _contains_degree_keyword(
        sanitized_parts[1], degree_keywords
    )

    # Three clear branches for degree detection
    if part1_has_degree and not part0_has_degree:
        return {
            "institution": sanitized_parts[0],
            "degree": sanitized_parts[1] if len(sanitized_parts) > 1 else "",
        }
    if part0_has_degree:
        return {
            "degree": sanitized_parts[0],
            "institution": sanitized_parts[1] if len(sanitized_parts) > 1 else "",
        }

    # Fallback when neither flag is set: treat whole entry as institution-only
    return {
        "institution": " ".join(sanitized_parts),
        "degree": "",
    }


def _parse_dash_separated_education(
    item: str, degree_keywords: list[str]
) -> dict[str, str]:
    """Parse education entry with dash separator, detecting which side is degree vs institution."""
    parts = item.split(" - ", 1)
    if len(parts) < 2:
        return {
            "institution": final_sanitize(parts[0]),
            "degree": "",
        }

    # Detect which part is the degree and which is the institution
    part0_sanitized = final_sanitize(parts[0])
    part1_sanitized = final_sanitize(parts[1])

    # Check for degree keywords in each part using the shared helper
    part0_has_degree = _contains_degree_keyword(part0_sanitized, degree_keywords)
    part1_has_degree = _contains_degree_keyword(part1_sanitized, degree_keywords)

    # Check for institution keywords
    institution_patterns = [r"\bUniversity\b", r"\bCollege\b", r"\bInstitute\b"]

    part0_has_institution = any(
        re.search(pattern, part0_sanitized, re.IGNORECASE)
        for pattern in institution_patterns
    )
    part1_has_institution = any(
        re.search(pattern, part1_sanitized, re.IGNORECASE)
        for pattern in institution_patterns
    )

    # If left side has degree markers and right side has institution markers, swap
    if part0_has_degree and part1_has_institution:
        return {
            "degree": part0_sanitized,
            "institution": part1_sanitized,
        }
    # If left side has institution markers and right side has degree markers, use as-is
    if part0_has_institution and part1_has_degree:
        return {
            "institution": part0_sanitized,
            "degree": part1_sanitized,
        }

    # Default: assume left is institution, right is degree (original behavior)
    return {
        "institution": part0_sanitized,
        "degree": part1_sanitized,
    }


def _parse_degree_only_education(sanitized: str) -> dict[str, str]:
    """Parse education entry that contains only degree information."""
    return {"institution": "", "degree": sanitized}


def _parse_institution_only_education(sanitized: str) -> dict[str, str]:
    """Parse education entry that contains only institution information."""
    return {"institution": sanitized, "degree": ""}


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

    # Handle comma-separated format
    if "," in sanitized:
        return _parse_comma_separated_education(sanitized, degree_keywords)

    # Handle dash-separated format
    if " - " in sanitized:
        return _parse_dash_separated_education(sanitized, degree_keywords)

    # Handle degree-only entries
    if _contains_degree_keyword(sanitized, degree_keywords):
        return _parse_degree_only_education(sanitized)

    # Handle institution-only entries (case-insensitive)
    sanitized_lower = sanitized.lower()
    if (
        "institute" in sanitized_lower
        or "university" in sanitized_lower
        or "college" in sanitized_lower
    ):
        return _parse_institution_only_education(sanitized)

    # Fallback: treat whole line as institution
    return _parse_institution_only_education(sanitized)


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


def _handle_strategic_impact_section(
    lines: list[str], start_idx: int
) -> tuple[list[str], int]:
    """
    Extract strategic-impact bullet entries from a section and return them with the index after the section.

    Returns:
        tuple[list[str], int]: A list of sanitized strategic impact bullets, and the index of the line immediately following the parsed section.
    """
    content, next_idx = _parse_generic_section(lines, start_idx)
    _, bullets = semantic_bullet_split(" ".join(content), STRATEGIC_KEYWORDS)
    return bullets, next_idx


def _handle_education_section(
    lines: list[str], start_idx: int
) -> tuple[list[dict], int]:
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
    education_entries = [
        _parse_education_entry(item, DEGREE_KEYWORDS) for item in content
    ]
    return education_entries, next_idx


def _process_bullet_line(
    line: str, current: str | None, languages: list[str]
) -> str | None:
    """Process a bullet line, returning the new current language or None."""
    line_without_bullet = re.sub(r"^\s*•\s*", "", line).strip()
    sanitized_text = final_sanitize(line_without_bullet)
    if sanitized_text and LINKEDIN_KEYWORD not in sanitized_text.lower():
        if current:
            languages.append(current)
        return sanitized_text
    return current


def _process_non_bullet_line(line: str, current: str | None) -> str | None:
    """Process a non-bullet line, appending to current if valid."""
    sanitized_text = final_sanitize(line)
    if sanitized_text and LINKEDIN_KEYWORD not in sanitized_text.lower():
        if current:
            return current + " " + sanitized_text
        return sanitized_text
    return current


def _parse_bulleted_languages(
    lines: list[str], start_idx: int
) -> tuple[list[str], int]:
    """
    Parse language entries formatted with bullet points.

    Aggregates multi-line bullet items into single entries and filters out LinkedIn URLs.

    Parameters:
        lines (list[str]): OCR text lines for the whole document.
        start_idx (int): Index of the section header line.

    Returns:
        tuple[list[str], int]: Sanitized language entries and next line index.
    """
    content, next_idx = _parse_generic_section(lines, start_idx)
    languages = []
    current = None

    for original_line in content:
        if original_line.startswith("•"):
            current = _process_bullet_line(original_line, current, languages)
        else:
            current = _process_non_bullet_line(original_line, current)

    if current:
        languages.append(current)

    return languages, next_idx


def _parse_inline_languages(lines: list[str], start_idx: int) -> tuple[list[str], int]:
    """
    Parse language entries in plain-line format (no bullets).

    Treats each non-empty line as a separate language entry and filters out LinkedIn URLs.

    Parameters:
        lines (list[str]): OCR text lines for the whole document.
        start_idx (int): Index of the section header line.

    Returns:
        tuple[list[str], int]: Sanitized language entries and next line index.
    """
    content, next_idx = _parse_generic_section(lines, start_idx)
    languages = []

    for content_line in content:
        sanitized_line = final_sanitize(content_line)
        if sanitized_line and LINKEDIN_KEYWORD not in sanitized_line.lower():
            languages.append(sanitized_line)

    return languages, next_idx


def _detect_language_format(lines: list[str], start_idx: int) -> str | None:
    """
    Detect the format of the languages section: 'bulleted' or 'inline'.

    Returns None if the section is empty.
    """
    i = start_idx + 1
    while i < len(lines) and not _is_header(lines[i]):
        line = lines[i].strip()
        if line:
            if line.startswith("•"):
                return "bulleted"
            return "inline"
        i += 1
    return None


def _handle_languages_section(
    lines: list[str], start_idx: int
) -> tuple[list[str], int]:
    """
    Parse the Languages section into a list of sanitized language entries.

    This routine reads the section content starting after the header, supports both bullet-formatted and plain-line formats, aggregates multi-line bullet items into single entries, filters out lines containing the LinkedIn URL keyword, and applies OCR sanitization to each entry.

    Parameters:
        lines (list[str]): OCR text lines for the whole document.
        start_idx (int): Index of the section header line; parsing begins at the line after this index.

    Returns:
        tuple[list[str], int]: A tuple where the first element is the list of sanitized language entries (in original order) and the second element is the index of the next line to process after this section.
    """
    format_type = _detect_language_format(lines, start_idx)
    if format_type == "bulleted":
        return _parse_bulleted_languages(lines, start_idx)
    elif format_type == "inline":
        return _parse_inline_languages(lines, start_idx)
    else:
        # Empty section fallback
        i = start_idx + 1
        while i < len(lines) and not _is_header(lines[i]):
            i += 1
        return [], i


def _handle_competencies_and_skills_section(
    lines: list[str], start_idx: int
) -> tuple[dict, int]:
    """
    Map competencies and skills in the section to sanitized category→skill lists.

    Parses the section starting after start_idx, splits content into keyword-led blocks using SKILL_KEYWORDS, and for each block containing a colon treats the left side as a category and the right side as comma- or semicolon-separated skills. Category names and skill values are sanitized; blocks without a colon are ignored.

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
                final_sanitize(v.strip()) for v in re.split(r"[;,]", vals) if v.strip()
            ]
    return skills_dict, next_idx


def _handle_generic_fallback_section(
    lines: list[str], start_idx: int, _canonical_section: str
) -> tuple[list[str], int]:
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
    header_languages = _parse_header_languages(lines)

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
                cv_data[canonical_section], i = section_handlers[canonical_section](
                    lines, i
                )
            else:
                # Generic fallback for other configured sections
                cv_data[canonical_section], i = _handle_generic_fallback_section(
                    lines, i, canonical_section
                )
        else:
            i += 1

    # Preserve any header language entries when no dedicated LANGUAGES section is present.
    if header_languages and not cv_data["languages"]:
        cv_data["languages"].extend(header_languages)

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
