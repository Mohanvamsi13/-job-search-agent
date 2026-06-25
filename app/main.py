"""FastAPI app. Run with: uvicorn app.main:app --reload

Endpoints so far (stage 1 of the build):
  POST /resume/parse   - upload a resume file, get structured ResumeData back
  POST /jd/parse       - submit raw JD text, get structured JobDescription back
  POST /resume/tailor  - submit resume + JD, get tailored resume + fact-check flags

Nothing here submits anything anywhere. These endpoints only produce drafts
and flags for you to review - matching the human/tool division we mapped out.
"""
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel

from app.models import JobDescription, ResumeData, TailoredResume
from app.resume_parser import parse_resume
from app.jd_parser import parse_jd
from app.tailor import tailor_resume

app = FastAPI(title="Job Search Agent", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/resume/parse", response_model=ResumeData)
def resume_parse_endpoint(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".docx", ".pdf", ".txt"):
        raise HTTPException(400, f"Unsupported file type: {suffix}")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        return parse_resume(tmp_path)
    except Exception as e:
        raise HTTPException(500, f"Failed to parse resume: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


class JDParseRequest(BaseModel):
    raw_text: str
    company_hint: str = ""
    title_hint: str = ""


@app.post("/jd/parse", response_model=JobDescription)
def jd_parse_endpoint(req: JDParseRequest):
    try:
        return parse_jd(req.raw_text, req.company_hint, req.title_hint)
    except Exception as e:
        raise HTTPException(500, f"Failed to parse job description: {e}")


class TailorRequest(BaseModel):
    resume: ResumeData
    job_description: JobDescription


@app.post("/resume/tailor", response_model=TailoredResume)
def resume_tailor_endpoint(req: TailorRequest):
    try:
        return tailor_resume(req.resume, req.job_description)
    except Exception as e:
        raise HTTPException(500, f"Failed to tailor resume: {e}")
