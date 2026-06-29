"""Streamlit GUI for the job search agent.

Run with: streamlit run streamlit_app.py

Flow:
  1. Upload your resume once (stays in session).
  2. Search live jobs (Arbeitnow) by role/domain + your experience level.
     Jobs are ranked against your resume with no LLM calls - free and instant.
  3. Click into a specific job -> the LLM tailors your resume and writes a
     cover letter for THAT job, with the fact-check guard applied to both.
  4. Review, download, then open the original posting to apply yourself.
     Nothing is ever submitted automatically.
"""
import os
import tempfile
from pathlib import Path

import streamlit as st

from app.resume_parser import parse_resume
from app.jd_parser import parse_jd
from app.models import JobDescription
from app.tailor import tailor_resume
from app.gap_analysis import compute_gaps
from app.skill_confirmation import apply_confirmed_skills
from app.llm_client import FriendlyRateLimitError
from app.cover_letter import generate_cover_letter
from app.resume_writer import write_resume_docx
from app.resume_writer_pdf import write_resume_pdf_standard
from app.resume_writer_pdf_europass import write_resume_pdf_europass
from app.resume_writer_pdf_sidebar import write_resume_pdf_sidebar
from app.cover_letter_writer import write_cover_letter_docx
from app.cover_letter_writer_pdf import write_cover_letter_pdf
from app.job_sources.arbeitnow import fetch_jobs as fetch_arbeitnow_jobs
from app.job_sources.arbeitsagentur import (
    fetch_jobs as fetch_arbeitsagentur_jobs,
    fetch_job_description,
)
from app.job_matcher import rank_jobs
from app.quick_links import build_quick_links

st.set_page_config(page_title="Job Search Agent", page_icon="🧰", layout="wide")

# Optional password gate. Does nothing for local use (no APP_PASSWORD set).
# If you ever deploy this somewhere with a public URL, set APP_PASSWORD as
# an environment variable / secret there and this locks the app down so
# strangers can't burn your API quota.
_app_password = os.getenv("APP_PASSWORD", "")
if _app_password:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("Job Search Agent")
        entered = st.text_input("Password", type="password")
        if entered:
            if entered == _app_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
        st.stop()

