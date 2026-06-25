"""Scores and ranks JobListings against the candidate's resume and stated
experience level.

Deliberately LLM-free: this needs to run against potentially hundreds of
fetched listings, and Groq's free tier has real rate limits (30 RPM). The
LLM is reserved for the moment you pick ONE job to actually tailor for -
see app/tailor.py and app/cover_letter.py. This module is just keyword
overlap and simple heuristics, which is enough to triage and rank.
"""
import re

from app.models import JobListing, ResumeData

LEVEL_KEYWORDS = {
    "junior": ["junior", "entry level", "entry-level", "graduate", "associate", "intern"],
    "mid": ["mid level", "mid-level", "intermediate"],
    "senior": ["senior", "sr.", "experienced"],
    "lead": ["lead", "principal", "staff", "head of", "manager"],
}

LEVEL_ORDER = ["junior", "mid", "senior", "lead"]


def detect_level(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    found = [level for level, kws in LEVEL_KEYWORDS.items() if any(kw in text for kw in kws)]
    if len(found) == 1:
        return found[0]
    if len(found) > 1:
        # prefer the most senior signal mentioned if multiple appear
        for level in reversed(LEVEL_ORDER):
            if level in found:
                return level
    return "unspecified"


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+.#/-]{1,}", text.lower()))


def score_job(job: JobListing, resume: ResumeData, target_level: str = "") -> JobListing:
    """Mutates and returns the job with match_score, matched_skills, and
    detected_level filled in."""
    job_text = f"{job.title} {job.description} {' '.join(job.tags)}"
    job_tokens = _tokenize(job_text)

    matched = [s for s in resume.skills if s.lower() in job_tokens or s.lower() in job_text.lower()]
    skill_ratio = len(matched) / max(len(resume.skills), 1)

    detected = detect_level(job.title, job.description)

    level_adjustment = 0.0
    if target_level and target_level != "unspecified":
        if detected == "unspecified":
            level_adjustment = 0.0  # no signal either way
        elif detected == target_level:
            level_adjustment = 15.0
        elif abs(LEVEL_ORDER.index(detected) - LEVEL_ORDER.index(target_level)) == 1:
            level_adjustment = -5.0  # adjacent level, mild mismatch
        else:
            level_adjustment = -20.0  # far mismatch (e.g. junior applying to lead role)

    score = min(100.0, max(0.0, skill_ratio * 100 + level_adjustment))

    job.match_score = round(score, 1)
    job.matched_skills = matched
    job.detected_level = detected
    return job


def rank_jobs(jobs: list[JobListing], resume: ResumeData, target_level: str = "") -> list[JobListing]:
    scored = [score_job(j, resume, target_level) for j in jobs]
    return sorted(scored, key=lambda j: j.match_score, reverse=True)
