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
from app.cover_letter import generate_cover_letter
from app.resume_writer import write_resume_docx
from app.resume_writer_de import write_resume_docx_de
from app.cover_letter_writer import write_cover_letter_docx
from app.job_sources.arbeitnow import fetch_jobs
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
    "jobs": [],
    "selected_job": None,
    "tailored": None,
    "cover_letter": None,
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
    if uploaded and st.button("Parse resume"):
        with st.spinner("Reading your resume..."):
            suffix = Path(uploaded.name).suffix
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(uploaded.getvalue())
                tmp_path = tmp.name
            try:
                st.session_state.resume = parse_resume(tmp_path)
                st.rerun()
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
        with st.spinner("Fetching live job postings..."):
            raw_jobs = fetch_jobs(
                keyword=keyword,
                location=location,
                remote_only=remote_only,
                posted_within_days=posted_within_days,
                max_pages=6,
            )
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
                    st.caption(f"{job.location or 'location unspecified'}  |  posted {posted_label}  |  level: {job.detected_level}  |  matched skills: {', '.join(job.matched_skills) or 'none'}")
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
                jd = parse_jd(job.description, company_hint=job.company, title_hint=job.title)
                st.session_state.tailored = tailor_resume(st.session_state.resume, jd)
                st.session_state.cover_letter = generate_cover_letter(st.session_state.resume, jd)
            except Exception as e:
                st.error(f"Something went wrong: {e}")

    if st.session_state.tailored:
        tr_result = st.session_state.tailored
        cl_result = st.session_state.cover_letter

        cv_format = st.radio(
            "CV / cover letter format",
            ["German style (tabular CV + formal business letter)", "Standard / international"],
            horizontal=True,
            help="German employers generally expect a tabellarischer Lebenslauf "
                 "(tabular CV with dates, personal details block, and a closing "
                 "signature line) and a formal business-letter cover letter, "
                 "rather than a US-style resume.",
        )
        use_german_format = cv_format.startswith("German")

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
            if use_german_format:
                write_resume_docx_de(tr, out_path)
            else:
                write_resume_docx(tr, out_path)
            with open(out_path, "rb") as f:
                st.download_button(
                    "Download tailored resume (.docx)",
                    f,
                    file_name=f"resume_{(tr.full_name or 'tailored').replace(' ', '_')}_{job.company.replace(' ', '_')}.docx",
                    use_container_width=True,
                )
            if use_german_format and not tr.languages:
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

            if use_german_format:
                jd_for_letter = JobDescription(title=job.title, company=job.company, location=job.location)
                letter_out_path = "/tmp/cover_letter.docx"
                write_cover_letter_docx(st.session_state.resume, jd_for_letter, letter_text, letter_out_path)
                with open(letter_out_path, "rb") as f:
                    st.download_button(
                        "Download cover letter (.docx)",
                        f,
                        file_name=f"cover_letter_{job.company.replace(' ', '_')}.docx",
                        use_container_width=True,
                    )
            else:
                st.download_button(
                    "Download cover letter (.txt)",
                    letter_text,
                    file_name=f"cover_letter_{job.company.replace(' ', '_')}.txt",
                    use_container_width=True,
                )

        st.divider()
        st.info(
            "Review both documents above, then open the original posting "
            "to submit your application yourself - this tool never applies for you."
        )
        st.link_button(f"Open job posting at {job.company} →", job.url, type="primary")
