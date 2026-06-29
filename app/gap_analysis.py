"""Compares a tailored resume against a job description and reports which
required/preferred skills and technologies aren't reflected anywhere in the
resume. This is the honest alternative to inventing content to close gaps:
it tells you exactly what's missing so you can decide what to do about each
one - add a real bullet to your master resume if you actually have that
experience and just forgot to write it down, learn it before applying, or
knowingly apply anyway and be ready to address the gap in the interview.

No LLM call - simple substring matching against the resume's full text,
same approach as job_matcher.py.
"""
from app.models import JobDescription, ResumeData


def _is_covered(skill: str, resume_text_lower: str) -> bool:
    return skill.lower().strip() in resume_text_lower


def compute_gaps(resume: ResumeData, jd: JobDescription) -> dict:
    resume_text_lower = resume.flat_text().lower()

    missing_required = [s for s in jd.required_skills if not _is_covered(s, resume_text_lower)]
    missing_preferred = [s for s in jd.preferred_skills if not _is_covered(s, resume_text_lower)]
    missing_technologies = [
        t for t in jd.technologies
        if not _is_covered(t, resume_text_lower)
        and t not in missing_required and t not in missing_preferred
    ]

    return {
        "missing_required": missing_required,
        "missing_preferred": missing_preferred,
        "missing_technologies": missing_technologies,
    }
