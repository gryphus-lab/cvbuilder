import re
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pytesseract as pt
from pdf2image import convert_from_path

SECTION_HEADERS = {
    "PROFILE": "profile",
    "STRATEGIC IMPACT & TRANSFORMATIONS": "strategic_impact",
    "PROFESSIONAL EXPERIENCE": "professional_experience",
    "CERTIFICATES AND TRAINING": "certificates_and_training",
    "EDUCATION": "education",
    "LANGUAGES": "languages",
    "COMPETENCIES AND SKILLS": "competencies_and_skills",
    "VOLUNTEERING": "volunteering",
}

# Keywords for semantic splitting
ACHIEVEMENT_KEYWORDS = [
    "Migration Impact",
    "AI Efficiency",
    "Team Leadership",
    "Portfolio TCO",
    "Security Transformation",
    "Modernization",
    "DACH Market Advisory",
    "Legacy Modernization",
    "Engineering Standards",
    "High-Availability Delivery",
    "Supply Chain Optimization",
    "High-Volume Architecture",
    "Rapid Progression",
    "Middleware Leadership",
]

SKILL_KEYWORDS = [
    "Artificial Intelligence",
    "Architecture",
    "Frameworks",
    "Tools",
    "Cloud & Platforms",
    "DevSecOps",
    "Data & BPM",
    "Development",
    "Regulatory/Governance",
]

STRATEGIC_KEYWORDS = [
    "AI-Augmented SDLC Strategy",
    "Large-Scale M&A Integration",
    "Enterprise Portfolio & TCO Optimization",
]


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

    # Only the real OCR issue you mentioned
    text = text.replace("ii", "ü")

    for kw in ACHIEVEMENT_KEYWORDS + SKILL_KEYWORDS + STRATEGIC_KEYWORDS:
        double_pattern = rf"\b({re.escape(kw)})\s+({re.escape(kw)})\b"
        text = re.sub(double_pattern, r"\1", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*[:]\s*", ": ", text)
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


def _parse_personal_info(lines: List[str]) -> Dict[str, str]:
    """Parse personal info directly from the raw OCR output (no hardcoded strings)."""
    info = {}
    for line in lines[:20]:  # only top of document
        # Email
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", line)
        if email_match:
            info["email"] = email_match.group(0)
        # Phone
        phone_match = re.search(r"\+41\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}", line)
        if phone_match:
            info["phone"] = phone_match.group(0)
        # Date of Birth
        dob_match = re.search(r"Date of Birth:\s*([\d.]+)", line)
        if dob_match:
            info["date_of_birth"] = dob_match.group(1)
        # Nationality
        nat_match = re.search(r"Nationality:\s*(\w+)", line)
        if nat_match:
            info["nationality"] = nat_match.group(1)
        # Permit
        permit_match = re.search(r"Permit:\s*(.+?)(?:\s+|$)", line)
        if permit_match:
            info["permit"] = permit_match.group(1).strip()
        # Address (first line that looks like an address)
        if (
            not info.get("address")
            and any(c.isdigit() for c in line)
            and "Date of Birth" not in line
        ):
            info["address"] = line.strip()
    return info


def _parse_experience(lines: list[str], start_idx: int) -> tuple[list[dict], int]:
    jobs = []
    i = start_idx + 1

    while i < len(lines):
        line = lines[i].strip()
        if _is_header(line):
            break

        job_match = re.search(r"(.+?),\s*(.+?)(?:,\s*(.+?))?\s*\((.+?)\)", line)

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
                and not re.search(r",.*\(?\d{2}/\d{4}", lines[i])
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


def _parse_generic_section(lines: List[str], start_idx: int) -> Tuple[List[str], int]:
    items = []
    i = start_idx + 1
    while i < len(lines) and not _is_header(lines[i]):
        line = lines[i].strip()
        if line:
            items.append(line)
        i += 1
    return items, i


def parse_cv_to_json(pdf_path: str):
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

        if line_upper == "PROFILE":
            cv_data["profile"], i = _parse_generic_section(lines, i)
        elif line_upper == "PROFESSIONAL EXPERIENCE":
            cv_data["professional_experience"], i = _parse_experience(lines, i)
        elif line_upper == "STRATEGIC IMPACT & TRANSFORMATIONS":
            content, i = _parse_generic_section(lines, i)
            _, bullets = semantic_bullet_split(" ".join(content), STRATEGIC_KEYWORDS)
            cv_data["strategic_impact"] = bullets
        elif line_upper == "EDUCATION":
            content, i = _parse_generic_section(lines, i)
            edu = []
            for item in content:
                if "Indian Institute" in item:
                    edu.append({"institution": final_sanitize(item)})
                elif "Bachelor of Technology" in item:
                    if edu:
                        edu[-1]["degree"] = final_sanitize(item)
                    else:
                        edu.append({"degree": final_sanitize(item)})
            cv_data["education"] = edu
        elif line_upper == "LANGUAGES":
            content, i = _parse_generic_section(lines, i)
            languages = []
            current = None
            for line in content:
                line = final_sanitize(line)
                if line and "linkedin.com" not in line.lower():
                    if line.startswith("•") or "English" in line or "German" in line:
                        if current:
                            languages.append(current)
                        current = re.sub(r"^\s*•\s*", "", line).strip()
                    elif current:
                        current += " " + line
                    else:
                        current = line
            if current:
                languages.append(current)
            cv_data["languages"] = languages
        elif line_upper == "COMPETENCIES AND SKILLS":
            content, i = _parse_generic_section(lines, i)
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
            cv_data["competencies_and_skills"] = skills_dict
        elif line_upper in SECTION_HEADERS:
            key = SECTION_HEADERS[line_upper]
            content, i = _parse_generic_section(lines, i)
            cv_data[key] = [final_sanitize(item) for item in content]
        else:
            i += 1

    return cv_data


def save_to_json(data: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


__all__ = ["parse_cv_to_json", "save_to_json"]
