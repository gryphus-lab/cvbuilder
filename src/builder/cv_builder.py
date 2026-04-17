import os
from pathlib import Path
from typing import Dict, Any
import jinja2
import weasyprint
from jinja2 import Environment, BaseLoader
from weasyprint import HTML


class CVBuilder:
    def __init__(self):
        """Builder initialized with embedded Jinja2 template."""
        pass

    def build(
        self,
        cv_data: Dict[str, Any],
        output_pdf: str | Path,
        photo_path: str | Path | None = None,
    ) -> None:
        output_pdf = Path(output_pdf)
        output_pdf.parent.mkdir(parents=True, exist_ok=True)

        photo_url = ""
        if photo_path:
            photo_url = Path(photo_path).resolve().as_uri()

        html_content = self._render_html(cv_data, photo_url)

        HTML(string=html_content, base_url=os.getcwd()).write_pdf(str(output_pdf))

        print(f'✅ CV PDF successfully generated at: "{output_pdf.resolve()}"')

    def _render_html(self, cv: Dict[str, Any], photo: str = "") -> str:
        template_str = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @page { size: A4; margin: 1.8cm 1.5cm; }
        body {
            font-family: "Calibri", regular, sans-serif;
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
            font-family: "Calibri", regular, sans-serif;
            font-size: 24pt;
            margin: 0 0 4px 0;
            color: #000000;
        }
        .header-left h2 {
            font-family: "Calibri", regular, sans-serif;
            font-size: 14pt;
            margin: 0;
            color: #000000;
        }
        .contact {
            font-family: "Calibri", monospace, sans-serif;
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
            font-family: "Calibri", regular, sans-serif;
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
            font-family: "Calibri", regular, sans-serif;
            font-weight: bold;
            font-size: 11pt;
        }
        .job-company {
            font-family: "Calibri", regular, sans-serif;
            font-weight: 500;
        }
        .job-location {
                    font-family: "Calibri", regular, sans-serif;

            color: #555;
            font-size: 11pt;
        }
        .job-dates {
            float: right;
            font-size: 11pt;
            font-family: "Calibri", regular, sans-serif;

        }

        ul {
            margin: 6px 0 0 18px;
            padding: 0;
        }
        li {
            margin-bottom: 3px;
        }

        .category {
            font-family: "Calibri", regular, sans-serif;
            font-weight: bold;
            margin-top: 12px;
            margin-bottom: 4px;
            font-size: 11pt;
        }

        .footer {
            font-family: "Calibri", regular, sans-serif;
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
                {{ cv.personal_info.address }} | {{ cv.personal_info.phone }}<br>
                <strong>Email:</strong> {{ cv.personal_info.email }}
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
        <span class="job-title">{{ job.title }}</span>
        {% if job.company %}, <span class="job-company">{{ job.company }}</span>{% endif %}
        {% if job.location %}, <span class="job-location">{{ job.location }}</span>{% endif %}
        <span class="job-dates">{{ job.dates }}</span>
        
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
    {% for category, skills in cv.competencies_and_skills.items() %}
    <div class="category">{{ category }}</div>
    <ul>
    {% for skill in skills %}
        <li>{{ skill }}</li>
    {% endfor %}
    </ul>
    {% endfor %}

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

        env = Environment(loader=BaseLoader())
        template = env.from_string(template_str)
        return template.render(cv=cv, photo=photo)