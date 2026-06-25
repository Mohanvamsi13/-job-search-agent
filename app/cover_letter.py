"""Generates a cover letter draft for a specific job, using only facts
present in the candidate's resume. Same fact-check guard as tailor.py is
applied here - a fabricated cover letter is just as much of a risk as a
fabricated resume.
"""
from app.llm_client import complete
from app.models import JobDescription, ResumeData
from app.fact_check import fact_check_text

SYSTEM_PROMPT = """You write a cover letter for a job application.

STRICT RULES:
- Use ONLY facts, skills, and experience present in the candidate's resume
  text given below. Never invent achievements, technologies, team sizes, or
  outcomes that are not in the resume.
- Address why the candidate fits THIS specific role, referencing the job's
  required/preferred skills only where the candidate's real resume supports it.
- If the candidate's resume doesn't cover something the JD asks for, do not
  paper over the gap - simply don't mention it; do not pretend they have it.
- Tone: professional, concise, confident but not exaggerated. 3-4 short
  paragraphs. No greeting placeholder like "Dear [Name]" - use "Dear Hiring
  Team" or the company name if given.
- End with a professional closing line (e.g. "Sincerely,") followed by the
  candidate's full name on the next line - this letter will be placed
  directly into a formal business letter template, so it needs its own
  closing rather than trailing off.
- Output plain text only. No markdown, no headers, no JSON.
"""


def generate_cover_letter(resume: ResumeData, jd: JobDescription) -> dict:
    user_prompt = f"""CANDIDATE'S RESUME (the only source of facts):
{resume.flat_text()}

Candidate's name: {resume.full_name}

JOB TO WRITE FOR:
Title: {jd.title}
Company: {jd.company or "the company"}
Required skills: {", ".join(jd.required_skills)}
Preferred skills: {", ".join(jd.preferred_skills)}
Responsibilities: {", ".join(jd.responsibilities)}
"""
    letter_text = complete(SYSTEM_PROMPT, user_prompt, max_tokens=1000).strip()
    flags = fact_check_text(resume, letter_text, document_label="COVER LETTER")

    return {"text": letter_text, "flags": flags}
