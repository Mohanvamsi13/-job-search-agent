"""Renders ResumeData directly to PDF using reportlab - a pure-Python
library with prebuilt wheels, deliberately chosen over a docx->PDF
conversion route (which would need LibreOffice installed on the server:
heavier, slower to build, and another thing that can fail on a hosting
platform). PDF is also a better choice than docx for a final resume
anyway - it renders identically everywhere, where docx can shift slightly
between Word/Google Docs/Pages.

No LLM calls here - pure deterministic formatting of content you already
reviewed in the docx version.
"""
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors

from app.models import ResumeData
from app.de_format_utils import extract_city

DE_LABELS = {
    "personal": "Persönliche Daten",
    "address": "Adresse",
    "phone": "Telefon",
    "email": "E-Mail",
    "nationality": "Nationalität",
    "profile": "Profil",
    "experience": "Berufserfahrung",
    "education": "Ausbildung",
    "skills": "Kenntnisse & Fähigkeiten",
    "languages": "Sprachkenntnisse",
    "certifications": "Zertifizierungen",
    "present": "heute",
}


def _esc(text) -> str:
    """Escapes a value for safe use inside reportlab's mini-HTML markup -
    without this, a resume containing '&', '<', or '>' could break
    rendering or be silently dropped."""
    return escape(str(text or ""))


def _styles():
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle("Name", parent=base["Title"], fontSize=20, leading=24, spaceAfter=4),
        "name_center": ParagraphStyle("NameCenter", parent=base["Title"], fontSize=18, leading=22,
                                       alignment=TA_CENTER, spaceAfter=2),
        "contact_center": ParagraphStyle("ContactCenter", parent=base["Normal"], fontSize=9.5,
                                          alignment=TA_CENTER, spaceAfter=10),
        "heading": ParagraphStyle("Heading", parent=base["Heading2"], fontSize=12,
                                   spaceBefore=10, spaceAfter=4),
        "normal": ParagraphStyle("Normal2", parent=base["Normal"], fontSize=10, leading=13),
        "date_label": ParagraphStyle("DateLabel", parent=base["Normal"], fontSize=9,
                                      fontName="Helvetica-Oblique", textColor=colors.grey, leading=12),
        "right": ParagraphStyle("Right", parent=base["Normal"], fontSize=10, alignment=TA_RIGHT),
    }


def write_resume_pdf_standard(resume: ResumeData, output_path: str) -> str:
    s = _styles()
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    el = []

    el.append(Paragraph(_esc(resume.full_name) or "Your Name", s["name_center"]))
    contact_bits = [b for b in [resume.email, resume.phone, resume.location] if b]
    if contact_bits:
        el.append(Paragraph(" | ".join(_esc(b) for b in contact_bits), s["contact_center"]))

    if resume.summary:
        el.append(Paragraph("Summary", s["heading"]))
        el.append(Paragraph(_esc(resume.summary), s["normal"]))

    if resume.skills:
        el.append(Paragraph("Skills", s["heading"]))
        el.append(Paragraph(" | ".join(_esc(sk) for sk in resume.skills), s["normal"]))

    if resume.experience:
        el.append(Paragraph("Experience", s["heading"]))
        for exp in resume.experience:
            dates = " - ".join(d for d in [exp.start_date, exp.end_date] if d)
            meta = "  |  ".join(b for b in [dates, exp.location] if b)
            header = f"<b>{_esc(exp.title)} - {_esc(exp.company)}</b>"
            if meta:
                header += f"  <i>{_esc(meta)}</i>"
            el.append(Paragraph(header, s["normal"]))
            for bullet in exp.bullets:
                el.append(Paragraph(f"&bull; {_esc(bullet)}", s["normal"]))
            el.append(Spacer(1, 6))

    if resume.certifications:
        el.append(Paragraph("Certifications", s["heading"]))
        el.append(Paragraph(" | ".join(_esc(c) for c in resume.certifications), s["normal"]))

    if resume.education:
        el.append(Paragraph("Education", s["heading"]))
        for edu in resume.education:
            line = " - ".join(b for b in [edu.degree, edu.field, edu.institution] if b)
            text = f"{_esc(line)} ({_esc(edu.graduation_date)})" if edu.graduation_date else _esc(line)
            el.append(Paragraph(text, s["normal"]))

    doc.build(el)
    return output_path


