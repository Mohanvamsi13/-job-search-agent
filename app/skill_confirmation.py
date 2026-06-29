"""Applies skills the candidate has explicitly confirmed having real
experience with, after being asked directly during the gap report step.

This is NOT the same as auto-adding skills based on JD requirements - that
was declined throughout this project for good reason (inventing experience
the candidate doesn't have). This is the opposite: the candidate is the one
asserting the fact, in their own words, about their own background. The
tool's job here is just to fold a real, human-provided fact into the resume
cleanly - not to judge or embellish it further.
"""
from app.models import ResumeData


def apply_confirmed_skills(resume: ResumeData, confirmed: dict[str, str]) -> ResumeData:
    """confirmed maps skill name -> the candidate's own one-line description
    of what they did with it. Each confirmed skill gets added to the skills
    list (if not already present) and its description becomes a new bullet
    on the most recent (first) experience entry, since that's the most
    defensible place for a newly-surfaced but real piece of experience."""
    updated = resume.model_copy(deep=True)

    for skill, description in confirmed.items():
        description = description.strip()
        if not description:
            continue
        if skill not in updated.skills:
            updated.skills.append(skill)
        if updated.experience:
            updated.experience[0].bullets.append(description)

    return updated
