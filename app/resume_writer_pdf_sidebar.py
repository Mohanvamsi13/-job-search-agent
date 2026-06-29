"""Modern sidebar-style PDF resume: a colored left column (photo, contact
info, skills, languages, certifications) and a white main content area
(name, profile, work experience, education).

This needs reportlab's lower-level page template system rather than just
SimpleDocTemplate, because the colored sidebar must span the FULL page
height as a background - independent of how much sidebar content there is
- and must keep appearing on every page if the resume runs long, while new
content after page 1 only continues in the main column (re-flowing sidebar
content across pages isn't how this style of template works).

No LLM calls. Nothing invented - photo/city/country/etc. only render if
present in your original resume.
"""
import io
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, FrameBreak, NextPageTemplate,
    Paragraph, Spacer, Table, TableStyle, Image,
)

from app.models import ResumeData

SIDEBAR_BG = colors.HexColor("#2C3E50")
SIDEBAR_TEXT = colors.HexColor("#ECF0F1")
SIDEBAR_ACCENT = colors.HexColor("#5DADE2")
MAIN_ACCENT = colors.HexColor("#2C3E50")

PAGE_W, PAGE_H = A4
SIDEBAR_W = 6.5 * cm
MARGIN = 1.0 * cm


def _esc(text) -> str:
    return escape(str(text or ""))


def _styles():
    base = getSampleStyleSheet()
    return {
        "sidebar_heading": ParagraphStyle("SBHeading", parent=base["Normal"], fontSize=9.5,
                                           textColor=SIDEBAR_ACCENT, fontName="Helvetica-Bold",
                                           spaceBefore=14, spaceAfter=6),
        "sidebar_text": ParagraphStyle("SBText", parent=base["Normal"], fontSize=9,
                                        leading=12, textColor=SIDEBAR_TEXT),
        "name": ParagraphStyle("Name", parent=base["Title"], fontSize=13, leading=16,
                                textColor=MAIN_ACCENT, alignment=TA_LEFT, spaceAfter=2),
        "main_heading": ParagraphStyle("MainHeading", parent=base["Normal"], fontSize=10,
                                        textColor=MAIN_ACCENT, fontName="Helvetica-Bold",
                                        spaceBefore=12, spaceAfter=4),
        "normal": ParagraphStyle("Normal2", parent=base["Normal"], fontSize=9, leading=12),
        "date": ParagraphStyle("Date", parent=base["Normal"], fontSize=8.5, leading=11,
                                textColor=colors.grey),
    }


def _circular_photo(photo_bytes: bytes, size_px: int = 280):
    from PIL import Image as PILImage, ImageDraw

    img = PILImage.open(io.BytesIO(photo_bytes)).convert("RGB")
    w, h = img.size
    side = min(w, h)
    left, top = (w - side) // 2, (h - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((size_px, size_px))

    mask = PILImage.new("L", (size_px, size_px), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size_px, size_px), fill=255)

    output = PILImage.new("RGBA", (size_px, size_px), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask)

    buf = io.BytesIO()
    output.save(buf, format="PNG")
    buf.seek(0)
    return buf


