# Job Search Agent

A personal job search copilot for cloud/DevOps/SRE roles in Germany. Finds jobs,
tailors your resume and cover letter per job description, tracks applications,
and preps you for interviews — while keeping you in control of every decision
and every submission.

## Why it's built this way

The riskiest part of a tool like this is resume tailoring. An LLM asked to
"match keywords" will happily invent a claim like "led a 5,000-node Kubernetes
migration" if your real bullet just said "managed Kubernetes clusters." This
project treats that as a guardrail problem, not a prompting problem:

1. `tailor.py` rewrites bullets using ONLY facts present in your structured resume.
2. `fact_check.py` independently re-scans the tailored output and flags any
   technology, number, or scale claim that doesn't trace back to your original
   resume text. These flags are surfaced to you, not silently fixed.
3. Nothing gets submitted automatically. You review every tailored resume and
   every cover letter before it goes anywhere.

## How it works (current flow)

1. **Upload your resume once** - parsed and kept in your session.
2. **Search live jobs** by role/domain keyword (Cloud, DevOps, SRE...) and
   your experience level. This pulls from Arbeitnow's free public API and
   ranks every result against your resume - no LLM calls here, so it's
   instant and free even across hundreds of postings.
3. **Pick one job** - only now does the LLM get involved: it parses that
   job's full description, tailors your resume to it, and drafts a cover
   letter. Both pass through the fact-check guard.
4. **Review the flags, download both documents, then open the original
   posting to apply yourself.** This tool never submits anything for you.

## Why search and tailor are split apart

Tailoring needs an LLM call (to rewrite bullets, write a cover letter, and
fact-check both). Searching/ranking hundreds of jobs does not - it's just
keyword overlap and simple heuristics. Keeping them separate means you can
browse as many jobs as you want for free, and only spend LLM calls (and
Groq's rate-limited free quota) on the handful of jobs you actually care
about.

## Setup

```bash
cd job-search-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your GROQ_API_KEY (free, no credit card)
```

Get a free API key at https://console.groq.com - no credit card required,
and unlike Gemini's free tier, Groq's free tier has no EEA/UK/Switzerland
billing restriction, so it works for Germany-based use without paying.

## Running it

**Option A — friendly web UI (recommended):**
```bash
streamlit run streamlit_app.py
```
Opens a browser tab with a simple 3-step interface: upload resume, paste job
description, click tailor, review flags, download the result as a Word doc.

**Option B — raw API (for testing endpoints directly):**
```bash
uvicorn app.main:app --reload
```
Then visit http://127.0.0.1:8000/docs for the interactive Swagger UI.

Both call the exact same underlying code in `app/` - pick whichever you prefer.

## Project layout

```
streamlit_app.py      # the GUI - run this
app/
  config.py            # env/config loading
  llm_client.py         # unified Groq client - swap providers here only
  models.py             # shared data structures (ResumeData, JobListing, etc.)
  resume_parser.py       # docx/pdf resume -> structured ResumeData
  jd_parser.py            # raw JD text -> structured JobDescription
  tailor.py                # ResumeData + JobDescription -> tailored resume draft
  cover_letter.py          # ResumeData + JobDescription -> cover letter draft
  fact_check.py             # flags unsupported claims in tailored output
  resume_writer.py          # structured resume -> formatted .docx
  job_matcher.py            # scores/ranks fetched jobs against resume (no LLM)
  job_sources/
    arbeitnow.py             # Arbeitnow public API client (Germany/EU)
  main.py                   # FastAPI app (alternative to the Streamlit UI)
```

## Status: scaffold

This is stage 1 of the build: resume parsing, JD parsing, the tailoring
engine, and the fact-check guard. Job fetching (Arbeitnow + Arbeitsagentur),
cover letters, application tracking, and interview prep get layered on next.

Every LLM call goes through `app/llm_client.py`, which talks to Groq's free,
OpenAI-compatible API (model: `llama-3.3-70b-versatile`). This was chosen
over Gemini's free tier (which excludes EEA/UK/Switzerland users per its
terms) and over the Anthropic API (which requires billing from the first
token) — Groq's free tier needs no credit card and has no such restriction.
If you want to swap providers later, `llm_client.py` is the only file that
needs to change — every other module calls `complete()` / `complete_json()`
and doesn't know which provider is behind them.

## Deploying it (optional)

This is built and intended to run locally - your resume and API key never
leave your machine that way. If you want it as a visible portfolio project:

- **Push the code to GitHub.** `.gitignore` already excludes `.env`,
  `venv/`, and anything you drop in `data/` - your real resume and API key
  never get committed, only the code itself.
- **If you ever deploy it somewhere with a public URL** (Streamlit
  Community Cloud, Render, etc.), set an `APP_PASSWORD` environment
  variable / secret on that platform. `streamlit_app.py` checks for it and
  shows a password gate if it's set - this stops strangers from finding the
  URL and burning your Groq quota. Locally, just don't set `APP_PASSWORD`
  and the gate never appears.

## German CV / cover letter format

German employers generally expect a tabellarischer Lebenslauf (tabular CV)
and a formal business-letter cover letter, not a US-style resume. When you
tailor for a job, you can pick "German style" and get:

- **Resume**: a two-column dated layout, a "Persönliche Daten" block
  (address/phone/email/nationality - only fields you actually provided),
  a languages section with proficiency levels, and a closing place/date
  signature line.
- **Cover letter**: a proper sender block, right-aligned date, recipient
  block, bold subject line, then the letter body - the structural envelope
  a German Anschreiben is expected to have.

Two things worth knowing:
- **Nationality and language proficiency are never invented.** They only
  appear if your original resume explicitly stated them. If you want a
  languages section, add one to your master resume (e.g.
  "Languages: German (B2), English (Fluent)") and re-upload.
- **Content language is not auto-translated.** The structure follows
  German conventions, but the actual text stays in whatever language your
  resume and the generated letter are in (English, by default, since
  that's what was tailored). If you want the letter itself written in
  German, mention that and the prompt can be adjusted.