def write_resume_pdf_de(resume: ResumeData, output_path: str, signature_city: str = "") -> str:
    s = _styles()
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    el = []
    col_widths = [3.2 * cm, 12.8 * cm]
    table_style = TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ])

    el.append(Paragraph(_esc(resume.full_name) or "Name", s["name"]))
    el.append(Spacer(1, 6))

    personal_rows = []
    if resume.location:
        personal_rows.append([Paragraph(DE_LABELS["address"], s["date_label"]),
                               Paragraph(_esc(resume.location), s["normal"])])
    if resume.phone:
        personal_rows.append([Paragraph(DE_LABELS["phone"], s["date_label"]),
                               Paragraph(_esc(resume.phone), s["normal"])])
    if resume.email:
        personal_rows.append([Paragraph(DE_LABELS["email"], s["date_label"]),
                               Paragraph(_esc(resume.email), s["normal"])])
    if resume.nationality:
        personal_rows.append([Paragraph(DE_LABELS["nationality"], s["date_label"]),
                               Paragraph(_esc(resume.nationality), s["normal"])])
    if personal_rows:
        el.append(Paragraph(DE_LABELS["personal"], s["heading"]))
        t = Table(personal_rows, colWidths=col_widths)
        t.setStyle(table_style)
        el.append(t)

    if resume.summary:
        el.append(Paragraph(DE_LABELS["profile"], s["heading"]))
        el.append(Paragraph(_esc(resume.summary), s["normal"]))

    if resume.experience:
        el.append(Paragraph(DE_LABELS["experience"], s["heading"]))
        exp_rows = []
        for exp in resume.experience:
            end = exp.end_date or DE_LABELS["present"]
            date_range = f"{exp.start_date} – {end}".strip(" –")
            header = f"<b>{_esc(exp.title)}</b>  |  {_esc(exp.company)}"
            if exp.location:
                header += f", {_esc(exp.location)}"
            bullets_html = "<br/>".join(f"&bull; {_esc(b)}" for b in exp.bullets)
            content = header + (f"<br/>{bullets_html}" if bullets_html else "")
            exp_rows.append([Paragraph(date_range, s["date_label"]), Paragraph(content, s["normal"])])
        t = Table(exp_rows, colWidths=col_widths)
        t.setStyle(table_style)
        el.append(t)

    if resume.education:
        el.append(Paragraph(DE_LABELS["education"], s["heading"]))
        edu_rows = []
        for edu in resume.education:
            line = " - ".join(b for b in [edu.degree, edu.field] if b)
            content = f"<b>{_esc(line)}</b>"
            if edu.institution:
                content += f"<br/>{_esc(edu.institution)}"
            edu_rows.append([Paragraph(_esc(edu.graduation_date), s["date_label"]), Paragraph(content, s["normal"])])
        t = Table(edu_rows, colWidths=col_widths)
        t.setStyle(table_style)
        el.append(t)

    if resume.skills:
        el.append(Paragraph(DE_LABELS["skills"], s["heading"]))
        el.append(Paragraph(" | ".join(_esc(sk) for sk in resume.skills), s["normal"]))

    if resume.languages:
        el.append(Paragraph(DE_LABELS["languages"], s["heading"]))
        el.append(Paragraph(" | ".join(_esc(lang) for lang in resume.languages), s["normal"]))

    if resume.certifications:
        el.append(Paragraph(DE_LABELS["certifications"], s["heading"]))
        el.append(Paragraph(" | ".join(_esc(c) for c in resume.certifications), s["normal"]))

    el.append(Spacer(1, 24))
    city = signature_city or extract_city(resume.location)
    today = date.today().strftime("%d.%m.%Y")
    sig_line = f"{city}, {today}" if city else f"___________, {today}"
    el.append(Paragraph(_esc(sig_line), s["normal"]))

    doc.build(el)
    return output_path