def write_resume_pdf_sidebar(resume: ResumeData, output_path: str, photo_bytes: bytes = None) -> str:
    s = _styles()

    def paint_sidebar(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(SIDEBAR_BG)
        canvas.rect(0, 0, SIDEBAR_W, PAGE_H, fill=1, stroke=0)
        canvas.restoreState()

    sidebar_frame = Frame(MARGIN * 0.6, MARGIN, SIDEBAR_W - MARGIN * 0.6 - 0.3 * cm,
                           PAGE_H - 2 * MARGIN, id="sidebar")
    main_frame_p1 = Frame(SIDEBAR_W + MARGIN, MARGIN, PAGE_W - SIDEBAR_W - 2 * MARGIN,
                           PAGE_H - 2 * MARGIN, id="main1")
    main_frame_later = Frame(SIDEBAR_W + MARGIN, MARGIN, PAGE_W - SIDEBAR_W - 2 * MARGIN,
                              PAGE_H - 2 * MARGIN, id="main2")

    doc = BaseDocTemplate(output_path, pagesize=A4)
    doc.addPageTemplates([
        PageTemplate(id="First", frames=[sidebar_frame, main_frame_p1], onPage=paint_sidebar),
        PageTemplate(id="Later", frames=[main_frame_later], onPage=paint_sidebar),
    ])

    # ---------------------------------------------------------- SIDEBAR
    sidebar_flow = []
    if photo_bytes:
        try:
            photo_buf = _circular_photo(photo_bytes)
            photo_size = SIDEBAR_W - MARGIN * 0.6 - 0.3 * cm - 0.4 * cm
            img = Image(photo_buf, width=photo_size, height=photo_size)
            sidebar_flow.append(img)
            sidebar_flow.append(Spacer(1, 14))
        except Exception:
            pass

    sidebar_flow.append(Paragraph("CONTACT", s["sidebar_heading"]))
    if resume.location:
        sidebar_flow.append(Paragraph(_esc(resume.location), s["sidebar_text"]))
    if resume.phone:
        sidebar_flow.append(Paragraph(_esc(resume.phone), s["sidebar_text"]))
    if resume.email:
        sidebar_flow.append(Paragraph(_esc(resume.email), s["sidebar_text"]))
    if resume.linkedin_url:
        sidebar_flow.append(Paragraph(_esc(resume.linkedin_url), s["sidebar_text"]))
    if resume.nationality:
        sidebar_flow.append(Paragraph(f"Nationality: {_esc(resume.nationality)}", s["sidebar_text"]))

    if resume.skills:
        sidebar_flow.append(Paragraph("SKILLS", s["sidebar_heading"]))
        for sk in resume.skills:
            sidebar_flow.append(Paragraph(f"• {_esc(sk)}", s["sidebar_text"]))

    if resume.languages:
        sidebar_flow.append(Paragraph("LANGUAGES", s["sidebar_heading"]))
        for lang in resume.languages:
            sidebar_flow.append(Paragraph(_esc(lang), s["sidebar_text"]))

    if resume.certifications:
        sidebar_flow.append(Paragraph("CERTIFICATIONS", s["sidebar_heading"]))
        for cert in resume.certifications:
            sidebar_flow.append(Paragraph(_esc(cert), s["sidebar_text"]))

    # ---------------------------------------------------------- MAIN
    main_flow = []
    main_flow.append(Paragraph(_esc(resume.full_name) or "Name", s["name"]))
    if resume.experience:
        main_flow.append(Paragraph(_esc(resume.experience[0].title), ParagraphStyle(
            "Subtitle", parent=s["normal"], fontSize=9, textColor=colors.grey, spaceAfter=10)))

    if resume.summary:
        main_flow.append(Paragraph("PROFILE", s["main_heading"]))
        main_flow.append(Paragraph(_esc(resume.summary), s["normal"]))

    col_w = [3.4 * cm, (PAGE_W - SIDEBAR_W - 2 * MARGIN) - 3.4 * cm]

    if resume.experience:
        main_flow.append(Paragraph("WORK EXPERIENCE", s["main_heading"]))
        rows = []
        header_row_indices = []
        for exp in resume.experience:
            date_p = Paragraph(f"{_esc(exp.start_date)} – {_esc(exp.end_date) or 'Present'}", s["date"])
            company_bits = [b for b in [exp.city, exp.country] if b] or ([exp.location] if exp.location else [])
            company_line = f"<b>{_esc(exp.title)}</b> — {_esc(exp.company)}"
            if company_bits:
                company_line += f"<br/><i>{_esc(', '.join(company_bits))}</i>"
            header_row_indices.append(len(rows))
            rows.append([date_p, Paragraph(company_line, s["normal"])])
            for bullet in exp.bullets:
                rows.append(["", Paragraph(f"• {_esc(bullet)}", s["normal"])])

        exp_table = Table(rows, colWidths=col_w)
        style_cmds = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]
        for idx in header_row_indices[1:]:
            style_cmds.append(("TOPPADDING", (0, idx), (-1, idx), 14))
        exp_table.setStyle(TableStyle(style_cmds))
        main_flow.append(exp_table)

    if resume.education:
        main_flow.append(Paragraph("EDUCATION", s["main_heading"]))
        edu_rows = []
        for edu in resume.education:
            date_p = Paragraph(_esc(edu.graduation_date), s["date"])
            line = f"<b>{_esc(edu.degree)}</b>" if edu.degree else ""
            if edu.institution:
                line += f"<br/><i>{_esc(edu.institution)}</i>"
            meta_bits = [b for b in [edu.city, edu.country] if b]
            if meta_bits:
                line += f"<br/>{_esc(', '.join(meta_bits))}"
            edu_rows.append([date_p, Paragraph(line, s["normal"])])
        edu_table = Table(edu_rows, colWidths=col_w)
        edu_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        main_flow.append(edu_table)

    flowables = sidebar_flow + [FrameBreak(), NextPageTemplate("Later")] + main_flow
    doc.build(flowables)
    return output_path
