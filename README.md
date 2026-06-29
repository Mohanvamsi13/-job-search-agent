# Job Search Agent

A personal job search assistant for cloud/DevOps/SRE roles in Germany.
Upload your resume once, search real job postings, then get a tailored
resume and cover letter for whichever job you pick — every claim checked
against what's actually true in your resume. You stay in control of every
download and every application; nothing gets submitted automatically.

**Live demo:** https://careerpilot-de.streamlit.app (password-protected — ask
the owner for access)

---

## What it does

- **Searches two free job sources** (Arbeitnow + Germany's official
  Arbeitsagentur) and ranks results against your resume and experience level
- **Tailors your resume** to a specific job — reorders and rewords your real
  bullets to match what that job is asking for, without inventing anything
- **Writes a cover letter** for that job, same honesty rules
- **Flags anything that looks made up** — an independent check compares the
  tailored output against your original resume and calls out any claim it
  can't trace back to something you actually wrote
- **Tells you what's missing** — if a job wants a skill your resume doesn't
  show, it'll ask if you genuinely have real experience with it; if you do,
  you describe it yourself and that becomes a real bullet, in your words
- **Three resume designs** — a modern colored-sidebar layout, an
  Europass-style layout (with your photo, City/Country/EQF-level fields),
  or a clean standard layout — each downloadable as PDF or Word
- **Quick-launch search links** for LinkedIn, Indeed, StepStone, and Xing,
  since those don't offer a public search API

## What it deliberately does NOT do

- Never adds a skill, technology, or achievement to your resume unless it's
  either already in your original resume or something you typed yourself
  after being asked directly
- Never submits an application for you — it gets your documents ready, then
  hands you a link to apply yourself

---

## Quick start

```bash
git clone https://github.com/Mohanvamsi13/-job-search-agent.git
cd -job-search-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and add a free Groq API key (no credit card needed):
get one at **console.groq.com** → API Keys → Create API Key, then paste it
into `.env`:

```
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

Then run it:

```bash
streamlit run streamlit_app.py
```

A browser tab opens automatically. If not, go to **http://localhost:8501**.

## How to use it

1. **Upload your resume** (.docx, .pdf, or .txt) and optionally a photo
2. **Search** — type a role keyword (e.g. "DevOps"), pick a location and
   experience level, click **Find jobs**
3. **Pick a job** from the results and click **Tailor for this**
4. **Review** — check the fact-check flags, fill in any skill-gap questions
   if you genuinely have that experience, pick a resume design
5. **Download** your resume and cover letter (PDF or Word)
6. **Apply** — click through to the original posting and submit it yourself

---

## Why it's built this way (for the curious)

The riskiest part of a tool like this is resume tailoring — an AI asked to
"match keywords" will happily invent a claim that sounds plausible but
isn't true. This project treats that as a guardrail problem, not a
prompting problem: the AI is only ever shown your real resume as source
material, and a second, independent pass re-checks its output and flags
anything that doesn't trace back to something you actually wrote. Those
flags are shown to you, never silently auto-corrected.

Job searching and job tailoring are also kept deliberately separate:
searching/ranking hundreds of postings is just keyword matching, so it's
instant and free; tailoring needs an actual AI call, so it only happens for
the one job you click into — not all of them.

## Project structure

```
streamlit_app.py             the app - run this
app/
  config.py                   loads your .env settings
  llm_client.py                talks to Groq (swap providers here only)
  models.py                     shared data structures
  resume_parser.py               resume file -> structured data
  jd_parser.py                    job posting text -> structured data
  tailor.py                        does the actual tailoring
  cover_letter.py                   writes the cover letter
  fact_check.py                     flags unsupported claims
  gap_analysis.py                    finds JD requirements your resume lacks
  skill_confirmation.py               adds skills you confirm having
  resume_writer_pdf_sidebar.py         modern sidebar PDF design
  resume_writer_pdf_europass.py         Europass-style PDF design
  resume_writer_pdf.py                   standard PDF design + .docx writers
  cover_letter_writer.py                  formal cover letter .docx
  cover_letter_writer_pdf.py                formal cover letter PDF
  job_matcher.py                             ranks jobs against your resume
  quick_links.py                              search links for other sites
  job_sources/
    arbeitnow.py                               Arbeitnow API client
    arbeitsagentur.py                           Arbeitsagentur API client
  main.py                                       optional REST API (FastAPI)
```

## Status

**Built:** everything described above.

**Not yet built:** application tracking (applied/interview/offer status)
and interview prep generation.

## FAQ / troubleshooting

**"Invalid API Key" error** — your `.env` file doesn't have a real key in
it, or it got copied with a typo/extra space. Open `.env` and check the
line reads exactly `GROQ_API_KEY=gsk_...` with no quotes or spaces.

**"Rate limit reached" error** — Groq's free tier caps usage per day. Wait
the amount of time shown in the error (resets on a rolling basis), or
reduce how many jobs you tailor in one sitting.

**A job's description couldn't be fetched** — happens occasionally with
Arbeitsagentur listings. The app will ask you to paste the description in
manually rather than guessing from nothing.

**Want to deploy this somewhere with a public link?** Set an `APP_PASSWORD`
environment variable on your hosting platform (e.g. Streamlit Community
Cloud's "Secrets" panel) — `streamlit_app.py` shows a password gate
whenever that variable is set, so a public URL doesn't mean public access.