DEFAULTS = {
    "resume": None,
    "photo_bytes": None,
    "jobs": [],
    "selected_job": None,
    "tailored": None,
    "cover_letter": None,
    "last_jd": None,
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

st.title("Job Search Agent")
st.caption(
    "Upload your resume once, search real job postings, then tailor your "
    "resume and cover letter for whichever job you pick. Every fact gets "
    "checked against your real resume - nothing gets submitted for you."
)

# ============================================================ STEP 1
st.header("1. Your resume")

if st.session_state.resume is None:
    uploaded = st.file_uploader("Upload your master resume", type=["docx", "pdf", "txt"])
    photo_upload = st.file_uploader(
        "Optional: profile photo for Europass-style CV", type=["jpg", "jpeg", "png"]
    )
    if uploaded and st.button("Parse resume"):
        with st.spinner("Reading your resume..."):
            suffix = Path(uploaded.name).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            try:
                st.session_state.resume = parse_resume(tmp_path)
                if photo_upload:
                    st.session_state.photo_bytes = photo_upload.getvalue()
                st.rerun()
            except FriendlyRateLimitError as e:
                st.error(f"⏳ {e}")
            except Exception as e:
                st.error(f"Couldn't parse resume: {e}")
            finally:
                Path(tmp_path).unlink(missing_ok=True)
else:
    r = st.session_state.resume
    col1, col2 = st.columns([5, 1])
    with col1:
        st.success(f"Resume loaded: **{r.full_name or 'you'}** — skills: {', '.join(r.skills[:8])}{'...' if len(r.skills) > 8 else ''}")
    with col2:
        if st.button("Replace resume"):
            st.session_state.resume = None
            st.session_state.jobs = []
            st.session_state.selected_job = None
            st.rerun()

# ============================================================ STEP 2
if st.session_state.resume:
    st.header("2. Find jobs")

    c1, c2, c3, c4, c5 = st.columns([2, 1.6, 1.6, 1, 1])
    with c1:
        keyword = st.text_input("Role / domain keyword", value="DevOps",
                                 help="e.g. Cloud, DevOps, SRE, Platform Engineer")
    with c2:
        location = st.text_input("Location", value="", placeholder="e.g. Frankfurt, Berlin, Remote",
                                  help="City names work best (e.g. Frankfurt). Country names like "
                                       "'Germany' are treated as no filter, since this source is "
                                       "already Germany/Austria/Switzerland-focused.")
    with c3:
        posted_choice = st.selectbox("Posted", ["Today", "Last 3 days", "Last 7 days", "Anytime"], index=2)
    with c4:
        level = st.selectbox("Experience", ["unspecified", "junior", "mid", "senior", "lead"], index=2)
    with c5:
        st.write("")
        st.write("")
        search_clicked = st.button("Find jobs", type="primary", use_container_width=True)

    remote_only = st.checkbox("Remote only")

    posted_days_map = {"Today": 0, "Last 3 days": 3, "Last 7 days": 7, "Anytime": None}
    posted_within_days = posted_days_map[posted_choice]

    st.caption("Also check these directly - they don't offer a public API, so here are one-click pre-filled searches instead of scraping them:")
    links = build_quick_links(keyword, location)
    link_cols = st.columns(len(links))
    for col, (platform, url) in zip(link_cols, links.items()):
        with col:
            st.link_button(f"Search {platform} →", url, use_container_width=True)

    if search_clicked:
        with st.spinner("Fetching live job postings from Arbeitnow and Arbeitsagentur..."):
            arbeitnow_jobs = fetch_arbeitnow_jobs(
                keyword=keyword,
                location=location,
                remote_only=remote_only,
                posted_within_days=posted_within_days,
                max_pages=6,
            )
            try:
                arbeitsagentur_jobs = fetch_arbeitsagentur_jobs(
                    keyword=keyword,
                    location=location,
                    remote_only=remote_only,
                    posted_within_days=posted_within_days,
                    max_pages=4,
                )
            except Exception:
                # Don't let one source's failure block the other - this is
                # a community-documented (not officially supported) API,
                # so a graceful degrade matters here.
                arbeitsagentur_jobs = []

            raw_jobs = arbeitnow_jobs + arbeitsagentur_jobs
            st.session_state.jobs = rank_jobs(raw_jobs, st.session_state.resume, level)
            st.session_state.selected_job = None
            st.session_state.tailored = None
            st.session_state.cover_letter = None
        if not st.session_state.jobs:
            st.warning(
                "No jobs found for that combination. Try a broader keyword, "
                "a wider date range, or clearing the location."
            )

    if st.session_state.jobs:
        st.write(f"**{len(st.session_state.jobs)} jobs found**, ranked by fit to your resume and experience level:")
        for i, job in enumerate(st.session_state.jobs[:25]):
            with st.container(border=True):
                cols = st.columns([4, 1.2, 1, 1])
                with cols[0]:
                    st.markdown(f"**{job.title}** — {job.company}")
                    posted_label = job.posted_at[:10] if job.posted_at else "date unknown"
                    st.caption(f"{job.location or 'location unspecified'}  |  posted {posted_label}  |  level: {job.detected_level}  |  source: {job.source}  |  matched skills: {', '.join(job.matched_skills) or 'none'}")
                with cols[1]:
                    st.metric("Match", f"{job.match_score:.0f}%", label_visibility="collapsed")
                with cols[2]:
                    st.link_button("View posting", job.url, use_container_width=True)
                with cols[3]:
                    if st.button("Tailor for this", key=f"tailor_{i}", use_container_width=True):
                        st.session_state.selected_job = job
                        st.session_state.tailored = None
                        st.session_state.cover_letter = None
                        st.rerun()

# ============================================================ STEP 3
if st.session_state.selected_job:
    job = st.session_state.selected_job
    st.header(f"3. Tailoring for: {job.title} at {job.company}")

    if st.session_state.tailored is None:
        with st.spinner("Analyzing job description, tailoring your resume, and writing a cover letter..."):
            try:
                description = job.description
                if not description and job.source == "arbeitsagentur":
                    description = fetch_job_description(job.external_id)
                    if not description:
                        st.warning(
                            "Couldn't retrieve the full job description from "
                            "Arbeitsagentur for this listing - tailoring may be "
                            "limited. You can open the original posting and "
                            "paste the description in manually if needed."
                        )
                jd = parse_jd(description, company_hint=job.company, title_hint=job.title)
                # Compute both results into locals first - only commit to
                # session_state once BOTH succeed. Otherwise a failure in
                # the second call (e.g. hitting a rate limit right after
                # the first call succeeded) would leave tailored resume set
                # but cover_letter still None, crashing the render below.
                tailored_result = tailor_resume(st.session_state.resume, jd)
                cover_letter_result = generate_cover_letter(st.session_state.resume, jd)
                st.session_state.last_jd = jd
                st.session_state.tailored = tailored_result
                st.session_state.cover_letter = cover_letter_result
            except FriendlyRateLimitError as e:
                st.error(f"⏳ {e}")
            except Exception as e:
                st.error(f"Something went wrong: {e}")

    if st.session_state.tailored:
        tr_result = st.session_state.tailored
        cl_result = st.session_state.cover_letter

        if st.session_state.get("last_jd"):
            gaps = compute_gaps(tr_result.resume, st.session_state.last_jd)
            gap_skills = list(dict.fromkeys(gaps["missing_required"] + gaps["missing_preferred"]))[:8]
            if gap_skills:
                with st.expander("This job mentions a few things not yet in your resume - want to check?", expanded=False):
                    st.caption(
                        "These are just listed for you to consider - nothing here gets "
                        "added automatically. If you genuinely have real experience with "
                        "any of these, briefly describe what you actually did, and it'll be "
                        "added as a real bullet in your own words. Leave blank to skip."
                    )
                    confirmed = {}
                    job_key = st.session_state.selected_job.external_id or st.session_state.selected_job.title
                    for skill in gap_skills:
                        desc = st.text_input(
                            f"{skill} — what did you do with it? (leave blank if you haven't used it)",
                            key=f"gap_confirm_{job_key}_{skill}",
                        )
                        if desc.strip():
                            confirmed[skill] = desc.strip()

                    if confirmed and st.button("Add these to my resume", key=f"apply_gap_{job_key}"):
                        tr_result.resume = apply_confirmed_skills(tr_result.resume, confirmed)
                        st.success(f"Added: {', '.join(confirmed.keys())} - based on what you described, in your own words.")
                        st.rerun()
            else:
                st.success("No major skill gaps detected between this JD and your resume.")

        cv_format = st.radio(
            "CV / cover letter format",
            [
                "Modern sidebar (colored column, photo, skills)",
                "Europass-style (photo, structured EU fields)",
                "Standard / international",
            ],
            horizontal=True,
            help="Modern sidebar is a colored left column with your photo, "
                 "contact info, and skills, with experience/education in the "
                 "main area - a contemporary resume look. Europass-style "
                 "matches the official EU CV structure with EQF levels, with "
                 "the same modern visual treatment. Standard is a clean "
                 "international layout.",
        )
        use_sidebar_format = cv_format.startswith("Modern sidebar")
        use_europass_format = cv_format.startswith("Europass")

        col_resume, col_letter = st.columns(2)

        with col_resume:
            st.subheader("Tailored resume")
            st.caption(tr_result.match_notes or "")
            if tr_result.flags:
                st.warning(f"{len(tr_result.flags)} claim(s) flagged - review before using:")
                for f in tr_result.flags:
                    icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(f.severity, "⚪")
                    st.write(f"{icon} **{f.claim}** — {f.reason}")
            else:
                st.success("No unsupported claims detected in the resume.")

            tr = tr_result.resume
            with st.expander("Preview tailored resume", expanded=False):
                st.write("**Summary:**", tr.summary or "—")
                st.write("**Skills:**", ", ".join(tr.skills) or "—")
                if tr.languages:
                    st.write("**Languages:**", ", ".join(tr.languages))
                for exp in tr.experience:
                    st.write(f"**{exp.title}** — {exp.company}")
                    for b in exp.bullets:
                        st.write(f"- {b}")

            out_path = "/tmp/tailored_resume.docx"
            pdf_path = "/tmp/tailored_resume.pdf"
            file_stub = f"resume_{(tr.full_name or 'tailored').replace(' ', '_')}_{job.company.replace(' ', '_')}"
            if use_sidebar_format:
                write_resume_pdf_sidebar(tr, pdf_path, photo_bytes=st.session_state.photo_bytes)
                write_resume_docx(tr, out_path)  # no dedicated sidebar docx writer yet - standard docx as fallback
            elif use_europass_format:
                write_resume_pdf_europass(tr, pdf_path, photo_bytes=st.session_state.photo_bytes)
                write_resume_docx(tr, out_path)  # no dedicated Europass docx writer yet - standard docx as fallback
            else:
                write_resume_docx(tr, out_path)
                write_resume_pdf_standard(tr, pdf_path)

            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                with open(out_path, "rb") as f:
                    st.download_button(
                        "Download resume (.docx)",
                        f,
                        file_name=f"{file_stub}.docx",
                        use_container_width=True,
                    )
            with dl_col2:
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "Download resume (.pdf)",
                        f,
                        file_name=f"{file_stub}.pdf",
                        use_container_width=True,
                    )
            if use_sidebar_format and not st.session_state.photo_bytes:
                st.caption(
                    "No photo uploaded - the sidebar will render without one. "
                    "Go back to step 1 and upload a photo if you want it included."
                )
            if use_europass_format and not st.session_state.photo_bytes:
                st.caption(
                    "No photo uploaded - the PDF will render without one. "
                    "Go back to step 1 and upload a photo if you want it included."
                )
            if use_europass_format and not tr.languages:
                st.caption(
                    "Note: no language section appears because your original "
                    "resume didn't list language proficiencies. Add a "
                    "'Languages' section to your master resume (e.g. "
                    "'German (B2), English (C1)') and re-upload to include one."
                )

        with col_letter:
            st.subheader("Cover letter draft")
            if cl_result["flags"]:
                for f in cl_result["flags"]:
                    icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(f.severity, "⚪")
                    st.write(f"{icon} **{f.claim}** — {f.reason}")
            else:
                st.success("No unsupported claims detected in the cover letter.")

            letter_text = st.text_area("Edit before sending:", value=cl_result["text"], height=300)
            jd_for_letter = JobDescription(title=job.title, company=job.company, location=job.location)
            letter_stub = f"cover_letter_{job.company.replace(' ', '_')}"

            letter_dl_col1, letter_dl_col2 = st.columns(2)
            with letter_dl_col1:
                if use_europass_format:
                    letter_out_path = "/tmp/cover_letter.docx"
                    write_cover_letter_docx(st.session_state.resume, jd_for_letter, letter_text, letter_out_path)
                    with open(letter_out_path, "rb") as f:
                        st.download_button(
                            "Download letter (.docx)",
                            f,
                            file_name=f"{letter_stub}.docx",
                            use_container_width=True,
                        )
                else:
                    st.download_button(
                        "Download letter (.txt)",
                        letter_text,
                        file_name=f"{letter_stub}.txt",
                        use_container_width=True,
                    )
            with letter_dl_col2:
                letter_pdf_path = "/tmp/cover_letter.pdf"
                write_cover_letter_pdf(st.session_state.resume, jd_for_letter, letter_text, letter_pdf_path)
                with open(letter_pdf_path, "rb") as f:
                    st.download_button(
                        "Download letter (.pdf)",
                        f,
                        file_name=f"{letter_stub}.pdf",
                        use_container_width=True,
                    )

        st.divider()
        st.info(
            "Review both documents above, then open the original posting "
            "to submit your application yourself - this tool never applies for you."
        )
        st.link_button(f"Open job posting at {job.company} →", job.url, type="primary")
