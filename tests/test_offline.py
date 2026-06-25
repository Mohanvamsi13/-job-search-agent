"""Run with: python -m tests.test_offline
These tests don't call the Anthropic API - they verify the parts of the
pipeline that are pure, deterministic Python: the docx writer and the
numeric heuristic check inside fact_check.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import ResumeData, ExperienceEntry, EducationEntry
from app.resume_writer import write_resume_docx
from app.fact_check import _heuristic_numeric_check


def test_resume_writer():
    resume = ResumeData(
        full_name="Max Mustermann",
        email="max@example.com",
        phone="+49 151 000 0000",
        location="Frankfurt, Germany",
        summary="Cloud and DevOps engineer with experience running production Kubernetes clusters.",
        skills=["AWS", "Terraform", "Kubernetes", "Docker", "CI/CD", "Linux"],
        certifications=["AWS Certified Solutions Architect - Associate"],
        experience=[
            ExperienceEntry(
                company="ExampleCorp",
                title="DevOps Engineer",
                start_date="2022",
                end_date="Present",
                location="Frankfurt, Germany",
                bullets=[
                    "Managed Kubernetes clusters with approximately 50 nodes across production environments.",
                    "Built CI/CD pipelines using GitHub Actions, reducing deployment time by half.",
                ],
            )
        ],
        education=[
            EducationEntry(
                institution="TU Darmstadt",
                degree="B.Sc.",
                field="Computer Science",
                graduation_date="2021",
            )
        ],
    )
    out_path = "/tmp/test_resume_output.docx"
    write_resume_docx(resume, out_path)
    assert Path(out_path).exists()
    print(f"OK: docx written to {out_path}")


def test_numeric_heuristic_flags_invented_numbers():
    original = "Managed Kubernetes clusters with approximately 50 nodes."
    tailored_safe = "Operated Kubernetes clusters with approximately 50 nodes in production."
    tailored_invented = "Built a Kubernetes platform supporting 5,000 nodes across the org."

    flags_safe = _heuristic_numeric_check(original, tailored_safe)
    flags_invented = _heuristic_numeric_check(original, tailored_invented)

    assert len(flags_safe) == 0, f"Expected no flags, got: {flags_safe}"
    assert len(flags_invented) > 0, "Expected the invented '5,000 nodes' claim to be flagged"
    print("OK: numeric heuristic correctly distinguishes safe vs invented claims")
    print(f"  Flagged: {[f.claim for f in flags_invented]}")


if __name__ == "__main__":
    test_resume_writer()
    test_numeric_heuristic_flags_invented_numbers()
    print("\nAll offline tests passed.")
