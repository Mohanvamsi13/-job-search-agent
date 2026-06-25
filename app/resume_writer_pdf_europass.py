"""Renders ResumeData as a PDF in the structural style of a Europass CV:
photo + name + contact block at the top, then sections with a label in a
fixed left column and content to the right, dates in their own sub-column
for experience/education, and explicit City/Country/Field-of-study/EQF-
level metadata lines.

This is an ORIGINAL layout inspired by that structural convention - it does
not reproduce Europass's own branded design (their specific icon set,
exact color values, or official template grid/files). The structure
(label-left/content-right, photo top-left, metadata line format) is a
common convention, not Europass's proprietary IP; the visual rendering
here (colors, fonts, exact spacing) is built from scratch.

No LLM calls here. Nothing is invented: city, country, URLs, and EQF level
only render if your original resume stated them (see resume_parser.py).
"""
import io
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors

from app.models import ResumeData

ACCENT = colors.HexColor("#235789")   # an original color choice, not Europass's specific brand color
LABEL_COL = 4.6 * cm
DATE_COL = 3.0 * cm
CONTENT_COL_FULL = 18.0 * cm - LABEL_COL          # for sections with no date column
CONTENT_COL_NARROW = 18.0 * cm - LABEL_COL - DATE_COL  # for sections with a date column


def _esc(text) -> str:
    return escape(str(text or ""))


def _styles():
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle("Name", parent=base["Title"], fontSize=20, leading=24,
                                alignment=TA_LEFT, textColor=colors.black),
        "contact": ParagraphStyle("Contact", parent=base["Normal"], fontSize=10, leading=14),
        "label": ParagraphStyle("Label", parent=base["Normal"], fontSize=10, leading=13,
                                 textColor=ACCENT, fontName="Helvetica-Bold"),
        "date": ParagraphStyle("Date", parent=base["Normal"], fontSize=9, leading=12,
                                textColor=colors.grey),
        "normal": ParagraphStyle("Normal2", parent=base["Normal"], fontSize=10, leading=13),
        "meta": ParagraphStyle("Meta", parent=base["Normal"], fontSize=9, leading=12,
                                textColor=colors.grey),
    }


def _prepare_photo(photo_bytes: bytes, size_cm: float = 2.6):
    """Center-crops the photo to a square and returns a reportlab Image
    flowable. No circular mask (kept simple/robust) - a clean square photo
    is a reasonable cosmetic compromise."""
    from PIL import Image as PILImage

    img = PILImage.open(io.BytesIO(photo_bytes)).convert("RGB")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((300, 300))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return Image(buf, width=size_cm * cm, height=size_cm * cm)


def _link(text: str, url: str) -> str:
    if not url:
        return text
    safe_url = escape(url)
    return f'<link href="{safe_url}" color="#235789">{text}</link>'


