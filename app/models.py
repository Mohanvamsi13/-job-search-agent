"""Shared data structures. Keeping these explicit (rather than passing raw
dicts around) makes the fact-check step possible: we need a reliable,
structured place to look up "did the candidate actually say this" against."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class ExperienceEntry(BaseModel):
    company: str
    title: str
    start_date: str = ""
    end_date: str = ""
    location: str = ""       # free-text fallback, kept for backward compatibility
    city: str = ""
    country: str = ""
    company_url: str = ""
    bullets: list[str] = Field(default_factory=list)

    def location_line(self) -> str:
        bits = [b for b in [self.city, self.country] if b]
        return ", ".join(bits) or self.location


class EducationEntry(BaseModel):
    institution: str
    degree: str = ""
    field: str = ""
    graduation_date: str = ""
    city: str = ""
    country: str = ""
    institution_url: str = ""
    level_eqf: str = ""   # European Qualifications Framework level, only if stated


class ResumeData(BaseModel):
    """Structured representation of the candidate's REAL, master resume.
    This is the single source of truth fact-checking is performed against."""
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    nationality: str = ""       # used in German/Europass CV header, only if candidate stated it
    linkedin_url: str = ""      # only if explicitly present in the original resume
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)   # e.g. "German (C1)", "English (Native)"
    certifications: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)

    def flat_text(self) -> str:
        """All resume content joined into one block of text, used as the
        ground truth corpus for fact-checking tailored output against."""
        parts = [self.summary, " ".join(self.skills), " ".join(self.languages),
                  " ".join(self.certifications)]
        for exp in self.experience:
            parts.append(f"{exp.company} {exp.title} {exp.location_line()} {exp.company_url}")
            parts.extend(exp.bullets)
        for edu in self.education:
            parts.append(f"{edu.institution} {edu.degree} {edu.field} {edu.city} {edu.country} {edu.level_eqf}")
        return "\n".join(p for p in parts if p)


class JobDescription(BaseModel):
    """Structured extraction of a job posting."""
    title: str = ""
    company: str = ""
    location: str = ""
    raw_text: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    experience_years: Optional[str] = None
    responsibilities: list[str] = Field(default_factory=list)


class JobListing(BaseModel):
    """A single job posting fetched from a job board, before full JD parsing."""
    source: str = ""           # e.g. "arbeitnow"
    external_id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    remote: bool = False
    tags: list[str] = Field(default_factory=list)
    job_types: list[str] = Field(default_factory=list)
    description: str = ""      # raw description text from the listing
    url: str = ""              # link to apply / view original posting
    posted_at: str = ""
    match_score: float = 0.0
    matched_skills: list[str] = Field(default_factory=list)
    detected_level: str = "unspecified"


class FactCheckFlag(BaseModel):
    claim: str
    reason: str
    severity: str  # "high" | "medium" | "low"


class TailoredResume(BaseModel):
    resume: ResumeData
    flags: list[FactCheckFlag] = Field(default_factory=list)
    match_notes: str = ""
