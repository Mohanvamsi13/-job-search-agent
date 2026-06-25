"""Renders a cover letter directly to PDF using reportlab, mirroring the
formal business-letter structure from cover_letter_writer.py: sender block,
right-aligned date, recipient block, bold subject line, then the body.
"""
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from app.models import JobDescription, ResumeData
from app.de_format_utils import extract_city


def _esc_block(text: str) -> str:
    """Escapes a multi-line block of text and converts single newlines to
    <br/> so paragraph breaks from the generated letter survive in the PDF."""
    return escape(text or "").replace("\n", "<br/>")


def write_cover_letter_pdf(
    resume: ResumeData,
    jd: JobDescription,
    letter_text: str,
    output_path: str,
    signature_city: str = "",
) -> str:
    base = getSampleStyleSheet()
    normal = ParagraphStyle("Normal2", parent=base["Normal"], fontSize=11, leading=15, spaceAfter=8)
    right = ParagraphStyle("Right", parent=normal, alignment=TA_RIGHT)
    bold = ParagraphStyle("Bold", parent=normal, fontName="Helvetica-Bold")

    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm,
                             topMargin=2 * cm, bottomMargin=2 * cm)
    el = []

    for line in [resume.full_name, resume.location, resume.phone, resume.email]:
        if line:
            el.append(Paragraph(escape(line), normal))
    el.append(Spacer(1, 10))

    city = signature_city or extract_city(resume.location)
    today = date.today().strftime("%d.%m.%Y")
    el.append(Paragraph(escape(f"{city}, {today}" if city else today), right))
    el.append(Spacer(1, 10))

    if jd.company:
        el.append(Paragraph(escape(jd.company), normal))
    el.append(Paragraph("Attn: Hiring Team", normal))
    if jd.location:
        el.append(Paragraph(escape(jd.location), normal))
    el.append(Spacer(1, 10))

    subject = f"Application for the position of {jd.title}" if jd.title else "Application"
    el.append(Paragraph(escape(subject), bold))
    el.append(Spacer(1, 10))

    for para in letter_text.split("\n\n"):
        para = para.strip()
        if para:
            el.append(Paragraph(_esc_block(para), normal))

    doc.build(el)
    return output_path
