import os
import logging
from pathlib import Path
from typing import Dict, Any
import jinja2
import weasyprint
from jinja2 import Environment, BaseLoader, select_autoescape
from weasyprint import HTML

logger = logging.getLogger(__name__)


class CVBuilder:
    def __init__(self):
        """
        Create a CVBuilder instance.

        This constructor performs no initialization and stores no instance state.
        """
        pass

    def build(
        self,
        cv_data: Dict[str, Any],
        output_pdf: str | Path,
        photo_path: str | Path | None = None,
    ) -> None:
        """
        Builds a PDF CV from provided CV data and saves it to the given output path.

        Parameters:
            cv_data (Dict[str, Any]): Data used to render the CV template (expected keys include personal_info, profile, strategic_impact, professional_experience, certificates_and_training, education, languages, competencies_and_skills, volunteering).
            output_pdf (str | Path): Target filesystem path for the generated PDF; parent directories will be created if they do not exist.
            photo_path (str | Path | None): Optional path to a photo file to embed in the CV. If provided, the path is resolved to a file URI and embedded when the file exists; missing or non-file paths emit a warning and resolution failures emit an error.

        Side effects:
            - Creates parent directories for output_pdf if necessary.
            - Writes the generated PDF to output_pdf.
            - Logs warnings/errors when the photo_path cannot be used.
        """
        output_pdf = Path(output_pdf)
        output_pdf.parent.mkdir(parents=True, exist_ok=True)

        photo_url = ""
        if photo_path:
            try:
                photo_file = Path(photo_path).expanduser().resolve()
                if photo_file.exists() and photo_file.is_file():
                    photo_url = photo_file.as_uri()
                else:
                    logger.warning(
                        f"Photo path does not exist or is not a file: {photo_path}"
                    )
            except (OSError, RuntimeError) as e:
                logger.error(f"Failed to resolve photo path '{photo_path}': {e}")

        html_content = self._render_html(cv_data, photo_url)

        HTML(string=html_content, base_url=os.getcwd()).write_pdf(str(output_pdf))

        print(f'✅ CV PDF successfully generated at: "{output_pdf.resolve()}"')

    def _render_html(self, cv: Dict[str, Any], photo: str = "") -> str:
        """
        Render a CV data structure into a complete HTML document string suitable for PDF generation.

        Parameters:
            cv (Dict[str, Any]): Mapping with CV content. Expected keys include:
                - personal_info (dict): contains `name`, `title`, `address`, `phone`, `email`.
                - profile (str)
                - strategic_impact (list[str])
                - professional_experience (list[dict]): each job may include `title`, `company`, `location`, `dates`, `description`, `achievements`.
                - certificates_and_training (list[str])
                - education (list[dict]): each item should include `institution` and `degree`.
                - languages (list[str])
                - competencies_and_skills (dict[str, list[str]])
                - volunteering (list[str])
            photo (str): Optional image URI (e.g., a `file://` URI) to include as a header photo; pass an empty string to omit the photo.

        Returns:
            str: The rendered HTML document as a string.
        """
        template_str = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @page { size: A4; margin: 1.8cm 1.5cm; }
        body {
            font-family: "Arial", sans-serif;
            font-size: 11pt;
            line-height: 1.25;
            color: #00000;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
            border-bottom: 3px solid #000000;
            padding-bottom: 12px;
        }
        .header-left h1 {
            font-family: "Arial", sans-serif;
            font-size: 24pt;
            margin: 0 0 4px 0;
            color: #000000;
        }
        .header-left h2 {
            font-family: "Arial", sans-serif;
            font-size: 14pt;
            margin: 0;
            color: #000000;
        }
        .contact {
            font-family: "Arial", monospace, sans-serif;
            font-size: 9.5pt;
            margin-top: 8px;
            color: #333;
        }
        .photo {
            width: 84px;
            height: 112px;
        }
        .photo img { width: 84px; height: 112px; }

        h2.section {
            font-family: "Arial", sans-serif;
            font-size: 11pt;
            color: #000000;
            border-bottom: 2px solid #000000;
            padding-bottom: 4px;
            margin: 22px 0 10px 0;
        }

        .job {
            margin-bottom: 11px;
        }
        .job-title {
            font-family: "Arial", sans-serif;
            font-weight: bold;
            font-size: 11pt;
        }
        .job-company {
            font-family: "Arial", sans-serif;
            font-weight: bold;

        }
        .job-location {
                    font-family: "Arial", sans-serif;
            color: #555;
            font-size: 11pt;
            font-weight: bold;

        }
        .job-dates {
            font-size: 11pt;
            font-family: "Arial", sans-serif;
            font-weight: bold;
        }

        ul {
            margin: 6px 0 0 18px;
            padding: 0;
        }
        li {
            margin-bottom: 3px;
        }

        .category {
            font-family: "Arial", sans-serif;
            font-weight: bold;
            margin-top: 12px;
            margin-bottom: 4px;
            font-size: 11pt;
        }

        .footer {
            font-family: "Arial", sans-serif;
            text-align: right;
            font-size: 9pt;
            color: #777;
            margin-top: 30px;
            border-top: 1px solid #ddd;
            padding-top: 8px;
        }
    </style>
