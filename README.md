# Job Search Agent

A personal job search copilot for cloud/DevOps/SRE roles in Germany. Searches
two free job sources, tailors your resume and cover letter to a specific
posting, fact-checks both against your real resume, and formats either as a
standard or German-style CV — while keeping you in control of every decision
and every submission. (Application tracking and interview prep are on the
roadmap, not built yet - see Status below.)

## Live demo

Deployed at: **https://careerpilot-de.streamlit.app**

It's password-gated (see `APP_PASSWORD` below) so it's visible as a working
project without letting random visitors burn through the Groq API quota.

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
Opens a browser tab with the full flow: upload your resume once, search live
jobs by keyword/location/experience level (merging Arbeitnow + Arbeitsagentur),
pick a job, get a tailored resume + cover letter with fact-check flags, choose
standard or German CV format, download both, then open the original posting
to apply yourself.

**Option B — raw API (for testing endpoints directly):**
```bash
uvicorn app.main:app --reload
```
Then visit http://127.0.0.1:8000/docs for the interactive Swagger UI. Note:
this covers resume parsing, JD parsing, and tailoring only - job search and
cover letters are currently Streamlit-only, not yet exposed as API endpoints.

Both call the exact same underlying code in `app/` where functionality overlaps.

## Project layout

```
streamlit_app.py        # the GUI - run this
app/
  config.py               # env/config loading
  llm_client.py            # unified Groq client - swap providers here only
  models.py                # shared data structures (ResumeData, JobListing, etc.)
  resume_parser.py          # docx/pdf resume -> structured ResumeData
  jd_parser.py               # raw JD text -> structured JobDescription
  tailor.py                   # ResumeData + JobDescription -> tailored resume draft
  cover_letter.py             # ResumeData + JobDescription -> cover letter draft
  fact_check.py                # flags unsupported claims in tailored output
  resume_writer.py              # structured resume -> standard formatted .docx
  resume_writer_de.py            # structured resume -> German tabular CV .docx
  cover_letter_writer.py          # cover letter text -> formal business letter .docx
  job_matcher.py                   # scores/ranks fetched jobs against resume (no LLM)
  quick_links.py                    # pre-filled search URLs for LinkedIn/Indeed/StepStone/Xing
  job_sources/
    arbeitnow.py                     # Arbeitnow public API client (Germany/EU)
    arbeitsagentur.py                 # Bundesagentur fur Arbeit Jobsuche API client
  main.py                              # FastAPI app (alternative to the Streamlit UI)
```

## Status

**Built:** resume parsing, JD parsing, the tailoring engine with the
fact-check guard, cover letter generation (same guard), job search across
two free sources (Arbeitnow + Arbeitsagentur) with no-LLM-cost ranking by
resume fit and experience level, quick-launch search links for platforms
with no public API, and German/Europass-style CV + formal cover letter
formatting.

**Not yet built:** application tracking (applied/interview/offer status),
interview prep generation, and semi-automated apply assistance (prefilling
application forms via Playwright, with you still clicking submit).

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

## Arbeitsagentur integration

Job search now pulls from two free, legitimate sources and merges them
before ranking:

- **Arbeitnow** - public API, good startup/tech coverage
- **Arbeitsagentur** - Germany's official federal job board, the largest
  free source available (1M+ active postings), strong on enterprise/
  Mittelstand roles Arbeitnow doesn't have

One technical note: Arbeitsagentur's search results don't include the full
job description (only title/employer/location) - getting the full text
needs a second API call per job. To avoid making hundreds of extra calls
for jobs you never select, that second call only happens when you click
"Tailor for this" on a specific Arbeitsagentur listing - not during the
search itself.

This integration uses a community-documented (bundesAPI/jobsuche-api), not
officially supported, API - it's the same endpoint Arbeitsagentur's own
mobile app calls, but Arbeitsagentur could change it without notice. If a
search using this source ever returns nothing, Arbeitnow results still
come through independently - one source failing doesn't block the other.

## PDF output

Both the resume and cover letter can now be downloaded as PDF in addition
to docx, for both the standard and German formats. PDF is generated
directly with `reportlab` (a pure-Python library) rather than converting
docx -> PDF, which would require installing LibreOffice on the server -
heavier, slower to build, and another dependency that can fail on a
hosting platform. PDF is also a better choice for a final resume anyway:
it renders identically everywhere, whereas docx can shift slightly between
Word, Google Docs, and Pages.

`app/de_format_utils.py` holds a shared `extract_city()` helper used by
both the docx and PDF German-format writers, for the closing "City, Date"
signature line - it correctly pulls the city out of a full street address
(e.g. "Langenbergstraße 96, 50765, Köln, Germany" -> "Köln") rather than
naively taking the first comma-separated chunk, which would have produced
the street address instead of the city.
