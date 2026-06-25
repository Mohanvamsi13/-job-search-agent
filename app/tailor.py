"""Tailors a candidate's resume to a specific job description.

Design constraint: the model is given the candidate's real resume as the
only source of facts, and instructed to reorder/reword/emphasize - never
invent. This file does NOT trust that instruction blindly: every tailored
resume is passed through fact_check.py before being returned, and any claim
that can't be traced back to the original resume is flagged for the human
to review (see app/fact_check.py).
"""
import json

from app.llm_client import complete_json
from app.models import JobDescription, ResumeData, TailoredResume
from app.fact_check import fact_check

TAILOR_SYSTEM_PROMPT = """You tailor a resume to a specific job description.

STRICT RULES:
- You may ONLY use facts, skills, technologies, and achievements that appear
  in the candidate's original resume text given to you below. Never invent,
  exaggerate, or add scale/numbers/technologies that are not already present.
- You MAY: reorder bullets to put the most relevant ones first, reword bullets
  for clarity and impact, surface technologies the candidate already listed
  but that were buried, and tighten language.
- You MUST NOT: add technologies, certifications, team sizes, infrastructure
  scale, or outcomes that are not explicitly present in the original resume.
- If the JD requires something the candidate's resume does not support,
  do not paper over the gap - leave it out rather than fabricate it.

Output ONLY valid JSON with this schema, no markdown fences, no commentary:

{
  "summary": "",
  "skills": [""],
  "certifications": [""],
  "experience": [
    {"company": "", "title": "", "start_date": "", "end_date": "", "location": "", "bullets": [""]}
  ],
  "match_notes": "1-3 sentences on how well this candidate fits, and any gaps."
}

Keep company/title/dates/location identical to the original - only summary,
skills ordering, certifications ordering, and bullet wording/order may change.
"""


def _build_user_prompt(resume: ResumeData, jd: JobDescription) -> str:
    return f"""CANDIDATE'S ORIGINAL RESUME (the only source of facts):
{resume.model_dump_json(indent=2)}

JOB DESCRIPTION TO TAILOR FOR:
Title: {jd.title}
Company: {jd.company}
Required skills: {", ".join(jd.required_skills)}
Preferred skills: {", ".join(jd.preferred_skills)}
Technologies mentioned: {", ".join(jd.technologies)}
Responsibilities: {", ".join(jd.responsibilities)}
"""


def tailor_resume(resume: ResumeData, jd: JobDescription) -> TailoredResume:
    text = complete_json(
        TAILOR_SYSTEM_PROMPT, _build_user_prompt(resume, jd), max_tokens=4000
    )
    data = json.loads(text)

    tailored = ResumeData(
        full_name=resume.full_name,
        email=resume.email,
        phone=resume.phone,
        location=resume.location,
        nationality=resume.nationality,
        languages=resume.languages,
        summary=data.get("summary", resume.summary),
        skills=data.get("skills", resume.skills),
        certifications=data.get("certifications", resume.certifications),
        experience=data.get("experience", [e.model_dump() for e in resume.experience]),
        education=[e.model_dump() for e in resume.education],
    )
    match_notes = data.get("match_notes", "")

    flags = fact_check(original=resume, tailored=tailored)

    return TailoredResume(resume=tailored, flags=flags, match_notes=match_notes)