</head>
<body>

    <div class="header">
        <div class="header-content">
            <h1>{{ cv.personal_info.name }}</h1>
            <h2 class="title">{{ cv.personal_info.title }}</h2>
            <div class="contact-info">
                {% set contact_parts = [] %}
                {% if cv.personal_info.address %}
                    {% set contact_parts = contact_parts + [cv.personal_info.address] %}
                {% endif %}
                {% if cv.personal_info.phone %}
                    {% set contact_parts = contact_parts + [cv.personal_info.phone] %}
                {% endif %}
                {% if cv.personal_info.email %}
                    {% set contact_parts = contact_parts + [cv.personal_info.email] %}
                {% endif %}
                {% if contact_parts %}
                    {{ contact_parts | join(' | ') }}<br>
                {% endif %}

                {% set identity_parts = [] %}
                {% if cv.personal_info.date_of_birth %}
                    {% set identity_parts = identity_parts + ['Date of Birth: ' ~ cv.personal_info.date_of_birth] %}
                {% endif %}
                {% if cv.personal_info.nationality %}
                    {% set identity_parts = identity_parts + ['Nationality: ' ~ cv.personal_info.nationality] %}
                {% endif %}
                {% if cv.personal_info.permit %}
                    {% set identity_parts = identity_parts + ['Permit: ' ~ cv.personal_info.permit] %}
                {% endif %}
                {% if identity_parts %}
                    {{ identity_parts | join(' | ') }}
                {% endif %}
            </div>
        </div>
        {% if photo %}
        <div class="header-photo">
            <img src="{{ photo }}" class="photo-img">
        </div>
        {% endif %}
    </div>

    <!-- PROFILE -->
    <h2 class="section">PROFILE</h2>
    <p>{{ cv.profile }}</p>

    <!-- STRATEGIC IMPACT -->
    <h2 class="section">STRATEGIC IMPACT &amp; TRANSFORMATIONS</h2>
    <ul>
    {% for item in cv.strategic_impact %}
        <li>{{ item }}</li>
    {% endfor %}
    </ul>

    <!-- PROFESSIONAL EXPERIENCE -->
    <h2 class="section">PROFESSIONAL EXPERIENCE</h2>
    {% for job in cv.professional_experience %}
    <div class="job">
        <div class="job-header">
            <span class="job-dates">{{ job.dates }}</span>
            {% if job.title %} | <span class="job-title">{{ job.title }}</span>{% endif %}
            {% if job.company %} | <span class="job-company">{{ job.company }}</span>{% endif %}
            {% if job.location %}, <span class="job-location">{{ job.location }}</span>{% endif %}
        </div>
        {% if job.description %}
        <p>{{ job.description }}</p>
        {% endif %}
        
        <ul>
        {% for ach in job.achievements %}
            <li>{{ ach }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endfor %}

    <!-- CERTIFICATES -->
    <h2 class="section">CERTIFICATES AND TRAINING</h2>
    <ul>
    {% for cert in cv.certificates_and_training %}
        <li>{{ cert }}</li>
    {% endfor %}
    </ul>

    <!-- EDUCATION -->
    <h2 class="section">EDUCATION</h2>
    {% for edu in cv.education %}
    <p><strong>{{ edu.institution }}</strong><br>{{ edu.degree }}</p>
    {% endfor %}

    <!-- LANGUAGES -->
    <h2 class="section">LANGUAGES</h2>
    <ul>
    {% for lang in cv.languages %}
        <li>{{ lang }}</li>
    {% endfor %}
    </ul>

    <!-- COMPETENCIES -->
    <h2 class="section">COMPETENCIES AND SKILLS</h2>
    <ul>
    {% for category, skills in cv.competencies_and_skills.items() %}
    <li><span class="category">{{ category }}:</span> {{ skills | join(", ") }}</li>
    {% endfor %}
    </ul>

    <!-- VOLUNTEERING -->
    <h2 class="section">VOLUNTEERING</h2>
    <ul>
    {% for item in cv.volunteering %}
        <li>{{ item }}</li>
    {% endfor %}
    </ul>

</body>
</html>
        """

        env = Environment(
            loader=BaseLoader(), autoescape=select_autoescape(["html", "xml"])
        )
        template = env.from_string(template_str)
        return template.render(cv=cv, photo=photo)
