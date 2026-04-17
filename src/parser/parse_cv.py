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
    if not text:
        return ""

    OCR_REPLACEMENTS = {
        "ii": "ü",
        "Al-": "AI-",
        "OpenAl": "OpenAI",
        "Al ": "AI ",
        "¢": "",
        "©": "",
        "•": "",
    }

    for old, new in OCR_REPLACEMENTS.items():
        text = text.replace(old, new)

    for kw in ACHIEVEMENT_KEYWORDS + SKILL_KEYWORDS + STRATEGIC_KEYWORDS:
        double_pattern = rf"\b({re.escape(kw)})\s+({re.escape(kw)})\b"
        text = re.sub(double_pattern, r"\1", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*[:]\s*", ": ", text)  # Normalize colons
    text = re.sub(r"\s+[a-zA-Z¢©•]\.?$", "", text.strip())
    text = text.replace("Nativ", "Native")

    return text.strip()


def semantic_bullet_split(text: str, keywords: list) -> tuple[str, list[str]]:
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


def _parse_experience(lines: list[str], start_idx: int) -> tuple[list[dict], int]:
    jobs = []
    i = start_idx + 1

    while i < len(lines):
        line = lines[i].strip()
        if _is_header(line):
            break

        job_match = re.search(r"(.+?),\s*(.+?),\s*(.+?)\s*\((.+?)\)", line)

        if job_match:
            job = {
                "title": job_match.group(1).strip(),
                "company": job_match.group(2).strip(),
                "location": final_sanitize(job_match.group(3).strip()),
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
        "personal_info": [],
        "profile": "",
        "strategic_impact": [],
        "professional_experience": [],
        "certificates_and_training": [],
        "education": [],
        "languages": [],
        "competencies_and_skills": {},
        "volunteering": [],
    }

    i = 0
    while i < len(lines):
        line_upper = lines[i].upper().strip().rstrip(":")

        if line_upper == "PROFILE":
            content, i = _parse_generic_section(lines, i)
            cv_data["profile"] = final_sanitize(" ".join(content))
        elif line_upper == "PROFESSIONAL EXPERIENCE":
            cv_data["professional_experience"], i = _parse_experience(lines, i)
        elif line_upper == "STRATEGIC IMPACT & TRANSFORMATIONS":
            content, i = _parse_generic_section(lines, i)
            _, bullets = semantic_bullet_split(" ".join(content), STRATEGIC_KEYWORDS)
            cv_data["strategic_impact"] = bullets
        elif line_upper == "COMPETENCIES AND SKILLS":
            content, i = _parse_generic_section(lines, i)
            _, skill_blocks = semantic_bullet_split(" ".join(content), SKILL_KEYWORDS)
            skills_dict = {}
            for block in skill_blocks:
                if ":" in block:
                    cat, vals = block.split(":", 1)
                    skills_dict[cat.strip()] = [
                        v.strip() for v in re.split(r"[;,]", vals) if v.strip()
                    ]
            cv_data["competencies_and_skills"] = skills_dict
        elif line_upper in SECTION_HEADERS:
            key = SECTION_HEADERS[line_upper]
            content, i = _parse_generic_section(lines, i)
            cv_data[key] = [final_sanitize(item) for item in content]
        else:
            if "@" in lines[i] and "email" not in cv_data["personal_info"]:
                email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", lines[i])
                if email:
                    cv_data["personal_info"] = email.group(0)
            i += 1

    return cv_data


def save_to_json(data: Dict[str, Any], output_path: Path) -> None:
    import json

    output_path.parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


__all__ = ["parse_cv_to_json", "save_to_json"]