def _section_table(rows: list[list], col_widths: list[float]) -> Table:
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def write_resume_pdf_europass(resume: ResumeData, output_path: str, photo_bytes: bytes = None) -> str:
    s = _styles()
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                             topMargin=1.3 * cm, bottomMargin=1.3 * cm)
    el = []

    # ---------------------------------------------------------- HEADER
    contact_lines = []
    if resume.location:
        contact_lines.append(f"<b>Home:</b> {_esc(resume.location)}")
    email_phone = []
    if resume.email:
        email_phone.append(f"<b>Email address:</b> {_esc(resume.email)}")
    if resume.phone:
        email_phone.append(f"<b>Phone:</b> {_esc(resume.phone)}")
    if email_phone:
        contact_lines.append("    ".join(email_phone))
    if resume.linkedin_url:
        contact_lines.append(f"<b>LinkedIn:</b> {_link(_esc(resume.linkedin_url), resume.linkedin_url)}")

    name_block = [Paragraph(_esc(resume.full_name) or "Name", s["name"])]
    for line in contact_lines:
        name_block.append(Paragraph(line, s["contact"]))

    if photo_bytes:
        try:
            photo = _prepare_photo(photo_bytes)
            header_table = Table([[photo, name_block]], colWidths=[3.2 * cm, 14.8 * cm])
            header_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]))
            el.append(header_table)
        except Exception:
            el.extend(name_block)  # fall back gracefully if the photo can't be processed
    else:
        el.extend(name_block)

    el.append(Spacer(1, 6))
    rule = Table([[""]], colWidths=[18.0 * cm], rowHeights=[1])
    rule.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1, colors.lightgrey)]))
    el.append(rule)
    el.append(Spacer(1, 10))

    # ---------------------------------------------------------- ABOUT
    if resume.summary:
        el.append(_section_table(
            [[Paragraph("ABOUT MYSELF", s["label"]), Paragraph(_esc(resume.summary), s["normal"])]],
            [LABEL_COL, CONTENT_COL_FULL],
        ))

    # ---------------------------------------------------------- EDUCATION
    if resume.education:
        rows = []
        for i, edu in enumerate(resume.education):
            label = Paragraph("EDUCATION &<br/>TRAINING", s["label"]) if i == 0 else Paragraph("", s["label"])
            date_p = Paragraph(f"[ {_esc(edu.graduation_date)} ]" if edu.graduation_date else "", s["date"])

            degree_line = f"<b>{_esc(edu.degree)}</b>" if edu.degree else ""
            inst_line = _link(f"<i>{_esc(edu.institution)}</i>", edu.institution_url) if edu.institution else ""

            meta_bits = []
            if edu.city:
                meta_bits.append(f"<b>City:</b> {_esc(edu.city)}")
            if edu.country:
                meta_bits.append(f"<b>Country:</b> {_esc(edu.country)}")
            if edu.field:
                meta_bits.append(f"<b>Field(s) of study:</b> {_esc(edu.field)}")
            if edu.level_eqf:
                meta_bits.append(f"<b>Level in EQF:</b> {_esc(edu.level_eqf)}")
            meta_line = " | ".join(meta_bits)

            content_html = "<br/>".join(p for p in [degree_line, inst_line, meta_line] if p)
            rows.append([label, date_p, Paragraph(content_html, s["normal"])])
        el.append(_section_table(rows, [LABEL_COL, DATE_COL, CONTENT_COL_NARROW]))

    # ---------------------------------------------------------- EXPERIENCE
    if resume.experience:
        rows = []
        for i, exp in enumerate(resume.experience):
            label = Paragraph("WORK<br/>EXPERIENCE", s["label"]) if i == 0 else Paragraph("", s["label"])
            date_p = Paragraph(f"[ {_esc(exp.start_date)} - {_esc(exp.end_date) or 'Present'} ]", s["date"])

            company_line = _link(f"<b>{_esc(exp.company)}</b>", exp.company_url) if exp.company else ""
            meta_bits = []
            if exp.city:
                meta_bits.append(f"<b>City:</b> {_esc(exp.city)}")
            if exp.country:
                meta_bits.append(f"<b>Country:</b> {_esc(exp.country)}")
            if not meta_bits and exp.location:
                meta_bits.append(_esc(exp.location))
            meta_line = " | ".join(meta_bits)
            title_line = f"<b>{_esc(exp.title)}</b>" if exp.title else ""
            bullets_html = "<br/>".join(f"&bull; {_esc(b)}" for b in exp.bullets)

            content_html = "<br/>".join(p for p in [company_line, meta_line, title_line, bullets_html] if p)
            rows.append([label, date_p, Paragraph(content_html, s["normal"])])
        el.append(_section_table(rows, [LABEL_COL, DATE_COL, CONTENT_COL_NARROW]))

    # ---------------------------------------------------------- SKILLS
    if resume.skills:
        el.append(_section_table(
            [[Paragraph("SKILLS", s["label"]), Paragraph(" | ".join(_esc(sk) for sk in resume.skills), s["normal"])]],
            [LABEL_COL, CONTENT_COL_FULL],
        ))

    # ---------------------------------------------------------- LANGUAGES
    if resume.languages:
        el.append(_section_table(
            [[Paragraph("LANGUAGES", s["label"]), Paragraph(" | ".join(_esc(l) for l in resume.languages), s["normal"])]],
            [LABEL_COL, CONTENT_COL_FULL],
        ))

    # ---------------------------------------------------------- CERTIFICATIONS
    if resume.certifications:
        el.append(_section_table(
            [[Paragraph("CERTIFICATIONS", s["label"]),
              Paragraph(" | ".join(_esc(c) for c in resume.certifications), s["normal"])]],
            [LABEL_COL, CONTENT_COL_FULL],
        ))

    doc.build(el)
    return output_path
