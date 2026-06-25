"""Extracts structured requirements from a raw job description.

This is the JD analysis step from the plan: required skills, preferred
skills, technologies, certifications, years of experience, responsibilities
- so you never have to manually re-read a JD to know if you qualify.
"""
import json

from app.llm_client import complete_json
from app.models import JobDescription

EXTRACTION_SYSTEM_PROMPT = """You extract structured requirements from a job
description. Be faithful to the source text - do not infer requirements
that aren't stated or strongly implied.

Output ONLY valid JSON matching this schema, no markdown fences, no commentary:

{
  "title": "",
  "company": "",
  "location": "",
  "required_skills": [""],
  "preferred_skills": [""],
  "technologies": [""],
  "certifications": [""],
  "experience_years": "",
  "responsibilities": [""]
}

Guidance:
- required_skills: things stated as must-have / required / minimum qualifications.
- preferred_skills: things stated as nice-to-have / preferred / bonus.
- technologies: specific tools, platforms, languages (e.g. Terraform, AWS,
  Kubernetes, ArgoCD) mentioned anywhere in the posting, deduplicated.
- experience_years: a short string like "5+ years" or "" if not mentioned.
"""


def parse_jd(raw_text: str, company_hint: str = "", title_hint: str = "") -> JobDescription:
    text = complete_json(EXTRACTION_SYSTEM_PROMPT, raw_text, max_tokens=2000)
    data = json.loads(text)

    jd = JobDescription(**data, raw_text=raw_text)
    if company_hint and not jd.company:
        jd.company = company_hint
    if title_hint and not jd.title:
        jd.title = title_hint
    return jd
