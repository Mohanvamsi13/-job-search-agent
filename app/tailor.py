"""Tailors a candidate's resume to a specific job description.

Design constraint: the model is given the candidate's real resume as the
only source of facts, and instructed to reorder/reword/emphasize - never
invent. This file does NOT trust that instruction blindly: every tailored
resume is passed through fact_check.py before being returned, and any claim
that can't be traced back to the original resume is flagged for the human
to review (see app/fact_check.py).

Design note: the LLM is only ever asked to return summary/skills/
certifications ordering and per-job bullet lists - it is NEVER asked to
re-emit company names, cities, countries, or URLs. Earlier versions asked
for the full experience entry back as JSON, which led to the LLM
mangling/merging fields it didn't need to touch (e.g. squashing company
name + city + country into one string). Structured facts are now always
copied mechanically from the original resume; only bullet text is LLM-
generated, then fact-checked.
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
- You MAY: reorder bullets within each job to put the most relevant ones
  first, reword bullets for clarity and impact, surface technologies the
  candidate already listed but that were buried, and tighten language.
- You MUST NOT: add technologies, certifications, team sizes, infrastructure
  scale, or outcomes that are not explicitly present in the original resume.
- If the JD requires something the candidate's resume does not support,
  do not paper over the gap - leave it out rather than fabricate it.
- Do NOT change company names, job titles, dates, cities, countries, or URLs
  - those are not part of your output at all (see schema below).

Output ONLY valid JSON with this schema, no markdown fences, no commentary:

{
  "summary": "",
  "skills": [""],
  "certifications": [""],
  "experience_bullets": [["bullet1", "bullet2"], ["bullet1", "bullet2"]],
  "match_notes": "1-3 sentences on how well this candidate fits, and any gaps."
}

"experience_bullets" must have exactly the same number of entries, in the
same order, as the candidate's original "experience" list below - each
inner list is the tailored bullets for that job (same job, reordered/
reworded bullets only, never a different job or a different bullet count
that changes the underlying meaning).
"""


def _build_user_prompt(resume: ResumeData, jd: JobDescription) -> str:
    experience_summary = [
        {"company": e.company, "title": e.title, "bullets": e.bullets}
        for e in resume.experience
    ]
    return f"""CANDIDATE'S ORIGINAL RESUME (the only source of facts):
Summary: {resume.summary}
Skills: {", ".join(resume.skills)}
Certifications: {", ".join(resume.certifications)}
Experience (company/title/bullets only - city/country/dates/URLs are fixed
and not part of what you're asked to return):
{json.dumps(experience_summary, indent=2)}

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

    bullet_sets = data.get("experience_bullets", [])
    tailored_experience = []
    for i, exp in enumerate(resume.experience):
        new_bullets = bullet_sets[i] if i < len(bullet_sets) else exp.bullets
        entry = exp.model_dump()
        entry["bullets"] = new_bullets
        tailored_experience.append(entry)

    tailored = ResumeData(
        full_name=resume.full_name,
        email=resume.email,
        phone=resume.phone,
        location=resume.location,
        nationality=resume.nationality,
        linkedin_url=resume.linkedin_url,
        languages=resume.languages,
        summary=data.get("summary", resume.summary),
        skills=data.get("skills", resume.skills),
        certifications=data.get("certifications", resume.certifications),
        experience=tailored_experience,
        education=[e.model_dump() for e in resume.education],
    )
    match_notes = data.get("match_notes", "")

    flags = fact_check(original=resume, tailored=tailored)

    return TailoredResume(resume=tailored, flags=flags, match_notes=match_notes)
